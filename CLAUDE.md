# CLAUDE.md — 契約チェッカー (Contract Checker)

## ⚠️ MANDATORY: Read DESIGN.md and SPEC.md First

**Before starting ANY task, you MUST read these two files in the project root:**
1. **`DESIGN.md`** — Product design: business plan, target users, pricing, go-to-market strategy, development roadmap. Answers "WHAT to build and WHY".
2. **`SPEC.md`** — Technical specification: architecture, API design, database schema, file structure, development phases. Answers "HOW to build it".

All implementation decisions must align with both documents. When in doubt, DESIGN.md takes precedence on product decisions, SPEC.md takes precedence on technical decisions.

## ⚠️ MANDATORY: Sync Docs on Git Commit

**When committing code changes, you MUST also update the following files to reflect the new code:**
1. **`CLAUDE.md`** — Update project overview, key files, architecture decisions, and any other sections affected by the code changes.
2. **`SPEC.md`** — Update implementation status (mark completed items, add new discoveries, adjust plans). This is the living technical spec — keep it in sync with reality.
3. **`README.md`** (English) — Update to reflect new features, architecture changes, or usage instructions.
4. **`README_CN.md`** (Chinese) — Keep in sync with README.md content, translated to Chinese.
5. **`README_JA.md`** (Japanese) — Keep in sync with README.md content, translated to Japanese.

All five docs must stay consistent with the actual codebase. Do not commit code-only changes without updating relevant documentation.

**注意：文档同步不需要每次微小提交都更新全部 5 个文档。仅在功能里程碑（完成一个完整功能模块）时同步更新文档。**

## ⚠️ MANDATORY: Granular Git Commits

**每完成一个最小逻辑单元，就立即提交。禁止攒一大批改动一次提交。**

提交粒度规范：
- **一个新文件 = 一次提交**（例：创建 config.py 后立即提交）
- **一个功能模块 = 一次提交**（例：创建 models/order.py + models/report.py + models/referral.py 可以合并为一次 "Add database models" 提交）
- **一个 bug 修复 = 一次提交**
- **文档更新 = 单独提交**（不要和代码变更混在一起）
- **依赖/配置变更 = 单独提交**（例：pyproject.toml、docker-compose.yml）

禁止的做法：
- ❌ 完成整个 Day 1-2 工作后一次提交 37 个文件
- ❌ 把不相关的改动放在同一个提交里
- ❌ 提交消息写 "Update multiple files" 这样模糊的描述

正确的做法：
- ✅ 每 1-5 个相关文件一次提交
- ✅ 提交消息清晰描述做了什么（例："Add SQLAlchemy Order/Report/Referral models"）
- ✅ 代码审查修复单独提交（例："Fix HTTP error responses per code review"）

---

## Project Overview

**契約チェッカー** — An AI-powered contract risk analysis service for Chinese residents in Japan. Users upload Japanese contracts (photo/PDF/text), pay per use (¥299–¥1,299), and receive a Chinese-language risk analysis report via SSE streaming.

**Target Users:** Chinese people living in Japan (~800K) who need to understand Japanese legal contracts but face language barriers.

**Core Value:** Affordable (price of a coffee), instant, Chinese-language risk analysis of Japanese contracts — filling the gap between "free but unreliable" (social media) and "professional but expensive" (lawyers at ¥30,000–50,000).

Built with LangGraph (agentic loop), ChromaDB (RAG), FastAPI (REST + SSE), React/Vite (frontend), and FastMCP (MCP server).

**Current prototype pipeline:** `parse_contract → analyze_risks → generate_report`

- `parse_contract`: LLM splits contract text into individual clauses (JSON)
- `analyze_risks`: LLM agentic loop calls `analyze_clause_risk` (RAG inside) and `generate_suggestion` tools
- `generate_report`: Aggregates results into final structured report

**Target MVP pipeline (per DESIGN.md):** `upload_contract → recognize_text (OCR) → parse_contract → analyze_risks → generate_report → output_chinese_report`

New capabilities needed for MVP: photo/PDF upload, GPT-4o Vision OCR, KOMOJU payment, Chinese report output, email delivery, 24h auto-deletion.

---

## Running the Project

**All services run via Docker. Never try to run Python directly for verification.**

```bash
# Start all services
docker compose up --build

# Restart after code changes
docker compose up --build backend

# View backend logs
docker compose logs -f backend

# Test the API
curl -X POST http://localhost:8000/api/review/stream \
  -H "Content-Type: application/json" \
  -d '{"contract_text": "第1条（目的）..."}'
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Health check: `GET http://localhost:8000/api/health`

---

## Key Files

