# 异常检测引擎 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a product-level anomaly detection engine that compares daily snapshots against 7-day baselines for sales amount, sales volume, price, and BSR, with configurable thresholds and a dedicated frontend page.

**Architecture:** SQL-based detection reads from `product_30d_snapshot`, computes per-product baselines, and writes flagged anomalies to a new `anomaly_alerts` table. A FastAPI router exposes detect (POST) and query (GET) endpoints. A React page lets users configure thresholds, trigger detection, and browse results.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy Core (text queries), MySQL, React 18, TypeScript, Ant Design v6, React Query, axios

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `db/migrations/003_create_anomaly_alerts_table.sql` | DDL for anomaly_alerts table |
| Create | `backend/analysis/anomaly_detector.py` | Detection logic |
| Create | `backend/routers/anomalies.py` | POST /detect and GET /latest endpoints |
| Modify | `backend/main.py` | Register anomalies router |
| Create | `backend/tests/test_anomaly_detector.py` | Unit + integration tests for detector |
| Create | `backend/tests/test_anomalies_router.py` | API endpoint tests |
| Create | `frontend/src/api/anomalies.ts` | API client functions + types |
| Create | `frontend/src/pages/Anomalies.tsx` | Detection page |
| Modify | `frontend/src/App.tsx` | Add /anomalies route |
| Modify | `frontend/src/components/Layout.tsx` | Add 异常检测 menu item |

---

## Task 1: Database Migration


**Files:**
- Create: `db/migrations/003_create_anomaly_alerts_table.sql`

- [ ] **Step 1: Write the migration file**

```sql
CREATE TABLE IF NOT EXISTS anomaly_alerts (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    detected_at DATETIME NOT NULL,
    product_id VARCHAR(100) NOT NULL,
    brand VARCHAR(100) NOT NULL,
    anomaly_type ENUM('sales_amount','sales_volume','price','bsr') NOT NULL,
    current_value DECIMAL(18,4) NOT NULL,
    baseline_value DECIMAL(18,4) NOT NULL,
    change_pct DECIMAL(10,4) NOT NULL,
    threshold_pct DECIMAL(10,4) NOT NULL,
    direction ENUM('up','down') NOT NULL,
    INDEX idx_detected_at (detected_at),
    INDEX idx_brand (brand),
    INDEX idx_type (anomaly_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: Apply the migration**

```bash
mysql -u root -p mercadolibre < db/migrations/003_create_anomaly_alerts_table.sql
```

Expected: no errors, table exists.

- [ ] **Step 3: Verify table exists**

```bash
mysql -u root -p mercadolibre -e "DESCRIBE anomaly_alerts;"
```

Expected: columns id, detected_at, product_id, brand, anomaly_type, current_value, baseline_value, change_pct, threshold_pct, direction.

- [ ] **Step 4: Commit**

```bash
git add db/migrations/003_create_anomaly_alerts_table.sql
git commit -m "feat: add anomaly_alerts table migration"
```

---

## Task 2: Anomaly Detector Core

**Files:**
- Create: `backend/analysis/anomaly_detector.py`
- Create: `backend/tests/test_anomaly_detector.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_anomaly_detector.py`:

```python
# backend/tests/test_anomaly_detector.py
import pytest
from datetime import date, datetime, timedelta
from sqlalchemy import text
from backend.database import engine
from backend.analysis.anomaly_detector import run_anomaly_detection

TEST_PRODUCT = "TEST_ANOM_001"
TEST_BRAND = "Blackview"
BASE_DATE = date(2026, 1, 15)


def _insert_snapshot(conn, snapshot_date, price, sales_30d, revenue, bsr):
    conn.execute(text("""
        INSERT INTO product_30d_snapshot
            (snapshot_date, product_id, brand, price, sales_30d, revenue, bsr,
             review_count, review_rating, growth_rate)
        VALUES (:d, :pid, :brand, :price, :sales, :rev, :bsr, 10, 4.5, 0.1)
        ON DUPLICATE KEY UPDATE
            price=VALUES(price), sales_30d=VALUES(sales_30d),
            revenue=VALUES(revenue), bsr=VALUES(bsr)
    """), {"d": snapshot_date, "pid": TEST_PRODUCT, "brand": TEST_BRAND,
           "price": price, "sales": sales_30d, "rev": revenue, "bsr": bsr})


