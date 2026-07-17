# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Backend - run dev server (port 1332, auto-reload)
python run.py --reload

# Backend - run tests
backend/venv/bin/python -m pytest

# Backend - run single test
backend/venv/bin/python -m pytest backend/tests/test_api.py::test_overview_default_and_market

# Frontend - dev server (port 8088, proxies /api to localhost:1332)
cd frontend && npm run dev

# Frontend - build
cd frontend && npm run build

# Docker
docker-compose up -d

# Re-run aggregation for a date (4 个聚合阶段 + 日报 LLM)
backend/venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from datetime import date
from backend.aggregation.product_snapshot import run_product_snapshot
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
from backend.aggregation.overview_summary import run_overview_summary
from backend.analysis.llm_report import run_llm_analysis
d = date(2026, 7, 17)
run_product_snapshot(d); run_brand_summary(d); run_category_summary(d)
run_overview_summary(d)
run_llm_analysis(d, 'daily')
"

# 生成周报/月报的 LLM 分析(与日报各自独立,口径不同)
backend/venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from datetime import date
from backend.analysis.llm_report import run_llm_analysis
run_llm_analysis(date(2026, 7, 17), 'weekly')
"

# 手动触发一次钉钉推送(测试用)
curl -X POST "http://localhost:1332/api/reports/push?period=weekly"
```

## Architecture

Amazon 多站点竞品分析平台，聚焦**储能电源赛道**。**OUKITEL** 是我们的品牌；竞品是
**EcoFlow、Bluetti、Jackery、VTOMAN、Anker**（共 6 个 focus 品牌，见 `FOCUS_BRANDS`）。
数据来自 影刀 RPA + 卖家精灵，覆盖 10 个站点（US/UK/DE/FR/ES/IT/CA/JP/IN/MX）。

> 历史包袱：本项目早期是**手机**赛道（竞品为 Blackview/Ulefone/CUBOT/DOOGEE/FOSSiBOT），
> 后整体转向储能。`brand_models` / `daily_model_summary` 两张表，以及
> `aggregation/model_summary.py`、`routers/brands.py` 的型号排名、
> `pages/ModelRanking.tsx`，都是那个时期的遗留——**当前 0 行数据，功能实际未启用**。
> 动这些地方前先确认是否还需要。

### Backend (FastAPI + MySQL)

- `run.py` — CWD 无关的启动器，把仓库根注入 sys.path；绑 `0.0.0.0`（uvicorn 默认只绑
  `127.0.0.1`，会让内网其他设备访问不到）；配置 uvicorn access log 格式
- `backend/main.py` — FastAPI app，挂载路由，启动 APScheduler，挂 `/static/report-charts`
- `backend/constants.py` — `FOCUS_BRANDS` / `FOCUS_BRAND_DISPLAY`、`FX_TO_USD`、
  `STORAGE_LEAF_REGEX`（储能）/ `SOLAR_LEAF_REGEX`（光伏）/ `ACCESSORY_LEAF_REGEX`（配件）、
  `SUB_CATEGORY_ZH`（本地化名→中文标签）、`canonical_brand()`、`normalize_sub_category()`、
  `fx_case_sql()`、`corrected_brand_sql()`（上游会把 OUKITEL 储能商品的 brand 标成第三方
  店铺名，需按 product_title 校正）
- `backend/database.py` — SQLAlchemy `QueuePool(pool_size=10, max_overflow=20)`
- `backend/scheduler.py` — APScheduler：03:00 每日聚合 + 03:30–09:30 每小时补跑 + 启动时补跑；
  钉钉推送 09:00 日报 / 周一 09:05 周报 / 每月 1 号 09:10 月报；
  周报月报的 LLM 分析在推送前一小时（周一 08:00 / 1 号 08:10）单独生成
- `backend/routers/`
  - `overview.py` — 市场总览（读 `daily_overview_summary`，按**单日**读）
  - `brands.py` — 品牌趋势/详情；型号排名（遗留，无数据）
  - `products.py` / `compare.py` / `trends.py` / `anomalies.py` / `sales_analysis.py`
  - `reports.py` — LLM 报告读取（`?period=daily|weekly|monthly`）、报告页图表数据、手动推送
  - `search.py` — 卖家精灵实时搜索，cookie 过期自动重登刷新
  - `meta.py` — 下拉框元数据（读聚合表，不扫 `amazon`）
- `backend/aggregation/` — 每日 ETL，跨站点求和前一律先套 `fx_case_sql()`：
  - `product_snapshot.py` — 每个 `(asin, market)` 的每日快照
  - `brand_summary.py` / `category_summary.py` — 品牌/品类日聚合
  - `overview_summary.py` — **仅储能口径**的总览 + 品类营收 Top10
  - `model_summary.py` — 遗留，无数据
- `backend/analysis/`
  - `report_data.py` — `build_summary(period, date)`：周期内品牌营收/销量/均价/评分 + 品类分布。
    **报告页和钉钉推送共用同一口径**
  - `llm_report.py` — 调内网 Gemma 生成分析，**日报/周报/月报各自独立生成**
  - `report_charts.py` — matplotlib 渲染 PNG 图表
  - `dingtalk_push.py` — 钉钉自定义机器人推送（加签）
  - `anomaly_detector.py` — 7 日基线异常检测
  - `sales_analyzer.py` — 销售分析

### Frontend (React + Vite + Ant Design + ECharts)

- `frontend/src/pages/` — `Overview.tsx`、`BrandDetail.tsx`、`ProductList.tsx`、
  `ProductDetail.tsx`、`Compare.tsx`、`Trends.tsx`、`Anomalies.tsx`、`Reports.tsx`、
  `SalesAnalysis.tsx`、`AmazonSearch.tsx`；`ModelRanking.tsx`（遗留，无数据）
- `frontend/src/theme/brands.ts` — 每个品牌的配色/渐变/简介。`brandTheme()` 内部做小写归一 +
  `ALIASES`，原始名（`ef ecoflow`）和 canonical 名（`EcoFlow`）都认
- `frontend/src/context/MarketContext.tsx` — 全局站点选择器
- `frontend/src/global.css` — 滚动条、`.brand-card-hover`、`.markdown-body`

### Database (MySQL 8.0, `amazon_sellersprite_db`)

| Table | Purpose | 备注 |
|---|---|---|
| `amazon` | 原始爬虫数据 | |
| `product_daily_snapshot` | 去重后的每日快照 | |
| `daily_brand_summary` | 品牌×站点 日聚合 | |
| `daily_category_summary` | 品类×品牌×站点 日聚合 | |
| `daily_overview_summary` | 储能口径总览（品牌级，跨站点已合并） | 一行 = 一品牌一天 |
| `daily_overview_category` | 品类营收 Top10 | `sub_category` 存的是**未归一化的本地化名** |
| `daily_analysis_reports` | LLM 报告 | 唯一键 `(report_date, period)` |
| `anomaly_alerts` | 异常检测结果 | |
| `brand_models` / `daily_model_summary` | 型号排名 | **遗留，0 行** |

**`amazon` 表索引**：`idx_crawl_date_brand`、`idx_crawl_date_asin_market`、`idx_asin`

## Key Domain Rules

1. **变体去重（关键）**：`monthly_sales` / `monthly_revenue` 是**父 listing 级**指标，
   被复制到该家族的每一个变体行。必须按 `(parent_asin, market)` 用 `MAX()` 聚合一次
   ——**绝不能** `SUM()` 跨变体求和。价格/评分是变体级，用 `AVG()`。

2. **美元换算**：原始价格是本地货币（JPY/EUR/GBP/MXN/CAD/INR）。跨站点求和前
   **必须**先套 `fx_case_sql("market")`。

3. **品类必须归一化**：`category_path` 和 `daily_overview_category.sub_category`
   都是**按站点本地化**的——"发电机" / "Outdoor Generators" / "Externe Handyakkus"
   是同一个品类。聚合或展示前先过 `normalize_sub_category()`，
   否则同一品类会被拆成多行、**重复计算**。
   分类判定要匹配**叶子段**（`SUBSTRING_INDEX(category_path, ':', -1)`），
   并加 `COLLATE utf8mb4_unicode_ci` 以兼容正则。

4. **品牌大小写（踩过坑）**：库里同一品牌存在多种大小写（历史 `Anker` / 后来 `anker`，
   `EF ECOFLOW` / `ef ecoflow`）。
   - SQL 侧：`LOWER(brand) IN (...)` 过滤、`GROUP BY LOWER(brand)` 分组
   - **Python 侧：必须用 `brand.lower()` 当 dict key。** MySQL 默认排序规则大小写不敏感，
     `GROUP BY brand` 看着结果是干净的，但 Python dict 是敏感的——
     直接拿原始 brand 当 key 会把一个品牌拆成两条，**指标当场翻倍**
   - 展示：一律过 `canonical_brand()`

5. **OUKITEL 优先**：OUKITEL 是我们的品牌——在所有品牌列表/卡片里排到第 0 位。

6. **预聚合优先**：面向用户的查询读预聚合表（`daily_*`）或走索引列，绝不全表扫 `amazon`。

## 钉钉推送

`backend/analysis/dingtalk_push.py`，自定义机器人**加签模式**，`msgtype: markdown`。

**表格可以用**（数据区块都用表格排版）。注意官方文档的"支持的 Markdown 语法子集"
清单里**没有表格**，但真机实测能正常渲染——那份清单不完整，别拿它当"不支持"的依据。
要确认某个语法行不行，发一条探测消息到群里实测最快
（限流：每个机器人每分钟最多 20 条，超了封 10 分钟）。

**换行必须用行尾两个空格**：单个 `\n` 在 markdown 里是软换行、会渲染成空格，
整份报告会挤成一大段。`_compose()` 用 `"  \n".join(lines)`。

**图表是硬限制**：钉钉自定义机器人只有 text/link/markdown/actionCard/feedCard 五种消息，
图片**只能给 URL**，不支持 base64、不支持附件上传。而且去拉图的**不是查看者本人**
——私有地址（`10.x` / `192.168.x`）无论绑不绑 `0.0.0.0`、看的人在不在内网，都拉不到，
嵌进去必然是裂图。所以 `REPORT_EMBED_CHARTS` 默认 `0`（纯文字推送）。
要开图，先把 `PUBLIC_BASE_URL` 指向**公网可访问**的地址
（OSS / 图床 / 内网穿透 / 公网服务器），再设 `REPORT_EMBED_CHARTS=1`。

不要用 `actionCard` + `singleURL`：那样点卡片任意位置都会跳网页，而不是一份报告。

## Configuration

配置集中在 `config/config.py`，每项都可用同名环境变量覆盖：

- `DB_HOST` / `DB_USER` / `DB_PASS` / `DB_NAME`（默认 localhost root / `amazon_sellersprite_db`）
- `ANALYSIS_LLM_BASE_URL`（默认 `http://10.0.0.22:8005/v1`）、
  `ANALYSIS_LLM_MODEL`（默认 `gemma-4-31b-it-fp8`）
- `DINGTALK_ACCESS_TOKEN` / `DINGTALK_SECRET` → 拼出 `DINGTALK_WEBHOOK`
- `REPORT_EMBED_CHARTS`（默认 `0`）、`PUBLIC_BASE_URL`、`REPORT_PAGE_URL`
- `SELLERSPRITE_COOKIE` / `SELLERSPRITE_EMAIL` / `SELLERSPRITE_PASSWORD` / `SELLERSPRITE_SALT`
  （cookie 过期自动刷新）
- 前端 dev 代理：`/api` → `http://localhost:1332`（vite.config.ts）