```
backend/
  agent/
    state.py      # AgentState TypedDict
    tools.py      # LangChain tools: analyze_clause_risk (RAG inside), generate_suggestion
    nodes.py      # Node functions: parse_contract, analyze_risks, generate_report
    graph.py      # LangGraph workflow + run_review / run_review_stream
  rag/
    store.py      # ChromaDB singleton (get_store()); add_documents() for JSON, add_chunks() for TXT
    loader.py     # load_legal_knowledge() for JSON + load_text_documents() for TXT chunks
  eval/
    evaluator.py  # Recall@K and MRR evaluation logic
  mcp/
    server.py     # FastMCP server exposing review_contract + search_legal_reference
  main.py         # FastAPI app entry point
  data/
    eval_dataset.json  # Hand-labeled eval test set (5 samples)
    civil_law.txt      # Civil law TXT source for chunk ingestion
frontend/
  src/
    App.tsx       # Single-page UI consuming SSE stream
docker-compose.yml
pyproject.toml
```

---

## Architecture Decisions

### RAG is inside the tool, not a separate node
`analyze_clause_risk(clause_text)` calls `get_store().search()` directly inside the tool.
The LLM calls the tool per clause → receives real legal knowledge → makes risk judgment.
Do NOT add a `retrieve_knowledge` node back. Do NOT pre-inject RAG results into prompts.

### Tool calling pattern
- `ALL_TOOLS` contains exactly two tools: `analyze_clause_risk` and `generate_suggestion`.
- Use `get_store().search()` directly in tools. Do NOT add a `search_legal_knowledge` tool back — its functionality is already covered by `analyze_clause_risk` internally.
- `analyze_clause_risk` is responsible for risk judgment: queries RAG and returns relevant legal knowledge to the outer LLM.
- `generate_suggestion` is responsible for producing modification text: internally invokes a dedicated `gpt-4o` LLM and returns the concrete suggestion. The outer LLM must use the return value directly as the `suggestion` field — do NOT have the outer LLM write suggestions itself.

### State fields
`AgentState` has exactly: `contract_text`, `clauses`, `risk_analysis`, `review_report`, `messages`.
Do NOT add `rag_results` or `current_clause_index` back — they were removed as dead fields.

### Streaming
`run_review_stream` uses `astream_events(version="v2")` from LangGraph. The frontend consumes SSE events of types: `node_start`, `token`, `tool_call`, `complete`, `error`.

### TXT documents are chunked alongside JSON knowledge
`load_text_documents()` scans `data/*.txt`, splits with `RecursiveCharacterTextSplitter`
(chunk_size=200, chunk_overlap=40, separators=["\n\n", "\n", "。", "、", ""]),
calls `store.add_chunks()`. Both live in the same ChromaDB collection; `store.search()`
retrieves from both uniformly. User contracts are NEVER stored — query-only.

### RAG evaluation
`GET /api/eval/rag` runs Recall@K and MRR against `eval_dataset.json`.
Eval only references JSON document IDs; TXT chunk auto-generated IDs do not affect eval.

---

## Environment

Requires `.env` at project root:
```
OPENAI_API_KEY=sk-...
```

ChromaDB data is persisted in Docker volume `chroma_data`. RAG knowledge is loaded from `backend/data/` on startup.

---

## Development Notes

- Python 3.11+, dependencies in `pyproject.toml`
- Backend hot-reload: add `--reload` flag to uvicorn in `backend/Dockerfile` if needed
- MCP server runs as a separate process: `python -m backend.mcp.server`
- Code comments in English; user-facing UI messages in Chinese (target users are Chinese residents in Japan)
- Legal disclaimers and compliance text in Japanese (required by 弁護士法72条)
- Git commit messages must NOT include any Co-Authored-By or Claude signature lines
- Git commits must be granular: one logical unit per commit, never batch large changes

### Product Constraints (from DESIGN.md)

- **No user registration/login** — payment email serves as identity
- **No history feature** — report link is sent via email
- **Mobile-first web** — no native app in V1
- **Multi-language UI (9 languages)** — ja (default/fallback), en, zh-CN, zh-TW, pt-BR, id, ko, vi, ne. Auto-detect via `navigator.language`, manual switch stored in `localStorage`. Reports also output in user's selected language.
- **Pay-per-use only** — no subscriptions
- **Contracts are never stored** — deleted immediately after analysis, reports cached 24h then auto-deleted
- **Legal disclaimer required** on every page: 「本サービスは法律相談ではありません。具体的な法的判断は弁護士にご相談ください」
- **No assertive legal language** — never use "违法" "无效", only "可能存在风险" "建议确认" "建议咨询专业人士"
