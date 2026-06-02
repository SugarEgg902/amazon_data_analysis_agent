# backend/analysis/sales_analyzer.py
import os
import io
import logging
import pandas as pd
from sqlalchemy import text
from openai import OpenAI
from backend.database import engine

logger = logging.getLogger(__name__)

SALES_LLM_BASE_URL = os.getenv("SALES_LLM_BASE_URL", "http://10.0.0.21:8000/v1")
SALES_LLM_MODEL = os.getenv("SALES_LLM_MODEL", "qwen3.6-35b-a3b-fp8")


def _classify_columns(df: pd.DataFrame):
    date_cols, numeric_cols, cat_cols = [], [], []
    n = len(df)
    for col in df.columns:
        s = df[col]
        if pd.api.types.is_numeric_dtype(s):
            numeric_cols.append(col)
            continue
        parsed = pd.to_datetime(s, errors="coerce")
        if parsed.notna().mean() > 0.8:
            date_cols.append(col)
            continue
        nunique = s.nunique(dropna=True)
        if nunique < 50 and nunique < n:   # 低基数 → 分类列；近似唯一 → ID 列（丢弃）
            cat_cols.append(col)
    return date_cols, numeric_cols, cat_cols


def _build_summary(df, date_cols, numeric_cols, cat_cols):
    parts = [f"## 数据概览\n行数: {len(df)}, 列数: {len(df.columns)}",
             f"数值列: {numeric_cols}", f"分类列: {cat_cols}", f"日期列: {date_cols}"]

    if numeric_cols:
        top = df[numeric_cols].sum(numeric_only=True).abs().sort_values(ascending=False).head(3).index.tolist()
        if date_cols:
            d = date_cols[0]
            tmp = df.copy()
            tmp[d] = pd.to_datetime(tmp[d], errors="coerce")
            monthly = tmp.dropna(subset=[d]).groupby(tmp[d].dt.to_period("M"))[top].sum()
            parts.append("## 时间趋势（按月汇总 top 数值列）\n" + monthly.to_string())

    dist = []
    for c in numeric_cols:
        q = df[c].quantile([0, .25, .5, .75, 1]).tolist()
        dist.append(f"- {c}: min={q[0]:.2f} p25={q[1]:.2f} med={q[2]:.2f} p75={q[3]:.2f} max={q[4]:.2f}")
    if dist:
        parts.append("## 数值分布\n" + "\n".join(dist))

    for cc in cat_cols:
        for nc in numeric_cols[:3]:
            top10 = df.groupby(cc)[nc].sum().sort_values(ascending=False).head(10)
            parts.append(f"## {cc} × {nc} Top10\n" + top10.to_string())

    return "\n\n".join(parts)


def run_sales_analysis(file_bytes: bytes, filename: str) -> dict:
    ext = filename.lower().rsplit(".", 1)[-1]
    if ext == "csv":
        df = pd.read_csv(io.BytesIO(file_bytes))
    elif ext in ("xlsx", "xls"):
        df = pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise ValueError(f"unsupported format: {ext}")

    date_cols, numeric_cols, cat_cols = _classify_columns(df)
    if not numeric_cols:
        raise ValueError("no_numeric_columns")

    summary = _build_summary(df, date_cols, numeric_cols, cat_cols)
    prompt = (f"你是亚马逊销售数据分析师。基于以下统计摘要生成中文 Markdown 报告，"
              f"分节：数据概览、时间趋势、价格/数值分布、分类排名、增长亮点与风险、综合建议。\n\n{summary}")

    content, status, err = "", "success", None
    try:
        client = OpenAI(base_url=SALES_LLM_BASE_URL, api_key="none")
        resp = client.chat.completions.create(
            model=SALES_LLM_MODEL, temperature=0.3, max_tokens=4096, timeout=120,
            messages=[{"role": "user", "content": prompt}], stream=False,
        )
        content = (resp.choices[0].message.content or "").strip()
        if not content:
            status, err = "failed", "empty response"
    except Exception as e:  # noqa
        status, err = "failed", str(e)
        logger.exception("sales LLM failed")

    with engine.begin() as conn:
        result = conn.execute(text("""
            INSERT INTO sales_analysis_reports
                (filename, row_count, report_date, content, model, status, error_message)
            VALUES (:f, :n, NOW(), :c, :m, :s, :e)
        """), {"f": filename, "n": len(df), "c": content,
               "m": SALES_LLM_MODEL, "s": status, "e": err})
        new_id = result.lastrowid

    return {"id": new_id, "content": content, "row_count": len(df), "status": status}
