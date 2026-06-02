# MercadoLibre 竞品分析平台 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建一个面向团队的 MercadoLibre 竞品数据分析平台，支持选品、竞品监控、市场全局分析三大场景。

**Architecture:** FastAPI 后端提供 REST API 并托管 React 静态文件；MySQL 存储原始商品数据和三张预聚合表；APScheduler 每日触发聚合计算；Docker Compose 两容器部署。

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy (Core), APScheduler, pytest / React 18, Vite, TypeScript, Ant Design, ECharts (echarts-for-react), React Query, Axios / MySQL 8, Docker Compose

---

## Task 1: 数据库迁移 — 创建聚合表

**Files:**
- Create: `db/migrations/001_create_aggregation_tables.sql`

- [ ] **Step 1: 编写 SQL 迁移文件**

```sql
-- db/migrations/001_create_aggregation_tables.sql

CREATE TABLE IF NOT EXISTS daily_brand_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_date DATE NOT NULL,
    brand VARCHAR(255) NOT NULL,
    product_count INT DEFAULT 0,
    total_revenue DECIMAL(18,2) DEFAULT 0,
    total_sales_30d BIGINT DEFAULT 0,
    avg_price DECIMAL(10,2) DEFAULT 0,
    avg_rating DECIMAL(3,2) DEFAULT 0,
    avg_growth_rate DECIMAL(10,4) DEFAULT 0,
    UNIQUE KEY uq_date_brand (data_date, brand)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS daily_category_summary (
    id INT AUTO_INCREMENT PRIMARY KEY,
    data_date DATE NOT NULL,
    sub_category VARCHAR(255) NOT NULL,
    brand VARCHAR(255) NOT NULL,
    product_count INT DEFAULT 0,
    total_revenue DECIMAL(18,2) DEFAULT 0,
    total_sales_30d BIGINT DEFAULT 0,
    avg_price DECIMAL(10,2) DEFAULT 0,
    UNIQUE KEY uq_date_cat_brand (data_date, sub_category, brand)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS product_30d_snapshot (
    id INT AUTO_INCREMENT PRIMARY KEY,
    snapshot_date DATE NOT NULL,
    product_id VARCHAR(100) NOT NULL,
    brand VARCHAR(255),
    price DECIMAL(10,2),
    sales_30d BIGINT,
    revenue DECIMAL(18,2),
    bsr INT,
    review_count INT,
    review_rating DECIMAL(3,2),
    growth_rate DECIMAL(10,4),
    UNIQUE KEY uq_snapshot_product (snapshot_date, product_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

- [ ] **Step 2: 在数据库中执行迁移**

```bash
mysql -h localhost -u root -prootroot shadowcraw_db < db/migrations/001_create_aggregation_tables.sql
```

Expected: 无报错，三张表创建成功。

- [ ] **Step 3: 验证表已创建**

```bash
mysql -h localhost -u root -prootroot shadowcraw_db -e "SHOW TABLES;"
```

Expected: 输出包含 `daily_brand_summary`、`daily_category_summary`、`product_30d_snapshot`。

- [ ] **Step 4: Commit**

```bash
git init
git add db/
git commit -m "feat: add aggregation table migrations"
```

---

## Task 2: 后端基础 — 项目结构、依赖、数据库连接

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/database.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 创建 requirements.txt**

```
fastapi==0.111.0
uvicorn[standard]==0.29.0
sqlalchemy==2.0.30
pymysql==1.1.1
apscheduler==3.10.4
pydantic==2.7.1
pytest==8.2.0
pytest-asyncio==0.23.6
httpx==0.27.0
python-dotenv==1.0.1
```

- [ ] **Step 2: 安装依赖**

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Expected: 所有包安装成功，无报错。

- [ ] **Step 3: 编写 database.py**

```python
# backend/database.py
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

DB_URL = "mysql+pymysql://root:rootroot@localhost/shadowcraw_db?charset=utf8mb4"

engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

def get_connection():
    return engine.connect()
```

- [ ] **Step 4: 编写 conftest.py**

```python
# backend/tests/conftest.py
import pytest
from sqlalchemy import create_engine, text
from backend.database import engine

@pytest.fixture(scope="session")
def db():
    with engine.connect() as conn:
        yield conn
```

- [ ] **Step 5: 写失败测试验证数据库连接**

```python
# backend/tests/test_database.py
from sqlalchemy import text
from backend.database import engine

def test_database_connection():
    with engine.connect() as conn:
        result = conn.execute(text("SELECT 1"))
        assert result.scalar() == 1

def test_products_table_exists():
    with engine.connect() as conn:
        result = conn.execute(text("SHOW TABLES LIKE 'products'"))
        assert result.fetchone() is not None
```

- [ ] **Step 6: 运行测试确认通过**

```bash
cd backend
pytest tests/test_database.py -v
```

Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add backend/requirements.txt backend/database.py backend/tests/
git commit -m "feat: backend project setup and database connection"
```

---

## Task 3: 聚合逻辑 — brand_summary 和 category_summary

**Files:**
- Create: `backend/aggregation/brand_summary.py`
- Create: `backend/aggregation/category_summary.py`
- Create: `backend/tests/test_aggregation.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_aggregation.py
from datetime import date
from sqlalchemy import text
from backend.database import engine
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary

def test_run_brand_summary_inserts_rows():
    target_date = date.today()
    run_brand_summary(target_date)
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM daily_brand_summary WHERE data_date = :d"),
            {"d": target_date}
        )
        assert result.scalar() > 0

def test_run_category_summary_inserts_rows():
    target_date = date.today()
    run_category_summary(target_date)
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM daily_category_summary WHERE data_date = :d"),
            {"d": target_date}
        )
        assert result.scalar() > 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_aggregation.py -v
```

Expected: ImportError 或 ModuleNotFoundError

- [ ] **Step 3: 实现 brand_summary.py**

