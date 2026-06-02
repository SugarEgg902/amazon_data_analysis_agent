# Sales Analysis Feature Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a sales data analysis page where users upload CSV/Excel files, pandas computes statistical summaries, and a local LLM generates a structured Markdown report saved to the database.

**Architecture:** Server-side preprocessing with pandas (column auto-detection, time trends, price distribution, category rankings, growth rates) feeds a compact summary to `qwen3.6-35b-a3b-fp8` via OpenAI-compatible API. Reports are persisted in `sales_analysis_reports` table and browsable via a history panel.

**Tech Stack:** FastAPI, pandas, openpyxl, openai SDK, React 18, TypeScript, Ant Design v6, react-markdown, @tanstack/react-query

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `db/migrations/004_create_sales_analysis_reports_table.sql` | Create | DB schema |
| `backend/analysis/sales_analyzer.py` | Create | pandas preprocessing + LLM call + DB write |
| `backend/routers/sales_analysis.py` | Create | FastAPI endpoints |
| `backend/main.py` | Modify | Register new router |
| `backend/tests/test_sales_analyzer.py` | Create | Unit tests for column classification and summaries |
| `backend/tests/test_sales_analysis_router.py` | Create | Integration tests for upload/history/detail endpoints |
| `frontend/src/api/salesAnalysis.ts` | Create | API client functions |
| `frontend/src/pages/SalesAnalysis.tsx` | Create | Upload + report display + history table |
| `frontend/src/components/Layout.tsx` | Modify | Add sidebar menu entry |
| `frontend/src/App.tsx` | Modify | Add route |

---

## Task 1: Database Migration


**Files:**
- Create: `db/migrations/004_create_sales_analysis_reports_table.sql`

- [ ] **Step 1: Create the migration file**

```sql
-- db/migrations/004_create_sales_analysis_reports_table.sql
CREATE TABLE IF NOT EXISTS sales_analysis_reports (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    filename      VARCHAR(255) NOT NULL,
    row_count     INT NOT NULL,
    report_date   DATETIME NOT NULL,
    content       MEDIUMTEXT,
    model         VARCHAR(100) NOT NULL,
    status        ENUM('success', 'failed') NOT NULL DEFAULT 'success',
    error_message TEXT,
    created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at)
);
```

- [ ] **Step 2: Apply the migration**

```bash
mysql -u root mercadolibre < db/migrations/004_create_sales_analysis_reports_table.sql
```

Expected: no error output.

- [ ] **Step 3: Verify table exists**

```bash
mysql -u root mercadolibre -e "DESCRIBE sales_analysis_reports;"
```

Expected: shows all 9 columns.

- [ ] **Step 4: Commit**

```bash
git add db/migrations/004_create_sales_analysis_reports_table.sql
git commit -m "feat: add sales_analysis_reports table migration"
```

---

## Task 2: Column Classifier and Summary Engine (TDD)

**Files:**
- Create: `backend/analysis/sales_analyzer.py`
- Create: `backend/tests/test_sales_analyzer.py`

This task covers only the pandas logic — no LLM, no DB. The LLM call and DB write are added in Task 3.

- [ ] **Step 1: Write failing tests for column classification**

Create `backend/tests/test_sales_analyzer.py`:

