# MercadoLibre LLM 每日分析报告 设计文档

**日期**：2026-05-26  
**状态**：已确认

---

## 概述

在每天凌晨 02:30（UTC）的独立定时任务中，读取当日聚合数据，调用本地 LLM 生成包含市场趋势、竞品对比、选品建议的综合日报，存入数据库，并在前端新增"每日报告"页面展示。

---

## 架构变更

```
APScheduler
  ├── 02:00 UTC  run_daily_aggregation()   [已有]
  └── 02:30 UTC  run_llm_analysis()        [新增]
                    ↓
              读取 daily_brand_summary
              读取 daily_category_summary
                    ↓
              调用本地 LLM (OpenAI 兼容)
                    ↓
              写入 daily_analysis_reports  [新增表]

FastAPI
  └── GET /api/reports          [新增路由]
  └── GET /api/reports/latest   [新增路由]

React
  └── /reports 页面             [新增页面]
```

---

## 数据层

### 新增表：daily_analysis_reports

```sql
CREATE TABLE daily_analysis_reports (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    report_date   DATE NOT NULL,
    content       MEDIUMTEXT NOT NULL,
    model         VARCHAR(100) NOT NULL,
    generated_at  DATETIME NOT NULL,
    status        ENUM('success', 'failed') NOT NULL DEFAULT 'success',
    error_message TEXT,
    UNIQUE KEY uq_report_date (report_date)
);
```

| 字段 | 说明 |
|------|------|
| report_date | 报告对应的数据日期（与 data_date 对齐） |
| content | LLM 生成的 Markdown 格式报告正文 |
| model | 调用的模型名称（来自环境变量） |
| generated_at | 报告生成时间 |
| status | success / failed |
| error_message | 失败时的错误信息 |

---

## 后端

### 新增模块：backend/analysis/llm_report.py

**函数：`run_llm_analysis(target_date: date) -> None`**

执行流程：
1. 从 `daily_brand_summary` 查询 `target_date` 的品牌聚合数据
2. 从 `daily_category_summary` 查询 `target_date` 的品类聚合数据
3. 从 `daily_brand_summary` 查询前一天数据，计算环比变化
4. 若当日聚合数据为空，记录 warning 并退出（不写 failed 记录）
5. 构建中文 Prompt（见下方 Prompt 结构）
6. 调用本地 LLM，`timeout=120s`，失败重试一次
7. 若返回内容为空，重试一次；仍为空则写入 `status='failed'`
8. 将报告写入 `daily_analysis_reports`（ON DUPLICATE KEY UPDATE）

**Prompt 结构（三段）：**

```
你是一位电商数据分析师，请根据以下 MercadoLibre 平台数据生成一份中文日报。

## 一、市场趋势
[各品牌当日数据：商品数、总营收、30天销量、均价、平均评分、平均增长率]
[与昨日对比的环比变化]

## 二、竞品对比
[各品牌横向对比，指出增长最快/最慢的品牌及原因分析]

## 三、选品建议
[增长率最高的品类，潜在机会点，值得关注的趋势]

请用 Markdown 格式输出，包含标题、要点列表和简要结论。
```

**LLM 调用参数：**
- `temperature=0.3`
- `max_tokens=4096`
- `timeout=120`

### 新增模块：backend/analysis/__init__.py

空文件，使 analysis 成为 Python 包。

### 修改：backend/scheduler.py

新增 job：
```python
from backend.analysis.llm_report import run_llm_analysis

def run_llm_analysis_job():
    today = date.today()
    try:
        run_llm_analysis(today)
        logger.info("LLM analysis completed for %s", today)
    except Exception:
        logger.exception("LLM analysis failed for %s", today)

scheduler.add_job(run_llm_analysis_job, "cron", hour=2, minute=30, misfire_grace_time=3600)
```

### 新增路由：backend/routers/reports.py

| 接口 | 说明 |
|------|------|
| `GET /api/reports?date=YYYY-MM-DD` | 返回指定日期报告 |
| `GET /api/reports/latest` | 返回最新一份报告 |

响应结构：
```json
{
  "data": {
    "report_date": "2026-05-26",
    "content": "# 每日分析报告\n...",
    "model": "gemma-4-31b-it-fp8",
    "generated_at": "2026-05-26T02:35:12",
    "status": "success",
    "error_message": null
  },
  "error": null
}
```

若无报告返回 `{ "data": null, "error": null }`（不报 404）。

### 修改：backend/main.py

注册新路由：
```python
from backend.routers import reports
app.include_router(reports.router, prefix="/api")
```

### 修改：backend/requirements.txt

新增：
```
openai==1.30.5
```

---

## 配置

### 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ANALYSIS_LLM_BASE_URL` | `http://10.0.0.21:8005/v1` | LLM 服务地址 |
| `ANALYSIS_LLM_MODEL` | `gemma-4-31b-it-fp8` | 模型名称 |

### 修改：docker-compose.yml

在 fastapi 服务的 environment 下新增：
```yaml
ANALYSIS_LLM_BASE_URL: "http://10.0.0.21:8005/v1"
ANALYSIS_LLM_MODEL: "gemma-4-31b-it-fp8"
```

### 新增：.env（本地开发）

```
ANALYSIS_LLM_BASE_URL=http://10.0.0.21:8005/v1
ANALYSIS_LLM_MODEL=gemma-4-31b-it-fp8
```

---

## 前端

### 新增页面：frontend/src/pages/Reports.tsx

- 顶部：`DatePicker` 默认选中最新报告日期
- 报告元信息：生成时间、模型名称（灰色小字）
- 主体：`react-markdown` 渲染 `content` 字段
- 状态：加载中显示 `Skeleton`；`data=null` 时显示"当日报告尚未生成"；`status='failed'` 时显示 `Alert`（title="报告生成失败"）展示 `error_message`

### 新增文件：frontend/src/api/reports.ts

```typescript
export interface ReportData {
  report_date: string;
  content: string;
  model: string;
  generated_at: string;
  status: 'success' | 'failed';
  error_message: string | null;
}

export async function fetchLatestReport(): Promise<ReportData | null>
export async function fetchReport(date: string): Promise<ReportData | null>
```

### 修改：frontend/src/components/Layout.tsx

导航菜单新增：`{ key: '/reports', label: '每日报告' }`

### 修改：frontend/src/App.tsx

新增路由：`<Route path="/reports" element={<Reports />} />`

### 新增依赖：react-markdown

```
npm install react-markdown@9
```

---

## 错误处理

| 场景 | 处理方式 |
|------|----------|
| 当日聚合数据为空 | 记录 warning，跳过，不写 DB |
| LLM 网络超时 | 重试一次（共 2 次），失败写 `status='failed'` |
| LLM 返回空内容 | 重试一次，仍为空写 `status='failed'` |
| DB 写入失败 | 记录 exception 日志，不影响聚合任务 |
| 前端读到 failed 报告 | Alert 展示 error_message，页面不崩溃 |
| 前端无报告（data=null） | 提示"当日报告尚未生成" |

---

## 数据库迁移

新增迁移文件：`db/migrations/002_create_analysis_reports_table.sql`

---

## 不在本次范围内

- 报告历史列表页（仅支持按日期查询单份报告）
- 邮件推送
- LLM 流式输出
- 手动触发报告生成的 API
