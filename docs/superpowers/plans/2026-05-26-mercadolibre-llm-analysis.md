# MercadoLibre LLM 每日分析报告 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在每天凌晨 02:30 UTC 的独立定时任务中调用本地 LLM，生成包含市场趋势、竞品对比、选品建议的 Markdown 日报，存入 MySQL，并在前端新增"每日报告"页面展示。

**Architecture:** APScheduler 在 02:30 UTC 触发 `run_llm_analysis_job()`，读取当日 `daily_brand_summary` 和 `daily_category_summary` 数据，构建中文 Prompt 调用本地 OpenAI 兼容接口，将 Markdown 报告写入新表 `daily_analysis_reports`。FastAPI 新增 `/api/reports` 路由，React 新增 `/reports` 页面用 `react-markdown` 渲染报告。

**Tech Stack:** Python openai==1.30.5（OpenAI 兼容客户端）、APScheduler 3.10.4、FastAPI、SQLAlchemy Core、React 18 + TypeScript、react-markdown@9、Ant Design v6

---

## 文件结构

**新建：**
- `db/migrations/002_create_analysis_reports_table.sql` — 建表 DDL
- `backend/analysis/__init__.py` — 空包文件
- `backend/analysis/llm_report.py` — LLM 调用 + 报告写入逻辑
- `backend/routers/reports.py` — `/api/reports` 路由
- `backend/tests/test_llm_report.py` — analysis 模块测试
- `backend/tests/test_reports_router.py` — reports 路由测试
- `frontend/src/api/reports.ts` — 报告接口请求函数
- `frontend/src/pages/Reports.tsx` — 每日报告页面

**修改：**
- `backend/requirements.txt` — 新增 openai==1.30.5
- `backend/scheduler.py` — 新增 02:30 job
- `backend/main.py` — 注册 reports 路由
- `frontend/src/components/Layout.tsx` — 导航栏新增"每日报告"
- `frontend/src/App.tsx` — 新增 /reports 路由
- `docker-compose.yml` — fastapi 服务新增两个环境变量

---

### Task 1: 数据库迁移 — 创建 daily_analysis_reports 表

**Files:**
- Create: `db/migrations/002_create_analysis_reports_table.sql`

- [ ] **Step 1: 写迁移 SQL 文件**

```sql
-- db/migrations/002_create_analysis_reports_table.sql
CREATE TABLE IF NOT EXISTS daily_analysis_reports (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    report_date   DATE NOT NULL,
    content       MEDIUMTEXT NOT NULL,
    model         VARCHAR(100) NOT NULL,
    generated_at  DATETIME NOT NULL,
    status        ENUM('success', 'failed') NOT NULL DEFAULT 'success',
    error_message TEXT,
    UNIQUE KEY uq_report_date (report_date)
);
```

- [ ] **Step 2: 在本地 MySQL 执行迁移**

```bash
mysql -u root -prootroot shadowcraw_db < db/migrations/002_create_analysis_reports_table.sql
```

Expected: 无报错输出

- [ ] **Step 3: 验证表已创建**

```bash
mysql -u root -prootroot shadowcraw_db -e "DESCRIBE daily_analysis_reports;"
```

Expected: 输出包含 id, report_date, content, model, generated_at, status, error_message 字段

- [ ] **Step 4: Commit**

```bash
git add db/migrations/002_create_analysis_reports_table.sql
git commit -m "feat: add daily_analysis_reports migration"
```

---

### Task 2: 后端依赖 — 安装 openai 包

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 在 requirements.txt 末尾新增一行**

打开 `backend/requirements.txt`，在末尾添加：
```
openai==1.30.5
```

- [ ] **Step 2: 安装依赖**

```bash
cd /Users/wei/Desktop/Mercadolibre
source backend/venv/bin/activate
pip install openai==1.30.5
```

Expected: `Successfully installed openai-1.30.5` 或 `Requirement already satisfied`

- [ ] **Step 3: 验证可导入**

```bash
python -c "from openai import OpenAI; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "feat: add openai dependency for LLM analysis"
```

---

### Task 3: LLM 分析模块 — backend/analysis/llm_report.py