```python
# backend/aggregation/brand_summary.py
from datetime import date
from sqlalchemy import text
from backend.database import engine

def run_brand_summary(target_date: date) -> None:
    sql = text("""
        INSERT INTO daily_brand_summary
            (data_date, brand, product_count, total_revenue,
             total_sales_30d, avg_price, avg_rating, avg_growth_rate)
        SELECT
            :d,
            brand,
            COUNT(*) AS product_count,
            SUM(CAST(NULLIF(revenue, '') AS DECIMAL(18,2))) AS total_revenue,
            SUM(CAST(NULLIF(sales_30_days, '') AS BIGINT)) AS total_sales_30d,
            AVG(CAST(NULLIF(price, '') AS DECIMAL(10,2))) AS avg_price,
            AVG(CAST(NULLIF(review_rating, '') AS DECIMAL(3,2))) AS avg_rating,
            AVG(CAST(NULLIF(sales_growth_rate, '') AS DECIMAL(10,4))) AS avg_growth_rate
        FROM products
        WHERE data_date = :d
        GROUP BY brand
        ON DUPLICATE KEY UPDATE
            product_count = VALUES(product_count),
            total_revenue = VALUES(total_revenue),
            total_sales_30d = VALUES(total_sales_30d),
            avg_price = VALUES(avg_price),
            avg_rating = VALUES(avg_rating),
            avg_growth_rate = VALUES(avg_growth_rate)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"d": target_date})
```

- [ ] **Step 4: 实现 category_summary.py**

```python
# backend/aggregation/category_summary.py
from datetime import date
from sqlalchemy import text
from backend.database import engine

def run_category_summary(target_date: date) -> None:
    sql = text("""
        INSERT INTO daily_category_summary
            (data_date, sub_category, brand, product_count,
             total_revenue, total_sales_30d, avg_price)
        SELECT
            :d,
            sub_category,
            brand,
            COUNT(*) AS product_count,
            SUM(CAST(NULLIF(revenue, '') AS DECIMAL(18,2))) AS total_revenue,
            SUM(CAST(NULLIF(sales_30_days, '') AS BIGINT)) AS total_sales_30d,
            AVG(CAST(NULLIF(price, '') AS DECIMAL(10,2))) AS avg_price
        FROM products
        WHERE data_date = :d
        GROUP BY sub_category, brand
        ON DUPLICATE KEY UPDATE
            product_count = VALUES(product_count),
            total_revenue = VALUES(total_revenue),
            total_sales_30d = VALUES(total_sales_30d),
            avg_price = VALUES(avg_price)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"d": target_date})
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_aggregation.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/aggregation/ backend/tests/test_aggregation.py
git commit -m "feat: brand and category daily aggregation"
```

---

## Task 4: 聚合逻辑 — product_30d_snapshot

**Files:**
- Create: `backend/aggregation/product_snapshot.py`
- Modify: `backend/tests/test_aggregation.py`

- [ ] **Step 1: 追加失败测试**

在 `backend/tests/test_aggregation.py` 末尾追加：

```python
from backend.aggregation.product_snapshot import run_product_snapshot

def test_run_product_snapshot_inserts_rows():
    target_date = date.today()
    run_product_snapshot(target_date)
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT COUNT(*) FROM product_30d_snapshot WHERE snapshot_date = :d"),
            {"d": target_date}
        )
        assert result.scalar() > 0
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_aggregation.py::test_run_product_snapshot_inserts_rows -v
```

Expected: ImportError

- [ ] **Step 3: 实现 product_snapshot.py**

```python
# backend/aggregation/product_snapshot.py
from datetime import date
from sqlalchemy import text
from backend.database import engine

def run_product_snapshot(target_date: date) -> None:
    sql = text("""
        INSERT INTO product_30d_snapshot
            (snapshot_date, product_id, brand, price, sales_30d,
             revenue, bsr, review_count, review_rating, growth_rate)
        SELECT
            :d,
            product_id,
            brand,
            CAST(NULLIF(price, '') AS DECIMAL(10,2)),
            CAST(NULLIF(sales_30_days, '') AS BIGINT),
            CAST(NULLIF(revenue, '') AS DECIMAL(18,2)),
            CAST(NULLIF(bsr, '') AS UNSIGNED),
            CAST(NULLIF(review_count, '') AS UNSIGNED),
            CAST(NULLIF(review_rating, '') AS DECIMAL(3,2)),
            CAST(NULLIF(sales_growth_rate, '') AS DECIMAL(10,4))
        FROM products
        WHERE data_date = :d
        ON DUPLICATE KEY UPDATE
            price = VALUES(price),
            sales_30d = VALUES(sales_30d),
            revenue = VALUES(revenue),
            bsr = VALUES(bsr),
            review_count = VALUES(review_count),
            review_rating = VALUES(review_rating),
            growth_rate = VALUES(growth_rate)
    """)
    with engine.begin() as conn:
        conn.execute(sql, {"d": target_date})
```

- [ ] **Step 4: 运行全部聚合测试**

```bash
pytest tests/test_aggregation.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/aggregation/product_snapshot.py backend/tests/test_aggregation.py
git commit -m "feat: product 30-day snapshot aggregation"
```

---

## Task 5: FastAPI 入口、Schemas、调度器

**Files:**
- Create: `backend/models/schemas.py`
- Create: `backend/scheduler.py`
- Create: `backend/main.py`

- [ ] **Step 1: 创建 schemas.py**

```python
# backend/models/schemas.py
from pydantic import BaseModel
from typing import Any, Optional

class ApiResponse(BaseModel):
    data: Any
    error: Optional[str] = None

class BrandSummary(BaseModel):
    brand: str
    product_count: int
    total_revenue: float
    total_sales_30d: int
    avg_price: float
    avg_rating: float
    avg_growth_rate: float

class ProductRow(BaseModel):
    product_id: str
    product_name: Optional[str]
    brand: Optional[str]
    sub_category: Optional[str]
    price: Optional[float]
    sales_7_days: Optional[int]
    sales_30_days: Optional[int]
    sales_90_days: Optional[int]
    total_sales: Optional[int]
    revenue: Optional[float]
    sales_growth_rate: Optional[float]
    bsr: Optional[int]
    review_count: Optional[int]
    review_rating: Optional[float]
    image_url: Optional[str]
    product_url: Optional[str]
    data_date: Optional[str]

class ProductListResponse(BaseModel):
    items: list[ProductRow]
    total: int
    page: int
    page_size: int
```

