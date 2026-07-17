# backend/routers/reports.py
import logging
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.analysis.report_data import build_summary

logger = logging.getLogger(__name__)
router = APIRouter()


_COLS = ("report_date, period, content, model, generated_at, status, error_message")


def _row_to_dict(r):
    return {
        "report_date": str(r["report_date"]),
        "period": r["period"],
        "content": r["content"],
        "model": r["model"],
        "generated_at": str(r["generated_at"]),
        "status": r["status"],
        "error_message": r["error_message"],
    }


@router.get("/reports", response_model=ApiResponse)
def get_report(date: Optional[str] = Query(default=None),
               period: str = Query(default="daily", pattern="^(daily|weekly|monthly)$")):
    with engine.connect() as conn:
        if date:
            r = conn.execute(text(f"""
                SELECT {_COLS} FROM daily_analysis_reports
                WHERE report_date = :d AND period = :p
            """), {"d": date, "p": period}).mappings().first()
        else:
            r = conn.execute(text(f"""
                SELECT {_COLS} FROM daily_analysis_reports
                WHERE period = :p ORDER BY report_date DESC LIMIT 1
            """), {"p": period}).mappings().first()
    return ApiResponse(data=_row_to_dict(r) if r else None)


@router.get("/reports/latest", response_model=ApiResponse)
def get_latest_report(period: str = Query(default="daily",
                                          pattern="^(daily|weekly|monthly)$")):
    return get_report(date=None, period=period)


@router.get("/reports/summary", response_model=ApiResponse)
def report_summary(period: str = Query(default="daily", pattern="^(daily|weekly|monthly)$"),
                   date: Optional[str] = Query(default=None,
                                               description="基准日(YYYY-MM-DD),默认最新")):
    """报告页图表数据。具体口径见 backend/analysis/report_data.py(与钉钉推送共用)。"""
    return ApiResponse(data=build_summary(period, date))


@router.post("/reports/push", response_model=ApiResponse)
def push_report_now(period: str = Query(default="daily", pattern="^(daily|weekly|monthly)$")):
    """手动触发一次钉钉推送(测试用)。定时推送见 backend/scheduler.py。"""
    try:
        # 惰性导入必须放在 try 内:推送模块的导入本身就可能失败(缺依赖/配置项漏定义),
        # 放在外面会绕过这里的 except,变成一个没有任何信息的 500。
        from backend.analysis.dingtalk_push import push_report
        return ApiResponse(data=push_report(period))
    except Exception as e:  # noqa
        logger.exception("手动推送 %s 失败", period)
        return ApiResponse(data=None, error=f"{type(e).__name__}: {e}")