**Files:**
- Create: `backend/analysis/__init__.py`
- Create: `backend/analysis/llm_report.py`
- Test: `backend/tests/test_llm_report.py`

- [ ] **Step 1: 创建空包文件**

创建 `backend/analysis/__init__.py`，内容为空。

- [ ] **Step 2: 写失败测试**

创建 `backend/tests/test_llm_report.py`：

```python
# backend/tests/test_llm_report.py
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from sqlalchemy import text
from backend.database import engine
from backend.analysis.llm_report import run_llm_analysis, _build_prompt

TEST_DATE = date(2026, 5, 26)


def test_build_prompt_contains_brand_data():
    brand_rows = [
        {"brand": "BrandA", "product_count": 10, "total_revenue": 5000.0,
         "total_sales_30d": 200, "avg_price": 25.0, "avg_rating": 4.5,
         "avg_growth_rate": 0.12},
    ]
    category_rows = [
        {"sub_category": "Electronics", "product_count": 5,
         "total_revenue": 2000.0, "total_sales_30d": 80},
    ]
    prev_brand_rows = []
    prompt = _build_prompt(TEST_DATE, brand_rows, category_rows, prev_brand_rows)
    assert "BrandA" in prompt
    assert "Electronics" in prompt
    assert "2026-05-26" in prompt


def test_run_llm_analysis_writes_success_record():
    mock_content = "# 每日分析报告\n\n## 市场趋势\n测试内容"
    mock_response = MagicMock()
    mock_response.choices[0].message.content = mock_content

    with patch("backend.analysis.llm_report.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_cls.return_value = mock_client

        run_llm_analysis(TEST_DATE)

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status, content FROM daily_analysis_reports WHERE report_date = :d"),
            {"d": TEST_DATE}
        ).mappings().first()

    assert row is not None
    assert row["status"] == "success"
    assert "每日分析报告" in row["content"]

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM daily_analysis_reports WHERE report_date = :d"),
            {"d": TEST_DATE}
        )


def test_run_llm_analysis_writes_failed_record_on_exception():
    with patch("backend.analysis.llm_report.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("connection refused")
        mock_openai_cls.return_value = mock_client

        run_llm_analysis(TEST_DATE)

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status, error_message FROM daily_analysis_reports WHERE report_date = :d"),
            {"d": TEST_DATE}
        ).mappings().first()

    assert row is not None
    assert row["status"] == "failed"
    assert "connection refused" in row["error_message"]

    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM daily_analysis_reports WHERE report_date = :d"),
            {"d": TEST_DATE}
        )
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
cd /Users/wei/Desktop/Mercadolibre
source backend/venv/bin/activate
python -m pytest backend/tests/test_llm_report.py -v
```

Expected: FAILED with `ModuleNotFoundError` 或 `ImportError`

- [ ] **Step 4: 实现 backend/analysis/llm_report.py**

