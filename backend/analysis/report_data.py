# backend/analysis/report_data.py
# 报告数据构建:供 /api/reports/summary 接口和钉钉推送共用,口径一致。
from typing import Optional
from sqlalchemy import text
from backend.database import engine
from backend.constants import (canonical_brand, focus_brand_sql_list,
                               normalize_sub_category)

_FOCUS = focus_brand_sql_list()
# 日报=当天;周报=最近7天;月报=最近30天(均为截止基准日的滚动窗口)
PERIOD_DAYS = {"daily": 1, "weekly": 7, "monthly": 30}
PERIOD_LABELS = {"daily": "日报", "weekly": "周报", "monthly": "月报"}


def build_summary(period: str = "daily", date: Optional[str] = None) -> Optional[dict]:
    """六个聚焦品牌在指定周期内的营收/销量走势、品牌对比(期间日均)与品类营收分布。
    数据源 daily_overview_summary / daily_overview_category,与 Overview 页同口径。"""
    days = PERIOD_DAYS.get(period, 1)
    with engine.connect() as conn:
        end = date or conn.execute(
            text("SELECT MAX(data_date) FROM daily_overview_summary")
        ).scalar()
        if end is None:
            return None
        rng = {"end": end, "days": days}
        rows = conn.execute(text(f"""
            SELECT data_date, brand, total_revenue, total_monthly_sales,
                   avg_price, avg_rating
            FROM daily_overview_summary
            WHERE data_date <= :end AND data_date > DATE_SUB(:end, INTERVAL :days DAY)
              AND LOWER(brand) IN ({_FOCUS})
            ORDER BY data_date
        """), rng).mappings().all()
        # 按原始名称+日期取出,归一化后再合并:同一品类在各站点是本地化名称
        # (发电机 / Outdoor Generators / Externe Handyakkus 都是"发电机"),
        # 不归一就会被拆成多行重复计算。LIMIT 也必须放在合并之后。
        cat_rows = conn.execute(text("""
            SELECT sub_category, data_date, SUM(revenue) AS revenue
            FROM daily_overview_category
            WHERE data_date <= :end AND data_date > DATE_SUB(:end, INTERVAL :days DAY)
            GROUP BY sub_category, data_date
        """), rng).mappings().all()

    if not rows:
        return None

    dates = sorted({str(r["data_date"]) for r in rows})
    idx = {d: i for i, d in enumerate(dates)}
    brands: dict = {}
    for r in rows:
        # 必须按小写归一分组:表里同一品牌存在多种大小写(历史 'Anker' / 今日 'anker'),
        # 按原始名分组会把一个品牌劈成两条,总数直接翻倍。
        b = brands.setdefault((r["brand"] or "").lower(), {
            "brand": canonical_brand(r["brand"]),
            "revenue": [None] * len(dates),
            "sales": [None] * len(dates),
            "price": [None] * len(dates),
            "rating": [None] * len(dates),
        })
        i = idx[str(r["data_date"])]
        b["revenue"][i] = float(r["total_revenue"] or 0)
        b["sales"][i] = int(r["total_monthly_sales"] or 0)
        b["price"][i] = float(r["avg_price"]) if r["avg_price"] is not None else None
        b["rating"][i] = float(r["avg_rating"]) if r["avg_rating"] is not None else None

    def _avg(vals):
        vs = [v for v in vals if v is not None]
        return round(sum(vs) / len(vs), 2) if vs else 0

    out = []
    for b in brands.values():
        b["avg_revenue"] = _avg(b["revenue"])
        b["avg_sales"] = _avg(b["sales"])
        b["avg_price"] = _avg(b["price"])
        b["avg_rating"] = _avg(b["rating"])
        out.append(b)
    out.sort(key=lambda x: -x["avg_revenue"])

    return {
        "period": period, "start_date": dates[0], "end_date": str(end),
        "dates": dates,
        "brands": out,
        # 期间日均:各品牌日均值之和,便于跨周期对比
        "totals": {
            "revenue": round(sum(b["avg_revenue"] for b in out), 2),
            "sales": int(sum(b["avg_sales"] for b in out)),
        },
        "categories": merge_categories(cat_rows),
    }


def merge_categories(cat_rows, limit: int = 12) -> list:
    """把本地化品类名归一后合并,再取营收 Top N(期间日均)。"""
    acc: dict = {}
    for r in cat_rows:
        key = normalize_sub_category(r["sub_category"])
        a = acc.setdefault(key, {"revenue": 0.0, "dates": set()})
        a["revenue"] += float(r["revenue"] or 0)
        a["dates"].add(str(r["data_date"]))
    out = [{"sub_category": k, "revenue": round(v["revenue"] / len(v["dates"]), 2)}
           for k, v in acc.items() if v["dates"]]
    out.sort(key=lambda x: -x["revenue"])
    return out[:limit]
