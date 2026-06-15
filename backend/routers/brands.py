# backend/routers/brands.py
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.constants import (
    focus_brand_sql_list, canonical_brand, FOCUS_BRANDS,
    PHONE_LEAF_REGEX, TABLET_LEAF_REGEX, WATCH_LEAF_REGEX,
    fx_case_sql, normalize_sub_category,
)

router = APIRouter()

_FOCUS = focus_brand_sql_list()
_FX = fx_case_sql("market")


@router.get("/brands/trend", response_model=ApiResponse)
def get_brands_trend(days: int = Query(default=30, ge=1, le=365),
                     market: Optional[str] = Query(default=None)):
    params = {"days": days}
    market_clause = ""
    if market:
        market_clause = " AND market = :m"
        params["m"] = market
    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT data_date, brand, SUM(total_monthly_sales) AS sales
            FROM daily_brand_summary
            WHERE data_date >= DATE_SUB(
                (SELECT MAX(data_date) FROM daily_brand_summary), INTERVAL :days DAY)
            {market_clause}
              AND LOWER(brand) IN ({_FOCUS})
            GROUP BY data_date, brand
            ORDER BY data_date, brand
        """), params).mappings().all()
    dates = sorted({str(r["data_date"]) for r in rows})
    # 大小写归一后按规范名累加(CUBOT/Cubot 合并为一条线)
    series: dict = {}
    for r in rows:
        b = canonical_brand(r["brand"])
        series.setdefault(b, {})
        d = str(r["data_date"])
        series[b][d] = series[b].get(d, 0) + int(r["sales"] or 0)
    series_out = {b: [vals.get(d, 0) for d in dates] for b, vals in series.items()}
    return ApiResponse(data={"dates": dates, "series": series_out})


@router.get("/brands/{brand}/detail", response_model=ApiResponse)
def get_brand_detail(brand: str, date: Optional[str] = Query(default=None)):
    """品牌详情:概览指标 + 趋势 + 站点分布 + 全品类营收占比 + 该品牌手机Top10商品。"""
    brand_lower = brand.lower()
    if brand_lower not in FOCUS_BRANDS:
        raise HTTPException(status_code=404, detail=f"unknown brand: {brand}")

    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(crawl_date) FROM amazon")
        ).scalar()
        if target is None:
            return ApiResponse(data={
                "brand": canonical_brand(brand_lower),
                "date": None,
                "summary": None,
                "trend": {"dates": [], "sales": []},
                "market_distribution": [],
                "category_share": [],
                "top_products": [],
            })

        # 1. 品牌概览指标(仅三防手机品类,从原始数据实时聚合)
        summary_row = conn.execute(text(f"""
            WITH per_asin AS (
                SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market, asin,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)) AS sales,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS rev,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price,
                       MAX(CAST(NULLIF(rating,'') AS DECIMAL(3,2))) AS rating,
                       MAX(fulfillment_method = 'FBA') AS is_fba
                FROM amazon
                WHERE crawl_date = :d AND LOWER(brand) = :b
                  AND LOWER(SUBSTRING_INDEX(category_path, ':', -1)) COLLATE utf8mb4_unicode_ci REGEXP :re
                GROUP BY pkey, market, asin
            ),
            family AS (
                SELECT pkey, market,
                       MAX(sales) AS sales, MAX(rev) AS rev,
                       AVG(price) AS price, AVG(rating) AS rating, MAX(is_fba) AS is_fba
                FROM per_asin GROUP BY pkey, market
            )
            SELECT COUNT(*) AS product_count,
                   SUM(rev * {_FX}) AS total_revenue,
                   SUM(sales) AS total_monthly_sales,
                   AVG(price * {_FX}) AS avg_price,
                   AVG(rating) AS avg_rating,
                   AVG(is_fba) AS fba_ratio,
                   GROUP_CONCAT(DISTINCT market ORDER BY market) AS markets
            FROM family
        """), {"d": target, "b": brand_lower, "re": PHONE_LEAF_REGEX}).mappings().first()
        summary = dict(summary_row) if summary_row and summary_row["product_count"] else None

        # 1.5 品类分桶卡片(手机/平板/手表/其他)
        bucket_rows = conn.execute(text(f"""
            WITH per_asin AS (
                SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market, asin,
                       LOWER(SUBSTRING_INDEX(category_path, ':', -1)) AS leaf,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)) AS sales,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS rev,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price
                FROM amazon
                WHERE crawl_date = :d AND LOWER(brand) = :b
                GROUP BY pkey, market, asin, leaf
            ),
            family AS (
                SELECT pkey, market, MAX(leaf) AS leaf,
                       MAX(sales) AS sales, MAX(rev) AS rev, AVG(price) AS price
                FROM per_asin GROUP BY pkey, market
            ),
            bucketed AS (
                SELECT
                    CASE
                        WHEN leaf COLLATE utf8mb4_unicode_ci REGEXP :phone_re THEN '手机'
                        WHEN leaf COLLATE utf8mb4_unicode_ci REGEXP :tablet_re THEN '平板'
                        WHEN leaf COLLATE utf8mb4_unicode_ci REGEXP :watch_re THEN '手表'
                        ELSE '其他'
                    END AS bucket,
                    sales, rev, price, market
                FROM family
            )
            SELECT bucket,
                   SUM(sales) AS total_sales,
                   SUM(rev * {_FX}) AS total_revenue,
                   COUNT(*) AS product_count,
                   AVG(price * {_FX}) AS avg_price
            FROM bucketed
            GROUP BY bucket
            ORDER BY total_revenue DESC
        """), {"d": target, "b": brand_lower,
               "phone_re": PHONE_LEAF_REGEX,
               "tablet_re": TABLET_LEAF_REGEX,
               "watch_re": WATCH_LEAF_REGEX}).mappings().all()
        category_cards = [dict(r) for r in bucket_rows]

        # 2. 30 天月销量趋势(daily_brand_summary,按日聚合)
        trend_rows = conn.execute(text("""
            SELECT data_date, SUM(total_monthly_sales) AS sales
            FROM daily_brand_summary
            WHERE data_date >= DATE_SUB(:d, INTERVAL 30 DAY)
              AND data_date <= :d AND LOWER(brand) = :b
            GROUP BY data_date ORDER BY data_date
        """), {"d": target, "b": brand_lower}).mappings().all()
        trend = {
            "dates": [str(r["data_date"]) for r in trend_rows],
            "sales": [int(r["sales"] or 0) for r in trend_rows],
        }

        # 3. 各站点销量分布(从 daily_brand_summary 取该品牌当日各站点)
        market_rows = conn.execute(text("""
            SELECT market, total_monthly_sales AS sales, total_revenue AS revenue
            FROM daily_brand_summary
            WHERE data_date = :d AND LOWER(brand) = :b
            ORDER BY total_monthly_sales DESC
        """), {"d": target, "b": brand_lower}).mappings().all()
        market_distribution = [dict(r) for r in market_rows]

        # 4. 全品类营收占比(按sub_category, USD折算, parent去重)
        cat_rows = conn.execute(text(f"""
            WITH per_asin AS (
                SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market, asin,
                       MAX(sub_category) AS sub_category,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS rev
                FROM amazon
                WHERE crawl_date = :d AND LOWER(brand) = :b
                GROUP BY pkey, market, asin
            ),
            family AS (
                SELECT pkey, market, MAX(sub_category) AS sub_category, MAX(rev) AS rev
                FROM per_asin GROUP BY pkey, market
            )
            SELECT sub_category, SUM(rev * {_FX}) AS revenue
            FROM family
            WHERE sub_category IS NOT NULL AND sub_category <> ''
            GROUP BY sub_category
            ORDER BY revenue DESC
        """), {"d": target, "b": brand_lower}).mappings().all()
        merged: dict = {}
        for r in cat_rows:
            label = normalize_sub_category(r["sub_category"])
            merged[label] = merged.get(label, 0) + float(r["revenue"] or 0)
        category_share = [
            {"sub_category": k, "revenue": v}
            for k, v in sorted(merged.items(), key=lambda x: -x[1])[:10]
        ]

        # 5. 该品牌手机Top10商品(价格和营收折算USD)
        top = conn.execute(text(f"""
            WITH per_asin AS (
                SELECT COALESCE(NULLIF(parent_asin,''), asin) AS pkey, market, asin, brand,
                       MAX(product_title) AS product_title,
                       MAX(main_image) AS main_image,
                       MAX(product_url) AS product_url,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_sales,'[^0-9.]',''),'') AS UNSIGNED)) AS sales,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(monthly_revenue,'[^0-9.]',''),'') AS DECIMAL(18,2))) AS rev,
                       MAX(CAST(NULLIF(REGEXP_REPLACE(price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price
                FROM amazon
                WHERE crawl_date = :d AND LOWER(brand) = :b
                  AND LOWER(SUBSTRING_INDEX(category_path, ':', -1)) COLLATE utf8mb4_unicode_ci REGEXP :re
                GROUP BY pkey, market, asin, brand
            ),
            family AS (
                SELECT pkey, market, MAX(brand) AS brand,
                       MAX(asin) AS asin,
                       MAX(product_title) AS product_title,
                       MAX(main_image) AS main_image,
                       MAX(product_url) AS product_url,
                       MAX(sales) AS sales, MAX(rev) AS rev, MAX(price) AS price
                FROM per_asin GROUP BY pkey, market
            )
            SELECT brand, asin, market, product_title, main_image, product_url,
                   sales AS monthly_sales,
                   ROUND(rev * {_FX}, 2) AS monthly_revenue,
                   ROUND(price * {_FX}, 2) AS price
            FROM family
            WHERE sales IS NOT NULL
            ORDER BY sales DESC LIMIT 10
        """), {"d": target, "b": brand_lower, "re": PHONE_LEAF_REGEX}).mappings().all()

    return ApiResponse(data={
        "brand": canonical_brand(brand_lower),
        "date": str(target),
        "summary": summary,
        "category_cards": category_cards,
        "trend": trend,
        "market_distribution": market_distribution,
        "category_share": category_share,
        "top_products": [dict(r) for r in top],
    })


@router.get("/brands/{brand}/models", response_model=ApiResponse)
def get_brand_models(brand: str,
                     type: str = Query(default="手机"),
                     date: Optional[str] = Query(default=None)):
    """型号销量排名(从预聚合表读取)。"""
    brand_lower = brand.lower()
    if brand_lower not in FOCUS_BRANDS:
        raise HTTPException(status_code=404, detail=f"unknown brand: {brand}")

    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(data_date) FROM daily_model_summary")
        ).scalar()
        if target is None:
            return ApiResponse(data={"brand": canonical_brand(brand_lower),
                                     "type": type, "date": None, "models": []})

        rows = conn.execute(text("""
            SELECT model, market, total_sales, total_revenue, sku_count, avg_price
            FROM daily_model_summary
            WHERE data_date = :d AND LOWER(brand) = :b AND type = :t
            ORDER BY total_sales DESC
        """), {"d": target, "b": brand_lower, "t": type}).mappings().all()

    # 按型号聚合总量 + 保留各站点明细
    model_map: dict = {}
    for r in rows:
        m = r["model"]
        if m not in model_map:
            model_map[m] = {
                "model": m,
                "total_sales": 0,
                "total_revenue": 0,
                "sku_count": 0,
                "markets": [],
            }
        model_map[m]["total_sales"] += int(r["total_sales"] or 0)
        model_map[m]["total_revenue"] += float(r["total_revenue"] or 0)
        model_map[m]["sku_count"] += int(r["sku_count"] or 0)
        model_map[m]["markets"].append({
            "market": r["market"],
            "sales": int(r["total_sales"] or 0),
            "revenue": float(r["total_revenue"] or 0),
        })

    models = sorted(model_map.values(), key=lambda x: -x["total_sales"])

    return ApiResponse(data={
        "brand": canonical_brand(brand_lower),
        "type": type,
        "date": str(target),
        "models": models,
    })