```python
# backend/analysis/llm_report.py
import os
import logging
from datetime import date, datetime
from openai import OpenAI
from sqlalchemy import text
from backend.database import engine

logger = logging.getLogger(__name__)

LLM_BASE_URL = os.getenv("ANALYSIS_LLM_BASE_URL", "http://10.0.0.21:8005/v1")
LLM_MODEL = os.getenv("ANALYSIS_LLM_MODEL", "gemma-4-31b-it-fp8")


def _build_prompt(
    target_date: date,
    brand_rows: list,
    category_rows: list,
    prev_brand_rows: list,
) -> str:
    prev_map = {r["brand"]: r for r in prev_brand_rows}

    brand_lines = []
    for r in brand_rows:
        prev = prev_map.get(r["brand"])
        rev_change = ""
        if prev and prev["total_revenue"]:
            delta = (r["total_revenue"] - prev["total_revenue"]) / prev["total_revenue"] * 100
            rev_change = f"（营收环比 {delta:+.1f}%）"
        brand_lines.append(
            f"- {r['brand']}: 商品数={r['product_count']}, "
            f"总营收={r['total_revenue']:.2f}{rev_change}, "
            f"30天销量={r['total_sales_30d']}, "
            f"均价={r['avg_price']:.2f}, "
            f"平均评分={r['avg_rating']:.2f}, "
            f"平均增长率={float(r['avg_growth_rate'] or 0):.2%}"
        )

    category_lines = [
        f"- {r['sub_category']}: 商品数={r['product_count']}, "
        f"总营收={r['total_revenue']:.2f}, 30天销量={r['total_sales_30d']}"
        for r in category_rows
    ]

    return f"""你是一位电商数据分析师，请根据以下 MercadoLibre 平台 {target_date} 的数据生成一份中文日报。

## 品牌数据
{chr(10).join(brand_lines)}

## 品类数据
{chr(10).join(category_lines)}

请生成包含以下三个部分的 Markdown 格式报告：
1. **市场趋势**：各品牌销量、营收、增长率变化，市场整体走势
2. **竞品对比**：各品牌横向对比，指出增长最快/最慢的品牌及原因分析
3. **选品建议**：增长率最高的品类，潜在机会点，值得关注的趋势

要求：使用 Markdown 标题和列表，语言简洁专业，每部分 3-5 个要点。"""


def _fetch_brand_rows(conn, target_date: date) -> list:
    rows = conn.execute(
        text("""
            SELECT brand, product_count, total_revenue, total_sales_30d,
                   avg_price, avg_rating, avg_growth_rate
            FROM daily_brand_summary WHERE data_date = :d
        """),
        {"d": target_date},
    ).mappings().all()
    return [dict(r) for r in rows]


def _fetch_category_rows(conn, target_date: date) -> list:
    rows = conn.execute(
        text("""
            SELECT sub_category, product_count, total_revenue, total_sales_30d
            FROM daily_category_summary WHERE data_date = :d
            ORDER BY total_revenue DESC
        """),
        {"d": target_date},
    ).mappings().all()
    return [dict(r) for r in rows]


def _call_llm(prompt: str) -> str:
    client = OpenAI(base_url=LLM_BASE_URL, api_key="local")
    for attempt in range(2):
        try:
            resp = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=4096,
                timeout=120,
            )
            content = resp.choices[0].message.content or ""
            if content.strip():
                return content
            logger.warning("LLM returned empty content, attempt %d", attempt + 1)
        except Exception as e:
            if attempt == 1:
                raise
            logger.warning("LLM call failed on attempt %d: %s", attempt + 1, e)
    return ""


def _save_report(target_date: date, content: str, status: str, error_message: str | None) -> None:
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO daily_analysis_reports
                    (report_date, content, model, generated_at, status, error_message)
                VALUES (:d, :content, :model, :now, :status, :err)
                ON DUPLICATE KEY UPDATE
                    content = VALUES(content),
                    model = VALUES(model),
                    generated_at = VALUES(generated_at),
                    status = VALUES(status),
                    error_message = VALUES(error_message)
            """),
            {
                "d": target_date,
                "content": content,
                "model": LLM_MODEL,
                "now": datetime.utcnow(),
                "status": status,
                "err": error_message,
            },
        )


def run_llm_analysis(target_date: date) -> None:
    with engine.connect() as conn:
        brand_rows = _fetch_brand_rows(conn, target_date)
        category_rows = _fetch_category_rows(conn, target_date)
        from datetime import timedelta
        prev_date = target_date - timedelta(days=1)
        prev_brand_rows = _fetch_brand_rows(conn, prev_date)

    if not brand_rows:
        logger.warning("No aggregation data for %s, skipping LLM analysis", target_date)
        return

    prompt = _build_prompt(target_date, brand_rows, category_rows, prev_brand_rows)

    try:
        content = _call_llm(prompt)
        if not content.strip():
            _save_report(target_date, "", "failed", "LLM returned empty content after retries")
        else:
            _save_report(target_date, content, "success", None)
    except Exception as e:
        logger.exception("LLM analysis failed for %s", target_date)
        _save_report(target_date, "", "failed", str(e))
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
python -m pytest backend/tests/test_llm_report.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/analysis/__init__.py backend/analysis/llm_report.py backend/tests/test_llm_report.py
git commit -m "feat: add LLM analysis module with prompt builder and report writer"
```

---

### Task 4: Scheduler — 新增 02:30 UTC job

**Files:**
- Modify: `backend/scheduler.py`

- [ ] **Step 1: 修改 backend/scheduler.py**

