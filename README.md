# Amazon 储能竞品数据分析平台

## 项目简介

面向 Amazon 跨境电商**储能电源赛道**的竞品数据采集、聚合与可视化分析平台。以 **OUKITEL** 为核心视角，持续监控 EcoFlow、Bluetti、Jackery、VTOMAN、Anker 五个主要竞品在全球 10 个 Amazon 站点的表现，辅助产品、运营与管理层进行定价策略、选品决策和市场趋势研判。

分析结果由本地 LLM 生成日报/周报/月报，**每日自动推送到钉钉群**（图表托管在阿里云 OSS）。

## 业务背景

- **目标用户**：产品经理、运营、管理层
- **核心场景**：竞品价格监控、爆款选品、品类趋势研判、新品上架跟踪
- **监控品牌**：OUKITEL（自有）、EcoFlow、Bluetti、Jackery、VTOMAN、Anker
- **覆盖站点**：US、UK、DE、FR、ES、IT、CA、JP、IN、MX（共 10 个）
- **重点品类**：发电机、便携电源、太阳能板（光伏）、UPS、便携空调、相关配件

## 数据来源

| 工具 | 用途 | 频率 |
|------|------|------|
| **影刀 RPA** | 自动化抓取 Amazon 各站点商品页面数据（价格/销量/BSR/评分等） | 每日 |
| **卖家精灵 API** | 竞品实时搜索，提供 BSR、月销量、营收等深度指标 | 按需实时 |

---

# 快速启动

## 环境要求

Python 3.10+ / Node.js 18+ / MySQL 8.0

## 首次配置

```bash
# 1. 配置文件不入库(含密钥),从模板复制后填写
cp config/config.example.py config/config.py

# 2. docker 部署另需 .env
cp .env.example .env
```

编辑 `config/config.py`，填入数据库密码、卖家精灵账号，以及下面两节的**钉钉**和 **OSS** 凭据。



## 启动

```bash
# 后端(端口 1332)。务必用 venv 的 python:依赖(oss2/matplotlib)装在这里,
# 且与机器上其他项目的共享环境隔离
backend/venv/bin/python run.py --reload

# 前端(端口 8088,代理 /api 到后端)
cd frontend && npm install && npm run dev
```

生产模式：

```bash
cd frontend && npm run build      # 构建前端静态文件
backend/venv/bin/python run.py    # 后端同时托管前端静态文件
```

---

# 打通钉钉推送

报告推送到钉钉群，需要**钉钉机器人**和 **OSS 图床**两步。只配钉钉不配 OSS 也能用，图表会自动跳过（纯文字推送），不会推裂图。

## 一、创建机器人

1. 钉钉客户端进入目标群 → 右上角**群设置** → **机器人** → **添加机器人** → **自定义机器人**
2. 安全设置勾选 **加签**，复制生成的 `SEC` 开头字符串
3. 复制 webhook 地址里 `?access_token=` 后面那串

## 二、填入配置

```python
# config/config.py
DINGTALK_ACCESS_TOKEN = os.environ.get("DINGTALK_ACCESS_TOKEN", "你的 access_token")
DINGTALK_SECRET = os.environ.get("DINGTALK_SECRET", "SEC 开头的加签密钥")
```

`DINGTALK_WEBHOOK` 会自动由 access_token 拼出，无需单独填。

## 三、测试

```bash
curl -X POST "http://localhost:1332/api/reports/push?period=weekly"
# 返回 {"data":{"ok":true,...,"dingtalk":{"errcode":0,"errmsg":"ok"}},"error":null} 即成功
```

定时推送见 `backend/scheduler.py`：每日 09:00 日报 / 周一 09:05 周报 / 每月 1 号 09:10 月报。

## 钉钉 markdown 的坑（都是实测结论）

| 事项 | 结论 |
|---|---|
| **表格** | **能用**。但官方文档的"支持的 Markdown 语法子集"清单里**没有表格** —— 那份清单不完整，别拿它当"不支持"的依据 |
| **换行** | 单个 `\n` 是**软换行**，会渲染成空格、整份报告挤成一大段。**行尾必须加两个空格**才是硬换行 |
| **图片** | 只接受 URL，不支持 base64/附件。**去抓图的是钉钉服务端，不是查看者的客户端** —— 私有地址（`10.x`/`192.168.x`）谁都拉不到，必须公网托管，见下一节 |
| **协议** | 图片 URL 必须是 **https**，http 大概率被拒抓 |
| **消息类型** | 用 `markdown`，**不要用 `actionCard` + `singleURL`** —— 那样点卡片任意位置都会跳网页，而不是一份报告 |
| **限流** | 每个机器人**每分钟最多 20 条**，超了封 10 分钟 |
| **表格宽度** | 手机上会横向溢出、把列切掉。列数要克制（当前 4 列），金额/计数一律缩写成 `$49.85M` / `586.4K` |

