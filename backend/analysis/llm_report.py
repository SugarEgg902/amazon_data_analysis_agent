# backend/analysis/llm_report.py
import logging
import re
from datetime import date, timedelta
from sqlalchemy import text
from openai import OpenAI
from backend.database import engine
from backend.constants import canonical_brand, focus_brand_sql_list
from backend.analysis.report_data import (PERIOD_DAYS, PERIOD_LABELS,
                                          merge_categories)
from config.config import LLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

_FOCUS = focus_brand_sql_list()

# 环比基准在提示词里的说法
_PREV_LABEL = {"daily": "前一日", "weekly": "上一周", "monthly": "上一月"}

_LATEX_SYMBOLS = {
    "rightarrow": "→", "to": "→", "longrightarrow": "→", "Rightarrow": "⇒",
    "leftarrow": "←", "uparrow": "↑", "downarrow": "↓",
    "times": "×", "cdot": "·", "div": "÷", "pm": "±",
    "approx": "≈", "sim": "≈", "neq": "≠", "geq": "≥", "ge": "≥",
    "leq": "≤", "le": "≤", "infty": "∞", "alpha": "α", "beta": "β",
}
# 只匹配 "$\命令$" 这种明确的 LaTeX 行内公式。
# 绝不能笼统地剥 $...$:报告正文里的金额也是 $ 开头($482,135),
# 一刀切会把两个金额之间的内容当成公式吃掉。
_LATEX_CMD = re.compile(r"\$\s*\\([a-zA-Z]+)\s*\$")


def _strip_latex(content: str) -> str:
    """本地 Gemma 会吐 LaTeX(如 $\\rightarrow$),钉钉 markdown 和前端都不渲染,
    会原样显示。已知符号换成 Unicode 字符,未知的去掉 $\\ 包裹保留词本身。"""
    return _LATEX_CMD.sub(
        lambda m: _LATEX_SYMBOLS.get(m.group(1), m.group(1)), content)


def _fetch_brand_rows(conn, start, end):
    # 储能口径:读 daily_overview_summary(仅储能品类聚合,与 Overview 页一致)。
    # 必须 GROUP BY LOWER(brand):表里同一品牌存在多种大小写(历史 'Anker'/今日 'anker'),
    # 不归一会把一个品牌拆成两行、指标翻倍。
    # 周期>1 天时各指标取期间日均(AVG),与 build_summary / 钉钉报告同口径。
    return conn.execute(text(f"""
        SELECT LOWER(brand) AS brand,
               MAX(markets) AS markets,
               ROUND(AVG(product_count)) AS product_count,
               AVG(total_revenue) AS total_revenue,
               AVG(total_monthly_sales) AS total_monthly_sales,
               AVG(avg_price) AS avg_price,
               AVG(avg_rating) AS avg_rating,
               AVG(avg_growth_rate) AS avg_growth_rate,
               AVG(fba_ratio) AS fba_ratio
        FROM daily_overview_summary
        WHERE data_date BETWEEN :s AND :e AND LOWER(brand) IN ({_FOCUS})
        GROUP BY LOWER(brand)
        ORDER BY total_revenue DESC
    """), {"s": start, "e": end}).mappings().all()


def _fetch_categories(conn, start, end):
    """品类营收(期间日均)。本地化名称归一后合并,否则同一品类会被拆成多行。"""
    rows = conn.execute(text("""
        SELECT sub_category, data_date, SUM(revenue) AS revenue
        FROM daily_overview_category
        WHERE data_date BETWEEN :s AND :e
        GROUP BY sub_category, data_date
    """), {"s": start, "e": end}).mappings().all()
    return merge_categories(rows, limit=10)


