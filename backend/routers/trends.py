# backend/routers/trends.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()


@router.get("/trends", response_model=ApiResponse)
def get_trends(market: Optional[str] = Query(default=None),
               date: Optional[str] = Query(default=None)):
    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(snapshot_date) FROM product_daily_snapshot")
        ).scalar()
        if target is None:
            return ApiResponse(data={"date": None, "growth_ranking": [],
                                     "new_products": [], "category_trends": []})

        params: dict = {"d": target}
        sclause = " AND s.market = :m" if market else ""
        if market:
            params["m"] = market

        growth = conn.execute(text(f"""
            SELECT s.asin, s.market, s.brand, s.growth_rate, s.monthly_sales,
                   a.product_title, a.main_image
            FROM product_daily_snapshot s
            LEFT JOIN amazon a ON a.asin = s.asin AND a.market = s.market
                 AND a.crawl_date = s.snapshot_date
            WHERE s.snapshot_date = :d AND s.growth_rate IS NOT NULL {sclause}
            ORDER BY s.growth_rate DESC LIMIT 50
        """), params).mappings().all()

        new_clause = " AND a.market = :m" if market else ""
        new_products = conn.execute(text(f"""
            SELECT a.asin, a.market, MAX(a.brand) AS brand,
                   MAX(a.product_title) AS product_title, MAX(a.main_image) AS main_image,
                   MAX(a.launch_date) AS launch_date,
                   MAX(CAST(NULLIF(REGEXP_REPLACE(a.price,'[^0-9.]',''),'') AS DECIMAL(10,2))) AS price
            FROM amazon a
            WHERE a.crawl_date = :d AND a.launch_date IS NOT NULL
                  AND a.launch_date >= DATE_SUB(:d, INTERVAL 30 DAY) {new_clause}
            GROUP BY a.asin, a.market
            ORDER BY launch_date DESC LIMIT 50
        """), params).mappings().all()

        cat_clause = " AND market = :m" if market else ""
        cats = conn.execute(text(f"""
            SELECT sub_category, SUM(total_monthly_sales) AS total_sales
            FROM daily_category_summary
            WHERE data_date = :d {cat_clause}
            GROUP BY sub_category ORDER BY total_sales DESC LIMIT 20
        """), params).mappings().all()

    # 去重新品 LEFT JOIN 噪声
    seen, new_items = set(), []
    for r in new_products:
        k = (r["asin"], r["market"])
        if k in seen:
            continue
        seen.add(k)
        new_items.append(dict(r))

    return ApiResponse(data={
        "date": str(target),
        "growth_ranking": [dict(r) for r in growth],
        "new_products": new_items,
        "category_trends": [dict(r) for r in cats],
    })