> 要确认某个语法行不行，**发一条探测消息到群里实测最快**，比查文档可靠。

---

# 开启 OSS 图床

钉钉消息里的图表**必须挂在公网可达的地址**。本机内网地址（`10.x`）无论如何都拉不到 —— 绑不绑 `0.0.0.0`、看的人在不在内网都没用，因为去抓图的是钉钉服务端而非查看者。因此图表渲染后需上传至阿里云 OSS。

## 一、创建 Bucket

任意地域，**保持私有**（默认 ACL，不要开公共读）—— 竞品营收数据不该裸奔在公网。

目录无需手动创建：OSS 是扁平存储，`report-charts/` 只是 object key 前缀，控制台把它显示成"文件夹"而已。

## 二、创建 RAM 子账号（不要用主账号 AK）

主账号 AK 泄露 = 整个阿里云账号沦陷。

1. **RAM 访问控制** → **用户** → **创建用户**，勾选「使用永久 AccessKey 访问」
2. **AccessKey Secret 只显示一次**，当场保存
3. **权限策略** → **创建权限策略** → **脚本编辑**：

```json
{
  "Version": "1",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["oss:PutObject", "oss:GetObject"],
      "Resource": "acs:oss:*:*:你的bucket名/*"
    }
  ]
}
```

4. 回到用户 → **新增授权**，把该策略授予子账号

**为什么 `GetObject` 也要给**：默认用签名 URL。签名 URL 被访问时，OSS 会校验 URL 里 `OSSAccessKeyId` **对应身份**的读权限 —— 只给 `PutObject` 的话传得上去，但钉钉拉图会 **403**。

> 想把资源收窄到 `acs:oss:*:*:bucket/report-charts/*`（更安全）语法是合法的（官方文档场景 5 即此写法），但**可视化编辑器解析不了带前缀的资源**、会显示"无效授权"。用脚本编辑，或退而用整桶粒度。

## 三、填入配置

```python
# config/config.py
OSS_ACCESS_KEY_ID = os.environ.get("OSS_ACCESS_KEY_ID", "LTAI...")
OSS_ACCESS_KEY_SECRET = os.environ.get("OSS_ACCESS_KEY_SECRET", "你的 Secret")
OSS_ENDPOINT = os.environ.get("OSS_ENDPOINT", "oss-cn-shenzhen.aliyuncs.com")
OSS_BUCKET = os.environ.get("OSS_BUCKET", "你的bucket名")
REPORT_EMBED_CHARTS = os.environ.get("REPORT_EMBED_CHARTS", "1") == "1"
```

> **Endpoint 必须用外网地址**。Bucket 概览页会给两个：`oss-cn-shenzhen.aliyuncs.com`（外网 ✅）和 `oss-cn-shenzhen-internal.aliyuncs.com`（内网 ❌）。填成 internal 的话签名 URL 指向阿里云内网，钉钉在公网拉不到，**图照样裂** —— 绕一圈回到原点。不要带 `https://`、不要带 bucket 前缀。

## 四、自检

```bash
backend/venv/bin/python backend/scripts/check_oss.py
```

逐层验证并在失败处直接指出原因：

1. 配置齐不齐、endpoint 是否误填内网地址
2. 上传测试图 → 失败 = AccessKey 错 / 缺 `PutObject` / bucket 名或地域不对
3. **从公网拉取签名 URL**（模拟钉钉抓图）→ 403 = 缺 `GetObject`

> 第 3 步是关键：**必须从公网验证**。在本机 curl 本机地址走的是回环，证明不了外部能否访问 —— 这个坑踩过。

## 注意事项

- **签名 URL 默认 30 天过期**（`OSS_SIGN_EXPIRE_SEC`）。钉钉是服务端抓图并转存的，抓完大概率不再回源，但这是推断未经实证。若发现老报告图裂，可将 `OSS_USE_SIGNED_URL` 设为 `0` 改用公共读（代价：图公网可见，需 bucket ACL 为 public-read）。
- **建议给 `report-charts/` 配生命周期规则**（如 90 天自动删除），图会持续堆积。

---

# 核心功能

## 市场概览（Overview）
- 6 品牌卡片横向滑动展示，悬浮动画交互
- 储能口径统计，变体去重，USD 统一折算
- 7 天/30 天/90 天/半年/一年趋势切换
- 品类营收占比圆环图（Top 10）
- 支持按日期查看历史数据，点击卡片进入品牌详情

## 品牌详情页（Brand Detail）
- 品牌概览指标卡片（月销/营收/SKU/均价/评分/FBA 占比）
- 月销量趋势折线图、各站点分布柱状图、品类营收占比圆环图
- 销量 Top 10 商品列表（价格/营收已折算 USD）