- [ ] **Step 2: 创建 scheduler.py**

```python
# backend/scheduler.py
from datetime import date
from apscheduler.schedulers.background import BackgroundScheduler
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
from backend.aggregation.product_snapshot import run_product_snapshot

def run_daily_aggregation():
    today = date.today()
    run_brand_summary(today)
    run_category_summary(today)

def run_monthly_snapshot():
    today = date.today()
    run_product_snapshot(today)

def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_daily_aggregation, "cron", hour=2, minute=0)
    scheduler.add_job(run_monthly_snapshot, "cron", day=1, hour=3, minute=0)
    scheduler.start()
    return scheduler
```

- [ ] **Step 3: 创建 main.py**

```python
# backend/main.py
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from backend.scheduler import start_scheduler
from backend.routers import overview, brands, products, compare, trends, meta

scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    scheduler = start_scheduler()
    yield
    scheduler.shutdown()

app = FastAPI(title="MercadoLibre Analytics", lifespan=lifespan)

app.include_router(overview.router, prefix="/api")
app.include_router(brands.router, prefix="/api")
app.include_router(products.router, prefix="/api")
app.include_router(compare.router, prefix="/api")
app.include_router(trends.router, prefix="/api")
app.include_router(meta.router, prefix="/api")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if os.path.exists(STATIC_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(STATIC_DIR, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(os.path.join(STATIC_DIR, "index.html"))
```

- [ ] **Step 4: 验证 FastAPI 启动**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Expected: `Application startup complete.` 无报错，访问 `http://localhost:8000/docs` 可见 Swagger UI。

- [ ] **Step 5: Commit**

```bash
git add backend/models/ backend/scheduler.py backend/main.py
git commit -m "feat: fastapi app entry, schemas, and scheduler"
```

---

## Task 6: API 路由 — meta、overview、brands

**Files:**
- Create: `backend/routers/meta.py`
- Create: `backend/routers/overview.py`
- Create: `backend/routers/brands.py`
- Create: `backend/tests/test_overview.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_overview.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_meta_brands_returns_list():
    r = client.get("/api/meta/brands")
    assert r.status_code == 200
    body = r.json()
    assert "data" in body
    assert isinstance(body["data"], list)

def test_meta_categories_returns_list():
    r = client.get("/api/meta/categories")
    assert r.status_code == 200
    assert isinstance(r.json()["data"], list)

def test_overview_returns_brand_summaries():
    r = client.get("/api/overview")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "brands" in data

def test_brands_trend_returns_series():
    r = client.get("/api/brands/trend?days=30")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "dates" in data
    assert "series" in data
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_overview.py -v
```

Expected: ImportError 或 404

- [ ] **Step 3: 实现 meta.py**

```python
# backend/routers/meta.py
from fastapi import APIRouter
from sqlalchemy import text
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()

@router.get("/meta/brands", response_model=ApiResponse)
def get_brands():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT brand FROM products WHERE brand IS NOT NULL ORDER BY brand"))
        return ApiResponse(data=[r[0] for r in rows])

@router.get("/meta/categories", response_model=ApiResponse)
def get_categories():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT DISTINCT sub_category FROM products WHERE sub_category IS NOT NULL ORDER BY sub_category"))
        return ApiResponse(data=[r[0] for r in rows])
```

- [ ] **Step 4: 实现 overview.py**

```python
# backend/routers/overview.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from datetime import date
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()

@router.get("/overview", response_model=ApiResponse)
def get_overview(target_date: date = Query(default=None)):
    if target_date is None:
        target_date = date.today()
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT brand, product_count, total_revenue, total_sales_30d,
                       avg_price, avg_rating, avg_growth_rate
                FROM daily_brand_summary WHERE data_date = :d
            """),
            {"d": target_date}
        ).mappings().all()
        category_rows = conn.execute(
            text("""
                SELECT sub_category, SUM(total_revenue) as revenue
                FROM daily_category_summary WHERE data_date = :d
                GROUP BY sub_category ORDER BY revenue DESC LIMIT 10
            """),
            {"d": target_date}
        ).mappings().all()
    return ApiResponse(data={
        "date": str(target_date),
        "brands": [dict(r) for r in rows],
        "category_share": [dict(r) for r in category_rows],
    })
```

- [ ] **Step 5: 实现 brands.py**

```python
# backend/routers/brands.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()

@router.get("/brands/trend", response_model=ApiResponse)
def get_brands_trend(days: int = Query(default=30, ge=7, le=90)):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT data_date, brand, total_sales_30d
                FROM daily_brand_summary
                WHERE data_date >= DATE_SUB(CURDATE(), INTERVAL :days DAY)
                ORDER BY data_date, brand
            """),
            {"days": days}
        ).mappings().all()
    dates = sorted(set(str(r["data_date"]) for r in rows))
    brands = sorted(set(r["brand"] for r in rows))
    series = {b: [] for b in brands}
    lookup = {(str(r["data_date"]), r["brand"]): r["total_sales_30d"] for r in rows}
    for d in dates:
        for b in brands:
            series[b].append(lookup.get((d, b), 0))
    return ApiResponse(data={"dates": dates, "series": series})
```

- [ ] **Step 6: 运行测试确认通过**

```bash
pytest tests/test_overview.py -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add backend/routers/meta.py backend/routers/overview.py backend/routers/brands.py backend/tests/test_overview.py
git commit -m "feat: meta, overview, and brands trend API routes"
```

---

## Task 7: API 路由 — products（列表 + 详情）

