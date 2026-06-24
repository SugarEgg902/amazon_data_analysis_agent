# backend/analysis/llm_report.py
import os
import logging
from datetime import date, timedelta
from sqlalchemy import text
from openai import OpenAI
from backend.database import engine
from backend.constants import focus_brand_sql_list

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("ANALYSIS_LLM_BASE_URL", "http://10.0.0.22:8005/v1")
LLM_MODEL = os.getenv("ANALYSIS_LLM_MODEL", "gemma-4-31b-it-fp8")

_FOCUS = focus_brand_sql_list()


def _fetch_brand_rows(conn, d):
    # 仅 5 个聚焦品牌,跨所有站点合并为每品牌一行(不再按 market 拆分)
    return conn.execute(text(f"""
        SELECT brand,
               GROUP_CONCAT(DISTINCT market ORDER BY market) AS markets,
               SUM(product_count) AS product_count,
               SUM(total_revenue) AS total_revenue,
               SUM(total_monthly_sales) AS total_monthly_sales,
               AVG(avg_price) AS avg_price,
               AVG(avg_rating) AS avg_rating,
               AVG(avg_growth_rate) AS avg_growth_rate,
               AVG(avg_gross_margin) AS avg_gross_margin,
               AVG(fba_ratio) AS fba_ratio
        FROM daily_brand_summary
        WHERE data_date = :d AND LOWER(brand) IN ({_FOCUS})
        GROUP BY brand
        ORDER BY total_revenue DESC
    """), {"d": d}).mappings().all()


def _build_prompt(today_rows, prev_rows, cat_rows, d):
    def fmt(rows):
        return "\n".join(
            f"- {r['brand']}（覆盖站点 {r['markets']}）: 商品{r['product_count']} 总营收{r['total_revenue']} "
            f"总月销{r['total_monthly_sales']} 均价{r['avg_price']} 评分{r['avg_rating']} "
            f"增长{r['avg_growth_rate']} FBA占比{r['fba_ratio']}"
            for r in rows) or "（无数据）"
    cat = "\n".join(
        f"- {r['sub_category']}: 营收{r['revenue']}" for r in cat_rows
    ) or "（无数据）"
    return f"""你是一位亚马逊电商数据分析师，请根据以下 {d} 的数据生成一份中文日报。
本报告聚焦 Blackview、Ulefone、CUBOT、OUKITEL、DOOGEE 五个品牌，所有站点数据已合并统计（非分站点）。

## 一、品牌表现（五品牌全站点汇总）
{fmt(today_rows)}

## 二、环比对比（前一日同口径数据）
{fmt(prev_rows)}

## 三、热门品类（五品牌全站点按营收）
{cat}

请用 Markdown 输出，包含三部分：品牌整体表现、竞品对比（指出五品牌中增长最快/最慢的及原因）、选品建议（增长品类与机会点）。包含标题、要点列表和简要结论。注意：不要包含毛利率相关数据。"""


def run_llm_analysis(target_date: date) -> None:
    prev = target_date - timedelta(days=1)
    with engine.connect() as conn:
        today_rows = _fetch_brand_rows(conn, target_date)
        if not today_rows:
            logger.warning("no brand summary for %s, skip LLM report", target_date)
            return
        prev_rows = _fetch_brand_rows(conn, prev)
        cat_rows = conn.execute(text(f"""
            SELECT sub_category, SUM(total_revenue) AS revenue
            FROM daily_category_summary
            WHERE data_date = :d AND LOWER(brand) IN ({_FOCUS})
            GROUP BY sub_category ORDER BY revenue DESC LIMIT 20
        """), {"d": target_date}).mappings().all()

    prompt = _build_prompt(today_rows, prev_rows, cat_rows, target_date)
    client = OpenAI(base_url=LLM_BASE_URL, api_key="none")
    content, err = "", None
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL, temperature=0.3, max_tokens=4096, timeout=120,
                messages=[{"role": "user", "content": prompt}],
            )
            content = (resp.choices[0].message.content or "").strip()
            if content:
                break
        except Exception as e:  # noqa
            err = str(e)
            logger.exception("LLM call failed (attempt %d)", attempt + 1)
    status = "success" if content else "failed"

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO daily_analysis_reports
                (report_date, content, model, generated_at, status, error_message)
            VALUES (:d, :c, :m, NOW(), :s, :e)
            ON DUPLICATE KEY UPDATE content=VALUES(content), model=VALUES(model),
                generated_at=VALUES(generated_at), status=VALUES(status),
                error_message=VALUES(error_message)
        """), {"d": target_date, "c": content, "m": LLM_MODEL,
               "s": status, "e": None if content else (err or "empty response")})