## 商品列表（Products）
- 品牌/品类/关键词/日期多维筛选，品类支持**多选**
- 按当前筛选条件实时汇总（商品数/月销量/月营收/均价）
- 分页浏览，支持按月销量/营收/价格/BSR/评分/增长率排序

## 竞品对比（Compare）
- 6 品牌核心指标对比表 + 各品牌 Top 10 商品卡片

## 趋势分析（Trends）
- 品类销量趋势、近 30 天新品列表

## 实时搜索（Search）
- 卖家精灵 API 实时搜索，Cookie 过期后自动重登刷新

## 异常检测（Anomalies）
- 销量/销售额/价格/大类 BSR/小类 BSR 突变自动告警，7 天基线对比

## 报告（Reports）
- LLM 自动生成中文分析，**日报 / 周报 / 月报各自独立生成**（口径与结论不同，周报不会拿日报凑数）
- 内容：品牌整体表现、竞品对比（增长最快/最慢及原因）、选品建议
- Markdown 渲染，支持按周期和日期查看历史报告

## 定时任务
- 03:00 全量聚合 + 日报 LLM 生成
- 03:30–09:30 每小时检查补跑（防止数据延迟入库导致漏跑），启动时也检查一次
- 周一 08:00 / 每月 1 号 08:10 生成周报、月报的 LLM 分析（排在推送前一小时）
- 09:00 / 周一 09:05 / 每月 1 号 09:10 钉钉推送

---

# 技术架构

```
┌──────────────────┐   ┌───────────────────────────┐   ┌────────────────┐
│ 影刀 RPA + 卖家精灵 │──▶│ MySQL                      │◀──│  FastAPI 后端   │
└──────────────────┘   │ (amazon_sellersprite_db)   │   └───┬────────┬───┘
                       └───────────────────────────┘       │ /api   │
                                                            ▼        ▼
                                                   ┌────────────┐ ┌──────────┐
                                                   │ React (Vite)│ │ 钉钉机器人 │
                                                   └────────────┘ └────┬─────┘
                                                                       │ 图表 URL
                                                                       ▼
                                                                ┌────────────┐
                                                                │ 阿里云 OSS  │
                                                                └────────────┘
```

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.10 / FastAPI / SQLAlchemy / APScheduler |
| 前端 | React 18 / TypeScript / Vite / Ant Design / ECharts / React Query |
| 数据库 | MySQL 8.0（连接池 QueuePool，pool_size=10） |
| LLM | Gemma 4 31B（本地部署），生成日报/周报/月报分析 |
| 图表 | matplotlib 服务端渲染 PNG → 阿里云 OSS |
| 部署 | Docker + docker-compose / 或直接 `python run.py` |

## 数据库设计

| 表 | 用途 | 备注 |
|---|---|---|
| `amazon` | 原始爬虫数据（每日全量） | 日增 ~1300 行 |
| `product_daily_snapshot` | 商品日快照（去重后） | |
| `daily_brand_summary` | 品牌日聚合（品牌×站点×日） | |
| `daily_category_summary` | 品类日聚合 | |
| `daily_overview_summary` | 总览日聚合（储能口径，品牌级、跨站点已合并） | 一行 = 一品牌一天 |
| `daily_overview_category` | 品类营收 Top10 | `sub_category` 存的是**未归一化的本地化名** |
| `daily_analysis_reports` | LLM 报告 | 唯一键 `(report_date, period)` |
| `anomaly_alerts` | 异常告警 | |

## 索引优化

`amazon` 表索引（应对数据增长）：
- `idx_crawl_date_brand (crawl_date, brand)` — 品牌聚合、详情页
- `idx_crawl_date_asin_market (crawl_date, asin, market)` — Products 页 JOIN
- `idx_asin (asin)` — 商品详情页

前端查询全部走**预聚合表**或**索引**，不做全表扫描。预计 200 万行时仍可正常运行。

---

# 数据处理逻辑

## 变体去重
Amazon 的 `monthly_sales` 为父体（Listing）级指标，会被复制到每个变体行。聚合时按 `(parent_asin, market)` 为一个 family，销量/营收仅计一次（取 `MAX`），价格/评分等按变体平均。

## 货币折算
各站点数据为本地货币（JPY/EUR/GBP/MXN/CAD/INR/USD），聚合层统一按静态汇率折算为 USD 后再跨站点汇总。汇率维护于 `backend/constants.py` 的 `FX_TO_USD`。

## 品类识别与归一化
`category_path` 各站点为本地化路径，通过匹配**末段（叶子节点）**的跨语言正则识别储能/光伏/配件，见 `STORAGE_LEAF_REGEX` / `SOLAR_LEAF_REGEX` / `ACCESSORY_LEAF_REGEX`。

本地化品类名（`发电机` / `Outdoor Generators` / `Externe Handyakkus`）**是同一个品类**，聚合或展示前必须过 `normalize_sub_category()` 归一，否则同一品类会被拆成多行**重复计算**。

