# ContractGuard

面向在日外国人的日文合同风险分析服务。用户可以上传文本、图片或 PDF 合同，按次付费，实时查看 SSE 分析过程，并在 24 小时内取回报告。

[English](./README.md) | [日本語ドキュメント](./README_JA.md)

## 当前状态

截至 2026-03-27，本地 Docker MVP 流程已经跑通：

- `upload -> payment/create -> review/stream -> report -> 合同文本删除`
- 文本和可提取文本 PDF 会在付款前直接按文本估价；图片 / 扫描 PDF 现在走”双层 OCR”路径：先临时暂存并预估，付款后再做正式 OCR
- `pgvector` RAG 已运行在 PostgreSQL 中，覆盖 10 个法律类别共 331+ 条法律条文（租赁、劳动、兼职、业务委托、买卖等）
- 前端 9 语言界面已实现，包含品牌标识（ContractGuard）、隐私政策/服务条款页面、交互式示例展示
- 前端已加入路由级懒加载和延迟分析初始化，降低首屏 bundle 压力
- 仅当 `APP_ENV=development` 且 `KOMOJU_SECRET_KEY` 为空时，本地开发可走自动支付
- 部署配置已就绪：`fly.toml`（NRT 东京区域，强制 HTTPS）+ `vercel.json`（API 代理 + 安全头）
- 集成测试套件：7 个路由测试文件，39+ 测试函数，覆盖全部 API 端点
- SSE 断线重连：指数退避（3 次上限）+ 事件去重 + 60 秒无活动超时
- 首页已拆分为独立子组件（Hero、Flow、Examples、Upload）
- RAG embedding 批量化，减少 API 调用次数
- 死代码已清理（移除未使用的 `analyze_risks_streaming`）
- 数据库已为常用查询路径添加索引（email、payment_status、expires_at、analysis_status）
- CSS 部分迁移到 CSS Modules：layout、home、examples、legal 组件使用作用域模块 + `clsx`；report/review 因跨页面共享保持全局

仓库外仍待完成：

- KOMOJU、Resend、Sentry、PostHog 生产密钥与真实联调
- 真机拍照和跨设备手动测试
- 用户反馈收集机制（P2）
- OG tags 与社交媒体分享优化（P2）
- report/review 页面 CSS 模块化（因跨页面共享保持全局）

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
- Agent：LangGraph、按条款逐条分析的审查流水线
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
- 本地 OCR 依赖通过 `INSTALL_LOCAL_OCR=true` 的 Docker build 参数显式开启；默认后端镜像不会自动安装这些较重依赖。

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
2. 查看 token 估算、定价和 PII 提示。图片和扫描 PDF 现在会明确标注这是付款前的“预估报价”。
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
14. 保存后的报告页已进一步做成更像正式审阅文档的版式，并补充了浏览器打印 / 另存为 PDF 友好的样式规则。
15. 首页中的“首页 / 案例展示”现在都会滚动到明确锚点位置，首屏价格文案也不再硬编码展示可见最高价。

## 关键实现说明

