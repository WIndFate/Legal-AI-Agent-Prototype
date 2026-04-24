# Repository Agent Instructions — 契約チェッカー (ContractGuard)

This file is mirrored in `AGENTS.md` for tool compatibility. **Keep the two files in sync on every edit.**

This document contains **behavior rules for AI agents** working in this repo. Keep implementation details in the README files and source code; do not duplicate long status snapshots here.

---

## 开始任务前

先读 `README.md` 和与任务直接相关的源码 / 测试。`CLAUDE.md` / `AGENTS.md` 只写行为规则，不保存产品路线图、进度快照或审计清单。

---

## 项目一句话

面向日文合同风险分析场景的开源 AI 工程案例。技术栈：LangGraph + pgvector + FastAPI + React/Vite + Redis + KOMOJU reference implementation。合同分析后立即删除，报告 Redis 缓存 72h。

---

## 运行与验证（只用 Docker，严禁直接跑 Python）

```bash
docker compose up --build              # 启动
docker compose up --build backend      # 后端改动后
docker compose logs -f backend         # 查日志
curl http://localhost:8000/api/health  # 健康检查
```

Docker 纪律：
- 优先 `docker compose exec`，避免 `docker compose run`（会留下 `*-run-*` 孤儿容器阻塞 `down`）。
- 如必须用 `run`，加 `--rm` 并立即清理。

本地回归脚本（完成一个逻辑单元后自行跑）：
```
scripts/smoke_local_flow.sh      # 端到端冒烟
scripts/check_locale_keys.sh     # 9 语言 i18n key 一致性
scripts/check_rag_eval.sh        # RAG Recall@5 / MRR 基线
scripts/run_backend_pytests.sh   # 后端 pytest
```

---

## Git 提交纪律（强约束）

**每完成一个最小逻辑单元立即提交。禁止攒改动。**

- 新文件 = 一次提交；同一功能模块的 2–5 个相关文件 = 一次提交。
- Bug 修复、文档更新、依赖/配置变更各自独立提交。
- 提交信息清晰描述做了什么（例：`Add SQLAlchemy Order/Report/Referral models`），不要写 `Update multiple files`。
- ❌ 提交消息**不得**包含 `Co-Authored-By` 或任何 Claude 签名。
- ❌ 提交前**不要跳 hook**（`--no-verify` 等）。

---

## 文档同步纪律

功能**里程碑**（完整模块完成）时，同步更新 `README.md` + `README_CN.md` + `README_JA.md`，必要时同步 `CLAUDE.md` + `AGENTS.md`。日常微小提交**不需要**每次都更新全部文档。

分工底线：
- AI 行为规则 → **CLAUDE.md + AGENTS.md**（镜像）
- 开源项目说明 / 运行方式 / 架构摘要 → **README.md + README_CN.md + README_JA.md**

---

## 架构铁律（Do-Not-Break）

以下约定是**刻意的设计**，不要"顺手优化回去"：

