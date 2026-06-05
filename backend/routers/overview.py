# backend/routers/overview.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.constants import canonical_brand

router = APIRouter()


@router.get("/overview", response_model=ApiResponse)
def get_overview(date: Optional[str] = Query(default=None),
                 market: Optional[str] = Query(default=None)):
    # 读取预聚合表 daily_overview_summary(每日定时生成,已按变体去重+手机过滤+USD折算)
    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(data_date) FROM daily_overview_summary")
        ).scalar()
        if target is None:
            return ApiResponse(data={"date": None, "category": "手机",
                                     "brands": [], "category_share": []})

        rows = conn.execute(text("""
            SELECT brand, markets, product_count, total_revenue,
                   total_monthly_sales, avg_price, avg_rating,
                   avg_growth_rate, avg_gross_margin, fba_ratio
            FROM daily_overview_summary
            WHERE data_date = :d
            ORDER BY total_revenue DESC
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
        "category": "手机（全站点合并）",
        "brands": brand_rows,
        "category_share": [dict(r) for r in cats],
    })