```python
# backend/tests/test_sales_analyzer.py
import pandas as pd
import pytest
from backend.analysis.sales_analyzer import classify_columns, compute_summary


def _make_df():
    return pd.DataFrame({
        "date": pd.to_datetime(["2026-01-01", "2026-02-01", "2026-03-01"]),
        "brand": ["Blackview", "Cubot", "Blackview"],
        "product_id": ["P001", "P002", "P003"],  # high-cardinality → ID col
        "sales": [100, 200, 150],
        "price": [50.0, 60.0, 55.0],
    })


def test_classify_columns_detects_date():
    df = _make_df()
    result = classify_columns(df)
    assert "date" in result["date_cols"]


def test_classify_columns_detects_numeric():
    df = _make_df()
    result = classify_columns(df)
    assert "sales" in result["numeric_cols"]
    assert "price" in result["numeric_cols"]


def test_classify_columns_detects_categorical():
    df = _make_df()
    result = classify_columns(df)
    assert "brand" in result["categorical_cols"]


def test_classify_columns_excludes_id_col():
    df = _make_df()
    result = classify_columns(df)
    assert "product_id" not in result["categorical_cols"]
    assert "product_id" not in result["numeric_cols"]


def test_compute_summary_returns_string():
    df = _make_df()
    cols = classify_columns(df)
    summary = compute_summary(df, cols)
    assert isinstance(summary, str)
    assert len(summary) > 0


def test_compute_summary_contains_numeric_stats():
    df = _make_df()
    cols = classify_columns(df)
    summary = compute_summary(df, cols)
    assert "sales" in summary
    assert "price" in summary


def test_compute_summary_contains_category_ranking():
    df = _make_df()
    cols = classify_columns(df)
    summary = compute_summary(df, cols)
    assert "Blackview" in summary


def test_compute_summary_no_date_col():
    df = pd.DataFrame({"brand": ["A", "B"], "sales": [10, 20]})
    cols = classify_columns(df)
    summary = compute_summary(df, cols)
    assert "sales" in summary
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest backend/tests/test_sales_analyzer.py -v
```

Expected: `ImportError` or `ModuleNotFoundError` — `sales_analyzer` does not exist yet.

- [ ] **Step 3: Implement `classify_columns` and `compute_summary`**

Create `backend/analysis/sales_analyzer.py`:

```python
# backend/analysis/sales_analyzer.py
import os
import io
import logging
from datetime import datetime
from typing import Optional
import pandas as pd
from openai import OpenAI
from sqlalchemy import text
from backend.database import engine

logger = logging.getLogger(__name__)

SALES_LLM_BASE_URL = os.getenv("SALES_LLM_BASE_URL", "http://10.0.0.21:8000/v1")
SALES_LLM_MODEL = os.getenv("SALES_LLM_MODEL", "qwen3.6-35b-a3b-fp8")


def classify_columns(df: pd.DataFrame) -> dict:
    date_cols, numeric_cols, categorical_cols = [], [], []
    n = len(df)
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
        elif pd.api.types.is_numeric_dtype(df[col]):
            numeric_cols.append(col)
        elif df[col].dtype == object:
            unique_ratio = df[col].nunique() / max(n, 1)
            if df[col].nunique() < 50 and unique_ratio < 0.8:
                categorical_cols.append(col)
    return {"date_cols": date_cols, "numeric_cols": numeric_cols, "categorical_cols": categorical_cols}


def compute_summary(df: pd.DataFrame, cols: dict) -> str:
    lines = [f"## 数据概览\n行数: {len(df)}，列数: {len(df.columns)}"]
    lines.append(f"列名: {', '.join(df.columns.tolist())}\n")

    # Numeric distribution
    if cols["numeric_cols"]:
        lines.append("## 数值列统计分布")
        for col in cols["numeric_cols"]:
            s = df[col].dropna()
            lines.append(
                f"- {col}: min={s.min():.2f}, p25={s.quantile(0.25):.2f}, "
                f"median={s.median():.2f}, p75={s.quantile(0.75):.2f}, "
                f"max={s.max():.2f}, sum={s.sum():.2f}"
            )

    # Time trend (top 3 numeric cols by total sum)
    if cols["date_cols"] and cols["numeric_cols"]:
        date_col = cols["date_cols"][0]
        top_num = sorted(cols["numeric_cols"], key=lambda c: df[c].sum(), reverse=True)[:3]
        lines.append(f"\n## 时间趋势（按月聚合，日期列: {date_col}）")
        try:
            tmp = df.copy()
            tmp[date_col] = pd.to_datetime(tmp[date_col], errors="coerce")
            tmp = tmp.dropna(subset=[date_col])
            tmp = tmp.set_index(date_col)
            monthly = tmp[top_num].resample("ME").sum()
            lines.append(monthly.to_string())

            # Growth rate: first vs last period
            lines.append("\n## 增长率（首期 vs 末期）")
            for col in top_num:
                first = monthly[col].iloc[0] if len(monthly) > 0 else 0
                last = monthly[col].iloc[-1] if len(monthly) > 0 else 0
                if first and first != 0:
                    growth = (last - first) / abs(first) * 100
                    lines.append(f"- {col}: {first:.2f} → {last:.2f}（{growth:+.1f}%）")
        except Exception as e:
            lines.append(f"（时间趋势计算失败: {e}）")

    # Category rankings
    if cols["categorical_cols"] and cols["numeric_cols"]:
        lines.append("\n## 分类排名（Top 10）")
        for cat in cols["categorical_cols"]:
            for num in cols["numeric_cols"][:3]:
                ranking = df.groupby(cat)[num].sum().nlargest(10)
                lines.append(f"\n### {cat} × {num}")
                lines.append(ranking.to_string())

    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest backend/tests/test_sales_analyzer.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/sales_analyzer.py backend/tests/test_sales_analyzer.py
git commit -m "feat: add sales_analyzer column classifier and summary engine"
```

