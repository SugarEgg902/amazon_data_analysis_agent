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
    # Overview headline 仅统计储能品类(类比手机项目的"仅手机"口径):
    #   - OUKITEL 在本数据集为手机、无储能 → 自然显示 ~0
    #   - Anker 仅其储能(Generators/Power Banks)计入 headline
    # 数据源为 daily_overview_summary(已按储能叶子过滤聚合)。
    with engine.connect() as conn:
        target = date or conn.execute(
            text("SELECT MAX(data_date) FROM daily_overview_summary")
        ).scalar()
        if target is None:
            return ApiResponse(data={"date": None, "category": "储能品类",
                                     "brands": [], "category_share": []})

        # 储能口径汇总(从 daily_overview_summary 按品牌聚合所有站点)
        rows = conn.execute(text(f"""
            SELECT brand,
                   markets,
                   product_count,
                   total_revenue,
                   total_monthly_sales,
                   avg_price,
                   avg_rating,
                   avg_growth_rate,
                   fba_ratio
            FROM daily_overview_summary
            WHERE data_date = :d AND LOWER(brand) IN ({_FOCUS})
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
        "category": "储能品类（全站点合并）",
        "brands": brand_rows,
        "category_share": [dict(r) for r in cats],
    })
