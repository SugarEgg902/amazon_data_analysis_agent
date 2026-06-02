# Amazon 竞品分析平台 设计文档

**日期**：2026-06-01
**状态**：待确认

---

## 概述

参照 MercadoLibre 竞品分析平台的架构，面向团队构建一套 **Amazon** 竞品数据分析平台。数据来源为爬虫每日写入 `shadowcraw_db.amazon` 的原始商品数据（当前约 2.4 万行，覆盖 9 个站点）。支持选品、竞品监控、多站点市场分析三大场景。

与 MercadoLibre 的关键差异：

- **多站点**：amazon 表含 US/DE/FR/JP/UK/IT/ES/MX/CA 共 9 个 `market`，所有聚合都需带 market 维度。
- **双 BSR**：同时有 `main_bsr`（大类排名）和 `sub_bsr`（小类排名）。
- **配送/利润维度**：`fulfillment_method`（FBA/FBM/AMZ/NA）、`fba_fee`、`gross_margin`，是 Amazon 选品核心指标。
- **卖家维度**：`seller_location`（大量 CN 卖家）、`buybox_seller`、`seller_count`。
- **销量口径**：只有 `monthly_sales`/`monthly_revenue`，无 7/30/90 天分段。
- **运营标识**：best_seller / amazons_choice / a_plus / video / sp_ads 等布尔旗标。
- **脏数据**：所有指标均为 `varchar`，含货币符号（如 `円`）、`%`、千分位逗号、空串、NULL，聚合时需 `CAST` + `NULLIF` 清洗，转换失败的记录跳过。

---

## 数据库选型决策

**结论：新建专用数据库 `amazon_db`，并已将原始 `amazon` 表迁入 `amazon_db`。**

`shadowcraw_db` 原始现状（迁移前）：

```
shadowcraw_db
├── amazon                       原始爬虫表（24595 行，66 列）   ← 已迁出
├── mercadolibre                 ML 原始表
├── daily_brand_summary          ← 已被 ML 占用
├── daily_category_summary       ← 已被 ML 占用
├── daily_brand_category_summary ← 已被 ML 占用
├── daily_analysis_reports       ← 已被 ML 占用
├── anomaly_alerts               ← 已被 ML 占用
└── sales_analysis_reports       ← 已被 ML 占用
```

选择新建 `amazon_db` 而非复用 `shadowcraw_db` 的理由：

1. **命名冲突**：MercadoLibre 已占用所有通用聚合表名（`daily_brand_summary` 等）。若复用，Amazon 必须给每张表加 `amazon_` 前缀，既丑陋又易错；放进独立库后可沿用干净的标准表名。
2. **数据隔离**：两个产品的分析数据互不干扰，可独立迁移、备份、清库、调优，互不影响对方线上。
3. **schema 差异**：Amazon 的多站点 + 双 BSR + FBA/利润 维度与 ML 的 `products` 结构差异大，强行共库只会让两边的聚合逻辑互相牵制。
4. **原始表已迁入**：原始 `amazon` 表已通过 `RENAME TABLE shadowcraw_db.amazon TO amazon_db.amazon` 迁入本平台库（原子、瞬时、无数据拷贝）。本平台所有读写均在 `amazon_db` 内完成，不再跨库。爬虫侧需将写入目标库改为 `amazon_db.amazon`。

```
amazon_db
  ├── amazon                    原始数据源（24595 行，已迁入）
  ├── daily_brand_summary       每日 站点×品牌 聚合
  ├── daily_category_summary    每日 站点×品类×品牌 聚合
  ├── product_daily_snapshot    每日 商品(asin×market) 快照
  ├── anomaly_alerts            异常检测结果
  ├── daily_analysis_reports    LLM 每日报告
  └── sales_analysis_reports    上传销售文件分析报告
```

---

## 整体架构

```
浏览器 (React SPA)
    ↕ HTTP/JSON
FastAPI（Python，REST API + 静态文件托管）
    ↕
MySQL (同一实例)
  └── amazon_db.*                原始 amazon 表 + 平台聚合 / 报告 / 异常表

APScheduler（内嵌于 FastAPI 进程）
  ├── 每日 02:00 UTC  聚合计算
  └── 每日 02:30 UTC  LLM 日报
```

