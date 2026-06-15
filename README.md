# Amazon 多站点竞品数据分析平台

## 项目简介

本平台为公司 Amazon 跨境电商业务提供竞品数据采集、聚合与可视化分析能力。以 **OUKITEL** 为核心视角，持续监控 Blackview、Ulefone、CUBOT、DOOGEE、FOSSiBOT 五个主要竞品品牌在全球 8 个 Amazon 站点的表现，辅助产品、运营与管理层进行定价策略、选品决策和市场趋势研判。

## 业务背景

- **目标用户**：产品经理、运营、管理层
- **核心场景**：竞品价格监控、爆款选品、品类趋势研判、新品上架跟踪
- **监控品牌**：OUKITEL（自有）、Blackview、Ulefone、CUBOT、DOOGEE、FOSSiBOT
- **覆盖站点**：US、UK、DE、FR、ES、IT、CA、JP（共 8 个）
- **重点品类**：三防手机、平板电脑、智能手表、发电机、太阳能板、便携电源等

## 数据来源

| 工具 | 用途 | 频率 |
|------|------|------|
| **影刀 RPA** | 自动化抓取 Amazon 各站点商品页面数据（价格/销量/BSR/评分等） | 每日 |
| **卖家精灵 API** | 竞品实时搜索，提供 BSR、月销量、营收等深度指标 | 按需实时 |

## 核心功能

### 市场概览（Overview）
- 6 品牌卡片横向滑动展示，悬浮动画交互
- 仅统计手机品类，变体去重，USD 统一折算
- 30 天/7 天/90 天/半年/一年趋势切换
- 品类营收占比圆环图（Top 10）
- 支持按日期查看历史数据
- 点击卡片进入品牌详情子页面

### 品牌详情页（Brand Detail）
- 品牌概览指标卡片（仅三防手机：月销/营收/SKU/均价/评分/FBA占比）
- 30 天月销量趋势折线图
- 各站点月销量分布柱状图
- 全品类营收占比圆环图（Top 10）
- 手机品类销量 Top 10 商品列表（价格/营收已折算 USD）

### 商品列表（Products）
- 品牌/品类/关键词/日期多维筛选
- 品类支持**多选**，按当前筛选条件实时汇总（商品数/月销量合计/月营收/均价）
- 分页浏览，支持按月销量/营收/价格/BSR/评分/增长率排序
- 点击行跳转商品详情页（历史趋势图）

### 竞品对比（Compare）
- 6 品牌核心指标对比表
- 各品牌 Top 10 商品卡片

### 趋势分析（Trends）
- 品类销量趋势
- 近 30 天新品列表

### 实时搜索（Search）
- 卖家精灵 API 实时搜索竞品数据
- Cookie 自动刷新（过期后自动 POST 登录获取新 cookie）
- 展示搜索结果：图片/标题/品牌/价格/月销量/月营收/评分/BSR/类目/卖家/FBA/上架时间

### 异常检测（Anomalies）
- 销量/价格/BSR 突变自动告警
- 7 天基线对比，阈值可配

### 每日报告（Reports）
- LLM 自动生成中文分析日报
- 内容：品牌整体表现、竞品对比（增长最快/最慢及原因）、选品建议
- 支持按日期查看历史报告
- Markdown 渲染，表格/列表/标题样式优化

### 定时任务
- 凌晨 3:00 自动执行全量聚合 + 日报生成
- 3:30-8:30 每小时检查补跑（防止数据延迟入库导致漏跑）
- 启动时自动检测并补跑当天未聚合数据

## 技术架构

```
┌─────────────────┐     ┌──────────────────┐     ┌────────────────┐
│ 影刀 RPA + 卖家精灵 │────▶│  MySQL (amazon_db) │◀────│  FastAPI 后端    │
└─────────────────┘     └──────────────────┘     └───────┬────────┘
                                                         │ /api
                                                         ▼
                                                  ┌────────────────┐
                                                  │ React 前端 (Vite) │
                                                  └────────────────┘
```

### 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10 / FastAPI / SQLAlchemy / APScheduler / httpx |
| 前端 | React 18 / TypeScript / Vite / Ant Design / ECharts / React Query |
| 数据库 | MySQL 8.0（连接池 QueuePool，pool_size=10） |
| LLM | Gemma 4 31B（本地部署），每日自动生成竞品分析日报 |
| 部署 | Docker + docker-compose / 或直接 python run.py |

### 数据库设计

| 表 | 用途 | 量级 |
|---|---|---|
| `amazon` | 原始爬虫数据（每日全量） | 当前 ~5 万行，日增 ~1300 |
| `product_daily_snapshot` | 商品日快照（去重后） | 当前 ~4 万行 |
| `daily_brand_summary` | 品牌日聚合（品牌×站点×日） | 每天 ~50 行 |
| `daily_category_summary` | 品类日聚合 | 每天 ~400 行 |
| `daily_overview_summary` | 总览日聚合（仅手机品类） | 每天 ~6 行 |
| `daily_overview_category` | 品类营收 Top10 | 每天 ~10 行 |
| `daily_analysis_reports` | LLM 日报 | 每天 1 行 |
| `anomaly_alerts` | 异常告警 | 按需 |

### 索引优化