将文件内容替换为：

```python
# backend/scheduler.py
import logging
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
from backend.aggregation.product_snapshot import run_product_snapshot
from backend.analysis.llm_report import run_llm_analysis

logger = logging.getLogger(__name__)

def run_daily_aggregation():
    today = date.today()
    try:
        run_brand_summary(today)
        run_category_summary(today)
        logger.info("Daily aggregation completed for %s", today)
    except Exception:
        logger.exception("Daily aggregation failed for %s", today)

def run_monthly_snapshot():
    today = date.today()
    try:
        run_product_snapshot(today)
        logger.info("Monthly snapshot completed for %s", today)
    except Exception:
        logger.exception("Monthly snapshot failed for %s", today)

def run_llm_analysis_job():
    today = date.today()
    try:
        run_llm_analysis(today)
        logger.info("LLM analysis completed for %s", today)
    except Exception:
        logger.exception("LLM analysis job failed for %s", today)

def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC")
    scheduler.add_job(run_daily_aggregation, "cron", hour=2, minute=0, misfire_grace_time=3600)
    scheduler.add_job(run_monthly_snapshot, "cron", day=1, hour=3, minute=0, misfire_grace_time=3600)
    scheduler.add_job(run_llm_analysis_job, "cron", hour=2, minute=30, misfire_grace_time=3600)
    scheduler.start()
    return scheduler
```

- [ ] **Step 2: 验证语法**

```bash
cd /Users/wei/Desktop/Mercadolibre
source backend/venv/bin/activate
python -c "from backend.scheduler import start_scheduler; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/scheduler.py
git commit -m "feat: add LLM analysis job at 02:30 UTC to scheduler"
```

---

### Task 5: API 路由 — backend/routers/reports.py

**Files:**
- Create: `backend/routers/reports.py`
- Modify: `backend/main.py`
- Test: `backend/tests/test_reports_router.py`

- [ ] **Step 1: 写失败测试**

创建 `backend/tests/test_reports_router.py`：

```python
# backend/tests/test_reports_router.py
from fastapi.testclient import TestClient
from datetime import datetime
from sqlalchemy import text
from backend.database import engine
from backend.main import app

client = TestClient(app)

TEST_DATE = "2026-01-01"


def _insert_report(status="success", content="# 测试报告\n内容", error_message=None):
    with engine.begin() as conn:
        conn.execute(
            text("""
                INSERT INTO daily_analysis_reports
                    (report_date, content, model, generated_at, status, error_message)
                VALUES (:d, :content, :model, :now, :status, :err)
                ON DUPLICATE KEY UPDATE content = VALUES(content)
            """),
            {
                "d": TEST_DATE,
                "content": content,
                "model": "test-model",
                "now": datetime(2026, 1, 1, 2, 35, 0),
                "status": status,
                "err": error_message,
            },
        )


def _delete_report():
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM daily_analysis_reports WHERE report_date = :d"),
            {"d": TEST_DATE},
        )


def test_get_report_by_date_returns_report():
    _insert_report()
    try:
        r = client.get(f"/api/reports?date={TEST_DATE}")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data["report_date"] == TEST_DATE
        assert data["status"] == "success"
        assert "测试报告" in data["content"]
    finally:
        _delete_report()


def test_get_report_by_date_returns_null_when_missing():
    r = client.get("/api/reports?date=2000-01-01")
    assert r.status_code == 200
    assert r.json()["data"] is None


def test_get_latest_report_returns_most_recent():
    _insert_report()
    try:
        r = client.get("/api/reports/latest")
        assert r.status_code == 200
        assert r.json()["data"] is not None
    finally:
        _delete_report()
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest backend/tests/test_reports_router.py -v
```

Expected: FAILED with 404 or ImportError

- [ ] **Step 3: 实现 backend/routers/reports.py**

