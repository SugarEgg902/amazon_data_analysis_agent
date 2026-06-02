# Amazon 多站点竞品数据分析平台

## 项目简介

本平台为公司 Amazon 跨境电商业务提供竞品数据采集、聚合与可视化分析能力。以 **OUKITEL** 为核心视角，持续监控 Blackview、Ulefone、CUBOT、DOOGEE 四个主要竞品品牌在全球 9 个 Amazon 站点的表现，辅助产品、运营与管理层进行定价策略、选品决策和市场趋势研判。

## 数据来源

| 工具 | 用途 |
|------|------|
| **影刀 RPA** | 自动化执行采集任务，定时抓取 Amazon 各站点商品页面数据 |
| **卖家精灵** | 提供 BSR 排名、月销量估算、营收预估、评分变化等深度运营指标 |

覆盖站点：US、UK、DE、FR、ES、IT、CA、JP、MX（共 9 个）

采集频率：每日一次，数据落库后自动触发聚合与异常检测。

## 技术架构

```
┌─────────────┐     ┌──────────────────┐     ┌───────────────┐
│  影刀 + 卖家精灵  │────▶│  MySQL (amazon_db) │◀────│  FastAPI 后端   │
└─────────────┘     └──────────────────┘     └───────┬───────┘
                                                     │ /api
                                                     ▼
                                              ┌───────────────┐
                                              │ React 前端 (Vite)│
                                              └───────────────┘
```

- **后端**：Python 3.9 / FastAPI / SQLAlchemy / APScheduler
- **前端**：React 18 / TypeScript / Vite / Ant Design / ECharts
- **数据库**：MySQL 8.0
- **部署**：Docker + docker-compose
- **LLM 报告**：本地部署的 Gemma 模型，每日自动生成竞品分析日报

## 核心功能

| 模块 | 说明 |
|------|------|
| 市场概览 | 手机品类五品牌全站点汇总，变体去重，USD 统一折算，品牌卡片横向滑动 |
| 商品列表 | 支持品牌/商品名/ASIN 搜索，日期切换，分页浏览全量商品 |
| 竞品对比 | OUKITEL 与四竞品核心指标对比表 + Top 10 商品卡片 |
| 趋势分析 | 30 天月销量/营收趋势折线图，品牌配色一致 |
| 异常检测 | 销量/价格/BSR 突变自动告警，7 天基线对比，阈值可配 |
| 每日报告 | LLM 自动生成中文分析日报，含品牌表现、竞品对比、选品建议 |
| 销售分析 | 历史销售数据查询与可视化 |

## 快速启动

### 环境要求

- Python 3.9+
- Node.js 18+
- MySQL 8.0
- （可选）Docker & docker-compose

### 开发模式

```bash
# 后端（端口 8001）
python run.py --reload

# 前端（端口 5174，自动代理 /api 到后端）
cd frontend && npm install && npm run dev
```

### 生产模式

```bash
# 构建前端
cd frontend && npm run build

# 启动后端（同时托管前端静态文件）
python run.py
```

### Docker 部署

```bash
docker-compose up -d
```

## 项目结构

```
amazon/
├── backend/
│   ├── main.py              # FastAPI 应用入口
│   ├── constants.py         # 品牌列表、汇率、手机品类正则
│   ├── database.py          # 数据库连接
│   ├── scheduler.py         # APScheduler 定时聚合任务
│   ├── routers/             # API 路由（overview/products/compare/...）
│   ├── aggregation/         # 数据聚合模块（快照/品牌/品类汇总）
│   ├── analysis/            # 异常检测 + LLM 日报生成
│   ├── models/              # Pydantic 模型
│   └── tests/               # pytest 测试
├── frontend/
│   ├── src/pages/           # 页面组件
│   ├── src/components/      # 布局、图表等通用组件
│   ├── src/theme/brands.ts  # 品牌配色与简介
│   └── vite.config.ts       # Vite 配置
├── run.py                   # 统一启动脚本（CWD 无关）
├── docker-compose.yml       # 容器编排
└── README.md
```

## 数据处理逻辑

### 变体去重

Amazon 的 `monthly_sales` 为父体（Listing）级指标，会被复制到每个变体行。聚合时按 `(parent_asin, market)` 为一个 family，销量/营收仅计一次（取 MAX），价格/评分等按变体平均。

### 货币折算

各站点数据为本地货币（JPY/EUR/GBP/MXN/CAD/USD），聚合层统一按静态汇率折算为 USD 后再跨站点汇总。汇率维护于 `backend/constants.py` 的 `FX_TO_USD`。

### 手机品类识别

`category_path` 各站点为本地化路径，通过匹配末段（叶子节点）的跨语言正则识别手机品类，排除同路径下的配件/平板/手表。

## 配置说明

| 环境变量 | 默认值 | 说明 |
|----------|--------|------|
| `DATABASE_URL` | `mysql+pymysql://root:rootroot@localhost/amazon_db` | 数据库连接串 |
| `ANALYSIS_LLM_BASE_URL` | `http://10.0.0.21:8005/v1` | LLM 服务地址 |
| `ANALYSIS_LLM_MODEL` | `gemma-4-31b-it-fp8` | 日报生成模型 |
