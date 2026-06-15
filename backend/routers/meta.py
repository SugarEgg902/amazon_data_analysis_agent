# backend/routers/meta.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()


@router.get("/meta/markets", response_model=ApiResponse)
def get_markets():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT DISTINCT market FROM daily_brand_summary WHERE market IS NOT NULL ORDER BY market"
        ))
        return ApiResponse(data=[r[0] for r in rows])


@router.get("/meta/brands", response_model=ApiResponse)
def get_brands(market: Optional[str] = Query(default=None)):
    sql = "SELECT DISTINCT brand FROM daily_brand_summary WHERE brand IS NOT NULL"
    params = {}
    if market:
        sql += " AND market = :m"
        params["m"] = market
    sql += " ORDER BY brand"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        return ApiResponse(data=[r[0] for r in rows])


@router.get("/meta/categories", response_model=ApiResponse)
def get_categories(market: Optional[str] = Query(default=None)):
    sql = "SELECT DISTINCT sub_category FROM daily_category_summary WHERE sub_category IS NOT NULL"
    params = {}
    if market:
        sql += " AND market = :m"
        params["m"] = market
    sql += " ORDER BY sub_category"
    with engine.connect() as conn:
        rows = conn.execute(text(sql), params)
        return ApiResponse(data=[r[0] for r in rows])