**部署**：Docker Compose（fastapi + mysql 两容器），团队访问 `http://服务器IP:8000`。

---

## 数据层

### 原始表：amazon_db.amazon（已迁入本平台库）

按 `(asin, market, crawl_date)` 为天然采集粒度。所有指标字段均为 `varchar`，聚合时统一清洗。关键字段：

| 字段 | 说明 | 清洗方式 |
|------|------|----------|
| asin / parent_asin | 商品唯一标识 / 父 ASIN | 直接使用 |
| sku | 卖家 SKU | 直接使用 |
| brand | 品牌 | 直接使用 |
| product_title / product_url / main_image | 标题 / 链接 / 主图 | 直接使用 |
| main_category / sub_category | 大类 / 小类 | 直接使用 |
| main_bsr / sub_bsr | 大类排名 / 小类排名 | `CAST(... AS UNSIGNED)` |
| monthly_sales / monthly_revenue | 月销量 / 月营收 | `CAST(... AS DECIMAL)` |
| monthly_sales_growth_rate | 月销量环比增长率 | `CAST(... AS DECIMAL(10,4))` |
| price / prime_price | 价格 / Prime 价 | 去币种符号后 `CAST` |
| coupon | 优惠券（`5 %` / `10.00` / 空串混杂） | 提取数值，非数值置 NULL |
| rating / rating_count / review_score | 评分 / 评论数 / 评论分 | `CAST`，逗号需 `REPLACE` |
| fba_fee / gross_margin | FBA 费用 / 毛利率 | `CAST(... AS DECIMAL)` |
| fulfillment_method | FBA / FBM / AMZ / NA | 直接使用 |
| seller_count / buybox_seller / seller_location | 卖家数 / BuyBox 卖家 / 卖家地区 | 直接使用 |
| best_seller_flag / amazons_choice_flag / a_plus_flag / video_flag / sp_ads_flag 等 | 运营旗标（`Y` / NULL） | `= 'Y'` 转布尔 |
| launch_date / days_on_market | 上架日期 / 在售天数 | 直接使用 |
| market | 站点（US/DE/FR/JP/UK/IT/ES/MX/CA） | 直接使用 |
| crawl_date | 采集日期 | 聚合按此分组；NULL 行跳过 |

> **清洗注意**：`price`/`coupon` 在 JP/DE 等站点可能含 `円`、`,` 等符号。统一用 `NULLIF(REGEXP_REPLACE(col, '[^0-9.]', ''), '')` 去噪后再 `CAST`，转换失败记录跳过（与 ML 一致）。`crawl_date IS NULL` 的行（约 4763 条）不参与每日聚合。

### 聚合表：daily_brand_summary（站点 × 品牌 × 天）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT AUTO_INCREMENT | 主键 |
| data_date | DATE | 数据日期（= crawl_date） |
| market | VARCHAR(20) | 站点 |
| brand | VARCHAR(100) | 品牌 |
| product_count | INT | 商品数（去重 asin） |
| total_revenue | DECIMAL(18,2) | 月营收合计 |
| total_monthly_sales | BIGINT | 月销量合计 |
| avg_price | DECIMAL(10,2) | 均价 |
| avg_rating | DECIMAL(3,2) | 平均评分 |
| avg_growth_rate | DECIMAL(10,4) | 平均月增长率 |
| avg_gross_margin | DECIMAL(6,4) | 平均毛利率 |
| fba_ratio | DECIMAL(5,4) | FBA 商品占比 |
| UNIQUE KEY | (data_date, market, brand) | 幂等 upsert |

### 聚合表：daily_category_summary（站点 × 品类 × 品牌 × 天）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT AUTO_INCREMENT | 主键 |
| data_date | DATE | 数据日期 |
| market | VARCHAR(20) | 站点 |
| main_category | VARCHAR(100) | 大类 |
| sub_category | VARCHAR(100) | 小类 |
| brand | VARCHAR(100) | 品牌 |
| product_count | INT | 商品数 |
| total_revenue | DECIMAL(18,2) | 月营收合计 |
| total_monthly_sales | BIGINT | 月销量合计 |
| avg_price | DECIMAL(10,2) | 均价 |
| UNIQUE KEY | (data_date, market, sub_category, brand) | 幂等 upsert |