**Files:**
- Create: `backend/routers/products.py`
- Create: `backend/tests/test_products.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_products.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_product_list_returns_paginated():
    r = client.get("/api/products?page=1&page_size=20")
    assert r.status_code == 200
    body = r.json()["data"]
    assert "items" in body
    assert "total" in body
    assert "page" in body
    assert len(body["items"]) <= 20

def test_product_list_filter_by_brand():
    r = client.get("/api/products?page=1&page_size=10&brand=TestBrand")
    assert r.status_code == 200

def test_product_detail_returns_product():
    # 先取一个真实 product_id
    list_r = client.get("/api/products?page=1&page_size=1")
    items = list_r.json()["data"]["items"]
    if not items:
        return  # 无数据时跳过
    pid = items[0]["product_id"]
    r = client.get(f"/api/products/{pid}")
    assert r.status_code == 200
    assert r.json()["data"]["product_id"] == pid

def test_product_detail_404_for_unknown():
    r = client.get("/api/products/nonexistent_id_xyz")
    assert r.status_code == 404
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_products.py -v
```

Expected: 404 on all routes

- [ ] **Step 3: 实现 products.py**

```python
# backend/routers/products.py
from fastapi import APIRouter, Query, HTTPException
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()

@router.get("/products", response_model=ApiResponse)
def list_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    brand: Optional[str] = None,
    category: Optional[str] = None,
    sort: Optional[str] = Query(default="sales_30_days", regex="^(sales_30_days|price|bsr|review_rating|sales_growth_rate)$"),
    order: Optional[str] = Query(default="desc", regex="^(asc|desc)$"),
):
    filters = ["1=1"]
    params: dict = {"limit": page_size, "offset": (page - 1) * page_size}
    if brand:
        filters.append("brand = :brand")
        params["brand"] = brand
    if category:
        filters.append("sub_category = :category")
        params["category"] = category
    where = " AND ".join(filters)
    sort_col = f"CAST(NULLIF({sort}, '') AS DECIMAL(18,4))"
    with engine.connect() as conn:
        total = conn.execute(
            text(f"SELECT COUNT(*) FROM products WHERE {where}"), params
        ).scalar()
        rows = conn.execute(
            text(f"""
                SELECT product_id, product_name, brand, sub_category, price,
                       sales_7_days, sales_30_days, sales_90_days, total_sales,
                       revenue, sales_growth_rate, bsr, review_count, review_rating,
                       image_url, product_url, data_date
                FROM products WHERE {where}
                ORDER BY {sort_col} {order.upper()}
                LIMIT :limit OFFSET :offset
            """),
            params
        ).mappings().all()
    return ApiResponse(data={"items": [dict(r) for r in rows], "total": total, "page": page, "page_size": page_size})

@router.get("/products/{product_id}", response_model=ApiResponse)
def get_product(product_id: str):
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT * FROM products WHERE product_id = :pid
                ORDER BY data_date DESC
            """),
            {"pid": product_id}
        ).mappings().all()
    if not rows:
        raise HTTPException(status_code=404, detail="Product not found")
    latest = dict(rows[0])
    history = [{"data_date": str(r["data_date"]), "price": r["price"],
                "sales_30_days": r["sales_30_days"], "revenue": r["revenue"],
                "bsr": r["bsr"], "review_count": r["review_count"]} for r in rows]
    return ApiResponse(data={**latest, "history": history})
```

- [ ] **Step 4: 运行测试确认通过**

```bash
pytest tests/test_products.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/routers/products.py backend/tests/test_products.py
git commit -m "feat: products list and detail API routes"
```

---

## Task 8: API 路由 — compare 和 trends

**Files:**
- Create: `backend/routers/compare.py`
- Create: `backend/routers/trends.py`
- Create: `backend/tests/test_compare.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/test_compare.py
from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)

def test_compare_returns_brand_data():
    r = client.get("/api/compare")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "brands" in data

def test_trends_returns_growth_ranking():
    r = client.get("/api/trends")
    assert r.status_code == 200
    data = r.json()["data"]
    assert "growth_ranking" in data
    assert "new_products" in data
```

- [ ] **Step 2: 运行测试确认失败**

```bash
pytest tests/test_compare.py -v
```

Expected: 404 on all routes

- [ ] **Step 3: 实现 compare.py**

```python
# backend/routers/compare.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()

@router.get("/compare", response_model=ApiResponse)
def get_compare(target_date: Optional[str] = None):
    with engine.connect() as conn:
        if target_date:
            date_filter = "WHERE data_date = :d"
            params: dict = {"d": target_date}
        else:
            date_filter = "WHERE data_date = (SELECT MAX(data_date) FROM daily_brand_summary)"
            params = {}
        brands = conn.execute(
            text(f"SELECT * FROM daily_brand_summary {date_filter} ORDER BY total_sales_30d DESC"),
            params
        ).mappings().all()
        top_products = conn.execute(
            text("""
                SELECT brand, product_id, product_name, image_url,
                       CAST(NULLIF(sales_30_days,'') AS BIGINT) AS sales_30d
                FROM products
                WHERE data_date = (SELECT MAX(data_date) FROM products)
                ORDER BY brand, sales_30d DESC
            """)
        ).mappings().all()
    brand_top: dict = {}
    for r in top_products:
        b = r["brand"]
        if b not in brand_top:
            brand_top[b] = []
        if len(brand_top[b]) < 10:
            brand_top[b].append(dict(r))
    return ApiResponse(data={
        "brands": [dict(b) for b in brands],
        "top_products": brand_top,
    })
```

- [ ] **Step 4: 实现 trends.py**