---

## Task 3: LLM Call and DB Persistence (TDD)

**Files:**
- Modify: `backend/analysis/sales_analyzer.py` (add `_build_prompt`, `run_sales_analysis`)
- Modify: `backend/tests/test_sales_analyzer.py` (add LLM + DB tests)

- [ ] **Step 1: Add failing tests for `run_sales_analysis`**

Append to `backend/tests/test_sales_analyzer.py`:

```python
import csv
from unittest.mock import patch, MagicMock
from sqlalchemy import text
from backend.database import engine


def _make_csv_bytes() -> bytes:
    rows = [["date", "brand", "sales", "price"]]
    for i in range(5):
        rows.append([f"2026-0{i+1}-01", "Blackview", str(100 + i * 10), str(50.0 + i)])
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    return buf.getvalue().encode()


def test_run_sales_analysis_returns_success():
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "## 分析报告\n测试内容"
    with patch("backend.analysis.sales_analyzer.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = mock_resp
        result = run_sales_analysis(_make_csv_bytes(), "test.csv")
    assert result["status"] == "success"
    assert "分析报告" in result["content"]
    assert result["row_count"] == 5
    # cleanup
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM sales_analysis_reports WHERE id = :id"), {"id": result["id"]})
        conn.commit()


def test_run_sales_analysis_saves_to_db():
    mock_resp = MagicMock()
    mock_resp.choices[0].message.content = "## 报告内容"
    with patch("backend.analysis.sales_analyzer.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.return_value = mock_resp
        result = run_sales_analysis(_make_csv_bytes(), "test.csv")
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id, filename, status FROM sales_analysis_reports WHERE id = :id"),
            {"id": result["id"]}
        ).mappings().first()
    assert row is not None
    assert row["filename"] == "test.csv"
    assert row["status"] == "success"
    # cleanup
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM sales_analysis_reports WHERE id = :id"), {"id": result["id"]})
        conn.commit()


def test_run_sales_analysis_handles_llm_failure():
    with patch("backend.analysis.sales_analyzer.OpenAI") as MockClient:
        MockClient.return_value.chat.completions.create.side_effect = Exception("LLM unreachable")
        result = run_sales_analysis(_make_csv_bytes(), "test.csv")
    assert result["status"] == "failed"
    assert result["content"] is None
    # cleanup
    with engine.connect() as conn:
        conn.execute(text("DELETE FROM sales_analysis_reports WHERE id = :id"), {"id": result["id"]})
        conn.commit()


def test_run_sales_analysis_rejects_unsupported_format():
    from backend.analysis.sales_analyzer import UnsupportedFileError
    with pytest.raises(UnsupportedFileError):
        run_sales_analysis(b"data", "file.txt")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest backend/tests/test_sales_analyzer.py::test_run_sales_analysis_returns_success -v
```

Expected: `ImportError` — `run_sales_analysis` not defined yet.

- [ ] **Step 3: Add `_build_prompt`, `UnsupportedFileError`, and `run_sales_analysis` to `sales_analyzer.py`**

Append to `backend/analysis/sales_analyzer.py` (after `compute_summary`):