def _cleanup(conn):
    conn.execute(text("DELETE FROM product_30d_snapshot WHERE product_id = :p"),
                 {"p": TEST_PRODUCT})
    conn.execute(text("DELETE FROM anomaly_alerts WHERE product_id = :p"),
                 {"p": TEST_PRODUCT})


def test_detects_sales_amount_spike():
    with engine.begin() as conn:
        # 7 baseline days: revenue=1000 each
        for i in range(7, 0, -1):
            _insert_snapshot(conn, BASE_DATE - timedelta(days=i),
                             price=50.0, sales_30d=100, revenue=1000.0, bsr=500)
        # latest day: revenue=2000 (100% spike, > 30% threshold)
        _insert_snapshot(conn, BASE_DATE, price=50.0, sales_30d=100, revenue=2000.0, bsr=500)

    try:
        result = run_anomaly_detection(
            sales_amount_threshold=0.30,
            sales_volume_threshold=0.30,
            price_threshold=0.20,
            bsr_threshold=0.30,
        )
        assert result["detected"] >= 1
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT anomaly_type, direction, change_pct
                FROM anomaly_alerts
                WHERE product_id = :p AND anomaly_type = 'sales_amount'
                ORDER BY id DESC LIMIT 1
            """), {"p": TEST_PRODUCT}).mappings().first()
        assert row is not None
        assert row["direction"] == "up"
        assert float(row["change_pct"]) > 30
    finally:
        with engine.begin() as conn:
            _cleanup(conn)


def test_skips_product_with_insufficient_history():
    with engine.begin() as conn:
        # Only 2 prior days (< 3 required)
        for i in range(2, 0, -1):
            _insert_snapshot(conn, BASE_DATE - timedelta(days=i),
                             price=50.0, sales_30d=100, revenue=1000.0, bsr=500)
        _insert_snapshot(conn, BASE_DATE, price=50.0, sales_30d=100, revenue=9999.0, bsr=500)

    try:
        result = run_anomaly_detection()
        with engine.connect() as conn:
            row = conn.execute(text("""
                SELECT id FROM anomaly_alerts WHERE product_id = :p
            """), {"p": TEST_PRODUCT}).mappings().first()
        assert row is None
    finally:
        with engine.begin() as conn:
            _cleanup(conn)


def test_no_anomaly_when_within_threshold():
    with engine.begin() as conn:
        for i in range(7, 0, -1):
            _insert_snapshot(conn, BASE_DATE - timedelta(days=i),
                             price=50.0, sales_30d=100, revenue=1000.0, bsr=500)
        # 10% change — below 30% threshold
        _insert_snapshot(conn, BASE_DATE, price=50.0, sales_30d=110, revenue=1100.0, bsr=500)

    try:
        result = run_anomaly_detection()
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT id FROM anomaly_alerts WHERE product_id = :p
            """), {"p": TEST_PRODUCT}).mappings().all()
        assert len(rows) == 0
    finally:
        with engine.begin() as conn:
            _cleanup(conn)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/wei/Desktop/Mercadolibre/backend
python -m pytest tests/test_anomaly_detector.py -v 2>&1 | head -30
```

Expected: ImportError or ModuleNotFoundError for `anomaly_detector`.

- [ ] **Step 3: Implement the detector**

Create `backend/analysis/anomaly_detector.py`:

```python
# backend/analysis/anomaly_detector.py
from datetime import datetime
from typing import Optional
from sqlalchemy import text
from backend.database import engine

TRACKED_BRANDS = ("Blackview", "Cubot", "Ulefone", "Doogee")

_METRICS = [
    ("revenue",   "sales_amount"),
    ("sales_30d", "sales_volume"),
    ("price",     "price"),
    ("bsr",       "bsr"),
]