```python
# backend/routers/trends.py
from fastapi import APIRouter, Query
from sqlalchemy import text
from typing import Optional
from backend.database import engine
from backend.models.schemas import ApiResponse

router = APIRouter()

@router.get("/trends", response_model=ApiResponse)
def get_trends(target_date: Optional[str] = None):
    with engine.connect() as conn:
        latest = conn.execute(text("SELECT MAX(data_date) FROM products")).scalar()
        date_val = target_date or str(latest)
        growth = conn.execute(
            text("""
                SELECT product_id, product_name, brand, image_url,
                       CAST(NULLIF(sales_growth_rate,'') AS DECIMAL(10,4)) AS growth_rate,
                       CAST(NULLIF(sales_30_days,'') AS BIGINT) AS sales_30d
                FROM products
                WHERE data_date = :d
                ORDER BY growth_rate DESC
                LIMIT 50
            """),
            {"d": date_val}
        ).mappings().all()
        new_products = conn.execute(
            text("""
                SELECT product_id, product_name, brand, image_url, launch_date,
                       CAST(NULLIF(price,'') AS DECIMAL(10,2)) AS price
                FROM products
                WHERE data_date = :d
                  AND launch_date >= DATE_SUB(:d, INTERVAL 30 DAY)
                ORDER BY launch_date DESC
                LIMIT 50
            """),
            {"d": date_val}
        ).mappings().all()
        cat_trend = conn.execute(
            text("""
                SELECT sub_category, SUM(total_sales_30d) AS total_sales
                FROM daily_category_summary
                WHERE data_date >= DATE_SUB(:d, INTERVAL 30 DAY)
                GROUP BY sub_category
                ORDER BY total_sales DESC
                LIMIT 20
            """),
            {"d": date_val}
        ).mappings().all()
    return ApiResponse(data={
        "date": date_val,
        "growth_ranking": [dict(r) for r in growth],
        "new_products": [dict(r) for r in new_products],
        "category_trends": [dict(r) for r in cat_trend],
    })
```

- [ ] **Step 5: 运行测试确认通过**

```bash
pytest tests/test_compare.py -v
```

Expected: 2 passed

- [ ] **Step 6: 运行全部后端测试**

```bash
pytest tests/ -v
```

Expected: 全部通过，无 FAILED。

- [ ] **Step 7: Commit**

```bash
git add backend/routers/compare.py backend/routers/trends.py backend/tests/test_compare.py
git commit -m "feat: compare and trends API routes"
```

---

## Task 9: 前端初始化 — Vite + React + Ant Design + ECharts

**Files:**
- Create: `frontend/` (Vite 项目)
- Create: `frontend/src/api/client.ts`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/components/Layout.tsx`

- [ ] **Step 1: 初始化 Vite + React + TypeScript 项目**

```bash
cd /Users/wei/Desktop/Mercadolibre
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install
npm install antd @ant-design/icons echarts echarts-for-react
npm install @tanstack/react-query axios
npm install -D @types/node
```

Expected: `frontend/node_modules` 安装完成，`npm run dev` 可以启动。

- [ ] **Step 2: 配置 vite.config.ts（开发时代理 API 请求）**

```typescript
// frontend/vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
    },
  },
  build: {
    outDir: 'dist',
  },
})
```

- [ ] **Step 3: 创建 API client**

```typescript
// frontend/src/api/client.ts
import axios from 'axios'

export const api = axios.create({ baseURL: '/api' })

export function unwrap<T>(promise: Promise<{ data: { data: T } }>): Promise<T> {
  return promise.then(r => r.data.data)
}
```

- [ ] **Step 4: 创建 App.tsx（路由配置）**

```tsx
// frontend/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Layout from './components/Layout'
import Overview from './pages/Overview'
import ProductList from './pages/ProductList'
import ProductDetail from './pages/ProductDetail'
import Compare from './pages/Compare'
import Trends from './pages/Trends'

const qc = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Navigate to="/overview" replace />} />
            <Route path="/overview" element={<Overview />} />
            <Route path="/products" element={<ProductList />} />
            <Route path="/products/:id" element={<ProductDetail />} />
            <Route path="/compare" element={<Compare />} />
            <Route path="/trends" element={<Trends />} />
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```

安装 react-router-dom：

```bash
cd frontend && npm install react-router-dom
```

- [ ] **Step 5: 创建 Layout.tsx（侧边栏导航）**

```tsx
// frontend/src/components/Layout.tsx
import { Layout as AntLayout, Menu } from 'antd'
import { useNavigate, useLocation } from 'react-router-dom'
import {
  DashboardOutlined, UnorderedListOutlined,
  SwapOutlined, RiseOutlined
} from '@ant-design/icons'

const { Sider, Content } = AntLayout

const items = [
  { key: '/overview', icon: <DashboardOutlined />, label: '市场概览' },
  { key: '/products', icon: <UnorderedListOutlined />, label: '商品列表' },
  { key: '/compare', icon: <SwapOutlined />, label: '竞品对比' },
  { key: '/trends', icon: <RiseOutlined />, label: '趋势分析' },
]

export default function Layout({ children }: { children: React.ReactNode }) {
  const nav = useNavigate()
  const { pathname } = useLocation()
  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider theme="dark" width={200}>
        <div style={{ color: '#fff', padding: '16px', fontWeight: 'bold', fontSize: 16 }}>
          ML Analytics
        </div>
        <Menu
          theme="dark" mode="inline"
          selectedKeys={[pathname]}
          items={items}
          onClick={({ key }) => nav(key)}
        />
      </Sider>
      <AntLayout>
        <Content style={{ padding: 24, background: '#f5f5f5', minHeight: '100vh' }}>
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  )
}
```

- [ ] **Step 6: 更新 main.tsx**

```tsx
// frontend/src/main.tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import 'antd/dist/reset.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>
)
```

- [ ] **Step 7: 验证前端启动**

```bash
cd frontend && npm run dev
```

Expected: 浏览器打开 `http://localhost:5173`，可见侧边栏导航，无 console 错误。

- [ ] **Step 8: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold with routing and layout"
```

---

## Task 10: 前端页面 — 市场概览（Overview）

**Files:**
- Create: `frontend/src/pages/Overview.tsx`
- Create: `frontend/src/components/BrandCard.tsx`
- Create: `frontend/src/components/TrendChart.tsx`
- Create: `frontend/src/components/PieChart.tsx`

- [ ] **Step 1: 创建 BrandCard.tsx**

```tsx
// frontend/src/components/BrandCard.tsx
import { Card, Statistic, Row, Col } from 'antd'

interface Props {
  brand: string
  product_count: number
  total_revenue: number
  total_sales_30d: number
  avg_price: number
  avg_rating: number
  avg_growth_rate: number
}