```python
class UnsupportedFileError(ValueError):
    pass


def _read_file(file_bytes: bytes, filename: str) -> pd.DataFrame:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext == "csv":
        return pd.read_csv(io.BytesIO(file_bytes))
    elif ext in ("xlsx", "xls"):
        return pd.read_excel(io.BytesIO(file_bytes))
    else:
        raise UnsupportedFileError(f"不支持的文件格式: .{ext}，仅支持 .csv / .xlsx / .xls")


def _build_prompt(summary: str, filename: str, row_count: int) -> str:
    return f"""你是一位资深电商数据分析师。以下是用户上传的销售数据文件「{filename}」（共 {row_count} 行）的统计摘要。

{summary}

请根据以上统计数据，用中文生成一份结构化的销售数据分析报告，必须包含以下章节：

## 数据概览
简述数据规模、时间范围、主要维度。

## 销量与营收趋势
分析时间维度上的变化规律，指出高峰期和低谷期。

## 价格与数值分布
分析各数值指标的分布特征，指出异常值或值得关注的区间。

## 品类/品牌排名分析
指出表现最好和最差的分类，分析原因。

## 增长亮点与风险
列出增长最快的维度和下滑最明显的维度。

## 综合建议
给出 3-5 条可操作的业务建议。

报告要求：数据驱动，引用具体数字，语言简洁专业。"""


def run_sales_analysis(file_bytes: bytes, filename: str) -> dict:
    df = _read_file(file_bytes, filename)
    row_count = len(df)
    cols = classify_columns(df)
    if not cols["numeric_cols"]:
        raise ValueError("未检测到数值列，无法生成分析")
    summary = compute_summary(df, cols)
    prompt = _build_prompt(summary, filename, row_count)

    content: Optional[str] = None
    error_message: Optional[str] = None
    status = "success"

    try:
        client = OpenAI(base_url=SALES_LLM_BASE_URL, api_key="none")
        resp = client.chat.completions.create(
            model=SALES_LLM_MODEL,
            messages=[{"role": "user", "content": prompt}],
            stream=False,
        )
        content = resp.choices[0].message.content
    except Exception as e:
        logger.error("Sales LLM call failed: %s", e)
        status = "failed"
        error_message = str(e)

    now = datetime.now()
    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO sales_analysis_reports
                (filename, row_count, report_date, content, model, status, error_message, created_at)
            VALUES
                (:filename, :row_count, :report_date, :content, :model, :status, :error_message, :created_at)
        """), {
            "filename": filename,
            "row_count": row_count,
            "report_date": now,
            "content": content,
            "model": SALES_LLM_MODEL,
            "status": status,
            "error_message": error_message,
            "created_at": now,
        })
        conn.commit()
        inserted_id = result.lastrowid

    return {"id": inserted_id, "content": content, "row_count": row_count, "status": status}
```

- [ ] **Step 4: Run all sales_analyzer tests**

```bash
python -m pytest backend/tests/test_sales_analyzer.py -v
```

Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/sales_analyzer.py backend/tests/test_sales_analyzer.py
git commit -m "feat: add run_sales_analysis with LLM call and DB persistence"
```

---

## Task 4: FastAPI Router (TDD)

**Files:**
- Create: `backend/routers/sales_analysis.py`
- Create: `backend/tests/test_sales_analysis_router.py`
- Modify: `backend/main.py`

- [ ] **Step 1: Write failing router tests**

Create `backend/tests/test_sales_analysis_router.py`:

```python
# backend/tests/test_sales_analysis_router.py
import io
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

MOCK_RESULT = {
    "id": 99,
    "content": "## 分析报告\n测试",
    "row_count": 100,
    "status": "success",
}

CSV_BYTES = b"date,brand,sales\n2026-01-01,Blackview,100\n2026-02-01,Cubot,200\n"


def test_upload_returns_report():
    with patch("backend.routers.sales_analysis.run_sales_analysis", return_value=MOCK_RESULT):
        resp = client.post(
            "/api/sales-analysis/upload",
            files={"file": ("test.csv", io.BytesIO(CSV_BYTES), "text/csv")},
        )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["id"] == 99
    assert data["status"] == "success"
    assert data["filename"] == "test.csv"


def test_upload_rejects_unsupported_format():
    with patch("backend.routers.sales_analysis.run_sales_analysis") as mock_fn:
        from backend.analysis.sales_analyzer import UnsupportedFileError
        mock_fn.side_effect = UnsupportedFileError("不支持的格式")
        resp = client.post(
            "/api/sales-analysis/upload",
            files={"file": ("data.txt", io.BytesIO(b"hello"), "text/plain")},
        )
    assert resp.status_code == 400


