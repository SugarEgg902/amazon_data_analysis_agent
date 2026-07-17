# backend/analysis/dingtalk_push.py
# 钉钉自定义机器人推送:日报/周报/月报,markdown 格式 + 服务端渲染图表。
# 注意:图片是每个查看者的钉钉客户端去拉取 PUBLIC_BASE_URL 的,
# 内网地址只有连着内网的设备能看到图,外网(4G)用户图会加载失败,文字不受影响。
import time
import hmac
import hashlib
import base64
import logging
import urllib.parse
from datetime import date, timedelta

import requests
from sqlalchemy import text

from backend.database import engine
from backend.constants import (FOCUS_BRANDS, canonical_brand,
                               focus_brand_sql_list)
from backend.analysis.report_data import build_summary, PERIOD_LABELS
from backend.analysis.report_charts import render_report_charts
from config.config import (DINGTALK_WEBHOOK, DINGTALK_SECRET, PUBLIC_BASE_URL,
                           REPORT_EMBED_CHARTS)

logger = logging.getLogger(__name__)

# LLM 日报全文附在消息里的最大长度(钉钉单条消息上限 20000 字节)
_MAX_LLM_CHARS = 3000

_FOCUS = focus_brand_sql_list()
# 异常类型 → 中文标签
_ANOMALY_LABELS = {
    "sales_amount": "销售额", "sales_volume": "销量", "price": "价格",
    "main_bsr": "大类排名", "sub_bsr": "小类排名",
}


def _signed_webhook() -> str:
    """在配置的 webhook 地址上追加加签参数。"""
    timestamp = str(round(time.time() * 1000))
    string_to_sign = f"{timestamp}\n{DINGTALK_SECRET}"
    hmac_code = hmac.new(DINGTALK_SECRET.encode(), string_to_sign.encode(),
                         digestmod=hashlib.sha256).digest()
    sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
    sep = "&" if "?" in DINGTALK_WEBHOOK else "?"
    return f"{DINGTALK_WEBHOOK}{sep}timestamp={timestamp}&sign={sign}"


def send_markdown(title: str, md_text: str) -> dict:
    """发送 markdown 消息:整条消息就是一份报告,图表内嵌在正文里。

    用 markdown 而非 actionCard:actionCard 配了 singleURL 后点卡片
    任意位置都会跳网页,这里要的是一份不跳转的报告。
    title 只用于通知栏摘要,不显示在正文。
    """
    body = {
        "msgtype": "markdown",
        "markdown": {
            "title": title,
            "text": md_text,
        },
    }
    resp = requests.post(_signed_webhook(), json=body,
                         headers={"Content-Type": "application/json"}, timeout=15)
    data = resp.json()
    if data.get("errcode") != 0:
        raise RuntimeError(f"钉钉推送失败: {data}")
    return data


def _fmt_money(v: float) -> str:
    return f"${v:,.0f}"


def _fmt_money_short(v: float) -> str:
    """表格单元格用的紧凑金额:$49,853,946 太长,手机上会把表格撑爆。"""
    v = float(v or 0)
    if abs(v) >= 1_000_000:
        return f"${v / 1_000_000:,.2f}M"
    if abs(v) >= 1_000:
        return f"${v / 1_000:,.1f}K"
    return f"${v:,.0f}"


def _fmt_count_short(v: float) -> str:
    """表格单元格用的紧凑计数:586,376 → 586.4K。同样是为了压表格宽度。"""
    v = float(v or 0)
    if abs(v) >= 1_000_000:
        return f"{v / 1_000_000:,.2f}M"
    if abs(v) >= 1_000:
        return f"{v / 1_000:,.1f}K"
    return f"{v:,.0f}"


def _fmt_delta(cur: float, prev: float) -> str:
    """环比涨跌。上一周期无数据时返回空串,不显示"0%"误导人。"""
    if not prev:
        return ""
    pct = (cur - prev) / prev * 100
    arrow = "↑" if pct >= 0 else "↓"
    return f" {arrow}{abs(pct):.1f}%"


def _prev_summary(period: str, summary: dict):
    """上一周期的同口径数据:以本周期起始日的前一天为基准日回跑 build_summary。"""
    prev_end = (date.fromisoformat(summary["start_date"]) - timedelta(days=1)).isoformat()
    try:
        return build_summary(period, prev_end)
    except Exception:
        logger.exception("上一周期数据获取失败,本次不显示环比")
        return None