### 快照表：product_daily_snapshot（商品 × 天）

支持商品级历史走势（价格、BSR、销量、评分）与异常检测基线。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT AUTO_INCREMENT | 主键 |
| snapshot_date | DATE | 快照日期 |
| asin | VARCHAR(50) | 商品 ASIN |
| market | VARCHAR(20) | 站点 |
| brand | VARCHAR(100) | 品牌 |
| sub_category | VARCHAR(100) | 小类 |
| price | DECIMAL(10,2) | 价格 |
| monthly_sales | BIGINT | 月销量 |
| monthly_revenue | DECIMAL(18,2) | 月营收 |
| main_bsr | INT | 大类排名 |
| sub_bsr | INT | 小类排名 |
| rating | DECIMAL(3,2) | 评分 |
| rating_count | INT | 评论数 |
| gross_margin | DECIMAL(6,4) | 毛利率 |
| growth_rate | DECIMAL(10,4) | 月增长率 |
| UNIQUE KEY | (snapshot_date, asin, market) | 幂等 upsert |

### 异常表：anomaly_alerts

沿用 ML 设计，新增 `market` 维度，异常类型扩展 `main_bsr` / `sub_bsr`。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | BIGINT AUTO_INCREMENT | 主键 |
| detected_at | DATETIME | 检测批次时间 |
| asin | VARCHAR(50) | 商品 |
| market | VARCHAR(20) | 站点 |
| brand | VARCHAR(100) | 品牌 |
| anomaly_type | ENUM('sales_amount','sales_volume','price','main_bsr','sub_bsr') | 异常类型 |
| current_value | DECIMAL(18,4) | 当前值 |
| baseline_value | DECIMAL(18,4) | 7 天基线均值 |
| change_pct | DECIMAL(10,4) | 变化幅度 |
| threshold_pct | DECIMAL(10,4) | 触发阈值 |
| direction | ENUM('up','down') | 方向 |

### 报告表：daily_analysis_reports / sales_analysis_reports

结构与 ML 设计一致（见 ML LLM 分析、销售分析设计文档），原样复用到 `amazon_db`，仅 `daily_analysis_reports` 的 `report_date` 唯一键可考虑加 `market` 维度（本期暂按全站点汇总，保持单一 `report_date` 唯一键）。

---

## 后端

技术栈与 ML 平台一致：Python 3.11 / FastAPI / SQLAlchemy Core / APScheduler / pytest。

### 数据库连接（backend/database.py）

```python
import os
from sqlalchemy import create_engine
from sqlalchemy.pool import QueuePool

DB_HOST = os.getenv("DB_HOST", "localhost")
# 原始 amazon 表与所有派生表同在 amazon_db，无需跨库
DB_URL = f"mysql+pymysql://root:rootroot@{DB_HOST}/amazon_db?charset=utf8mb4"

engine = create_engine(DB_URL, poolclass=QueuePool, pool_size=10,
                       max_overflow=20, pool_pre_ping=True)
```

聚合 SQL 内：数据源与目标聚合表同在 `amazon_db`，直接 `FROM amazon`，写入对应聚合表，无需库前缀。

### 聚合模块（backend/aggregation/）

- `brand_summary.py` — 按 `crawl_date, market, brand` 分组写 `daily_brand_summary`
- `category_summary.py` — 按 `crawl_date, market, sub_category, brand` 分组写 `daily_category_summary`
- `product_snapshot.py` — 逐 `(asin, market)` 写 `product_daily_snapshot`

每个函数签名 `run_xxx(target_date: date) -> None`，`ON DUPLICATE KEY UPDATE` 实现幂等。脏数据清洗统一封装为 SQL 内联 `CAST(NULLIF(REGEXP_REPLACE(...),'') AS ...)`。

### API 路由（多站点版）

所有列表/概览接口新增可选 `market` 查询参数（默认聚合全站点或选中站点）。

