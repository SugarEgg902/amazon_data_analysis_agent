# backend/routers/brands.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.constants import focus_brand_sql_list, canonical_brand

router = APIRouter()

_FOCUS = focus_brand_sql_list()


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