## 品牌大小写
库里同一品牌存在多种大小写（历史 `Anker` / 后来 `anker`，`EF ECOFLOW` / `ef ecoflow`）：

- SQL 侧：`LOWER(brand) IN (...)` 过滤、`GROUP BY LOWER(brand)` 分组
- **Python 侧：必须用 `brand.lower()` 当 dict key** —— MySQL 默认排序规则大小写不敏感，`GROUP BY brand` 看着结果是干净的，但 Python dict 是敏感的，拿原始 brand 当 key 会把一个品牌拆成两条、**指标当场翻倍**
- 展示：一律过 `canonical_brand()`

## 品牌校正
上游爬虫会把 OUKITEL 官方储能商品的 `brand` 字段标成第三方店铺名，但 `product_title` 一律以 OUKITEL 开头/包含。判定规则见 `backend/constants.py` 的 `corrected_brand_sql()`。

---

# 项目结构

```
amazon_sellersprite/
├── backend/
│   ├── main.py                   # FastAPI 应用入口
│   ├── constants.py              # 品牌、汇率、品类正则与归一化
│   ├── database.py               # SQLAlchemy 连接池
│   ├── scheduler.py              # 定时聚合 / LLM / 钉钉推送
│   ├── middleware.py             # 访问日志
│   ├── routers/                  # overview / brands / products / compare
│   │                             # trends / anomalies / reports / search / meta
│   ├── aggregation/              # product_snapshot / brand_summary
│   │                             # category_summary / overview_summary
│   ├── analysis/
│   │   ├── report_data.py        # build_summary(period) —— 报告页与钉钉共用口径
│   │   ├── llm_report.py         # 日/周/月报 LLM 分析
│   │   ├── report_charts.py      # matplotlib 渲染 PNG
│   │   ├── oss_upload.py         # 上传 OSS，换公网 https 签名 URL
│   │   ├── dingtalk_push.py      # 钉钉自定义机器人推送
│   │   ├── anomaly_detector.py   # 异常检测
│   │   └── sales_analyzer.py     # 销售分析
│   ├── scripts/check_oss.py      # OSS 连通性自检
│   └── models/                   # Pydantic 模型
├── frontend/
│   ├── src/pages/                # Overview / BrandDetail / ProductList / ...
│   ├── src/components/           # TrendChart / PieChart / Layout
│   ├── src/theme/brands.ts       # 品牌配色、渐变、简介
│   └── vite.config.ts
├── config/
│   ├── config.example.py         # 配置模板(入库)
│   └── config.py                 # 实际配置(含密钥,已 gitignore)
├── db/migrations/                # SQL 迁移
├── run.py                        # 统一启动脚本
├── docker-compose.yml
└── README.md
```

---

# 配置说明

所有配置集中在 `config/config.py`，每项均可用同名环境变量覆盖。

| 配置项 | 默认值 | 说明 |
|---|---|---|
| `DB_HOST` / `DB_USER` / `DB_PASS` | `localhost` / `root` / — | MySQL 连接 |
| `DB_NAME` | `amazon_sellersprite_db` | 数据库名 |
| `ANALYSIS_LLM_BASE_URL` | `http://10.0.0.22:8005/v1` | LLM 服务地址 |
| `ANALYSIS_LLM_MODEL` | `gemma-4-31b-it-fp8` | 报告生成模型 |
| `SELLERSPRITE_COOKIE` | — | 卖家精灵 cookie（过期自动刷新） |
| `SELLERSPRITE_EMAIL` / `_PASSWORD` / `_SALT` | — | 刷新 cookie 用的账号 |
| `DINGTALK_ACCESS_TOKEN` | — | 机器人 webhook 的 access_token |
| `DINGTALK_SECRET` | — | 加签密钥（`SEC` 开头） |
| `OSS_ACCESS_KEY_ID` / `_SECRET` | — | RAM 子账号凭据 |
| `OSS_ENDPOINT` | — | **外网** endpoint，不带协议 |
| `OSS_BUCKET` | — | Bucket 名 |
| `OSS_PREFIX` | `report-charts` | 对象 key 前缀 |
| `OSS_USE_SIGNED_URL` | `1` | `1`=私有桶+签名 URL；`0`=需 public-read |
| `OSS_SIGN_EXPIRE_SEC` | `2592000`（30 天） | 签名有效期 |
| `REPORT_EMBED_CHARTS` | `1` | 是否嵌入图表（未配 OSS 时自动跳过） |
| `PUBLIC_BASE_URL` | `http://10.0.5.134:1332` | 未配 OSS 时的图表回落地址（仅本机自测有意义） |
| `REPORT_PAGE_URL` | `http://10.0.5.134:8088/reports` | 报告页地址 |