def run_anomaly_detection(
    sales_amount_threshold: float = 0.30,
    sales_volume_threshold: float = 0.30,
    price_threshold: float = 0.20,
    bsr_threshold: float = 0.30,
) -> dict:
    thresholds = {
        "sales_amount": sales_amount_threshold,
        "sales_volume": sales_volume_threshold,
        "price":        price_threshold,
        "bsr":          bsr_threshold,
    }
    detected_at = datetime.utcnow().replace(microsecond=0)
    inserted = 0

    with engine.begin() as conn:
        latest_row = conn.execute(text(
            "SELECT MAX(snapshot_date) AS d FROM product_30d_snapshot"
        )).mappings().first()
        if not latest_row or not latest_row["d"]:
            return {"detected": 0, "detected_at": detected_at.isoformat()}
        latest_date = latest_row["d"]

        current_rows = conn.execute(text("""
            SELECT product_id, brand, revenue, sales_30d, price, bsr
            FROM product_30d_snapshot
            WHERE snapshot_date = :d AND brand IN :brands
        """), {"d": latest_date, "brands": TRACKED_BRANDS}).mappings().all()

        for row in current_rows:
            pid = row["product_id"]

            baseline_row = conn.execute(text("""
                SELECT
                    AVG(revenue)   AS avg_revenue,
                    AVG(sales_30d) AS avg_sales,
                    AVG(price)     AS avg_price,
                    AVG(bsr)       AS avg_bsr,
                    COUNT(*)       AS day_count
                FROM product_30d_snapshot
                WHERE product_id = :pid
                  AND snapshot_date < :d
                  AND snapshot_date >= DATE_SUB(:d, INTERVAL 7 DAY)
            """), {"pid": pid, "d": latest_date}).mappings().first()

            if not baseline_row or (baseline_row["day_count"] or 0) < 3:
                continue

            baseline_map = {
                "sales_amount": baseline_row["avg_revenue"],
                "sales_volume": baseline_row["avg_sales"],
                "price":        baseline_row["avg_price"],
                "bsr":          baseline_row["avg_bsr"],
            }
            current_map = {
                "sales_amount": row["revenue"],
                "sales_volume": row["sales_30d"],
                "price":        row["price"],
                "bsr":          row["bsr"],
            }

            for metric_key, anomaly_type in [
                ("sales_amount", "sales_amount"),
                ("sales_volume", "sales_volume"),
                ("price",        "price"),
                ("bsr",          "bsr"),
            ]:
                baseline_val = baseline_map[metric_key]
                current_val  = current_map[metric_key]
                if not baseline_val or baseline_val == 0:
                    continue
                if current_val is None:
                    continue

                change_pct = (float(current_val) - float(baseline_val)) / float(baseline_val) * 100
                threshold_pct = thresholds[anomaly_type] * 100

                if abs(change_pct) > threshold_pct:
                    direction = "up" if change_pct > 0 else "down"
                    conn.execute(text("""
                        INSERT INTO anomaly_alerts
                            (detected_at, product_id, brand, anomaly_type,
                             current_value, baseline_value, change_pct,
                             threshold_pct, direction)
                        VALUES
                            (:at, :pid, :brand, :atype,
                             :cur, :base, :chg, :thr, :dir)
                    """), {
                        "at":    detected_at,
                        "pid":   pid,
                        "brand": row["brand"],
                        "atype": anomaly_type,
                        "cur":   float(current_val),
                        "base":  float(baseline_val),
                        "chg":   round(change_pct, 4),
                        "thr":   round(threshold_pct, 4),
                        "dir":   direction,
                    })
                    inserted += 1

    return {"detected": inserted, "detected_at": detected_at.isoformat()}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/wei/Desktop/Mercadolibre/backend
python -m pytest tests/test_anomaly_detector.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/analysis/anomaly_detector.py backend/tests/test_anomaly_detector.py
git commit -m "feat: add anomaly detector core with SQL baseline comparison"
```

---

## Task 3: Anomalies API Router

**Files:**
- Create: `backend/routers/anomalies.py`
- Modify: `backend/main.py`
- Create: `backend/tests/test_anomalies_router.py`

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_anomalies_router.py`:

```python
# backend/tests/test_anomalies_router.py
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_detect_endpoint_returns_detected_count():
    mock_result = {"detected": 5, "detected_at": "2026-05-27T04:00:00"}
    with patch("backend.routers.anomalies.run_anomaly_detection", return_value=mock_result):
        resp = client.post("/api/anomalies/detect", json={
            "sales_amount_threshold": 0.30,
            "sales_volume_threshold": 0.30,
            "price_threshold": 0.20,
            "bsr_threshold": 0.30,
        })
    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["detected"] == 5
    assert body["data"]["detected_at"] == "2026-05-27T04:00:00"


def test_detect_endpoint_uses_defaults_when_body_empty():
    mock_result = {"detected": 0, "detected_at": "2026-05-27T04:00:00"}
    with patch("backend.routers.anomalies.run_anomaly_detection", return_value=mock_result) as mock_fn:
        resp = client.post("/api/anomalies/detect", json={})
    assert resp.status_code == 200
    mock_fn.assert_called_once_with(
        sales_amount_threshold=0.30,
        sales_volume_threshold=0.30,
        price_threshold=0.20,
        bsr_threshold=0.30,
    )


def test_latest_endpoint_returns_list():
    mock_rows = [
        {
            "id": 1, "detected_at": "2026-05-27T04:00:00",
            "product_id": "P001", "brand": "Blackview",
            "anomaly_type": "price", "current_value": 60.0,
            "baseline_value": 50.0, "change_pct": 20.0,
            "threshold_pct": 20.0, "direction": "up",
        }
    ]
    with patch("backend.routers.anomalies._fetch_latest_anomalies", return_value=mock_rows):
        resp = client.get("/api/anomalies/latest")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert data[0]["product_id"] == "P001"


def test_latest_endpoint_brand_filter():
    with patch("backend.routers.anomalies._fetch_latest_anomalies", return_value=[]) as mock_fn:
        resp = client.get("/api/anomalies/latest?brand=Blackview&type=price")
    assert resp.status_code == 200
    mock_fn.assert_called_once_with(brand="Blackview", anomaly_type="price")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/wei/Desktop/Mercadolibre/backend
python -m pytest tests/test_anomalies_router.py -v 2>&1 | head -20
```

Expected: ImportError for `backend.routers.anomalies`.

- [ ] **Step 3: Create the router**

Create `backend/routers/anomalies.py`:

```python
# backend/routers/anomalies.py
from typing import Optional
from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text
from backend.database import engine
from backend.models.schemas import ApiResponse
from backend.analysis.anomaly_detector import run_anomaly_detection

router = APIRouter()


class DetectRequest(BaseModel):
    sales_amount_threshold: float = 0.30
    sales_volume_threshold: float = 0.30
    price_threshold: float = 0.20
    bsr_threshold: float = 0.30


def _fetch_latest_anomalies(
    brand: Optional[str] = None,
    anomaly_type: Optional[str] = None,
) -> list:
    with engine.connect() as conn:
        latest = conn.execute(text(
            "SELECT MAX(detected_at) AS t FROM anomaly_alerts"
        )).mappings().first()
        if not latest or not latest["t"]:
            return []
        latest_at = latest["t"]

        filters = "WHERE detected_at = :at"
        params: dict = {"at": latest_at}
        if brand:
            filters += " AND brand = :brand"
            params["brand"] = brand
        if anomaly_type:
            filters += " AND anomaly_type = :atype"
            params["atype"] = anomaly_type

        rows = conn.execute(text(f"""
            SELECT id, detected_at, product_id, brand, anomaly_type,
                   current_value, baseline_value, change_pct,
                   threshold_pct, direction
            FROM anomaly_alerts
            {filters}
            ORDER BY ABS(change_pct) DESC
        """), params).mappings().all()

        return [
            {
                "id": r["id"],
                "detected_at": str(r["detected_at"]),
                "product_id": r["product_id"],
                "brand": r["brand"],
                "anomaly_type": r["anomaly_type"],
                "current_value": float(r["current_value"]),
                "baseline_value": float(r["baseline_value"]),
                "change_pct": float(r["change_pct"]),
                "threshold_pct": float(r["threshold_pct"]),
                "direction": r["direction"],
            }
            for r in rows
        ]


@router.post("/anomalies/detect", response_model=ApiResponse)
def detect_anomalies(body: DetectRequest):
    result = run_anomaly_detection(
        sales_amount_threshold=body.sales_amount_threshold,
        sales_volume_threshold=body.sales_volume_threshold,
        price_threshold=body.price_threshold,
        bsr_threshold=body.bsr_threshold,
    )
    return ApiResponse(data=result)


@router.get("/anomalies/latest", response_model=ApiResponse)
def get_latest_anomalies(
    brand: Optional[str] = Query(default=None),
    type: Optional[str] = Query(default=None),
):
    rows = _fetch_latest_anomalies(brand=brand, anomaly_type=type)
    return ApiResponse(data=rows)
```

- [ ] **Step 4: Register router in main.py**

In `backend/main.py`, add the import and include:

```python
from backend.routers import overview, brands, products, compare, trends, meta, reports, anomalies
```

And after the existing `app.include_router(reports.router, prefix="/api")` line:

```python
app.include_router(anomalies.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd /Users/wei/Desktop/Mercadolibre/backend
python -m pytest tests/test_anomalies_router.py -v
```