def _fetch_llm_report(period: str, end_date: str) -> str:
    """取本周期自己的 LLM 分析(周报取周报的,不会拿日报凑数)。
    基准日当天没有则退回同周期最近一份成功的,并注明实际日期。"""
    with engine.connect() as conn:
        r = conn.execute(text("""
            SELECT report_date, content FROM daily_analysis_reports
            WHERE status = 'success' AND period = :p AND report_date <= :d
            ORDER BY report_date DESC LIMIT 1
        """), {"p": period, "d": end_date}).mappings().first()
    if not r or not r["content"]:
        return ""
    content = r["content"]
    if str(r["report_date"]) != str(end_date):
        content = f"(以下为 {r['report_date']} 生成的分析)\n\n{content}"
    return content


def _fetch_anomalies(start_date: str, end_date: str, limit: int = 8) -> tuple:
    """周期内聚焦品牌的异常告警,按变动幅度取前 N 条。返回 (总数, 明细)。

    只取销量/销售额/价格三类,排除 main_bsr/sub_bsr:名次是序数,
    27 名掉到 11419 名会算出 +42588% 这种没有业务含义的百分比,
    按幅度排序时会把真正该看的销量/价格异常全部挤掉。
    OUKITEL(我们的品牌)的异常优先排在最前。

    不要给 baseline_value 加最小阈值来"降噪"。销量 1 → 44 这种低基数暴涨
    看着像噪音,实际是竞品新品起量的早期信号(爆款潜质),正是竞品监控最该
    第一时间抓到的东西。按 ABS(change_pct) 排序会把它们排在前面 —— 这是
    有意为之,不是 bug。
    """
    rng = {"s": start_date, "e": end_date}
    where = f"""
        WHERE DATE(detected_at) BETWEEN :s AND :e
          AND LOWER(brand) IN ({_FOCUS})
          AND anomaly_type IN ('sales_amount', 'sales_volume', 'price')
    """
    with engine.connect() as conn:
        total = conn.execute(text(
            f"SELECT COUNT(*) FROM anomaly_alerts {where}"), rng).scalar() or 0
        rows = conn.execute(text(f"""
            SELECT brand, market, asin, anomaly_type, direction,
                   current_value, baseline_value, change_pct
            FROM anomaly_alerts {where}
            ORDER BY (LOWER(brand) = 'oukitel') DESC, ABS(change_pct) DESC
            LIMIT :n
        """), {**rng, "n": limit}).mappings().all()
    return total, rows


def _fetch_bsr_anomalies(start_date: str, end_date: str, each: int = 3) -> tuple:
    """BSR 名次异动:名次上升/下滑各取前 N 条。返回 (总数, 上升, 下滑)。

    名次是序数,口径和销量/价格完全不同,所以单独一张表、单独一套排序:

    1. 方向语义是反的 —— 名次数字变小(DB 里 direction='down')才是排名上升、
       是好事。direction 描述的是原始值涨跌而非好坏,展示时必须反过来。
    2. 不能按 change_pct 排序 —— 名次上升数学上永远跨不过 -100%
       (实测最小 -99.2%),而下滑无上界(实测最大 +42,588%)。按 ABS(change_pct)
       排,下滑会永远霸榜、上升永远进不了前 N。改用倍数 GREATEST(base/cur, cur/base),
       对两个方向对称。
    3. 即便用倍数,下滑仍能跌几百倍、上升受名次下限约束,单一排序还是会被下滑占满
       (实测前 8 全是下滑)。所以**两个方向各取前 N**,保证爆款信号(名次猛冲)
       一定有位置。
    4. 不做 OUKITEL 置顶 —— OUKITEL 的 BSR 告警条数多,置顶会把整张表占满,
       竞品的大异动一条都进不来,而竞品异动正是这张表的意义。
    """
    rng = {"s": start_date, "e": end_date}
    where = f"""
        WHERE DATE(detected_at) BETWEEN :s AND :e
          AND LOWER(brand) IN ({_FOCUS})
          AND anomaly_type IN ('main_bsr', 'sub_bsr')
          AND baseline_value > 0 AND current_value > 0
    """
    sql = f"""
        SELECT brand, market, asin, anomaly_type,
               current_value, baseline_value,
               GREATEST(baseline_value / current_value,
                        current_value / baseline_value) AS factor
        FROM anomaly_alerts {where} AND current_value {{op}} baseline_value
        ORDER BY factor DESC LIMIT :n
    """
    with engine.connect() as conn:
        total = conn.execute(text(
            f"SELECT COUNT(*) FROM anomaly_alerts {where}"), rng).scalar() or 0
        p = {**rng, "n": each}
        up = conn.execute(text(sql.format(op="<")), p).mappings().all()
        down = conn.execute(text(sql.format(op=">")), p).mappings().all()
    return total, up, down


