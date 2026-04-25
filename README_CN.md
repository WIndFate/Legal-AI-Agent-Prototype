# ContractGuard

[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)
![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)
![LangGraph](https://img.shields.io/badge/LangGraph-agentic%20workflow-purple.svg)

面向日文合同风险分析的 AI 工程案例 —— LangGraph workflow + pgvector RAG + 多模态输入 + 可恢复流式 UX。

> ⚠️ **不是法律服务。** 本仓库从未作为商业服务运营 —— 日本《弁護士法》第 72 条规定有偿法律咨询仅限持证律师从事。本项目作为开源技术案例发布，输出不构成法律意见。

[English](./README.md) | [日本語](./README_JA.md) | [License](./LICENSE)

## 项目状态

production-ready 级别的开源参考实现。整套技术栈 —— **前端、后端、OCR、支付、邮件、Postgres、Redis、错误追踪** —— 都接通了真实集成，随时可部署。只是因为律师法 72 条限制，从未投入商业运营（by design）。

仓库内置 [`docs/samples/`](./docs/samples/) 合成日文合同样本，clone 后即可一键跑通端到端流程。

## 架构

```mermaid
flowchart LR
  U[React/Vite UI<br/>文本、PDF、图片上传] --> API[FastAPI routers]
  API --> Q[估算 + PII + OCR 预算守卫]
  Q --> PAY[KOMOJU checkout<br/>参考实现]
  PAY --> JOB[持久化分析任务]
  JOB --> SSE[可恢复 SSE 流<br/>status + events + after_seq]
  JOB --> LG[LangGraph pipeline]
  LG --> P[parse_contract]
  P --> A[逐条 clause 风险分析]
  A --> T[tool call: analyze_clause_risk]
  T --> RAG[(PostgreSQL pgvector<br/>331 条日文法令)]
  A --> S[tool call: generate_suggestion<br/>仅中/高风险触发]
  S --> REP[报告生成 + 翻译]
  REP --> CACHE[(Redis 72h 报告缓存)]
  REP --> DB[(PostgreSQL orders/reports/costs)]
```

## 技术栈

| 层 | 选型 |
|---|---|
| 前端 | React、Vite、TypeScript、i18next（9 语言） |
| 后端 | FastAPI、SQLAlchemy async、Alembic、APScheduler |
| AI 工作流 | LangGraph + OpenAI tool calling、MCP server |
| RAG | PostgreSQL `pgvector`、331 条公开 e-Gov 日文法令 |
| OCR | Google Cloud Vision（`DOCUMENT_TEXT_DETECTION`） |
| 存储 | PostgreSQL（订单 / 报告 / 事件）、Redis（72h 缓存 + 速率限制） |
| 支付 | KOMOJU checkout |
| 邮件 | Resend |
| 观测 | Sentry + PostHog |
| 基础设施 | Docker Compose（本地）、Fly.io + Vercel（部署参考） |

## 本地启动

本地运行只需要 **OpenAI API Key**。

```bash
cp .env.example .env
# 编辑 .env：填入 OPENAI_API_KEY
docker compose up --build
```

然后打开 <http://localhost:5173>，上传 [`docs/samples/sample-contract-ja.txt`](./docs/samples/sample-contract-ja.txt) 即可测试。

最简模式下：

- ✅ 纯文本合同和**文本型 PDF**（可选中文字的 PDF）端到端可用。
- ❌ **图片 / 扫描 PDF 的 OCR** 不可用。如需启用，配置 `GOOGLE_APPLICATION_CREDENTIALS_JSON` 与 `GOOGLE_VISION_PROJECT_ID`。
- 开发模式下 KOMOJU / Resend 自动 bypass —— 不会真实扣款，也不会真实发邮件。

## 生产部署

仓库已具备生产部署形态，只需将 `APP_ENV=production` 并配置以下外部服务凭据：

| 服务 | 必需的环境变量 |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Google Cloud Vision（OCR） | `GOOGLE_APPLICATION_CREDENTIALS_JSON`、`GOOGLE_VISION_PROJECT_ID` |
| KOMOJU（支付） | `KOMOJU_SECRET_KEY`、`KOMOJU_PUBLISHABLE_KEY`、`KOMOJU_WEBHOOK_SECRET` |
| Resend（邮件） | `RESEND_API_KEY` |
| Sentry | `SENTRY_DSN`、`VITE_SENTRY_DSN` |
| PostHog | `POSTHOG_API_KEY`、`VITE_POSTHOG_KEY` |
| 数据库 / 缓存 | `DATABASE_URL`（托管 Postgres + pgvector）、`REDIS_URL`（托管 Redis） |
| 应用 | `FRONTEND_URL`（非 localhost）、`ADMIN_API_TOKEN` |

`APP_ENV=production` 时，应用会**拒绝启动**如果上述任一必需变量为空，或 `FRONTEND_URL` 仍指向 localhost。严格校验逻辑见 [`backend/config.py`](./backend/config.py) 的 `validate_runtime()`。

`fly.toml` 与 `vercel.json` 描述了开发期使用的部署拓扑。当前未托管运行。

## 运行流程

1. 上传合同（文本、PDF 或图片）。upload route 执行文本提取、PII 检测、token 估算、非合同判定、OCR 预算守卫。
2. checkout 参考链路创建订单。开发环境 KOMOJU 凭据为空时走本地 bypass。
3. `/review/:orderId` 启动或恢复持久化分析任务，进度事件可承受页面刷新。
4. LangGraph 解析条款、逐条 RAG-grounded tool call 分析、仅在必要条款生成建议。
5. `/report/:orderId` 展示报告、条款摘录、风险筛选、PDF 导出，72 小时保留。

用户合同正文在分析后删除。向量库只保存公开 e-Gov 法令，用户合同永不写入向量库。

## Demo

![home](./docs/demo-home.png)
![review progress](./docs/demo-review-progress.png)
![report](./docs/demo-report.png)

## 仓库地图

- [`backend/agent/graph.py`](./backend/agent/graph.py) —— LangGraph pipeline。
- [`backend/agent/tools.py`](./backend/agent/tools.py) —— RAG-grounded tool calls。
- [`backend/services/analysis_executor.py`](./backend/services/analysis_executor.py) —— 持久化分析任务 + 事件溯源。
- [`backend/rag/store.py`](./backend/rag/store.py) —— pgvector 存储与检索。
- [`backend/config.py`](./backend/config.py) —— 运行时配置与严格校验。
- [`frontend/src/pages/ReviewPage.tsx`](./frontend/src/pages/ReviewPage.tsx) —— 可恢复分析进度 UI。
- [`frontend/src/pages/ReportPage.tsx`](./frontend/src/pages/ReportPage.tsx) —— 报告页 UI、风险筛选、PDF 导出。
- [`tests/`](./tests/) —— 后端 pytest 测试套件。
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh) —— 端到端本地冒烟测试。