`amazon` 表索引（应对数据增长）：
- `idx_crawl_date_brand (crawl_date, brand)` — 品牌聚合、详情页
- `idx_crawl_date_asin_market (crawl_date, asin, market)` — Products 页 JOIN
- `idx_asin (asin)` — 商品详情页

前端查询全部走**预聚合表**或**索引**，不做全表扫描。预计 200 万行时仍可正常运行。

## 数据处理逻辑

### 变体去重
Amazon 的 `monthly_sales` 为父体（Listing）级指标，会被复制到每个变体行。聚合时按 `(parent_asin, market)` 为一个 family，销量/营收仅计一次（取 MAX），价格/评分等按变体平均。

### 货币折算
各站点数据为本地货币（JPY/EUR/GBP/MXN/CAD/USD），聚合层统一按静态汇率折算为 USD 后再跨站点汇总。汇率维护于 `backend/constants.py` 的 `FX_TO_USD`。

### 手机品类识别
`category_path` 各站点为本地化路径，通过匹配末段（叶子节点）的跨语言正则识别手机品类（覆盖中/英/德/法/西/意/日 7 种语言），排除同路径下的配件/平板/手表。

### 品类归一化
各站点本地化品类名（如 `Simlockfreie Handys` / `Cell Phones` / `スマートフォン本体`）通过映射表统一归一为中文标签（`智能手机`），用于饼图和报告展示。

## 快速启动

### 环境要求
- Python 3.10+
- Node.js 18+
- MySQL 8.0

### 开发模式

```bash
# 后端（端口 8001）
cd /path/to/amazon
backend/venv/bin/python run.py --reload

# 前端开发服务器（端口 5174，代理 /api 到后端）
cd frontend && npm install && npm run dev
```

### 生产模式

```bash
# 构建前端静态文件
cd frontend && npm run build

# 启动后端（同时托管前端静态文件）
python run.py
```

### 手动触发聚合

```bash
backend/venv/bin/python -c "
import sys; sys.path.insert(0,'.')
from datetime import date
from backend.aggregation.product_snapshot import run_product_snapshot
from backend.aggregation.brand_summary import run_brand_summary
from backend.aggregation.category_summary import run_category_summary
from backend.aggregation.overview_summary import run_overview_summary
from backend.analysis.llm_report import run_llm_analysis
d = date.today()
run_product_snapshot(d)
run_brand_summary(d)
run_category_summary(d)
run_overview_summary(d)
run_llm_analysis(d)
"
```

## 项目结构

```
amazon/
├── backend/
│   ├── main.py              # FastAPI 应用入口
│   ├── constants.py         # 品牌列表、汇率、手机品类正则、品类映射
│   ├── database.py          # 数据库连接（SQLAlchemy 连接池）
│   ├── scheduler.py         # APScheduler 定时聚合 + 补跑逻辑
│   ├── routers/
│   │   ├── overview.py      # 市场概览 API
│   │   ├── brands.py        # 品牌趋势 + 品牌详情 API
│   │   ├── products.py      # 商品列表 + 详情 API
│   │   ├── compare.py       # 竞品对比 API
│   │   ├── trends.py        # 趋势分析 API
│   │   ├── search.py        # 卖家精灵实时搜索 + Cookie 自动刷新
│   │   ├── reports.py       # 每日报告 API
│   │   └── meta.py          # 站点/品牌/品类下拉选项
│   ├── aggregation/
│   │   ├── product_snapshot.py   # 商品日快照聚合
│   │   ├── brand_summary.py      # 品牌日汇总
│   │   ├── category_summary.py   # 品类日汇总
│   │   └── overview_summary.py   # 总览聚合（仅手机品类）
│   ├── analysis/
│   │   ├── llm_report.py    # LLM 日报生成
│   │   └── anomaly.py       # 异常检测
│   └── models/              # Pydantic 模型
├── frontend/
│   ├── src/pages/
│   │   ├── Overview.tsx     # 市场概览
│   │   ├── BrandDetail.tsx  # 品牌详情
│   │   ├── ProductList.tsx  # 商品列表
│   │   ├── Compare.tsx      # 竞品对比
│   │   ├── Trends.tsx       # 趋势分析
│   │   ├── AmazonSearch.tsx # 实时搜索
│   │   ├── Reports.tsx      # 每日报告
│   │   └── Anomalies.tsx    # 异常告警
│   ├── src/components/      # TrendChart / PieChart / Layout
│   ├── src/theme/brands.ts  # 品牌配色、渐变、简介
│   └── vite.config.ts
├── config/
│   └── config.py            # 卖家精灵 Cookie、LLM 配置
├── run.py                   # 统一启动脚本
├── docker-compose.yml       # 容器编排
└── README.md
```

## 配置说明

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DB_HOST` | `localhost` | MySQL 主机 |
| `DB_USER` | `root` | MySQL 用户 |
| `DB_PASS` | `` | MySQL 密码 |
| `DB_NAME` | `amazon_db` | 数据库名 |
| `ANALYSIS_LLM_BASE_URL` | `http://10.0.0.21:8005/v1` | LLM 服务地址 |
| `ANALYSIS_LLM_MODEL` | `gemma-4-31b-it-fp8` | 日报生成模型 |