def _build_prompt(period, cur_rows, prev_rows, cat_rows, cur_rng, prev_rng):
    label = PERIOD_LABELS.get(period, period)
    prev_label = _PREV_LABEL.get(period, "上一周期")
    multi_day = period != "daily"
    avg_note = "（以下各项为期间日均）" if multi_day else ""

    def fmt(rows):
        return "\n".join(
            f"- {canonical_brand(r['brand'])}（覆盖站点 {r['markets']}）: "
            f"商品{r['product_count']} 总营收{r['total_revenue']} "
            f"总月销{r['total_monthly_sales']} 均价{r['avg_price']} 评分{r['avg_rating']} "
            f"增长{r['avg_growth_rate']} FBA占比{r['fba_ratio']}"
            for r in rows) or "（无数据）"
    cat = "\n".join(
        f"- {r['sub_category']}: 营收{r['revenue']}" for r in cat_rows
    ) or "（无数据）"

    trend_hint = ""
    if multi_day:
        trend_hint = (f"\n注意：本报告是{label}，请着眼于整个周期内的趋势与结构性变化，"
                      f"不要写成单日快照，也不要逐日罗列。")

    return f"""你是一位亚马逊电商数据分析师，请根据以下数据生成一份中文{label}。
数据范围：{cur_rng}。{avg_note}
本报告聚焦储能电源赛道，覆盖 OUKITEL、EcoFlow、Bluetti、Jackery、VTOMAN、Anker 六个品牌（OUKITEL 为自有品牌），所有站点数据已合并统计（非分站点）。核心品类为便携储能电源、太阳能板（光伏）、相关配件。{trend_hint}

## 一、品牌表现（六品牌全站点汇总）
{fmt(cur_rows)}

## 二、环比对比（{prev_label}同口径数据，{prev_rng}）
{fmt(prev_rows)}

## 三、热门品类（六品牌全站点按营收）
{cat}

请用 Markdown 输出，包含三部分：品牌整体表现、竞品对比（指出六品牌中增长最快/最慢的及原因）、选品建议（增长品类与机会点）。包含标题、要点列表和简要结论。

要求：
- 不要包含毛利率相关数据。
- 不要使用 LaTeX 数学公式语法（如 $\\rightarrow$、$\\times$）。需要箭头就直接写 → ，需要乘号就直接写 ×。渲染端不支持 LaTeX，写了会原样显示出来。"""


def _range(end: date, days: int) -> tuple:
    """周期的 (起始日, 结束日)。days=1 时起止同日。"""
    return end - timedelta(days=days - 1), end


def run_llm_analysis(target_date: date, period: str = "daily") -> None:
    days = PERIOD_DAYS.get(period, 1)
    start, end = _range(target_date, days)
    prev_start, prev_end = _range(start - timedelta(days=1), days)

    with engine.connect() as conn:
        cur_rows = _fetch_brand_rows(conn, start, end)
        if not cur_rows:
            logger.warning("no brand summary for %s %s~%s, skip LLM report",
                           period, start, end)
            return
        prev_rows = _fetch_brand_rows(conn, prev_start, prev_end)
        cat_rows = _fetch_categories(conn, start, end)

    def _rng(s, e):
        return str(e) if s == e else f"{s} ~ {e}"

    prompt = _build_prompt(period, cur_rows, prev_rows, cat_rows,
                           _rng(start, end), _rng(prev_start, prev_end))
    client = OpenAI(base_url=LLM_BASE_URL, api_key="none")
    content, err = "", None
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL, temperature=0.3, max_tokens=4096, timeout=120,
                messages=[{"role": "user", "content": prompt}],
            )
            content = _strip_latex((resp.choices[0].message.content or "").strip())
            if content:
                break
        except Exception as e:  # noqa
            err = str(e)
            logger.exception("LLM call failed (attempt %d)", attempt + 1)
    status = "success" if content else "failed"

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO daily_analysis_reports
                (report_date, period, content, model, generated_at, status, error_message)
            VALUES (:d, :p, :c, :m, NOW(), :s, :e)
            ON DUPLICATE KEY UPDATE content=VALUES(content), model=VALUES(model),
                generated_at=VALUES(generated_at), status=VALUES(status),
                error_message=VALUES(error_message)
        """), {"d": target_date, "p": period, "c": content, "m": LLM_MODEL,
               "s": status, "e": None if content else (err or "empty response")})
    logger.info("llm_report %s %s: %s", period, target_date, status)