1. **RAG 在 tool 内部**：`analyze_clause_risk(clause_text)` 直接调用 `get_store().search()`。**不要**加回 `retrieve_knowledge` 节点或 `search_legal_knowledge` tool；**不要**把 RAG 结果预注入 prompt。
2. **`AgentState` 字段固定**：`contract_text / clauses / risk_analysis / review_report / messages / target_language`。**不要**加回 `rag_results` 或 `current_clause_index`。
3. **逐条分析，非整合同对话**：`analyze_risks` 对每个 clause 单独跑 `analyze_clause_risk → gpt-4o 分级 → 仅高/中风险触发 generate_suggestion`。不要恢复"整合同一轮大 prompt"模式。
4. **合同文本永不入向量库**：`legal_knowledge_embeddings` 只存 e-Gov 法条；用户合同仅查询，分析完即删。
5. **报告翻译时保持日文原文**：`referenced_law`、`clause_number` 必须保留日文；`risk_reason / suggestion / summary / risk_level / overall_risk` 才翻译到目标语言。见 `_translate_report()`。
6. **ReviewPage 不暴露内部工具名**：不要把 `analyze_clause_risk` 这类名字显示给终端用户。
7. **`analysis_executor` 持久化事件流是主链路**：HTTP 不再由单次 SSE POST 直接驱动分析。前端通过 `status + events/?after_seq= + stream?after_seq=` 恢复。
8. **失败终止 vs 继续分析**：`parse_contract` 判定非合同时立刻以 `error_code = non_contract_document` 终止，**不要**继续走 risk review。ReviewPage 用 `error_code` 而非本地化 `error_message` 判断失败类型。
9. **KOMOJU session 不发送 `payment_types`**：方法由商户账号审核控制；不要在代码里列支付方式白名单。
10. **订单 UUID 路径统一走 `routers/_helpers.parse_order_id`**：非法 UUID 返回 404，不要暴露 SQL DataError 500。
11. **OCR 供应商固定为 Google Cloud Vision**：图片和扫描 PDF 统一走 `DOCUMENT_TEXT_DETECTION`，**不要**换回 GPT-4o Vision，也不要恢复“付款前低成本 OCR / 付款后正式 OCR”双层路径。遗留的 `temp_uploads.py`、`orders.temp_upload_*` 列及 `upload_token / upload_name / upload_mime_type` 请求字段已在迁移 011 中彻底移除，不要恢复。
12. **高成本预付费路径必须 fail-closed**：OCR / preview 的 Redis 或预算守卫异常必须直接拒绝请求，**不要**在高成本匿名入口上做 fail-open。

---

## 工程与合规硬约束（不可改）

- **Reference implementation 定位** — UI 和 README 必须明确说明这不是 live service，不得写成正在运营或招募用户的产品。
- **无用户注册 / 登录** — reference workflow 只保留邮箱 / 订单号路径。
- **无历史页** — 报告链接 / 订单号恢复只作为本地参考流程。
- **移动端 Web 优先**，无原生 App。
- **9 语言 UI**：`ja`(默认/fallback) / `en` / `zh-CN` / `zh-TW` / `pt-BR` / `id` / `ko` / `vi` / `ne`。报告按付款时锁定的语言生成。
- **KOMOJU / Resend / pricing policy 均为参考实现** — 文档和 UI 不得暗示当前可购买、可付费试用或仍在商业运营。
- **合同永不持久化** — 分析后立即删除；报告缓存 72h 自动清理。允许在 72h 报告内保留 clause 级原文片段用于对照。
- **每页必须带法律免责**：「本サービスは法律相談ではありません。具体的な法的判断は弁護士にご相談ください」。
- **禁止断言性法律表述**：不得使用「违法」「无效」等词；只能用「可能存在风险」「建议确认」「建议咨询专业人士」。

---

## 环境与安全

- `APP_ENV ∈ {development, production}`，默认 `development`。
- production-like 启动必须校验：KOMOJU / Resend / Google Vision 凭据齐全、`FRONTEND_URL` 非 localhost、CORS 仅允许 `FRONTEND_URL`。
- production-like 环境下 RAG 加载失败 = 启动失败（硬错误）。
- Dev payment bypass 仅在 `development` 且 KOMOJU 未配置时允许。

---

## 代码风格

- **代码注释用英文**，UI 文案按 9 语言 i18n。
- 目标用户是在日华人，默认用户界面以中文为主，法律合规文本用日文。
- 新前端组件优先 CSS Modules；跨页共享样式保留 global。
- Python 3.11+；依赖在 `pyproject.toml`。
- MCP server 作为独立进程运行：`python -m backend.mcp.server`（仅限生产用途；验证仍用 Docker）。

---

## 其他

- 用户在 CLI 中要求帮助或反馈时告知：`/help` 查看 Claude Code 帮助；反馈请去 https://github.com/anthropics/claude-code/issues 。
