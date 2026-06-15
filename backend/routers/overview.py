# backend/routers/overview.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.constants import canonical_brand, focus_brand_sql_list

router = APIRouter()

_FOCUS = focus_brand_sql_list()


@router.get("/overview", response_model=ApiResponse)
def get_overview(date: Optional[str] = Query(default=None),
                 market: Optional[str] = Query(default=None)):
    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(data_date) FROM daily_brand_summary")
        ).scalar()
        if target is None:
            return ApiResponse(data={"date": None, "category": "全品类",
                                     "brands": [], "category_share": []})

        # 全品类汇总（从 daily_brand_summary 按品牌聚合所有站点）
        rows = conn.execute(text(f"""
            SELECT brand,
                   GROUP_CONCAT(DISTINCT market ORDER BY market) AS markets,
                   SUM(product_count) AS product_count,
                   SUM(total_revenue) AS total_revenue,
                   SUM(total_monthly_sales) AS total_monthly_sales,
                   AVG(avg_price) AS avg_price,
                   AVG(avg_rating) AS avg_rating,
                   AVG(avg_growth_rate) AS avg_growth_rate,
                   AVG(fba_ratio) AS fba_ratio
            FROM daily_brand_summary
            WHERE data_date = :d AND LOWER(brand) IN ({_FOCUS})
            GROUP BY brand
            ORDER BY SUM(total_revenue) DESC
        """), {"d": target}).mappings().all()

        cats = conn.execute(text("""
            SELECT sub_category, revenue
            FROM daily_overview_category
            WHERE data_date = :d
            ORDER BY revenue DESC
        """), {"d": target}).mappings().all()

    brand_rows = []
    for r in rows:
        d = dict(r)
        d["brand"] = canonical_brand(r["brand"])
        brand_rows.append(d)

    return ApiResponse(data={
        "date": str(target),
        "category": "全品类（全站点合并）",
        "brands": brand_rows,
        "category_share": [dict(r) for r in cats],
    })
