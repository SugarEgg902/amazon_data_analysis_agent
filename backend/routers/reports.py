# backend/routers/reports.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()


def _row_to_dict(r):
    return {
        "report_date": str(r["report_date"]),
        "content": r["content"],
        "model": r["model"],
        "generated_at": str(r["generated_at"]),
        "status": r["status"],
        "error_message": r["error_message"],
    }


@router.get("/reports", response_model=ApiResponse)
def get_report(date: Optional[str] = Query(default=None)):
    with engine.connect() as conn:
        if date:
            r = conn.execute(text("""
                SELECT report_date, content, model, generated_at, status, error_message
                FROM daily_analysis_reports WHERE report_date = :d
            """), {"d": date}).mappings().first()
        else:
            r = conn.execute(text("""
                SELECT report_date, content, model, generated_at, status, error_message
                FROM daily_analysis_reports ORDER BY report_date DESC LIMIT 1
            """)).mappings().first()
    return ApiResponse(data=_row_to_dict(r) if r else None)


@router.get("/reports/latest", response_model=ApiResponse)
def get_latest_report():
    return get_report(date=None)
