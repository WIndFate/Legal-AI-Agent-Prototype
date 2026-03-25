# ContractGuard

面向在日外国人的日文合同风险分析服务。用户可以上传文本、图片或 PDF 合同，按次付费，实时查看 SSE 分析过程，并在 24 小时内取回报告。

[English](./README.md) | [日本語ドキュメント](./README_JA.md)

## 当前状态

截至 2026-03-25，本地 Docker MVP 流程已经跑通：

- `upload -> payment/create -> review/stream -> report -> 合同文本删除`
- `pgvector` RAG 已运行在 PostgreSQL 中
- 前端 9 语言界面已实现，包含品牌标识（ContractGuard）、隐私政策/服务条款页面、交互式示例展示
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

Docker 说明：

- 本地进入已启动服务时优先使用 `docker compose exec`，不要默认使用 `docker compose run`。
- `docker compose run` 容易留下 `*-run-*` 临时容器，导致 `docker compose down` 时 network 无法释放。

访问地址：

- 前端：`http://localhost:5173`
- 后端：`http://localhost:8000`
- 健康检查：`http://localhost:8000/api/health`

本地回归脚本：

```bash
docker compose up -d backend postgres redis
./scripts/smoke_local_flow.sh
./scripts/check_locale_keys.sh
./scripts/check_rag_eval.sh
./scripts/run_backend_pytests.sh
```

## 本地体验流程

1. 打开前端并上传文本、图片或 PDF 合同。
2. 查看 token 估算、定价和 PII 提示。
3. 创建支付订单。
4. 本地开发时如果 `APP_ENV=development` 且 `KOMOJU_SECRET_KEY` 为空，订单会自动标记为已支付并跳到审查页。
5. 在 `/review/:orderId` 观看 SSE 流式分析。
6. 在 `/report/:orderId` 获取已保存报告。
7. 流式审查阶段现在展示的是面向用户的进度文案，不再直接暴露内部工具/方法名。
8. 报告正文会固定为支付时选择的语言；之后切换站点语言只影响页面壳层文案。
9. 在上传合同的同一设备当前会话中，每条分析都可以就地展开对应原条款进行对照；分享链接和邮件链接不会带出原文。
10. 展开后的条款对照已针对阅读体验优化：移动端保持纵向阅读，大屏下会并排展示原条款与分析内容。
11. 首页包含交互式示例展示，提供三种合同场景（租房、劳动、兼职），每种场景的条款分析均支持全部 9 种语言。
12. 隐私政策 (`/privacy`) 和服务条款 (`/terms`) 页面将本地化摘要与日语法律全文结合。
13. 报告中的参考法条 (`referenced_law`) 始终保持日语原文，不随用户选择的语言翻译。

## 关键实现说明

- 用户合同文本不会写入向量数据库。
- 分析完成后，`orders.contract_text` 会被置为 `NULL`。
- 报告会缓存到 Redis 24 小时，并在 PostgreSQL 中保存带过期时间的记录。
- 为了本地 Docker 开发可直接运行，后端启动时会自动补齐关系表。生产环境仍应显式执行 Alembic migration。
- 生产环境如果缺少 KOMOJU / Resend 关键配置，或 `FRONTEND_URL` 仍指向 `localhost`，启动会直接失败。
- 支付、审查、邮件、报告读取路径现在会输出结构化应用日志，并补充 PostHog 埋点，便于联调定位问题。
- `/api/report/{order_id}` 在 Redis 命中和 PostgreSQL fallback 两种情况下，现在都会返回一致的 payload 结构。
- `analyze_clause_risk` 工具内部直接做 RAG 检索，没有单独的 retrieval node。
- `scripts/smoke_local_flow.sh` 是标准本地回归入口，会验证 `health -> upload -> payment -> review -> report -> contract deletion`。
- `scripts/smoke_local_flow.sh` 已兼容 SSE 正常收流时可能出现的 `curl` 退出码 `18`，会以实际流事件内容判断成功与否。
- 原条款文本只存在于流式完成结果和同设备会话缓存中；数据库报告、Redis 缓存、分享链接和邮件链接都不会保存或暴露原文。
- `scripts/check_locale_keys.sh` 会检查 9 个语言文件是否与 `ja.json` 保持相同键集合。
- `scripts/check_rag_eval.sh` 会检查 `/api/eval/rag` 是否满足当前本地基线阈值（`Recall@3 >= 0.5`、`MRR >= 0.6`）。
- `scripts/run_backend_pytests.sh` 会在 Docker 内安装 backend dev 依赖并执行回归单测。

## 仓库入口

- [`backend/main.py`](./backend/main.py)：应用启动、路由注册、Sentry/PostHog、清理任务
- [`backend/routers/review.py`](./backend/routers/review.py)：SSE 审查、报告落库、隐私清理
- [`backend/rag/store.py`](./backend/rag/store.py)：pgvector 存储与检索
- [`backend/eval/evaluator.py`](./backend/eval/evaluator.py)：RAG 评估指标与数据集执行入口
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh)：端到端本地 smoke/regression 脚本
- [`scripts/check_locale_keys.sh`](./scripts/check_locale_keys.sh)：多语言 key 一致性检查
- [`scripts/check_rag_eval.sh`](./scripts/check_rag_eval.sh)：本地 RAG 指标回归检查
- [`scripts/run_backend_pytests.sh`](./scripts/run_backend_pytests.sh)：Docker 内 backend pytest 运行脚本
- [`frontend/src/main.tsx`](./frontend/src/main.tsx)：前端路由、i18n、分析初始化
- [`SPEC.md`](./SPEC.md)：详细进度、待办和风险
- [`DESIGN.md`](./DESIGN.md)：产品设计和商业定位