def test_upload_rejects_no_numeric_columns():
    with patch("backend.routers.sales_analysis.run_sales_analysis") as mock_fn:
        mock_fn.side_effect = ValueError("未检测到数值列，无法生成分析")
        resp = client.post(
            "/api/sales-analysis/upload",
            files={"file": ("test.csv", io.BytesIO(CSV_BYTES), "text/csv")},
        )
    assert resp.status_code == 422


def test_history_returns_list():
    mock_items = [{"id": 1, "filename": "a.csv", "row_count": 50,
                   "report_date": "2026-05-27T10:00:00", "status": "success"}]
    with patch("backend.routers.sales_analysis._fetch_history", return_value={"items": mock_items, "total": 1}):
        resp = client.get("/api/sales-analysis/history")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["total"] == 1
    assert data["items"][0]["filename"] == "a.csv"


def test_get_report_returns_content():
    mock_report = {"id": 1, "filename": "a.csv", "row_count": 50,
                   "report_date": "2026-05-27T10:00:00", "content": "## 报告",
                   "model": "qwen3", "status": "success", "error_message": None}
    with patch("backend.routers.sales_analysis._fetch_report_by_id", return_value=mock_report):
        resp = client.get("/api/sales-analysis/reports/1")
    assert resp.status_code == 200
    assert resp.json()["data"]["content"] == "## 报告"


def test_get_report_404_for_missing():
    with patch("backend.routers.sales_analysis._fetch_report_by_id", return_value=None):
        resp = client.get("/api/sales-analysis/reports/9999")
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest backend/tests/test_sales_analysis_router.py -v
```

Expected: `ImportError` — router not registered yet.

- [ ] **Step 3: Create the router**

Create `backend/routers/sales_analysis.py`:

```python
# backend/routers/sales_analysis.py
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from sqlalchemy import text
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.analysis.sales_analyzer import run_sales_analysis, UnsupportedFileError

router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB


def _fetch_history(page: int, size: int) -> dict:
    offset = (page - 1) * size
    with engine.connect() as conn:
        total = conn.execute(text("SELECT COUNT(*) FROM sales_analysis_reports")).scalar()
        rows = conn.execute(text("""
            SELECT id, filename, row_count, report_date, status
            FROM sales_analysis_reports
            ORDER BY created_at DESC
            LIMIT :size OFFSET :offset
        """), {"size": size, "offset": offset}).mappings().all()
    return {
        "items": [
            {
                "id": r["id"],
                "filename": r["filename"],
                "row_count": r["row_count"],
                "report_date": str(r["report_date"]),
                "status": r["status"],
            }
            for r in rows
        ],
        "total": total,
    }


