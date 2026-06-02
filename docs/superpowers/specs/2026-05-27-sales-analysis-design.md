# Sales Analysis Feature Design

## Goal

Allow users to upload CSV/Excel sales data files (up to tens of thousands of rows), automatically compute statistical summaries via pandas, send summaries to a local LLM, and generate structured Markdown analysis reports that are persisted to the database with full history.

## Architecture

Server-side preprocessing approach: pandas reads and summarizes the file (time trends, price distribution, category rankings, growth rates), then the LLM receives only the compact summary (~a few hundred lines) rather than raw data. This avoids token limits and produces accurate statistics. Reports are stored in a dedicated table and viewable via a history panel.

## Tech Stack

- Backend: FastAPI, pandas, openpyxl, openai SDK (OpenAI-compatible)
- LLM: `qwen3.6-35b-a3b-fp8` at `http://10.0.0.21:8000/v1`
- Frontend: React 18, TypeScript, Ant Design v6, react-markdown, @tanstack/react-query

---

## Data Layer

### New table: `sales_analysis_reports`

```sql
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

Separate from `daily_analysis_reports`: no date uniqueness constraint, user-triggered, not scheduler-driven.

### Column auto-detection (pandas)

After reading the file, columns are classified as:
- **Date columns**: columns parseable as datetime
- **Numeric columns**: int/float dtype columns
- **Categorical columns**: object dtype with fewer than 50 unique values (brand, SKU, channel, etc.)
- **ID columns**: object dtype where unique count ≈ row count — excluded from analysis

---

## Backend

### New files

- `db/migrations/004_create_sales_analysis_reports_table.sql`
- `backend/analysis/sales_analyzer.py`
- `backend/routers/sales_analysis.py`

### LLM configuration (in `sales_analyzer.py`)

```python
SALES_LLM_BASE_URL = os.getenv("SALES_LLM_BASE_URL", "http://10.0.0.21:8000/v1")
SALES_LLM_MODEL    = os.getenv("SALES_LLM_MODEL", "qwen3.6-35b-a3b-fp8")
```

Independent of the existing `llm_report.py` configuration.

### `sales_analyzer.py` — core function

```python
def run_sales_analysis(file_bytes: bytes, filename: str) -> dict:
    # Returns: {"id": int, "content": str, "row_count": int, "status": str}
```

Processing pipeline:

1. **Read file**: `pd.read_csv` or `pd.read_excel` based on extension. Raise `ValueError` for unsupported formats.
2. **Classify columns**: date / numeric / categorical / id (excluded).
3. **Compute summaries**:
   - *Time trend*: if date column exists, resample numeric columns by month (sum and mean). Output top-3 numeric columns by total magnitude.
   - *Price distribution*: for each numeric column, compute min / p25 / median / p75 / max.
   - *Category rankings*: for each categorical column × each numeric column, compute top-10 by sum.
   - *Growth rate*: if date column exists, compare first-period vs last-period sum for each numeric column.
4. **Build prompt**: fixed Chinese template with sections: 数据概览、时间趋势、价格/数值分布、分类排名、增长亮点与风险、综合建议.
5. **Call LLM**: `openai.OpenAI(base_url=..., api_key="none")`, `chat.completions.create`, `stream=False`.
6. **Persist**: insert row into `sales_analysis_reports`. On LLM exception, insert with `status='failed'` and `error_message`.
7. **Return** id, content, row_count, status.

### API endpoints

#### `POST /api/sales-analysis/upload`

- Accepts `multipart/form-data`, field name `file`
- Supported extensions: `.csv`, `.xlsx`, `.xls`
- File size limit: 20 MB (enforced in router)
- Calls `run_sales_analysis(file_bytes, filename)`
- Returns `ApiResponse` with `{id, content, row_count, filename, status}`

#### `GET /api/sales-analysis/history`

- Query params: `page: int = 1`, `size: int = 20`
- Returns `ApiResponse` with `{items: [...], total: int}`
- Each item: `{id, filename, row_count, report_date, status}`
- Ordered by `created_at DESC`

#### `GET /api/sales-analysis/reports/{id}`

- Returns `ApiResponse` with full report: `{id, filename, row_count, report_date, content, model, status, error_message}`
- Returns 404 if not found

### `main.py` changes

```python
from backend.routers import sales_analysis
app.include_router(sales_analysis.router, prefix="/api")
```

---

## Frontend

### New files

- `frontend/src/pages/SalesAnalysis.tsx`
- `frontend/src/api/salesAnalysis.ts`

### `salesAnalysis.ts`

```ts
interface SalesReport {
  id: number
  filename: string
  row_count: number
  report_date: string
  content?: string
  model?: string
  status: 'success' | 'failed'
  error_message?: string
}

function uploadAndAnalyze(file: File): Promise<SalesReport>
function fetchHistory(page: number, size: number): Promise<{ items: SalesReport[], total: number }>
function fetchReport(id: number): Promise<SalesReport>
```

`uploadAndAnalyze` uses `FormData` + `axios.post('/api/sales-analysis/upload', formData)`.

### `SalesAnalysis.tsx` layout

Three sections:

**Upload section** (top)
- Ant Design `Upload.Dragger`, accept `.csv,.xlsx,.xls`, `showUploadList={false}`
- On file select: call `uploadAndAnalyze`, set loading state
- Loading message: "正在分析数据，预计需要 30–60 秒..."
- On success: populate report display section; on error: show Ant Design `message.error`

**Report display section** (middle)
- Shows: filename, row count, generation time, model name
- Renders `content` with `react-markdown`
- Hidden when no report loaded

**History table** (bottom)
- Columns: 文件名 / 行数 / 生成时间 / 状态（Tag: 成功/失败）/ 操作（查看按钮）
- Clicking 查看 calls `fetchReport(id)` and populates the display section
- Ant Design `Table` with server-side pagination, page size 20

### Sidebar entry (`Layout.tsx`)

Add menu item: `{ key: 'sales-analysis', icon: <BarChartOutlined />, label: '销售分析' }` after 异常检测.

---

## Error Handling

- Unsupported file format → HTTP 400 with message
- File > 20 MB → HTTP 413 with message
- No numeric columns detected → HTTP 422 with message "未检测到数值列，无法生成分析"
- LLM call fails → status='failed' saved to DB, HTTP 200 with status field indicating failure (frontend shows error alert)
- Report id not found → HTTP 404

---

## Testing

- `backend/tests/test_sales_analyzer.py`: unit tests for column classification and summary computation using small in-memory DataFrames (no LLM calls)
- `backend/tests/test_sales_analysis_router.py`: integration tests for upload endpoint using a small test CSV fixture; mock LLM call
- No frontend tests (manual verification via dev server)