```python
# backend/routers/reports.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()

_SELECT = """
    SELECT report_date, content, model, generated_at, status, error_message
    FROM daily_analysis_reports
"""


def _row_to_dict(row) -> dict:
    return {
        "report_date": str(row["report_date"]),
        "content": row["content"],
        "model": row["model"],
        "generated_at": str(row["generated_at"]),
        "status": row["status"],
        "error_message": row["error_message"],
    }


@router.get("/reports", response_model=ApiResponse)
def get_report(date: Optional[str] = Query(default=None)):
    with engine.connect() as conn:
        if date:
            row = conn.execute(
                text(_SELECT + " WHERE report_date = :d"),
                {"d": date},
            ).mappings().first()
        else:
            row = conn.execute(
                text(_SELECT + " ORDER BY report_date DESC LIMIT 1")
            ).mappings().first()
    return ApiResponse(data=_row_to_dict(row) if row else None)


@router.get("/reports/latest", response_model=ApiResponse)
def get_latest_report():
    with engine.connect() as conn:
        row = conn.execute(
            text(_SELECT + " ORDER BY report_date DESC LIMIT 1")
        ).mappings().first()
    return ApiResponse(data=_row_to_dict(row) if row else None)
```

- [ ] **Step 4: 注册路由到 backend/main.py**

在 `backend/main.py` 的 import 区新增：
```python
from backend.routers import reports
```

在其他 `app.include_router(...)` 行之后新增：
```python
app.include_router(reports.router, prefix="/api")
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
python -m pytest backend/tests/test_reports_router.py -v
```

Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add backend/routers/reports.py backend/main.py backend/tests/test_reports_router.py
git commit -m "feat: add /api/reports endpoint for daily analysis reports"
```

---

### Task 6: 环境变量配置

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: 修改 docker-compose.yml，在 fastapi 的 environment 下新增两行**

找到：
```yaml
    environment:
      DB_HOST: mysql
```

改为：
```yaml
    environment:
      DB_HOST: mysql
      ANALYSIS_LLM_BASE_URL: "http://10.0.0.21:8005/v1"
      ANALYSIS_LLM_MODEL: "gemma-4-31b-it-fp8"
```

- [ ] **Step 2: 验证 YAML 格式正确**

```bash
python -c "import yaml; yaml.safe_load(open('docker-compose.yml')); print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add docker-compose.yml
git commit -m "feat: add LLM env vars to docker-compose"
```

---

### Task 7: 前端 — 报告 API 客户端 + 页面 + 路由

**Files:**
- Create: `frontend/src/api/reports.ts`
- Create: `frontend/src/pages/Reports.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: 安装 react-markdown**

```bash
cd /Users/wei/Desktop/Mercadolibre/frontend
npm install react-markdown@9
```

Expected: `added N packages`

- [ ] **Step 2: 创建 frontend/src/api/reports.ts**

```typescript
// frontend/src/api/reports.ts
import { api, unwrap } from './client'

export interface ReportData {
  report_date: string
  content: string
  model: string
  generated_at: string
  status: 'success' | 'failed'
  error_message: string | null
}

export function fetchLatestReport(): Promise<ReportData | null> {
  return unwrap<ReportData | null>(api.get('/reports/latest'))
}

export function fetchReport(date: string): Promise<ReportData | null> {
  return unwrap<ReportData | null>(api.get('/reports', { params: { date } }))
}
```

- [ ] **Step 3: 创建 frontend/src/pages/Reports.tsx**

```tsx
// frontend/src/pages/Reports.tsx
import { useState } from 'react'
import { DatePicker, Skeleton, Alert, Typography, Space } from 'antd'
import { useQuery } from '@tanstack/react-query'
import ReactMarkdown from 'react-markdown'
import { fetchLatestReport, fetchReport, ReportData } from '../api/reports'

const { Text } = Typography

export default function Reports() {
  const [date, setDate] = useState<string | null>(null)

  const { data, isLoading } = useQuery<ReportData | null>({
    queryKey: ['report', date],
    queryFn: () => (date ? fetchReport(date) : fetchLatestReport()),
  })

  return (
    <div style={{ maxWidth: 900, margin: '0 auto' }}>
      <Space style={{ marginBottom: 16 }}>
        <DatePicker
          onChange={(_, s) => setDate((s as string) || null)}
          placeholder="选择日期（默认最新）"
        />
      </Space>

      {isLoading && <Skeleton active paragraph={{ rows: 12 }} />}

      {!isLoading && !data && (
        <Alert type="info" title="当日报告尚未生成，请在凌晨 2:30 后查看" />
      )}

      {!isLoading && data && data.status === 'failed' && (
        <Alert
          type="error"
          title="报告生成失败"
          description={data.error_message ?? '未知错误'}
          style={{ marginBottom: 16 }}
        />
      )}

      {!isLoading && data && data.status === 'success' && (
        <>
          <div style={{ marginBottom: 8 }}>
            <Text type="secondary" style={{ fontSize: 12 }}>
              生成时间：{data.generated_at}　模型：{data.model}
            </Text>
          </div>
          <div style={{ background: '#fff', padding: 24, borderRadius: 8 }}>
            <ReactMarkdown>{data.content}</ReactMarkdown>
          </div>
        </>
      )}
    </div>
  )
}
```

