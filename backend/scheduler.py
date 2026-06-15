# backend/scheduler.py
import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
from backend.aggregation.product_snapshot import run_product_snapshot
from backend.aggregation.overview_summary import run_overview_summary
from backend.aggregation.model_summary import run_model_summary
from backend.analysis.llm_report import run_llm_analysis
from sqlalchemy import text
from backend.database import engine

logger = logging.getLogger(__name__)


def run_daily_aggregation():
    today = date.today()
    for name, fn in (
        ("product_snapshot", run_product_snapshot),
        ("brand_summary", run_brand_summary),
        ("category_summary", run_category_summary),
        ("overview_summary", run_overview_summary),
        ("model_summary", run_model_summary),
    ):
        try:
            fn(today)
            logger.info("%s completed for %s", name, today)
        except Exception:
            logger.exception("%s failed for %s", name, today)
    try:
        run_llm_analysis(today)
        logger.info("llm_report completed for %s", today)
    except Exception:
        logger.exception("llm_report failed for %s", today)


def _catch_up_if_needed():
    """检查今天是否已聚合,如果没有且有原始数据则立即补跑。"""
    today = date.today()
    with engine.connect() as conn:
        has_raw = conn.execute(
            text("SELECT 1 FROM amazon WHERE crawl_date = :d LIMIT 1"),
            {"d": today},
        ).first()
        has_agg = conn.execute(
            text("SELECT 1 FROM daily_overview_summary WHERE data_date = :d LIMIT 1"),
            {"d": today},
        ).first()
    if has_raw and not has_agg:
        logger.info("补跑: 今天 %s 有原始数据但未聚合", today)
        run_daily_aggregation()


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    # 凌晨3点定时聚合
    scheduler.add_job(run_daily_aggregation, "cron", hour=3, minute=0,
                      misfire_grace_time=3600)
    # 每天凌晨3-9点,每小时检查一次是否需要补跑
    scheduler.add_job(_catch_up_if_needed, "cron", hour="3-9", minute=30,
                      misfire_grace_time=3600)
    scheduler.start()
    _catch_up_if_needed()
    return scheduler
