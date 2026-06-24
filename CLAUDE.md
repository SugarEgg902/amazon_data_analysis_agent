# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend - run dev server (port 8001, auto-reload)
python run.py --reload

# Backend - run tests
backend/venv/bin/python -m pytest

# Backend - run single test
backend/venv/bin/python -m pytest backend/tests/test_api.py::test_overview_default_and_market

# Frontend - dev server (port 5174, proxies /api to localhost:8001)
cd frontend && npm run dev

# Frontend - build
cd frontend && npm run build

# Docker
docker-compose up -d

# Re-run aggregation for a date (all 5 aggregation stages + LLM report)
backend/venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from datetime import date
from backend.aggregation.product_snapshot import run_product_snapshot
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
from backend.aggregation.overview_summary import run_overview_summary
from backend.aggregation.model_summary import run_model_summary
from backend.analysis.llm_report import run_llm_analysis
d = date(2026, 6, 2)
run_product_snapshot(d); run_brand_summary(d); run_category_summary(d)
run_overview_summary(d); run_model_summary(d); run_llm_analysis(d)
"

# Import competitor model list (after editing backend/brand_model_data_example/amazon_final_models.txt)
backend/venv/bin/python backend/scripts/import_models.py
```

## Architecture

Amazon multi-site competitive analysis platform. **OUKITEL** is our brand; competitors are **Blackview, Ulefone, CUBOT, DOOGEE, FOSSiBOT** (6 focus brands total in `FOCUS_BRANDS`). Data sourced from 影刀 RPA + 卖家精灵 across 8 Amazon markets (US/UK/DE/FR/ES/IT/CA/JP).

### Backend (FastAPI + MySQL)

- `run.py` — CWD-independent launcher, injects repo root onto sys.path; configures uvicorn access log format (timestamp | IP | method path | status | ms)
- `backend/main.py` — FastAPI app, mounts routers, starts APScheduler
- `backend/constants.py` — `FOCUS_BRANDS`, `FX_TO_USD`, `PHONE_LEAF_REGEX` / `TABLET_LEAF_REGEX` / `WATCH_LEAF_REGEX`, `SUB_CATEGORY_ZH` (localized→Chinese labels), `canonical_brand()`, `normalize_sub_category()`, `fx_case_sql()`
- `backend/database.py` — SQLAlchemy `QueuePool(pool_size=10, max_overflow=20)`
- `backend/scheduler.py` — APScheduler: daily aggregation at 03:00 + hourly catch-up 03:30–09:30 + startup catch-up if today's raw data exists but no aggregation
- `backend/routers/`
  - `overview.py` — market overview (all categories, reads `daily_brand_summary`)
  - `brands.py` — brand trend, brand detail (summary/trend/category_cards/market_distribution/top_products), **model ranking** (`/brands/{brand}/models?type=手机`)
  - `products.py` — list with multi-category filter + summary aggregation
  - `compare.py`, `trends.py`, `anomalies.py`, `reports.py`, `sales_analysis.py`
  - `search.py` — 卖家精灵 real-time search with **auto cookie refresh** (POST login when session expires)
  - `meta.py` — markets/brands/categories dropdowns (reads aggregated tables, not raw `amazon`)
- `backend/aggregation/` — daily ETL, all apply `fx_case_sql()` before cross-market sum:
  - `product_snapshot.py` — per-`(asin,market)` daily snapshot
  - `brand_summary.py`, `category_summary.py` — brand/category daily aggregates
  - `overview_summary.py` — phone-only overview + category revenue Top 10
  - `model_summary.py` — per-model×market sales, matches `product_title LIKE '%model%'` against `brand_models` table
- `backend/analysis/` — `anomaly_detector.py` (7-day baseline), `llm_report.py` (calls local Gemma model)
- `backend/scripts/import_models.py` — parses `brand_model_data_example/amazon_final_models.txt`, splits `/`-separated composite models

### Frontend (React + Vite + Ant Design + ECharts)

- `frontend/src/pages/`
  - `Overview.tsx` — brand cards (clickable→brand detail), 7d/30d/90d/180d/365d trend switcher, category revenue pie
  - `BrandDetail.tsx` — brand header with all-category summary, **4 category cards** (手机/平板/手表/其他); 手机/平板 cards are clickable → model ranking
  - `ModelRanking.tsx` — left: model ranking table; right: per-market bar chart + market share breakdown
  - `ProductList.tsx`, `Compare.tsx`, `Trends.tsx`, `Anomalies.tsx`, `Reports.tsx`, `SalesAnalysis.tsx`, `AmazonSearch.tsx` (卖家精灵 only)
- `frontend/src/theme/brands.ts` — per-brand colors/gradients/intros
- `frontend/src/context/MarketContext.tsx` — global market selector
- `frontend/src/global.css` — scrollbar styling, `.brand-card-hover` animation, `.markdown-body` report styles

### Database (MySQL 8.0, `amazon_db`)

| Table | Purpose | Daily growth |
|---|---|---|
| `amazon` | raw crawl data | ~1300 rows |
| `product_daily_snapshot` | deduplicated daily snapshot | ~1000 |
| `daily_brand_summary` | brand×market daily aggregate | ~50 |
| `daily_category_summary` | category×brand×market daily | ~400 |
| `daily_overview_summary` | phone-only overview | ~6 |
| `daily_overview_category` | category revenue Top 10 | ~10 |
| `daily_model_summary` | model×market daily sales | ~1600 |
| `brand_models` | static model list (239 rows) | manual updates |
| `daily_analysis_reports` | LLM daily report | 1 |
| `anomaly_alerts` | anomaly detection results | on-demand |

**`amazon` table indexes** (handle data growth to 1-2M rows):
- `idx_crawl_date_brand (crawl_date, brand)` — brand aggregation, detail pages
- `idx_crawl_date_asin_market (crawl_date, asin, market)` — Products list JOIN
- `idx_asin (asin)` — product detail

## Key Domain Rules

1. **Variant dedup (CRITICAL)**: `monthly_sales` / `monthly_revenue` are **parent-listing-level** metrics copied to every variant row. Always aggregate once per `(parent_asin, market)` family via `MAX()` — never `SUM()` across variants in a family. Price/rating are variant-level and should be `AVG()`.

2. **USD conversion**: Raw prices are local currency (JPY/EUR/GBP/MXN/CAD). All monetary aggregation **must** apply `fx_case_sql("market")` from constants.py before cross-market summation.

3. **Phone category filter**: `category_path` is localized per market. Match `PHONE_LEAF_REGEX` / `TABLET_LEAF_REGEX` / `WATCH_LEAF_REGEX` against the **leaf segment only** (`SUBSTRING_INDEX(category_path, ':', -1)`) with `COLLATE utf8mb4_unicode_ci` for regex compatibility. Bucket order in detail page: 手机 → 平板 → 手表 → 其他.

4. **Brand casing**: DB has mixed casing (Blackview/DOOGEE/CUBOT/Cubot, Oukitel/OUKITEL). Always filter with `LOWER(brand) IN (...)` and normalize display via `canonical_brand()`.

5. **OUKITEL first**: OUKITEL is our brand — sort it to position 0 in all brand lists/cards.

6. **Pre-aggregation over real-time**: User-facing queries read from pre-aggregated tables (`daily_*`) or indexed columns, never full-scan `amazon`. Aggregation runs once daily at 03:00.

## Configuration

- `DB_HOST` / `DB_USER` / `DB_PASS` / `DB_NAME` env vars (default: localhost root / `amazon_db`)
- `ANALYSIS_LLM_BASE_URL` (default: `http://10.0.0.21:8005/v1`)
- `ANALYSIS_LLM_MODEL` (default: `gemma-4-31b-it-fp8`)
- 卖家精灵 cookie: stored in `config/config.py` `SELLERSPRITE_COOKIE` (auto-refreshed on expiry)
- Frontend dev proxy: `/api` → `http://localhost:8001` (vite.config.ts)