export default function BrandCard(p: Props) {
  return (
    <Card title={p.brand} size="small">
      <Row gutter={8}>
        <Col span={12}><Statistic title="30天销量" value={p.total_sales_30d} /></Col>
        <Col span={12}><Statistic title="总营收" value={p.total_revenue} precision={0} prefix="$" /></Col>
        <Col span={12}><Statistic title="均价" value={p.avg_price} precision={2} prefix="$" /></Col>
        <Col span={12}><Statistic title="平均评分" value={p.avg_rating} precision={2} suffix="/ 5" /></Col>
        <Col span={12}><Statistic title="商品数" value={p.product_count} /></Col>
        <Col span={12}><Statistic title="平均增长率" value={(p.avg_growth_rate * 100).toFixed(1)} suffix="%" /></Col>
      </Row>
    </Card>
  )
}
```

- [ ] **Step 2: 创建 TrendChart.tsx**

```tsx
// frontend/src/components/TrendChart.tsx
import ReactECharts from 'echarts-for-react'

interface Props {
  dates: string[]
  series: Record<string, number[]>
  title?: string
  height?: number
}

export default function TrendChart({ dates, series, title = '', height = 300 }: Props) {
  const option = {
    title: title ? { text: title } : undefined,
    tooltip: { trigger: 'axis' },
    legend: { data: Object.keys(series) },
    xAxis: { type: 'category', data: dates },
    yAxis: { type: 'value' },
    series: Object.entries(series).map(([name, data]) => ({
      name, type: 'line', data, smooth: true,
    })),
  }
  return <ReactECharts option={option} style={{ height }} />
}
```

- [ ] **Step 3: 创建 PieChart.tsx**

```tsx
// frontend/src/components/PieChart.tsx
import ReactECharts from 'echarts-for-react'

interface Props {
  data: { name: string; value: number }[]
  title?: string
  height?: number
}

export default function PieChart({ data, title = '', height = 300 }: Props) {
  const option = {
    title: title ? { text: title, left: 'center' } : undefined,
    tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
    series: [{ type: 'pie', radius: '60%', data }],
  }
  return <ReactECharts option={option} style={{ height }} />
}
```

- [ ] **Step 4: 创建 Overview.tsx**

```tsx
// frontend/src/pages/Overview.tsx
import { DatePicker, Row, Col, Spin, Alert } from 'antd'
import { useQuery } from '@tanstack/react-query'
import dayjs from 'dayjs'
import { api, unwrap } from '../api/client'
import BrandCard from '../components/BrandCard'
import TrendChart from '../components/TrendChart'
import PieChart from '../components/PieChart'
import { useState } from 'react'

export default function Overview() {
  const [date, setDate] = useState<string | null>(null)
  const { data, isLoading, error } = useQuery({
    queryKey: ['overview', date],
    queryFn: () => unwrap(api.get('/overview', { params: date ? { target_date: date } : {} })),
  })
  const { data: trendData } = useQuery({
    queryKey: ['brands-trend'],
    queryFn: () => unwrap(api.get('/brands/trend?days=30')),
  })

  if (isLoading) return <Spin size="large" />
  if (error) return <Alert type="error" message="加载失败" />

  const pieData = (data?.category_share ?? []).map((c: any) => ({
    name: c.sub_category, value: Number(c.revenue),
  }))

  return (
    <div>
      <div style={{ marginBottom: 16 }}>
        <DatePicker onChange={(_, s) => setDate(s as string || null)} />
      </div>
      <Row gutter={16} style={{ marginBottom: 24 }}>
        {(data?.brands ?? []).map((b: any) => (
          <Col key={b.brand} xs={24} sm={12} lg={6}>
            <BrandCard {...b} />
          </Col>
        ))}
      </Row>
      {trendData && (
        <TrendChart dates={trendData.dates} series={trendData.series} title="30天销量趋势" />
      )}
      <PieChart data={pieData} title="品类营收占比" />
    </div>
  )
}
```

- [ ] **Step 5: 验证页面**

启动后端和前端：

```bash
# 终端1
cd backend && uvicorn main:app --reload --port 8000
# 终端2
cd frontend && npm run dev
```

访问 `http://localhost:5173/overview`，确认品牌卡片、折线图、饼图正常渲染，无 console 错误。

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Overview.tsx frontend/src/components/
git commit -m "feat: overview page with brand cards and charts"
```

---

## Task 11: 前端页面 — 商品列表 + 商品详情

**Files:**
- Create: `frontend/src/pages/ProductList.tsx`
- Create: `frontend/src/pages/ProductDetail.tsx`

- [ ] **Step 1: 创建 ProductList.tsx**

```tsx
// frontend/src/pages/ProductList.tsx
import { Table, Select, Input, Row, Col, Image } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
import { api, unwrap } from '../api/client'

export default function ProductList() {
  const nav = useNavigate()
  const [page, setPage] = useState(1)
  const [brand, setBrand] = useState<string | undefined>()
  const [category, setCategory] = useState<string | undefined>()
  const [sort, setSort] = useState('sales_30_days')

  const { data: brands } = useQuery({ queryKey: ['brands'], queryFn: () => unwrap(api.get('/meta/brands')) })
  const { data: cats } = useQuery({ queryKey: ['cats'], queryFn: () => unwrap(api.get('/meta/categories')) })
  const { data, isLoading } = useQuery({
    queryKey: ['products', page, brand, category, sort],
    queryFn: () => unwrap(api.get('/products', { params: { page, page_size: 20, brand, category, sort } })),
  })

  const columns = [
    { title: '图片', dataIndex: 'image_url', render: (u: string) => u ? <Image src={u} width={48} preview={false} /> : '-' },
    { title: '商品名', dataIndex: 'product_name', ellipsis: true },
    { title: '品牌', dataIndex: 'brand' },
    { title: '价格', dataIndex: 'price' },
    { title: '7天销量', dataIndex: 'sales_7_days', sorter: true },
    { title: '30天销量', dataIndex: 'sales_30_days', sorter: true },
    { title: '增长率', dataIndex: 'sales_growth_rate' },
    { title: 'BSR', dataIndex: 'bsr', sorter: true },
    { title: '评分', dataIndex: 'review_rating' },
  ]

  return (
    <div>
      <Row gutter={8} style={{ marginBottom: 16 }}>
        <Col><Select allowClear placeholder="品牌" style={{ width: 140 }} options={(brands ?? []).map((b: string) => ({ value: b, label: b }))} onChange={setBrand} /></Col>
        <Col><Select allowClear placeholder="品类" style={{ width: 200 }} options={(cats ?? []).map((c: string) => ({ value: c, label: c }))} onChange={setCategory} /></Col>
        <Col>
          <Select value={sort} style={{ width: 140 }} onChange={setSort} options={[
            { value: 'sales_30_days', label: '30天销量' },
            { value: 'price', label: '价格' },
            { value: 'bsr', label: 'BSR' },
            { value: 'review_rating', label: '评分' },
            { value: 'sales_growth_rate', label: '增长率' },
          ]} />
        </Col>
      </Row>
      <Table
        rowKey="product_id"
        loading={isLoading}
        columns={columns}
        dataSource={data?.items ?? []}
        pagination={{ current: page, pageSize: 20, total: data?.total ?? 0, onChange: setPage }}
        onRow={r => ({ onClick: () => nav(`/products/${r.product_id}`) })}
        size="small"
      />
    </div>
  )
}
```

- [ ] **Step 2: 创建 ProductDetail.tsx**

```tsx
// frontend/src/pages/ProductDetail.tsx
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Descriptions, Image, Button, Spin, Alert, Row, Col } from 'antd'
import { api, unwrap } from '../api/client'
import TrendChart from '../components/TrendChart'

