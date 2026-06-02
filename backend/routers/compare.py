# backend/routers/compare.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.constants import focus_brand_sql_list, canonical_brand

router = APIRouter()

_FOCUS = focus_brand_sql_list()


@router.get("/compare", response_model=ApiResponse)
def get_compare(market: Optional[str] = Query(default=None),
                date: Optional[str] = Query(default=None)):
    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(data_date) FROM daily_brand_summary")
        ).scalar()
        if target is None:
            return ApiResponse(data={"date": None, "brands": [], "top_products": {}})

        params: dict = {"d": target}
        market_clause = ""
        if market:
            market_clause = " AND market = :m"
            params["m"] = market

        # 仅 5 个聚焦品牌,跨站点按品牌汇总
        brands = conn.execute(text(f"""
            SELECT brand,
                   GROUP_CONCAT(DISTINCT market ORDER BY market) AS markets,
                   SUM(product_count) AS product_count,
                   SUM(total_revenue) AS total_revenue,
                   SUM(total_monthly_sales) AS total_monthly_sales,
                   AVG(avg_price) AS avg_price,
                   AVG(avg_rating) AS avg_rating,
                   AVG(avg_growth_rate) AS avg_growth_rate,
                   AVG(avg_gross_margin) AS avg_gross_margin,
                   AVG(fba_ratio) AS fba_ratio
            FROM daily_brand_summary
            WHERE data_date = :d {market_clause}
              AND LOWER(brand) IN ({_FOCUS})
            GROUP BY brand
            ORDER BY total_monthly_sales DESC
        """), params).mappings().all()

        s_market_clause = " AND s.market = :m" if market else ""
        top = conn.execute(text(f"""
            SELECT s.brand, s.asin, s.market, s.monthly_sales, s.monthly_revenue,
                   a.product_title, a.main_image
            FROM product_daily_snapshot s
            LEFT JOIN amazon a ON a.asin = s.asin AND a.market = s.market
                 AND a.crawl_date = s.snapshot_date
            WHERE s.snapshot_date = :d {s_market_clause}
              AND LOWER(s.brand) IN ({_FOCUS})
            ORDER BY s.brand, s.monthly_sales DESC
        """), params).mappings().all()

    brand_top: dict = {}
    seen = set()
    for r in top:
        k = (r["asin"], r["market"])
        if k in seen:
            continue
        seen.add(k)
        item = dict(r)
        b = canonical_brand(r["brand"])
        item["brand"] = b
        brand_top.setdefault(b, [])
        if len(brand_top[b]) < 10:
            brand_top[b].append(item)

    brand_list = []
    for b in brands:
        d = dict(b)
        d["brand"] = canonical_brand(b["brand"])
        brand_list.append(d)

    return ApiResponse(data={
        "date": str(target),
        "brands": brand_list,
        "top_products": brand_top,
    })