- [ ] **Step 4: 修改 frontend/src/components/Layout.tsx — 新增菜单项**

在 `items` 数组末尾新增一项：

找到：
```typescript
  { key: '/trends', icon: <RiseOutlined />, label: '趋势分析' },
]
```

改为：
```typescript
  { key: '/trends', icon: <RiseOutlined />, label: '趋势分析' },
  { key: '/reports', icon: <FileTextOutlined />, label: '每日报告' },
]
```

同时在 import 行新增 `FileTextOutlined`：

找到：
```typescript
import {
  DashboardOutlined, UnorderedListOutlined,
  SwapOutlined, RiseOutlined
} from '@ant-design/icons'
```

改为：
```typescript
import {
  DashboardOutlined, UnorderedListOutlined,
  SwapOutlined, RiseOutlined, FileTextOutlined
} from '@ant-design/icons'
```

- [ ] **Step 5: 修改 frontend/src/App.tsx — 新增路由**

新增 import：
```typescript
import Reports from './pages/Reports'
```

在 `<Route path="/trends" ... />` 后新增：
```tsx
<Route path="/reports" element={<Reports />} />
```

- [ ] **Step 6: 构建前端，确认无 TypeScript 错误**

```bash
cd /Users/wei/Desktop/Mercadolibre/frontend
npm run build
```

Expected: 无 error，输出 `dist/index.html` 等文件

- [ ] **Step 7: Commit**

```bash
cd /Users/wei/Desktop/Mercadolibre
git add frontend/src/api/reports.ts frontend/src/pages/Reports.tsx \
        frontend/src/App.tsx frontend/src/components/Layout.tsx \
        frontend/package.json frontend/package-lock.json
git commit -m "feat: add daily reports page with react-markdown renderer"
```

---

### Task 8: 端到端验证

**Files:** 无新增

- [ ] **Step 1: 运行全部后端测试**

```bash
cd /Users/wei/Desktop/Mercadolibre
source backend/venv/bin/activate
python -m pytest backend/tests/ -v
```

Expected: 全部 PASSED，无 FAILED

- [ ] **Step 2: 手动触发一次 LLM 分析，验证报告写入 DB**

```bash
python -c "
from datetime import date
from backend.analysis.llm_report import run_llm_analysis
run_llm_analysis(date(2026, 5, 26))
print('done')
"
```

Expected: `done`（若 LLM 服务可达则写入 success，否则写入 failed 记录）

- [ ] **Step 3: 确认 DB 中有记录**

```bash
mysql -u root -prootroot shadowcraw_db \
  -e "SELECT report_date, status, LEFT(content,80) FROM daily_analysis_reports;"
```

Expected: 至少一行，status 为 success 或 failed

- [ ] **Step 4: 启动后端，访问 API**

```bash
uvicorn backend.main:app --reload
```

在另一终端：
```bash
curl http://localhost:8000/api/reports/latest | python -m json.tool
```

Expected: JSON 响应，`data.report_date` 有值

- [ ] **Step 5: 构建前端并验证页面**

```bash
cd frontend && npm run build
```

访问 `http://localhost:8000/reports`，确认：
- 导航栏显示"每日报告"菜单项
- 有报告时显示 Markdown 渲染内容（标题、列表清晰可读）
- 无报告时显示"当日报告尚未生成"提示
- 日期选择器可切换历史报告

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: LLM daily analysis report — end-to-end complete"
```
```