| 接口 | 用途 |
|------|------|
| `GET /api/overview?date=&market=` | 市场概览（按站点的品牌卡片 + 趋势 + 品类占比） |
| `GET /api/brands/trend?days=&market=` | 品牌月销量趋势 |
| `GET /api/products?page=&market=&brand=&category=&fulfillment=&sort=` | 商品列表（分页+多筛选+排序） |
| `GET /api/products/{asin}?market=` | 商品详情 + 历史快照走势 |
| `GET /api/compare?market=&brands=` | 竞品对比 + 各品牌 Top 10 |
| `GET /api/trends?date=&market=` | 增长榜 / 新品追踪 / 品类热度 |
| `GET /api/anomalies/detect` `POST` | 触发异常检测 |
| `GET /api/anomalies/latest?market=&brand=&type=` | 最新异常 |
| `GET /api/reports?date=` `/latest` | LLM 日报 |
| `POST /api/sales-analysis/upload`、`GET .../history`、`GET .../reports/{id}` | 销售文件分析 |
| `GET /api/meta/markets` | 站点列表（筛选器用，新增） |
| `GET /api/meta/brands?market=` | 品牌列表 |
| `GET /api/meta/categories?market=` | 品类列表 |

统一响应结构：`{ "data": ..., "error": null }`。

---

## 前端

技术栈与 ML 一致：React 18 + Vite + TS + Ant Design + ECharts + React Query。

页面结构在 ML 五页基础上做 Amazon 适配：

1. **市场概览** — 顶部新增**站点切换器**（Select），品牌核心指标卡（月销量、月营收、均价、评分、毛利率、FBA 占比）、月销量趋势折线、品类营收占比饼图。
2. **商品列表** — 列：主图、标题、品牌、站点、价格、月销量、增长率、main_bsr、sub_bsr、评分、配送方式、毛利率；筛选新增 `市场 / 配送方式(FBA/FBM)`。
3. **商品详情** — 基本信息（含 parent_asin、卖家、产地、尺寸重量、运营旗标 Tag）、历史价格 / 销量 / BSR / 评分走势图。
4. **竞品对比** — 站点内按品牌横向对比，各品牌 Top 10。
5. **趋势分析** — 月增长率榜、近 30 天新品（按 launch_date）、品类热度。
6. **异常检测**、**每日报告**、**销售分析** — 沿用 ML 三个增量功能页，列表增加 `市场` 列/筛选。

导航菜单：市场概览 / 商品列表 / 竞品对比 / 趋势分析 / 异常检测 / 每日报告 / 销售分析。

---

## 数据库迁移

新建库 + 建表：`db/migrations/001_create_amazon_db.sql`

```bash
mysql -h localhost -u root -prootroot < db/migrations/001_create_amazon_db.sql
mysql -h localhost -u root -prootroot amazon_db -e "SHOW TABLES;"
```

原始 `amazon` 表已迁入 `amazon_db`（`RENAME TABLE shadowcraw_db.amazon TO amazon_db.amazon`，原子瞬时、无数据拷贝）。docker-compose 的 mysql 服务 `MYSQL_DATABASE` 可设为 `amazon_db`；迁移脚本 `001_create_amazon_db.sql` 通过 `CREATE DATABASE IF NOT EXISTS amazon_db` 自建本平台库并建表，`db/migrations` 挂载到 `/docker-entrypoint-initdb.d` 首次启动自动执行。爬虫侧需将写入目标改为 `amazon_db.amazon`。

---

## 错误处理 & 约束

- 聚合脚本失败记录日志，下次执行补算缺失日期；`crawl_date IS NULL` 行跳过。
- varchar 指标 `CAST` 前先 `REGEXP_REPLACE` 去币种/千分位符号，转换失败记录跳过，不中断整批。
- 同一 `(asin, market, crawl_date)` 存在重复行（已观测到），聚合用 `GROUP BY` 自然去重，快照表取每组任意一行（`ANY_VALUE` 或子查询取 `MAX(id)`）。
- 网络服务暴露 8000 端口、无鉴权——与 ML 一致，仅限内网团队访问；若需公网暴露应在反代层加访问控制（本期不含）。

---

## 不在本次范围内

- 历史报告列表页、邮件推送、LLM 流式输出
- 跨站点汇率归一化（各站点 price 保留本币原值，不折算 USD）
- 父子 ASIN（variant）聚合维度
- 鉴权 / 多租户