- 用户合同文本不会写入向量数据库。
- 分析完成后，`orders.contract_text` 会被置为 `NULL`。
- 图片和扫描 PDF 现在会在付款前短期暂存原文件；分析完成后或未支付超时后，定时清理会删除这些临时文件。
- 报告会缓存到 Redis 24 小时，并在 PostgreSQL 中保存带过期时间的记录。
- `backend/services/costing.py` 现在会为正式 OCR、parse、analyze、suggestion、translation 输出结构化成本日志。
- embedding 请求现在也会输出成本日志，review 完成时还会记录一份包含报价模式、输入类型和条款统计的订单级成本摘要。
- 这份订单级成本摘要现在也会持久化到 `reports.cost_summary`，后续排查成本时不再只依赖日志。
- `GET /api/eval/costs` 现在会基于 `reports.cost_summary` 聚合真实样本成本；当真实样本还不够时，会自动从 `backend/data/cost_samples_seed.json` 补足到 10 条基线样本。
- 运行时定价现在从 `backend/data/pricing_policy.json` 读取，不再把价格硬编码在 Python 里。当前试运行价表是 `¥299 / ¥499 / ¥799 / ¥1599`。
- `/api/eval/costs` 现在会同时返回“成本底线建议价”和“目标毛利建议价”，默认目标毛利率 `target_margin_rate=0.75`，方便区分“不能低于多少”和“商业上该卖多少”。
- `PARSE_MODEL` 和 `SUGGESTION_MODEL` 现在已经可配置，默认切到 `gpt-4o-mini`；正式 OCR 和逐条风险判断默认仍保持 `gpt-4o`。
- `analyze_risks` 已改为按条款逐条分析，不再维护一段不断膨胀的整合同多轮 tool-calling 会话，因此单单成本和上下文压力都明显下降。
- `analyze_clause_risk` 现在返回的是压缩后的 RAG 审查摘要，而不是把长篇知识片段原样塞回分类 prompt。
- `generate_suggestion` 现在会根据风险级别控制长度：中风险建议更短，高风险建议允许更具体。
- 为了本地 Docker 开发可直接运行，后端启动时会自动补齐关系表。生产环境仍应显式执行 Alembic migration。
- 生产环境如果缺少 KOMOJU / Resend 关键配置，或 `FRONTEND_URL` 仍指向 `localhost`，启动会直接失败。
- 支付、审查、邮件、报告读取路径现在会输出结构化应用日志，并补充 PostHog 埋点，便于联调定位问题。
- 前端页面采用路由懒加载，分析相关 SDK 改为异步初始化，避免把 observability 依赖塞进首屏主 chunk。
- 前端现在新增了 `RevealSection`、`OrderReminderDialog`、`ShareSheet` 三类通用 UX 组件，分别用于滚动显现、订单号提醒弹层和自定义分享面板。
- `/api/report/{order_id}` 在 Redis 命中和 PostgreSQL fallback 两种情况下，现在都会返回一致的 payload 结构。
- `analyze_clause_risk` 工具内部直接做 RAG 检索，没有单独的 retrieval node。
- `scripts/smoke_local_flow.sh` 是标准本地回归入口，会验证 `health -> upload -> payment -> review -> report -> contract deletion`。
- `scripts/smoke_local_flow.sh` 已兼容 SSE 正常收流时可能出现的 `curl` 退出码 `18`，会以实际流事件内容判断成功与否。
- 原条款文本只存在于流式完成结果和同设备会话缓存中；数据库报告、Redis 缓存、分享链接和邮件链接都不会保存或暴露原文。
- `scripts/check_locale_keys.sh` 会检查 9 个语言文件是否与 `ja.json` 保持相同键集合。
- 后端现在会在启动时加载 `backend/data/egov_laws.json` 中的官方 e-Gov 法条语料，覆盖 10 个法律类别共 331+ 条文。当前本地评估集已扩展到 20 条人工标注样本，覆盖损害赔偿、竞业禁止、单方解约、NDA、租赁等场景。
- `scripts/check_rag_eval.sh` 会检查 `/api/eval/rag` 是否满足当前本地基线阈值（`Recall@5 >= 0.45`、`MRR >= 0.45`）。
- `scripts/run_backend_pytests.sh` 会在 Docker 内安装 backend dev 依赖并执行完整 `tests/` 回归单测。
- 集成测试覆盖全部 7 个 API 路由（health、upload、payment、review、report、referral、eval），共 39+ 测试函数。
- `frontend/src/pages/HomePage.tsx` 现在只作为容器页，首屏、流程、案例、上传/支付区域已拆到独立的首页组件中（`HomeHeroSection`、`HomeFlowSection`、`HomeExamplesSection`、`HomeUploadSection`）。
- 首页在生成报价后会自动滚动到支付区域，并对支付卡片做短暂高亮，避免用户点击“开始分析”后误以为页面没有反应。
- 现在新增 `/lookup` 结果查询页，用户输入订单号即可重新进入付款状态页、分析页或最终报告页。
- 支付成功和分析完成后，前端会弹出订单提醒框，引导用户截图或复制订单号。
- 报告页分享按钮现在先打开自定义分享面板，支持宣传型预览、复制链接、复制订单号，以及设备支持时的原生分享入口。
- 查询页和报告页现在会更明确地区分订单号格式错误、弱网、离线和可重试失败状态。
- SSE 断线重连采用指数退避（基础延迟 1 秒，最多 3 次）+ 事件去重 + 60 秒无活动超时机制。
- RAG embedding 请求已批量化，通过 `_get_embeddings_batch_sync()` 和 `search_batch()` 减少 API 调用。

## 仓库入口

- [`backend/main.py`](./backend/main.py)：应用启动、路由注册、Sentry/PostHog、清理任务
- [`backend/routers/review.py`](./backend/routers/review.py)：SSE 审查、报告落库、隐私清理
- [`backend/rag/store.py`](./backend/rag/store.py)：pgvector 存储与检索
- [`backend/eval/evaluator.py`](./backend/eval/evaluator.py)：RAG 评估指标与数据集执行入口
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh)：端到端本地 smoke/regression 脚本
- [`scripts/check_locale_keys.sh`](./scripts/check_locale_keys.sh)：多语言 key 一致性检查
- [`scripts/check_rag_eval.sh`](./scripts/check_rag_eval.sh)：本地 RAG 指标回归检查
- [`scripts/run_backend_pytests.sh`](./scripts/run_backend_pytests.sh)：Docker 内 backend pytest 运行脚本
- [`frontend/src/main.tsx`](./frontend/src/main.tsx)：前端路由、i18n、懒加载与延迟分析初始化
- [`frontend/src/components/home/HomeHeroSection.tsx`](./frontend/src/components/home/HomeHeroSection.tsx)：首页 hero 区域组件
- [`frontend/src/components/home/HomeFlowSection.tsx`](./frontend/src/components/home/HomeFlowSection.tsx)：首页流程步骤组件
- [`frontend/src/components/home/HomeExamplesSection.tsx`](./frontend/src/components/home/HomeExamplesSection.tsx)：首页案例展示组件
- [`frontend/src/components/home/HomeUploadSection.tsx`](./frontend/src/components/home/HomeUploadSection.tsx)：首页上传界面组件
- [`frontend/src/pages/LookupPage.tsx`](./frontend/src/pages/LookupPage.tsx)：订单号结果查询页
- [`frontend/src/components/common/OrderReminderDialog.tsx`](./frontend/src/components/common/OrderReminderDialog.tsx)：订单号保存提醒弹层
- [`frontend/src/components/common/ShareSheet.tsx`](./frontend/src/components/common/ShareSheet.tsx)：自定义分享面板
- [`tests/`](./tests/)：全部 7 个 API 路由的集成测试 + 单元测试
- [`SPEC.md`](./SPEC.md)：详细进度、待办和风险
- [`DESIGN.md`](./DESIGN.md)：产品设计和商业定位
