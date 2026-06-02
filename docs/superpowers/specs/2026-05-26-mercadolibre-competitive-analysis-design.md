# MercadoLibre 竞品分析平台 设计文档

**日期**：2026-05-26  
**状态**：已确认

---

## 概述

面向团队的 MercadoLibre 竞品数据分析平台。数据来源为每日爬取的商品数据（1600条/天，4个品牌各400条），支持选品、竞品监控、市场全局分析三大场景。

---

## 整体架构

```
浏览器 (React SPA)
    ↕ HTTP/JSON
FastAPI（Python，REST API + 静态文件托管）
    ↕
MySQL
  ├── products（原始表）
  ├── daily_brand_summary（每日品牌聚合）
  ├── daily_category_summary（每日品类聚合）
  └── product_30d_snapshot（30天趋势快照）

APScheduler（内嵌于 FastAPI 进程）
  每天凌晨触发聚合计算
```

**部署**：Docker Compose，两个容器（fastapi + mysql），团队访问 `http://服务器IP:8000`。

---

## 数据层

### 原始表：products（已有）

| 字段 | 说明 |
|------|------|
| product_id | 商品唯一标识 |
| product_name | 商品名称 |
| brand | 品牌 |
| sub_category | 子品类 |
| price | 价格（varchar，查询时 CAST） |
| sales_7_days / sales_30_days / sales_90_days | 分段销量 |
| total_sales / revenue | 总销量、总营收 |
| sales_growth_rate | 增长率 |
| bsr | 类目排名 |
| stock_quantity / stock_type | 库存 |
| store_name / store_type | 店铺信息 |
| review_count / review_rating | 评论数、评分 |
| conversion_rate | 转化率 |
| launch_date | 上架日期 |
| data_date | 数据采集日期 |
| image_url / product_url | 图片、商品链接 |

### 聚合表：daily_brand_summary

每天每品牌一条记录，供仪表盘和趋势图使用。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT AUTO_INCREMENT | 主键 |
| data_date | DATE | 数据日期 |
| brand | VARCHAR(255) | 品牌名 |
| product_count | INT | 商品数量 |
| total_revenue | DECIMAL(18,2) | 总营收 |
| total_sales_30d | BIGINT | 30天总销量 |
| avg_price | DECIMAL(10,2) | 均价 |
| avg_rating | DECIMAL(3,2) | 平均评分 |
| avg_growth_rate | DECIMAL(10,4) | 平均增长率 |

### 聚合表：daily_category_summary

每天每品类一条记录，供品类分析使用。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT AUTO_INCREMENT | 主键 |
| data_date | DATE | 数据日期 |
| sub_category | VARCHAR(255) | 子品类 |
| brand | VARCHAR(255) | 品牌 |
| product_count | INT | 商品数量 |
| total_revenue | DECIMAL(18,2) | 总营收 |
| total_sales_30d | BIGINT | 30天总销量 |
| avg_price | DECIMAL(10,2) | 均价 |

### 聚合表：product_30d_snapshot

每30天对每个商品做一次快照，支持增长率和排名变化分析。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INT AUTO_INCREMENT | 主键 |
| snapshot_date | DATE | 快照日期 |
| product_id | VARCHAR(100) | 商品ID |
| brand | VARCHAR(255) | 品牌 |
| price | DECIMAL(10,2) | 价格 |
| sales_30d | BIGINT | 30天销量 |
| revenue | DECIMAL(18,2) | 营收 |
| bsr | INT | 类目排名 |
| review_count | INT | 评论数 |
| review_rating | DECIMAL(3,2) | 评分 |
| growth_rate | DECIMAL(10,4) | 增长率 |

---

## 页面结构

### 1. 市场概览（首页）
- 4个品牌核心指标卡片：总销量、总营收、均价、平均评分
- 30天销量趋势折线图（4条线，每品牌一条）
- 品类市场份额饼图
- 数据日期选择器（查看历史快照）

### 2. 商品列表
- 服务端分页、排序、多条件筛选（品牌、品类、价格区间、上架日期）
- 列：商品图片缩略图、名称、品牌、价格、7/30/90天销量、增长率、BSR、评分
- 点击行进入商品详情

### 3. 商品详情
- 商品基本信息（图片、名称、品牌、尺寸重量、状态）
- 历史价格走势图
- 历史销量走势图
- 库存、转化率、评论数趋势

### 4. 竞品对比
- 按品牌横向对比：各品类商品数量、均价、总销量、增长率
- 各品牌 Top 10 商品排行

### 5. 趋势分析
- 30天增长率排行榜（商品维度）
- 新品追踪（近30天上架的商品）
- 品类热度变化

---

## API 设计

| 接口 | 用途 |
|------|------|
| `GET /api/overview?date=` | 市场概览数据 |
| `GET /api/brands/trend?days=30` | 品牌销量趋势折线图 |
| `GET /api/products?page=&brand=&category=&sort=` | 商品列表（分页+筛选+排序） |
| `GET /api/products/{product_id}` | 商品详情 + 历史趋势 |
| `GET /api/compare?brands=` | 竞品对比数据 |
| `GET /api/trends?date=` | 30天趋势分析数据 |
| `GET /api/meta/brands` | 品牌列表（筛选器用） |
| `GET /api/meta/categories` | 品类列表（筛选器用） |

统一响应结构：`{ "data": ..., "error": null }`

---

## 前端技术栈

| 技术 | 用途 |
|------|------|
| React | SPA 框架 |
| Ant Design | UI 组件库（表格、筛选器、分页） |
| ECharts | 图表（折线图、饼图、柱状图） |
| React Query | 接口缓存，避免重复请求 |

---

## 错误处理 & 部署

**错误处理：**
- 聚合脚本失败记录日志，下次执行时补算缺失日期
- varchar 字段查询时用 `CAST` 转换，转换失败的记录跳过
- 前端统一错误提示组件

**部署（docker-compose.yml）：**
```
services:
  mysql:
    image: mysql:8
    volumes: [./data:/var/lib/mysql]  # 数据持久化

  fastapi:
    build: .
    ports: ["8000:8000"]             # 对外暴露
    depends_on: [mysql]
    # React build 产物打包进镜像，由 FastAPI StaticFiles 托管
```

团队成员访问 `http://服务器IP:8000`，无需本地安装任何依赖。
