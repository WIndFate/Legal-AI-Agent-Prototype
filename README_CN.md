# 合同检查器

面向在日外国人的日文合同风险分析服务。用户可以上传文本、图片或 PDF 合同，按次付费，实时查看 SSE 分析过程，并在 24 小时内取回报告。

[English](./README.md) | [日本語ドキュメント](./README_JA.md)

## 当前状态

截至 2026-03-24，本地 Docker MVP 流程已经跑通：

- `upload -> payment/create -> review/stream -> report -> 合同文本删除`
- `pgvector` RAG 已运行在 PostgreSQL 中
- 前端 9 语言界面已实现
- 仅当 `APP_ENV=development` 且 `KOMOJU_SECRET_KEY` 为空时，本地开发可走自动支付

仓库外仍待完成：

- Fly.io / Vercel / Supabase 生产部署
- KOMOJU、Resend、Sentry、PostHog 生产密钥
- 真机拍照和跨设备手动测试

## 架构

```text
React/Vite 前端
  -> FastAPI 后端
  -> LangGraph 流程：
     parse_contract
     -> analyze_risks
     -> generate_report

RAG：
  PostgreSQL pgvector + OpenAI embeddings

持久化：
  PostgreSQL 保存 orders/reports/referrals
  Redis 缓存 24 小时报告

第三方：
  GPT-4o / GPT-4o-mini
  KOMOJU
  Resend
  PostHog
  Sentry
```

## 技术栈

- 后端：FastAPI、SQLAlchemy async、Alembic、Redis、APScheduler
- Agent：LangGraph、LangChain Tool Calling
- RAG：PostgreSQL `pgvector`、`text-embedding-3-small`
- 前端：React、Vite、TypeScript、React Router、i18next
- 基础设施：Docker Compose、Fly.io 配置、Vercel 配置

## 快速开始

前置条件：

- Docker Desktop / Docker Engine
- OpenAI API Key

启动：

```bash
cp .env.example .env
# 在 .env 中填写 OPENAI_API_KEY
# 本地 Docker 保持 APP_ENV=development

docker compose up --build
```

访问地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- 健康检查：`http://localhost:8000/api/health`

本地回归脚本：

```bash
docker compose up -d backend postgres redis
./scripts/smoke_local_flow.sh
```

## 本地体验流程

1. 打开前端并上传文本、图片或 PDF 合同。
2. 查看 token 估算、定价和 PII 提示。
3. 创建支付订单。
4. 本地开发时如果 `APP_ENV=development` 且 `KOMOJU_SECRET_KEY` 为空，订单会自动标记为已支付并跳到审查页。
5. 在 `/review/:orderId` 观看 SSE 流式分析。
6. 在 `/report/:orderId` 获取已保存报告。

## 关键实现说明

- 用户合同文本不会写入向量数据库。
- 分析完成后，`orders.contract_text` 会被置为 `NULL`。
- 报告会缓存到 Redis 24 小时，并在 PostgreSQL 中保存带过期时间的记录。
- 为了本地 Docker 开发可直接运行，后端启动时会自动补齐关系表。生产环境仍应显式执行 Alembic migration。
- 生产环境如果缺少 KOMOJU / Resend 关键配置，或 `FRONTEND_URL` 仍指向 `localhost`，启动会直接失败。
- 支付、审查、邮件、报告读取路径现在会输出结构化应用日志，并补充 PostHog 埋点，便于联调定位问题。
- `analyze_clause_risk` 工具内部直接做 RAG 检索，没有单独的 retrieval node。
- `scripts/smoke_local_flow.sh` 是标准本地回归入口，会验证 `health -> upload -> payment -> review -> report -> contract deletion`。

## 仓库入口

- [`backend/main.py`](./backend/main.py)：应用启动、路由注册、Sentry/PostHog、清理任务
- [`backend/routers/review.py`](./backend/routers/review.py)：SSE 审查、报告落库、隐私清理
- [`backend/rag/store.py`](./backend/rag/store.py)：pgvector 存储与检索
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh)：端到端本地 smoke/regression 脚本
- [`frontend/src/main.tsx`](./frontend/src/main.tsx)：前端路由、i18n、分析初始化
- [`SPEC.md`](./SPEC.md)：详细进度、待办和风险
- [`DESIGN.md`](./DESIGN.md)：产品设计和商业定位
