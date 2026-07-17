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


def _safe_push(period: str):
    try:
        # 惰性导入:推送依赖(requests/matplotlib)缺失时不影响后端启动
        from backend.analysis.dingtalk_push import push_report
        result = push_report(period)
        logger.info("dingtalk push %s: %s", period, result)
    except Exception:
        logger.exception("dingtalk push %s failed", period)


def _safe_llm(period: str):
    try:
        run_llm_analysis(date.today(), period)
    except Exception:
        logger.exception("llm_report %s failed", period)


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

_catch_up_if_needed()  # 启动时立即检查一次,避免错过凌晨3点的调度
def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_aggregation, "cron", hour=3, minute=0,
                      misfire_grace_time=3600)
    # 每天凌晨3-9点,每小时检查一次是否需要补跑
    scheduler.add_job(_catch_up_if_needed, "cron", hour="3-9", minute=30,
                      misfire_grace_time=3600)
    # 周报/月报的 LLM 分析:各自独立生成(不能拿日报凑数,口径和结论都不同)。
    # 排在推送前一小时,给 LLM 留出重试余量;日报的 LLM 在 3 点聚合里已经跑了。
    scheduler.add_job(lambda: _safe_llm("weekly"), "cron", day_of_week="mon",
                      hour=8, minute=0, misfire_grace_time=3600)
    scheduler.add_job(lambda: _safe_llm("monthly"), "cron", day=1,
                      hour=8, minute=10, misfire_grace_time=3600)
    # 钉钉推送:每天9点日报;周一9:05周报;每月1号9:10月报
    # (放在上午推送而非聚合完成后,避免凌晨3点打扰;此时数据已聚合完)
    scheduler.add_job(lambda: _safe_push("daily"), "cron", hour=9, minute=0,
                      misfire_grace_time=3600)
    scheduler.add_job(lambda: _safe_push("weekly"), "cron", day_of_week="mon",
                      hour=9, minute=5, misfire_grace_time=3600)
    scheduler.add_job(lambda: _safe_push("monthly"), "cron", day=1,
                      hour=9, minute=10, misfire_grace_time=3600)
    scheduler.start()
    _catch_up_if_needed()
    return scheduler