export default function ProductDetail() {
  const { id } = useParams<{ id: string }>()
  const nav = useNavigate()
  const { data, isLoading, error } = useQuery({
    queryKey: ['product', id],
    queryFn: () => unwrap(api.get(`/products/${id}`)),
  })

  if (isLoading) return <Spin size="large" />
  if (error) return <Alert type="error" message="商品不存在" />

  const history = data?.history ?? []
  const dates = history.map((h: any) => h.data_date)
  const priceSeries = { '价格': history.map((h: any) => Number(h.price) || 0) }
  const salesSeries = { '30天销量': history.map((h: any) => Number(h.sales_30_days) || 0) }

  return (
    <div>
      <Button onClick={() => nav(-1)} style={{ marginBottom: 16 }}>← 返回</Button>
      <Row gutter={24}>
        <Col xs={24} md={6}>
          {data?.image_url && <Image src={data.image_url} width="100%" />}
        </Col>
        <Col xs={24} md={18}>
          <Descriptions bordered size="small" column={2}>
            <Descriptions.Item label="商品名" span={2}>{data?.product_name}</Descriptions.Item>
            <Descriptions.Item label="品牌">{data?.brand}</Descriptions.Item>
            <Descriptions.Item label="品类">{data?.sub_category}</Descriptions.Item>
            <Descriptions.Item label="价格">{data?.price}</Descriptions.Item>
            <Descriptions.Item label="BSR">{data?.bsr}</Descriptions.Item>
            <Descriptions.Item label="评分">{data?.review_rating}</Descriptions.Item>
            <Descriptions.Item label="评论数">{data?.review_count}</Descriptions.Item>
            <Descriptions.Item label="库存">{data?.stock_quantity} ({data?.stock_type})</Descriptions.Item>
            <Descriptions.Item label="转化率">{data?.conversion_rate}</Descriptions.Item>
            <Descriptions.Item label="上架日期">{data?.launch_date}</Descriptions.Item>
          </Descriptions>
        </Col>
      </Row>
      <TrendChart dates={dates} series={priceSeries} title="历史价格" height={250} />
      <TrendChart dates={dates} series={salesSeries} title="30天销量趋势" height={250} />
    </div>
  )
}
```

- [ ] **Step 3: 验证页面**

访问 `http://localhost:5173/products`，确认：
- 筛选器可用，表格分页正常
- 点击行跳转到详情页
- 详情页显示图表和商品信息

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ProductList.tsx frontend/src/pages/ProductDetail.tsx
git commit -m "feat: product list and detail pages"
```

---

## Task 12: 前端页面 — 竞品对比 + 趋势分析

**Files:**
- Create: `frontend/src/pages/Compare.tsx`
- Create: `frontend/src/pages/Trends.tsx`

- [ ] **Step 1: 创建 Compare.tsx**

```tsx
// frontend/src/pages/Compare.tsx
import { Table, Row, Col, Card, Spin, Alert } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '../api/client'