def _fmt_factor(f: float) -> str:
    """名次变动倍数。小倍数必须保留一位小数:1.3 舍成 '1倍' 中文读作'翻倍',
    但实际几乎没动,会误导。"""
    f = float(f)
    return f"{f:,.0f}×" if f >= 10 else f"{f:.1f}×"


def _compose(period: str, summary: dict, charts: list) -> tuple:
    label = PERIOD_LABELS.get(period, period)
    rng = (summary["end_date"] if summary["start_date"] == summary["end_date"]
           else f"{summary['start_date']} ~ {summary['end_date']}")
    title = f"储能竞品{label} {summary['end_date']}"
    avg_note = "(期间日均)" if len(summary["dates"]) > 1 else ""

    prev = _prev_summary(period, summary)
    prev_by_brand = {b["brand"]: b for b in prev["brands"]} if prev else {}

    lines = [f"### {title}", f"> 数据范围: {rng}{'  ·  指标为期间日均' if avg_note else ''}"]
    if prev:
        lines.append(f"> 环比基准: {prev['start_date']} ~ {prev['end_date']}")
    lines.append("")

    # ---- 总览 ----
    t, pt = summary["totals"], (prev["totals"] if prev else {})
    lines += [
        f"**总营收**: {_fmt_money(t['revenue'])}"
        f"{_fmt_delta(t['revenue'], pt.get('revenue', 0))}",
        f"**总销量**: {t['sales']:,}{_fmt_delta(t['sales'], pt.get('sales', 0))}",
        "",
    ]

    # ---- 品牌榜:全部聚焦品牌,OUKITEL(我们的品牌)置顶 ----
    ranked = sorted(summary["brands"], key=lambda b: -b["avg_revenue"])
    rank_no = {b["brand"]: i + 1 for i, b in enumerate(ranked)}
    ordered = sorted(ranked, key=lambda b: (b["brand"].lower() != "oukitel",
                                            -b["avg_revenue"]))
    # 列数必须克制:手机上表格会横向溢出,列多了品牌名会被切掉。
    # 环比并进营收格、名次并进品牌格、数字全部缩写,压到 4 列。
    lines += [
        "📊 **品牌榜**",
        "| 品牌 | 营收 | 销量 | 均价/评分 |",
        "| --- | --- | --- | --- |",
    ]
    for b in ordered:
        name = canonical_brand(b["brand"])
        mine = "🔸" if b["brand"].lower() == "oukitel" else ""
        p = prev_by_brand.get(b["brand"], {})
        delta = _fmt_delta(b["avg_revenue"], p.get("avg_revenue", 0)).strip()
        price = f"${b['avg_price']:,.0f}" if b.get("avg_price") else "—"
        rating = f"{b['avg_rating']:.2f}" if b.get("avg_rating") else "—"
        lines.append(
            f"| {mine}**{rank_no[b['brand']]} {name}** "
            f"| {_fmt_money_short(b['avg_revenue'])} {delta} "
            f"| {_fmt_count_short(b['avg_sales'])} "
            f"| {price} / {rating} |")
    lines.append("")

    # 数据里缺席的聚焦品牌也要点名,免得"没数据"被当成"没卖"
    # build_summary 返回的已是 canonical 展示名,两边都归一到 canonical 再比,
    # 否则 'ef ecoflow'(FOCUS_BRANDS key) 对不上 'EcoFlow' 会误报缺失。
    present = {b["brand"].lower() for b in summary["brands"]}
    missing = [canonical_brand(k) for k in FOCUS_BRANDS
               if canonical_brand(k).lower() not in present]
    if missing:
        lines += [f"> 本周期无数据: {', '.join(missing)}", ""]

    # ---- 品类分布 ----
    cats = summary.get("categories") or []
    if cats:
        cat_total = sum(c["revenue"] for c in cats) or 1
        lines += [
            "🥧 **品类营收分布**",
            "| 品类 | 营收 | 占比 |",
            "| --- | --- | --- |",
        ]
        for c in cats[:6]:
            lines.append(f"| {c['sub_category']} | {_fmt_money_short(c['revenue'])} "
                         f"| {c['revenue'] / cat_total * 100:.0f}% |")
        lines.append("")

    # ---- 异常提醒 ----
    total_anom, anomalies = _fetch_anomalies(summary["start_date"], summary["end_date"])
    if anomalies:
        lines += [
            f"⚠️ **异常提醒** (共 {total_anom} 条,按变动幅度取前 {len(anomalies)})",
            "| 品牌 · ASIN | 类型 | 变动 |",
            "| --- | --- | --- |",
        ]
        for a in anomalies:
            kind = _ANOMALY_LABELS.get(a["anomaly_type"], a["anomaly_type"])
            arrow = "↑" if a["direction"] == "up" else "↓"
            lines.append(
                f"| **{canonical_brand(a['brand'])}** {a['market']} {a['asin']} "
                f"| {kind} | {arrow}{abs(float(a['change_pct'])):.0f}% "
                f"({float(a['baseline_value']):,.0f}→{float(a['current_value']):,.0f}) |")
        lines.append("")

    # ---- BSR 名次异动:上升/下滑各取前 N,避免下滑霸榜 ----
    total_bsr, bsr_up, bsr_down = _fetch_bsr_anomalies(
        summary["start_date"], summary["end_date"])
    if bsr_up or bsr_down:
        lines += [
            f"🚀 **排名异动** (共 {total_bsr} 条,升/降各取前 {len(bsr_up)}/{len(bsr_down)})",
            "| 品牌 · ASIN | 榜单 | 名次变动 |",
            "| --- | --- | --- |",
        ]
        for a in list(bsr_up) + list(bsr_down):
            base, cur = float(a["baseline_value"]), float(a["current_value"])
            # 名次数字变小 = 排名上升 = 好事。箭头按名次好坏给,不按原始值涨跌
            arrow = "↑" if cur < base else "↓"
            board = "大类" if a["anomaly_type"] == "main_bsr" else "小类"
            lines.append(
                f"| **{canonical_brand(a['brand'])}** {a['market']} {a['asin']} "
                f"| {board} | {arrow}{_fmt_factor(a['factor'])} "
                f"({base:,.0f}→{cur:,.0f}) |")
        lines.append("")

    # ---- 图表 ----
    for c in charts:
        # 优先用 OSS 返回的公网 URL;没有则回落到本地地址(仅本机自测有意义)
        url = c.get("url") or f"{PUBLIC_BASE_URL}/static/report-charts/{c['file']}"
        lines.append(f"**{c['title']}**")
        lines.append(f"![{c['title']}]({url})")
        lines.append("")

    # ---- LLM 分析:三种周期各取自己那份 ----
    content = _fetch_llm_report(period, summary["end_date"])
    if content:
        if len(content) > _MAX_LLM_CHARS:
            content = content[:_MAX_LLM_CHARS] + "\n\n……(全文过长已截断)"
        # LLM 正文自带完整 markdown 结构(空行分段),保持原样不做硬换行处理
        lines += ["---", "🤖 **AI 分析**", "", content, ""]

    # 用 "  \n" 而非 "\n" 连接:markdown 里单个换行是软换行,会被渲染成空格,
    # 整份报告会挤成一大段。行尾两个空格才是硬换行(钉钉文档亦如此建议)。
    return title, "  \n".join(lines)


