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

# Re-run aggregation for a date
backend/venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from datetime import date
from backend.aggregation.product_snapshot import run_product_snapshot
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
d = date(2026, 6, 2)
run_product_snapshot(d); run_brand_summary(d); run_category_summary(d)
"
```

## Architecture

Amazon multi-site competitive analysis platform. OUKITEL is our product; Blackview, Ulefone, CUBOT, DOOGEE are competitors. Data sourced from 影刀 RPA + 卖家精灵 across 9 Amazon markets.

### Backend (FastAPI + MySQL)

- `run.py` — CWD-independent launcher, injects repo root onto sys.path
- `backend/main.py` — FastAPI app, mounts routers, starts APScheduler
- `backend/routers/` — API endpoints: overview, products, compare, brands, anomalies, reports, sales, meta
- `backend/aggregation/` — Daily ETL: product_snapshot, brand_summary, category_summary (all apply USD FX conversion)
- `backend/analysis/` — anomaly_detector (7-day baseline z-score), llm_report (calls local Gemma model)
- `backend/constants.py` — FOCUS_BRANDS, FX_TO_USD rates, PHONE_LEAF_REGEX, canonical_brand()
- `backend/scheduler.py` — APScheduler runs aggregation + anomaly detection daily

### Frontend (React + Vite + Ant Design + ECharts)

- `frontend/src/pages/` — Overview, ProductList, Compare, Trends, Anomalies, Reports, SalesAnalysis
- `frontend/src/components/` — Layout (fixed sidebar), TrendChart, PieChart
- `frontend/src/theme/brands.ts` — per-brand colors, gradients, intros
- `frontend/src/context/MarketContext.tsx` — global market selector state

### Database (MySQL 8.0, `amazon_db`)

Tables: `amazon` (raw crawl data), `product_daily_snapshot`, `daily_brand_summary`, `daily_category_summary`, `anomaly_alerts`, `daily_analysis_reports`

## Key Domain Rules

1. **Variant dedup**: `monthly_sales` and `monthly_revenue` are parent-listing-level metrics copied to every variant row. Aggregate once per `(parent_asin, market)` family — never sum across variants within a family. Price/rating vary per variant and should be averaged.

2. **USD conversion**: Raw prices are in local currency (JPY/EUR/GBP/MXN/CAD). All monetary aggregation must apply `fx_case_sql()` from constants.py before cross-market summation.

3. **Phone category filter**: `category_path` is localized per market. Use `PHONE_LEAF_REGEX` matched against the leaf segment only (`SUBSTRING_INDEX(category_path, ':', -1)`) to identify phones without catching accessories. Requires `COLLATE utf8mb4_unicode_ci` for regex compatibility.

4. **Brand casing**: Database has mixed casing (Blackview, DOOGEE, CUBOT, Cubot). Always filter with `LOWER(brand) IN (...)` and normalize display names via `canonical_brand()`.

5. **OUKITEL first**: OUKITEL is our brand — sort it to position 0 in all brand lists/cards.

## Configuration

- `DATABASE_URL` env var (default: `mysql+pymysql://root:rootroot@localhost/amazon_db`)
- `ANALYSIS_LLM_BASE_URL` (default: `http://10.0.0.21:8005/v1`)
- `ANALYSIS_LLM_MODEL` (default: `gemma-4-31b-it-fp8`)
- Frontend dev proxy: `/api` → `http://localhost:8001` (vite.config.ts)