Expected: 4 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/anomalies.py backend/main.py backend/tests/test_anomalies_router.py
git commit -m "feat: add anomalies router with detect and latest endpoints"
```

---

## Task 4: Frontend API Client

**Files:**
- Create: `frontend/src/api/anomalies.ts`

- [ ] **Step 1: Create the API client**

Create `frontend/src/api/anomalies.ts`:

```typescript
// frontend/src/api/anomalies.ts
import { api, unwrap } from './client'

export interface AnomalyAlert {
  id: number
  detected_at: string
  product_id: string
  brand: string
  anomaly_type: 'sales_amount' | 'sales_volume' | 'price' | 'bsr'
  current_value: number
  baseline_value: number
  change_pct: number
  threshold_pct: number
  direction: 'up' | 'down'
}

export interface DetectResult {
  detected: number
  detected_at: string
}

export interface DetectParams {
  sales_amount_threshold: number
  sales_volume_threshold: number
  price_threshold: number
  bsr_threshold: number
}

export function detectAnomalies(params: DetectParams): Promise<DetectResult> {
  return unwrap<DetectResult>(api.post('/anomalies/detect', params))
}

export function fetchLatestAnomalies(
  brand?: string,
  type?: string,
): Promise<AnomalyAlert[]> {
  return unwrap<AnomalyAlert[]>(
    api.get('/anomalies/latest', { params: { brand, type } }),
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/api/anomalies.ts
git commit -m "feat: add anomalies API client"
```

---

## Task 5: Anomalies Frontend Page

**Files:**
- Create: `frontend/src/pages/Anomalies.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: Create the Anomalies page**

Create `frontend/src/pages/Anomalies.tsx`:

```tsx
// frontend/src/pages/Anomalies.tsx
import { useState } from 'react'
import {
  Button, InputNumber, Form, Table, Tag, Space,
  Select, Typography, Spin, Alert,
} from 'antd'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  detectAnomalies, fetchLatestAnomalies,
  type AnomalyAlert, type DetectParams,
} from '../api/anomalies'

const { Text } = Typography

const TYPE_LABELS: Record<string, string> = {
  sales_amount: '销售额突变',
  sales_volume: '销量突变',
  price:        '价格异常',
  bsr:          'BSR变化',
}

const BRAND_OPTIONS = ['Blackview', 'Cubot', 'Ulefone', 'Doogee'].map(b => ({
  label: b, value: b,
}))

const TYPE_OPTIONS = Object.entries(TYPE_LABELS).map(([v, l]) => ({
  label: l, value: v,
}))

export default function Anomalies() {
  const qc = useQueryClient()
  const [filterBrand, setFilterBrand] = useState<string | undefined>()
  const [filterType, setFilterType] = useState<string | undefined>()
  const [lastResult, setLastResult] = useState<{ detected: number; detected_at: string } | null>(null)

  const { data: rows = [], isLoading } = useQuery<AnomalyAlert[]>({
    queryKey: ['anomalies-latest', filterBrand, filterType],
    queryFn: () => fetchLatestAnomalies(filterBrand, filterType),
  })

  const mutation = useMutation({
    mutationFn: (params: DetectParams) => detectAnomalies(params),
    onSuccess: (result) => {
      setLastResult(result)
      qc.invalidateQueries({ queryKey: ['anomalies-latest'] })
    },
  })

  const onDetect = (values: {
    sales_amount_threshold: number
    sales_volume_threshold: number
    price_threshold: number
    bsr_threshold: number
  }) => {
    mutation.mutate({
      sales_amount_threshold: values.sales_amount_threshold / 100,
      sales_volume_threshold: values.sales_volume_threshold / 100,
      price_threshold:        values.price_threshold / 100,
      bsr_threshold:          values.bsr_threshold / 100,
    })
  }

  const columns = [
    { title: '品牌', dataIndex: 'brand', key: 'brand' },
    { title: '商品ID', dataIndex: 'product_id', key: 'product_id' },
    {
      title: '异常类型', dataIndex: 'anomaly_type', key: 'anomaly_type',
      render: (v: string) => TYPE_LABELS[v] ?? v,
    },
    {
      title: '当前值', dataIndex: 'current_value', key: 'current_value',
      render: (v: number) => v.toFixed(2),
    },
    {
      title: '基准值（7天均值）', dataIndex: 'baseline_value', key: 'baseline_value',
      render: (v: number) => v.toFixed(2),
    },
    {
      title: '变化幅度', dataIndex: 'change_pct', key: 'change_pct',
      render: (v: number, r: AnomalyAlert) => (
        <span style={{ color: r.direction === 'up' ? '#cf1322' : '#3f8600', fontWeight: 600 }}>
          {v > 0 ? '+' : ''}{v.toFixed(2)}%
        </span>
      ),
    },
    {
      title: '方向', dataIndex: 'direction', key: 'direction',
      render: (v: string) => (
        <Tag color={v === 'up' ? 'red' : 'green'}>{v === 'up' ? '上涨' : '下跌'}</Tag>
      ),
    },
  ]

  return (
    <div>
      <Form
        layout="inline"
        initialValues={{
          sales_amount_threshold: 30,
          sales_volume_threshold: 30,
          price_threshold: 20,
          bsr_threshold: 30,
        }}
        onFinish={onDetect}
        style={{ marginBottom: 16, background: '#fff', padding: 16, borderRadius: 8 }}
      >
        <Form.Item label="销售额阈值%" name="sales_amount_threshold">
          <InputNumber min={1} max={200} style={{ width: 80 }} />
        </Form.Item>
        <Form.Item label="销量阈值%" name="sales_volume_threshold">
          <InputNumber min={1} max={200} style={{ width: 80 }} />
        </Form.Item>
        <Form.Item label="价格阈值%" name="price_threshold">
          <InputNumber min={1} max={200} style={{ width: 80 }} />
        </Form.Item>
        <Form.Item label="BSR阈值%" name="bsr_threshold">
          <InputNumber min={1} max={200} style={{ width: 80 }} />
        </Form.Item>
        <Form.Item>
          <Button type="primary" htmlType="submit" loading={mutation.isPending}>
            开始检测
          </Button>
        </Form.Item>
      </Form>

      {lastResult && (
        <Alert
          type="success"
          message={`本次检测发现 ${lastResult.detected} 条异常，检测时间 ${lastResult.detected_at.replace('T', ' ')}`}
          style={{ marginBottom: 16 }}
        />
      )}

      <div style={{ background: '#fff', padding: 16, borderRadius: 8 }}>
        <Space style={{ marginBottom: 12 }}>
          <Select
            allowClear placeholder="筛选品牌"
            options={BRAND_OPTIONS}
            style={{ width: 140 }}
            onChange={setFilterBrand}
          />
          <Select
            allowClear placeholder="筛选类型"
            options={TYPE_OPTIONS}
            style={{ width: 140 }}
            onChange={setFilterType}
          />
        </Space>

        {isLoading ? (
          <Spin />
        ) : (
          <Table
            dataSource={rows}
            columns={columns}
            rowKey="id"
            size="small"
            pagination={{ pageSize: 20 }}
            locale={{ emptyText: '暂无异常数据，请先运行检测' }}
          />
        )}
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add route in App.tsx**

In `frontend/src/App.tsx`, add the import:

```typescript
import Anomalies from './pages/Anomalies'
```

And add the route inside `<Routes>` after the `/reports` route:

```tsx
<Route path="/anomalies" element={<Anomalies />} />
```

- [ ] **Step 3: Add sidebar menu item in Layout.tsx**

In `frontend/src/components/Layout.tsx`, add `AlertOutlined` to the import:

```typescript
import {
  DashboardOutlined, UnorderedListOutlined,
  SwapOutlined, RiseOutlined, FileTextOutlined, AlertOutlined
} from '@ant-design/icons'
```

Add the menu item to the `items` array after the `每日报告` entry:

```typescript
{ key: '/anomalies', icon: <AlertOutlined />, label: '异常检测' },
```

- [ ] **Step 4: Build and verify**

```bash
cd /Users/wei/Desktop/Mercadolibre/frontend
npm run build 2>&1 | tail -20
```

Expected: build succeeds with no TypeScript errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Anomalies.tsx frontend/src/App.tsx frontend/src/components/Layout.tsx
git commit -m "feat: add anomaly detection frontend page with configurable thresholds"
```

---

## Task 6: Full Test Suite Verification

**Files:**
- No new files

- [ ] **Step 1: Run all backend tests**

```bash
cd /Users/wei/Desktop/Mercadolibre/backend
python -m pytest tests/ -v
```

Expected: all tests PASS (including existing tests for overview, products, compare, aggregation, llm_report, reports, and the new anomaly tests).

- [ ] **Step 2: Commit if any fixes were needed**

```bash
git add -A
git commit -m "fix: resolve any test regressions after anomaly detection feature"
```
