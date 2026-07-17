# backend/analysis/anomaly_detector.py
from datetime import datetime
from typing import Optional
from sqlalchemy import text
from backend.database import engine

# (metric column in snapshot, anomaly_type, default threshold fraction)
_METRICS = [
    ("monthly_revenue", "sales_amount", 0.30),
    ("monthly_sales", "sales_volume", 0.30),
    ("price", "price", 0.20),
    ("main_bsr", "main_bsr", 0.30),
    ("sub_bsr", "sub_bsr", 0.30),
]


def run_anomaly_detection(
    sales_amount_threshold: float = 0.30,
    sales_volume_threshold: float = 0.30,
    price_threshold: float = 0.20,
    main_bsr_threshold: float = 0.30,
    sub_bsr_threshold: float = 0.30,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
) -> dict:
    """基线 = 指定日期范围内快照的均值(始终不含最新快照当天)。
    不传日期时默认为最新快照前 7 天。当前值超过基线均值 threshold 比例即为异常。"""
    thresholds = {
        "sales_amount": sales_amount_threshold,
        "sales_volume": sales_volume_threshold,
        "price": price_threshold,
        "main_bsr": main_bsr_threshold,
        "sub_bsr": sub_bsr_threshold,
    }
    detected_at = datetime.now()
    inserted = 0

    with engine.begin() as conn:
        latest = conn.execute(
            text("SELECT MAX(snapshot_date) FROM product_daily_snapshot")
        ).scalar()
        if latest is None:
            return {"detected": 0, "detected_at": detected_at.isoformat()}

        # 当前值
        current_rows = conn.execute(text("""
            SELECT asin, market, brand, monthly_revenue, monthly_sales,
                   price, main_bsr, sub_bsr
            FROM product_daily_snapshot
            WHERE snapshot_date = :d
        """), {"d": latest}).mappings().all()

        # 基线（不含最新快照当天），按 (asin, market) 聚合均值 + 计数
        # 自定义日期范围优先；否则默认最新快照前 7 天
        if start_date and end_date:
            base_where = ("snapshot_date >= :start AND snapshot_date <= :end "
                          "AND snapshot_date < :d")
            base_params = {"d": latest, "start": start_date, "end": end_date}
            min_days = 1   # 自定义范围可能很短，有数据即可
        else:
            base_where = ("snapshot_date < :d "
                          "AND snapshot_date >= DATE_SUB(:d, INTERVAL 7 DAY)")
            base_params = {"d": latest}
            min_days = 3   # 默认窗口下历史不足 3 天，基线不可靠，跳过
        base_rows = conn.execute(text(f"""
            SELECT asin, market,
                   COUNT(*) AS n,
                   AVG(monthly_revenue) AS monthly_revenue,
                   AVG(monthly_sales)   AS monthly_sales,
                   AVG(price)           AS price,
                   AVG(main_bsr)        AS main_bsr,
                   AVG(sub_bsr)         AS sub_bsr
            FROM product_daily_snapshot
            WHERE {base_where}
            GROUP BY asin, market
        """), base_params).mappings().all()
        baseline = {(r["asin"], r["market"]): r for r in base_rows}

        for cur in current_rows:
            base = baseline.get((cur["asin"], cur["market"]))
            if not base or base["n"] < min_days:
                continue
            for col, atype, _ in _METRICS:
                cv, bv = cur[col], base[col]
                if cv is None or bv is None or float(bv) == 0:
                    continue
                cv, bv = float(cv), float(bv)
                change = (cv - bv) / bv
                if abs(change) > thresholds[atype]:
                    conn.execute(text("""
                        INSERT INTO anomaly_alerts
                            (detected_at, asin, market, brand, anomaly_type,
                             current_value, baseline_value, change_pct,
                             threshold_pct, direction)
                        VALUES (:ts, :asin, :market, :brand, :atype, :cv, :bv,
                                :chg, :thr, :dir)
                    """), {
                        "ts": detected_at, "asin": cur["asin"], "market": cur["market"],
                        "brand": cur["brand"] or "", "atype": atype,
                        "cv": cv, "bv": bv, "chg": change * 100,
                        "thr": thresholds[atype] * 100,
                        "dir": "up" if change > 0 else "down",
                    })
                    inserted += 1

    return {"detected": inserted, "detected_at": detected_at.isoformat()}
