# backend/scheduler.py
import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
from backend.aggregation.product_snapshot import run_product_snapshot
from backend.aggregation.overview_summary import run_overview_summary
from backend.analysis.llm_report import run_llm_analysis

logger = logging.getLogger(__name__)


def run_daily_aggregation():
    today = date.today()
    for name, fn in (
        ("product_snapshot", run_product_snapshot),
        ("brand_summary", run_brand_summary),
        ("category_summary", run_category_summary),
        ("overview_summary", run_overview_summary),
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


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_aggregation, "cron", hour=3, minute=0,
                      misfire_grace_time=3600)
    scheduler.start()
    return scheduler