def _fetch_report_by_id(report_id: int):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, filename, row_count, report_date, content, model, status, error_message
            FROM sales_analysis_reports WHERE id = :id
        """), {"id": report_id}).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "filename": row["filename"],
        "row_count": row["row_count"],
        "report_date": str(row["report_date"]),
        "content": row["content"],
        "model": row["model"],
        "status": row["status"],
        "error_message": row["error_message"],
    }


@router.post("/sales-analysis/upload", response_model=ApiResponse)
async def upload_and_analyze(file: UploadFile = File(...)):
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="文件超过 20MB 限制")
    try:
        result = run_sales_analysis(file_bytes, file.filename or "upload")
    except UnsupportedFileError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return ApiResponse(data={**result, "filename": file.filename})


@router.get("/sales-analysis/history", response_model=ApiResponse)
def get_history(page: int = Query(default=1, ge=1), size: int = Query(default=20, ge=1, le=100)):
    return ApiResponse(data=_fetch_history(page, size))


@router.get("/sales-analysis/reports/{report_id}", response_model=ApiResponse)
def get_report(report_id: int):
    report = _fetch_report_by_id(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="报告不存在")
    return ApiResponse(data=report)
```

- [ ] **Step 4: Register router in `main.py`**

In `backend/main.py`, change:

```python
from backend.routers import overview, brands, products, compare, trends, meta, reports, anomalies
```

to:

```python
from backend.routers import overview, brands, products, compare, trends, meta, reports, anomalies, sales_analysis
```

And add after `app.include_router(anomalies.router, prefix="/api")`:

```python
app.include_router(sales_analysis.router, prefix="/api")
```

- [ ] **Step 5: Run all router tests**

```bash
python -m pytest backend/tests/test_sales_analysis_router.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 6: Run full test suite to check for regressions**

```bash
python -m pytest backend/tests/ -v
```

Expected: all tests PASS (previously 27, now 33).

- [ ] **Step 7: Commit**

```bash
git add backend/routers/sales_analysis.py backend/tests/test_sales_analysis_router.py backend/main.py
git commit -m "feat: add sales analysis router with upload/history/detail endpoints"
```

---

## Task 5: Frontend API Client

**Files:**
- Create: `frontend/src/api/salesAnalysis.ts`

- [ ] **Step 1: Create the API client**

Create `frontend/src/api/salesAnalysis.ts`:

```typescript
// frontend/src/api/salesAnalysis.ts
import { api, unwrap } from './client'

export interface SalesReport {
  id: number
  filename: string
  row_count: number
  report_date: string
  content?: string
  model?: string
  status: 'success' | 'failed'
  error_message?: string
}

export interface HistoryResponse {
  items: SalesReport[]
  total: number
}

export function uploadAndAnalyze(file: File): Promise<SalesReport> {
  const form = new FormData()
  form.append('file', file)
  return unwrap<SalesReport>(
    api.post('/sales-analysis/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  )
}

export function fetchHistory(page = 1, size = 20): Promise<HistoryResponse> {
  return unwrap<HistoryResponse>(
    api.get('/sales-analysis/history', { params: { page, size } })
  )
}

export function fetchReport(id: number): Promise<SalesReport> {
  return unwrap<SalesReport>(api.get(`/sales-analysis/reports/${id}`))
}
```

- [ ] **Step 2: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/api/salesAnalysis.ts
git commit -m "feat: add salesAnalysis API client"
```

---

## Task 6: Frontend Page

**Files:**
- Create: `frontend/src/pages/SalesAnalysis.tsx`
- Modify: `frontend/src/components/Layout.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Install react-markdown if not already present**

```bash
cd frontend && npm list react-markdown 2>/dev/null | grep react-markdown || npm install react-markdown@9
```

Expected: `react-markdown@9.x.x` listed.

- [ ] **Step 2: Create the page**

Create `frontend/src/pages/SalesAnalysis.tsx`:

```tsx
// frontend/src/pages/SalesAnalysis.tsx
import { useState } from 'react'
import { Upload, Table, Tag, Button, Spin, Alert, Typography, Space, message } from 'antd'
import { InboxOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import type { UploadFile } from 'antd'
import {
  uploadAndAnalyze,
  fetchHistory,
  fetchReport,
  type SalesReport,
} from '../api/salesAnalysis'

const { Dragger } = Upload
const { Text } = Typography

export default function SalesAnalysis() {
  const [analyzing, setAnalyzing] = useState(false)
  const [currentReport, setCurrentReport] = useState<SalesReport | null>(null)
  const [page, setPage] = useState(1)

  const { data: history, refetch: refetchHistory } = useQuery({
    queryKey: ['sales-history', page],
    queryFn: () => fetchHistory(page, 20),
  })

  async function handleUpload(file: File) {
    setAnalyzing(true)
    setCurrentReport(null)
    try {
      const report = await uploadAndAnalyze(file)
      setCurrentReport(report)
      refetchHistory()
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '分析失败，请重试'
      message.error(msg)
    } finally {
      setAnalyzing(false)
    }
    return false
  }

  async function handleViewReport(id: number) {
    const report = await fetchReport(id)
    setCurrentReport(report)
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }

  const columns = [
    { title: '文件名', dataIndex: 'filename', key: 'filename' },
    { title: '行数', dataIndex: 'row_count', key: 'row_count' },
    { title: '生成时间', dataIndex: 'report_date', key: 'report_date' },
    {
      title: '状态', dataIndex: 'status', key: 'status',
      render: (s: string) => <Tag color={s === 'success' ? 'green' : 'red'}>{s === 'success' ? '成功' : '失败'}</Tag>,
    },
    {
      title: '操作', key: 'action',
      render: (_: unknown, record: SalesReport) => (
        <Button size="small" onClick={() => handleViewReport(record.id)}>查看</Button>
      ),
    },
  ]

  return (
    <div style={{ maxWidth: 960, margin: '0 auto' }}>
      <div className="page-header">
        <div className="dot" style={{ background: 'linear-gradient(180deg, #667eea, #764ba2)' }} />
        <h2 style={{ background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', backgroundClip: 'text' }}>销售分析</h2>
      </div>

      <Dragger
        accept=".csv,.xlsx,.xls"
        showUploadList={false}
        beforeUpload={handleUpload}
        disabled={analyzing}
        style={{ marginBottom: 24 }}
      >
        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
        <p className="ant-upload-text">点击或拖拽上传销售数据文件</p>
        <p className="ant-upload-hint">支持 .csv / .xlsx / .xls，文件大小不超过 20MB</p>
      </Dragger>

      {analyzing && (
        <div style={{ textAlign: 'center', padding: 32 }}>
          <Spin size="large" />
          <div style={{ marginTop: 12, color: '#666' }}>正在分析数据，预计需要 30–60 秒...</div>
        </div>
      )}

      {!analyzing && currentReport && (
        <div style={{ background: '#fff', padding: 24, borderRadius: 8, marginBottom: 24 }}>
          {currentReport.status === 'failed' ? (
            <Alert type="error" message="分析失败" description={currentReport.error_message ?? '未知错误'} />
          ) : (
            <>
              <Space style={{ marginBottom: 12 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  文件：{currentReport.filename}　行数：{currentReport.row_count}　
                  生成时间：{currentReport.report_date}　模型：{currentReport.model}
                </Text>
              </Space>
              <ReactMarkdown>{currentReport.content ?? ''}</ReactMarkdown>
            </>
          )}
        </div>
      )}

      <div style={{ background: '#fff', padding: 24, borderRadius: 8 }}>
        <div style={{ fontWeight: 600, marginBottom: 16 }}>历史分析记录</div>
        <Table
          dataSource={history?.items ?? []}
          columns={columns}
          rowKey="id"
          pagination={{
            current: page,
            pageSize: 20,
            total: history?.total ?? 0,
            onChange: setPage,
            showSizeChanger: false,
          }}
          size="small"
        />
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Add sidebar entry in `Layout.tsx`**

In `frontend/src/components/Layout.tsx`, change the import line:

```typescript
import {
  DashboardOutlined, UnorderedListOutlined,
  SwapOutlined, RiseOutlined, FileTextOutlined, AlertOutlined
} from '@ant-design/icons'
```

to:

```typescript
import {
  DashboardOutlined, UnorderedListOutlined,
  SwapOutlined, RiseOutlined, FileTextOutlined, AlertOutlined, BarChartOutlined
} from '@ant-design/icons'
```

And change the `items` array to add the new entry after `异常检测`:

```typescript
const items = [
  { key: '/overview', icon: <DashboardOutlined />, label: '市场概览' },
  { key: '/products', icon: <UnorderedListOutlined />, label: '商品列表' },
  { key: '/compare', icon: <SwapOutlined />, label: '竞品对比' },
  { key: '/trends', icon: <RiseOutlined />, label: '趋势分析' },
  { key: '/reports', icon: <FileTextOutlined />, label: '每日报告' },
  { key: '/anomalies', icon: <AlertOutlined />, label: '异常检测' },
  { key: '/sales-analysis', icon: <BarChartOutlined />, label: '销售分析' },
]
```

- [ ] **Step 4: Add route in `App.tsx`**

In `frontend/src/App.tsx`, add import:

```typescript
import SalesAnalysis from './pages/SalesAnalysis'
```

And add route inside `<Routes>`:

```tsx
<Route path="/sales-analysis" element={<SalesAnalysis />} />
```

- [ ] **Step 5: Verify TypeScript compiles**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors.

- [ ] **Step 6: Start dev server and verify manually**

```bash
cd frontend && npm run dev
```

Open http://localhost:5173/sales-analysis. Verify:
- Upload dragger renders
- Sidebar shows "销售分析" entry
- History table renders (empty is fine)
- Upload a small CSV and confirm loading spinner appears, then report renders

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/SalesAnalysis.tsx frontend/src/api/salesAnalysis.ts \
        frontend/src/components/Layout.tsx frontend/src/App.tsx
git commit -m "feat: add sales analysis frontend page with upload, report display, and history"
```
