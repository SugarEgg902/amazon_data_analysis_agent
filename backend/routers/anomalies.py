# backend/routers/anomalies.py
from fastapi import APIRouter, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy import text
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.analysis.anomaly_detector import run_anomaly_detection

router = APIRouter()


class DetectRequest(BaseModel):
    sales_amount_threshold: float = 0.30
    sales_volume_threshold: float = 0.30
    price_threshold: float = 0.20
    main_bsr_threshold: float = 0.30
    sub_bsr_threshold: float = 0.30
    # 基线日期范围(YYYY-MM-DD)。不传则默认最新快照前 7 天
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post("/anomalies/detect", response_model=ApiResponse)
def detect(req: DetectRequest = DetectRequest()):
    result = run_anomaly_detection(
        req.sales_amount_threshold, req.sales_volume_threshold,
        req.price_threshold, req.main_bsr_threshold, req.sub_bsr_threshold,
        start_date=req.start_date, end_date=req.end_date,
    )
    return ApiResponse(data=result)


@router.get("/anomalies/latest", response_model=ApiResponse)
def latest(market: Optional[str] = Query(default=None),
           brand: Optional[str] = Query(default=None),
           type: Optional[str] = Query(default=None)):
    with engine.connect() as conn:
        ts = conn.execute(text("SELECT MAX(detected_at) FROM anomaly_alerts")).scalar()
        if ts is None:
            return ApiResponse(data={"detected_at": None, "items": []})
        filters = ["detected_at = :ts"]
        params: dict = {"ts": ts}
        if market:
            filters.append("market = :m"); params["m"] = market
        if brand:
            filters.append("brand = :b"); params["b"] = brand
        if type:
            filters.append("anomaly_type = :t"); params["t"] = type
        where = " AND ".join(filters)
        rows = conn.execute(text(f"""
            SELECT id, asin, market, brand, anomaly_type, current_value,
                   baseline_value, change_pct, threshold_pct, direction
            FROM anomaly_alerts WHERE {where}
            ORDER BY ABS(change_pct) DESC
        """), params).mappings().all()
    return ApiResponse(data={"detected_at": str(ts), "items": [dict(r) for r in rows]})