def push_report(period: str = "daily") -> dict:
    """构建数据 → 渲染图表 → 推送钉钉。返回结果字典(供手动触发接口展示)。"""
    if (not DINGTALK_WEBHOOK or not DINGTALK_SECRET
            or "填入" in DINGTALK_WEBHOOK or "填入" in DINGTALK_SECRET):
        msg = "未配置钉钉机器人(config/config.py 的 DINGTALK_WEBHOOK/DINGTALK_SECRET),跳过推送"
        logger.warning(msg)
        return {"skipped": msg}

    summary = build_summary(period)
    if not summary:
        msg = f"{period} 无数据,跳过推送"
        logger.warning(msg)
        return {"skipped": msg}

    charts = []
    if REPORT_EMBED_CHARTS:
        try:
            charts = render_report_charts(summary)
        except Exception:
            logger.exception("图表渲染失败,退化为纯文字推送")
        if charts:
            from backend.analysis.oss_upload import is_configured, upload_charts
            from backend.analysis.report_charts import CHART_DIR
            if is_configured():
                charts = upload_charts(charts, CHART_DIR)
            else:
                # 没配 OSS 就只能回落到 PUBLIC_BASE_URL,而它多半是内网地址、
                # 钉钉拉不到 —— 与其推一堆裂图,不如不推图。
                logger.warning("OSS 未配置,本次不嵌图(内网地址钉钉拉不到)")
                charts = []
    else:
        logger.info("REPORT_EMBED_CHARTS=0,本次纯文字推送")

    title, md = _compose(period, summary, charts)
    resp = send_markdown(title, md)
    logger.info("钉钉%s推送成功: %s", PERIOD_LABELS.get(period, period), resp)
    return {"ok": True, "title": title, "charts": [c["file"] for c in charts],
            "dingtalk": resp}