export default function Compare() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['compare'],
    queryFn: () => unwrap(api.get('/compare')),
  })

  if (isLoading) return <Spin size="large" />
  if (error) return <Alert type="error" message="加载失败" />

  const brandCols = [
    { title: '品牌', dataIndex: 'brand' },
    { title: '商品数', dataIndex: 'product_count' },
    { title: '30天销量', dataIndex: 'total_sales_30d', sorter: (a: any, b: any) => a.total_sales_30d - b.total_sales_30d },
    { title: '总营收', dataIndex: 'total_revenue', render: (v: number) => `$${Number(v).toFixed(0)}` },
    { title: '均价', dataIndex: 'avg_price', render: (v: number) => `$${Number(v).toFixed(2)}` },
    { title: '平均增长率', dataIndex: 'avg_growth_rate', render: (v: number) => `${(Number(v) * 100).toFixed(1)}%` },
  ]

  const topCols = [
    { title: '商品名', dataIndex: 'product_name', ellipsis: true },
    { title: '30天销量', dataIndex: 'sales_30d' },
  ]

  return (
    <div>
      <Table rowKey="brand" columns={brandCols} dataSource={data?.brands ?? []} pagination={false} style={{ marginBottom: 24 }} />
      <Row gutter={16}>
        {Object.entries(data?.top_products ?? {}).map(([brand, products]: [string, any]) => (
          <Col key={brand} xs={24} md={12} lg={6} style={{ marginBottom: 16 }}>
            <Card title={`${brand} Top 10`} size="small">
              <Table rowKey="product_id" columns={topCols} dataSource={products} pagination={false} size="small" />
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  )
}
```

- [ ] **Step 2: 创建 Trends.tsx**

```tsx
// frontend/src/pages/Trends.tsx
import { Table, Tabs, Tag, Image, Spin, Alert } from 'antd'
import { useQuery } from '@tanstack/react-query'
import { api, unwrap } from '../api/client'
import PieChart from '../components/PieChart'

export default function Trends() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['trends'],
    queryFn: () => unwrap(api.get('/trends')),
  })

  if (isLoading) return <Spin size="large" />
  if (error) return <Alert type="error" message="加载失败" />

  const growthCols = [
    { title: '#', render: (_: any, __: any, i: number) => i + 1, width: 50 },
    { title: '图片', dataIndex: 'image_url', render: (u: string) => u ? <Image src={u} width={40} preview={false} /> : '-' },
    { title: '商品名', dataIndex: 'product_name', ellipsis: true },
    { title: '品牌', dataIndex: 'brand' },
    { title: '增长率', dataIndex: 'growth_rate', render: (v: number) => <Tag color={v > 0 ? 'green' : 'red'}>{(Number(v) * 100).toFixed(1)}%</Tag> },
    { title: '30天销量', dataIndex: 'sales_30d' },
  ]

  const newCols = [
    { title: '商品名', dataIndex: 'product_name', ellipsis: true },
    { title: '品牌', dataIndex: 'brand' },
    { title: '上架日期', dataIndex: 'launch_date' },
    { title: '价格', dataIndex: 'price', render: (v: number) => `$${Number(v).toFixed(2)}` },
  ]

  const pieData = (data?.category_trends ?? []).map((c: any) => ({
    name: c.sub_category, value: Number(c.total_sales),
  }))

  const items = [
    {
      key: '1', label: '增长率排行',
      children: <Table rowKey="product_id" columns={growthCols} dataSource={data?.growth_ranking ?? []} pagination={{ pageSize: 20 }} size="small" />,
    },
    {
      key: '2', label: '新品追踪',
      children: <Table rowKey="product_id" columns={newCols} dataSource={data?.new_products ?? []} pagination={{ pageSize: 20 }} size="small" />,
    },
    {
      key: '3', label: '品类热度',
      children: <PieChart data={pieData} title="30天品类销量分布" height={400} />,
    },
  ]

  return <Tabs items={items} />
}
```

- [ ] **Step 3: 验证页面**

访问 `http://localhost:5173/compare` 和 `http://localhost:5173/trends`，确认数据正常渲染，无 console 错误。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Compare.tsx frontend/src/pages/Trends.tsx
git commit -m "feat: compare and trends pages"
```

---

## Task 13: Docker Compose 部署

**Files:**
- Create: `backend/Dockerfile`
- Create: `docker-compose.yml`

- [ ] **Step 1: 创建 backend/Dockerfile**

```dockerfile
# backend/Dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# 复制前端构建产物
COPY ../frontend/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 2: 创建 docker-compose.yml**

```yaml
# docker-compose.yml
version: '3.9'

services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootroot
      MYSQL_DATABASE: shadowcraw_db
    volumes:
      - ./data/mysql:/var/lib/mysql
      - ./db/migrations:/docker-entrypoint-initdb.d
    ports:
      - "3306:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "localhost", "-prootroot"]
      interval: 10s
      timeout: 5s
      retries: 5

  fastapi:
    build:
      context: .
      dockerfile: backend/Dockerfile
    ports:
      - "8000:8000"
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      DB_HOST: mysql
```

- [ ] **Step 3: 更新 database.py 支持环境变量**

将 `backend/database.py` 中的 DB_URL 改为：

```python
# backend/database.py
import os
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_URL = f"mysql+pymysql://root:rootroot@{DB_HOST}/shadowcraw_db?charset=utf8mb4"

engine = create_engine(
    DB_URL,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

def get_connection():
    return engine.connect()
```

- [ ] **Step 4: 构建前端并打包**

```bash
cd frontend && npm run build
```

Expected: `frontend/dist/` 目录生成，包含 `index.html` 和 `assets/`。

- [ ] **Step 5: 启动 Docker Compose**

```bash
docker compose up --build -d
```

Expected: 两个容器启动，`docker compose ps` 显示均为 `running`。

- [ ] **Step 6: 验证部署**

```bash
curl http://localhost:8000/api/meta/brands
```

Expected: `{"data": [...], "error": null}`

访问 `http://localhost:8000`，确认前端页面正常加载。

- [ ] **Step 7: Commit**

```bash
git add backend/Dockerfile docker-compose.yml backend/database.py
git commit -m "feat: docker compose deployment"
```

---

## Task 14: ErrorBoundary 和全局错误处理

**Files:**
- Create: `frontend/src/components/ErrorBoundary.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: 创建 ErrorBoundary.tsx**

```tsx
// frontend/src/components/ErrorBoundary.tsx
import React from 'react'
import { Alert, Button } from 'antd'

interface State { hasError: boolean; message: string }

export default class ErrorBoundary extends React.Component<{ children: React.ReactNode }, State> {
  state: State = { hasError: false, message: '' }

  static getDerivedStateFromError(e: Error): State {
    return { hasError: true, message: e.message }
  }

  render() {
    if (this.state.hasError) {
      return (
        <Alert
          type="error"
          message="页面出错"
          description={this.state.message}
          action={<Button onClick={() => this.setState({ hasError: false, message: '' })}>重试</Button>}
        />
      )
    }
    return this.props.children
  }
}
```

- [ ] **Step 2: 在 App.tsx 中包裹路由**

在 `frontend/src/App.tsx` 的 `<Layout>` 内，将 `<Routes>` 包裹在 `<ErrorBoundary>` 中：

```tsx
import ErrorBoundary from './components/ErrorBoundary'

// 在 Layout 内：
<ErrorBoundary>
  <Routes>
    {/* ... 原有路由不变 ... */}
  </Routes>
</ErrorBoundary>
```

- [ ] **Step 3: 验证错误边界**

在任意页面组件中临时 `throw new Error('test')`，确认显示错误提示而非白屏，然后删除测试代码。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ErrorBoundary.tsx frontend/src/App.tsx
git commit -m "feat: error boundary for frontend pages"
```

