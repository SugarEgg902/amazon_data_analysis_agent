# 异常检测引擎 Design Spec

## Overview

Build an anomaly detection engine that compares each tracked product's daily snapshot against its 7-day baseline, flags statistically significant deviations across sales amount, sales volume, price, and BSR, and surfaces results in a dedicated frontend page with configurable thresholds.

---

## Data Layer

### New Table: `anomaly_alerts`

```sql
CREATE TABLE anomaly_alerts (
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

### Data Source

- Source table: `product_30d_snapshot` (already populated by daily aggregation)
- Latest date: `SELECT MAX(snapshot_date) FROM product_30d_snapshot`
- Baseline: average of the 7 days prior to the latest date for each `product_id`
- Scope: only the 4 tracked brands — Blackview, Cubot, Ulefone, Doogee

### Anomaly Fields Checked

| Field | anomaly_type | Default threshold |
|-------|-------------|-------------------|
| `revenue` | `sales_amount` | 30% |
| `sales_30d` | `sales_volume` | 30% |
| `price` | `price` | 20% |
| `bsr` | `bsr` | 30% |

Change formula: `change_pct = (current - baseline) / baseline * 100`

A row is flagged when `abs(change_pct) > threshold_pct`.

All anomalies from one detection run share the same `detected_at` timestamp.

---

## Backend

### New File: `backend/analysis/anomaly_detector.py`

Single public function:

```python
def run_anomaly_detection(
    sales_amount_threshold: float = 0.30,
    sales_volume_threshold: float = 0.30,
    price_threshold: float = 0.20,
    bsr_threshold: float = 0.30,
) -> dict:
    # Returns {"detected": int, "detected_at": str (ISO datetime)}
```

Steps:
1. Determine latest `snapshot_date` from `product_30d_snapshot`
2. For each tracked brand product on that date, compute 7-day baseline (avg of 7 prior days)
3. Skip products with fewer than 3 days of prior history (insufficient baseline)
4. For each of the 4 metric fields, compute `change_pct`; if `abs(change_pct) > threshold`, insert a row into `anomaly_alerts`
5. Return count of inserted rows and the `detected_at` timestamp

### New File: `backend/routers/anomalies.py`

**`POST /api/anomalies/detect`**

Request body (all fields optional, fall back to defaults):
```json
{
  "sales_amount_threshold": 0.30,
  "sales_volume_threshold": 0.30,
  "price_threshold": 0.20,
  "bsr_threshold": 0.30
}
```

Response:
```json
{"detected": 12, "detected_at": "2026-05-27T07:30:00"}
```

**`GET /api/anomalies/latest`**

Returns all rows sharing the most recent `detected_at` timestamp.

Query params (all optional):
- `brand` — filter by brand name
- `type` — filter by `anomaly_type`

Response: list of anomaly objects with all table fields.

### Register in `backend/main.py`

Add `anomalies` router with prefix `/api/anomalies`.

---

## Frontend

### New Page: `frontend/src/pages/Anomalies.tsx`

Route: `/anomalies`

**Section 1 — Configuration Panel (top)**

Four `InputNumber` fields for threshold percentages:
- 销售额阈值 (default 30)
- 销量阈值 (default 30)
- 价格阈值 (default 20)
- BSR阈值 (default 30)

A「开始检测」button that calls `POST /api/anomalies/detect`. Button shows loading state during the request.

**Section 2 — Result Summary (shown after detection)**

Text line: `本次检测发现 N 条异常，检测时间 YYYY-MM-DD HH:mm`

**Section 3 — Anomaly Table**

Calls `GET /api/anomalies/latest` on page load and after each detection run.

Columns:
- 品牌
- 商品ID
- 异常类型 (mapped to Chinese: 销售额突变 / 销量突变 / 价格异常 / BSR变化)
- 当前值
- 基准值（7天均值）
- 变化幅度 — colored: red for `up`, green for `down`
- 方向 — 上涨 / 下跌

Filter bar above table: brand selector + anomaly type selector (both optional, client-side filter).

### Sidebar Update: `frontend/src/components/Layout.tsx`

Add menu item「异常检测」with `AlertOutlined` icon, linking to `/anomalies`.

---

## Constraints

- Only 4 tracked brands: Blackview, Cubot, Ulefone, Doogee
- Products with fewer than 3 days of prior snapshot history are skipped (no reliable baseline)
- Each detection run is independent; old runs are preserved in `anomaly_alerts` (queryable by `detected_at`)
- No scheduled job — detection is always manually triggered from the frontend
