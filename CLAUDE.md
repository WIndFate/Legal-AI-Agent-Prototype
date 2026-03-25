# Repository Agent Instructions — 契約チェッカー (Contract Checker)

This document is intentionally mirrored in both `CLAUDE.md` and `AGENTS.md` for tool compatibility.
Keep the two files in sync whenever these instructions change.

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

**契約チェッカー** — An AI-powered contract risk analysis service for foreign residents in Japan. Users upload Japanese contracts (photo/PDF/text), pay per use (¥299–¥1,299), and receive a report in their selected language via SSE streaming.

**Target Users:** Chinese people living in Japan (~800K) who need to understand Japanese legal contracts but face language barriers.

**Core Value:** Affordable (price of a coffee), instant, understandable risk analysis of Japanese contracts — filling the gap between "free but unreliable" (social media) and "professional but expensive" (lawyers at ¥30,000–50,000).

Built with LangGraph (agentic loop), PostgreSQL pgvector (RAG), FastAPI (REST + SSE), React/Vite (frontend), Redis, and FastMCP (MCP server).

**Current implemented local MVP pipeline:** `upload_contract → (exact text quote | staged pre-OCR quote) → payment → recognize_text → parse_contract → analyze_risks → generate_report → persist_report`

- `upload_contract`: accepts text / image / PDF, estimates price, detects PII, and stages image/scanned PDF uploads for dual-OCR flow
- `recognize_text`: image OCR with GPT-4o Vision, PDF extraction with OCR fallback, but only after payment for staged OCR uploads
- `analyze_risks`: LLM agentic loop calls `analyze_clause_risk` (RAG inside) and `generate_suggestion`
- `generate_report`: aggregates results and translates to target language
- `persist_report`: stores report, caches it, emails link, and deletes contract text

**Target MVP pipeline (per DESIGN.md):** `upload_contract → recognize_text (OCR) → parse_contract → analyze_risks → generate_report → output_chinese_report`

Current status as of 2026-03-26:
- Local Docker end-to-end flow is verified through upload, payment creation, SSE review, report retrieval, and contract deletion.
- `APP_ENV=development` enables local-only conveniences such as auto table bootstrap and dev payment bypass.
- Dual-OCR groundwork is now in code: text/text-layer PDFs are quoted before payment, while image/scanned PDFs can be staged for local pre-estimation and formal OCR after payment.
- Production deployment and third-party production credentials are still pending.

---

## Running the Project

**All services run via Docker. Never try to run Python directly for verification.**

**Docker execution discipline for humans and AI tools:**
- Prefer `docker compose exec` for commands inside existing services.
- Avoid `docker compose run` unless there is no running service that can be reused.
- If `docker compose run` is unavoidable, use `--rm` and clean up immediately after use.
- If `docker compose down` reports that the network is still in use, inspect and remove leftover `*-run-*` containers before retrying cleanup.

```bash
# Start all services
docker compose up --build

# Restart after code changes
docker compose up --build backend

# View backend logs
docker compose logs -f backend

# Health check
curl http://localhost:8000/api/health

# Example upload
curl -X POST http://localhost:8000/api/upload \
  -F input_type=text \
  -F text='第1条（目的）本契約は業務委託について定める。'

# Local smoke regression
docker compose up -d backend postgres redis
./scripts/smoke_local_flow.sh
./scripts/check_locale_keys.sh
./scripts/check_rag_eval.sh
./scripts/run_backend_pytests.sh
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- Health check: `GET http://localhost:8000/api/health`

---

## Key Files

```
backend/
  agent/
    state.py      # AgentState TypedDict (+target_language field)
    tools.py      # LangChain tools: analyze_clause_risk (RAG inside), generate_suggestion
    nodes.py      # Node functions: parse_contract, analyze_risks, generate_report (+translation)
    graph.py      # LangGraph workflow + run_review / run_review_stream
  rag/
    store.py      # pgvector store (get_store()); OpenAI embeddings + cosine similarity search
    loader.py     # async load_legal_knowledge() for JSON + load_text_documents() for TXT chunks
  eval/
    evaluator.py  # Recall@K and MRR evaluation logic
  mcp/
    server.py     # FastMCP server exposing review_contract + search_legal_reference
  config.py       # pydantic-settings (OPENAI_API_KEY, DATABASE_URL, REDIS_URL, KOMOJU, etc.)
  dependencies.py # FastAPI deps: get_redis()
  main.py         # FastAPI app (router-based, lifespan: RAG load + Sentry + PostHog + APScheduler)
  db/
    session.py    # Async SQLAlchemy engine + session factory + get_db() dep
    migrations/   # Alembic async migrations (env.py + versions/)
  models/
    order.py      # Order model (UUID pk, payment_status, analysis_status, contract_deleted_at)
    report.py     # Report model (JSONB clause_analyses, 24h expires_at)
    referral.py   # Referral model (referral_code, uses_count, discount_jpy)
  schemas/
    order.py      # ReviewStreamRequest, etc.
    payment.py    # PaymentCreateRequest/Response
    report.py     # Report response schema
    upload.py     # UploadResponse
  routers/
    health.py     # GET /api/health
    upload.py     # POST /api/upload (image/PDF/text + OCR + PII + pricing)
    payment.py    # POST /api/payment/create + /api/payment/webhook
    review.py     # POST /api/review/stream (SSE, saves report + cache + email + cleanup)
    report.py     # GET /api/report/{order_id} (Redis cache → DB fallback)
    referral.py   # POST /api/referral/generate + GET /api/referral/{code}
    eval.py       # GET /api/eval/rag
  services/
    costing.py        # Model pricing table + usage extraction + structured cost logging
    local_ocr.py      # Optional PaddleOCR-based pre-payment quote estimation
    ocr.py            # GPT-4o Vision OCR
    pdf_extractor.py  # pypdf + OCR fallback
    temp_uploads.py   # Temporary upload staging for pre-payment OCR flows
    token_estimator.py # tiktoken + 4 price tiers + page-count fallback
    pii_detector.py   # Regex PII detection (phone, email, mynumber, address, postal)
    payment.py        # KOMOJU API client + HMAC webhook verification
    email.py          # Resend API client (9-language subjects)
    report_cache.py   # Redis report cache (24h TTL)
    cleanup.py        # APScheduler: expired reports + contract nullification
  data/
    eval_dataset.json  # Hand-labeled eval test set (5 samples)
    civil_law.txt      # Civil law TXT source for chunk ingestion
tests/
  test_token_estimator.py  # Token estimation + pricing unit tests
  test_pii_detector.py     # PII detection unit tests
frontend/
  src/
    main.tsx      # Router entry + i18n + lazy route loading + deferred analytics bootstrap
    data/
      exampleReports.ts  # Example report data (JP clause text + i18n key refs)
    components/
      Layout.tsx    # Header (brand + nav + lang) + footer (links + disclaimer)
    pages/
      HomePage.tsx    # Upload + pricing + payment form + example showcase
      PaymentPage.tsx # Payment polling / redirect
      ReviewPage.tsx  # SSE review progress + live report
      ReportPage.tsx  # Saved report page
      PrivacyPage.tsx # Privacy policy (i18n summary + JP legal text)
      TermsPage.tsx   # Terms of service (i18n summary + JP legal text)
docker-compose.yml  # backend + frontend + pgvector/pg16 + redis:7-alpine
scripts/
  smoke_local_flow.sh  # local end-to-end regression script
  check_locale_keys.sh # locale key consistency check
  check_rag_eval.sh    # local RAG metric regression check
  run_backend_pytests.sh # docker-based backend pytest runner
pyproject.toml
alembic.ini
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
- `generate_suggestion` is responsible for producing modification text: internally invokes a dedicated configurable suggestion model (currently defaulting to `gpt-4o-mini`) and returns the concrete suggestion. The outer LLM must use the return value directly as the `suggestion` field — do NOT have the outer LLM write suggestions itself.

### State fields
`AgentState` has exactly: `contract_text`, `clauses`, `risk_analysis`, `review_report`, `messages`, `target_language`.
Do NOT add `rag_results` or `current_clause_index` back — they were removed as dead fields.

### Streaming
`run_review_stream` uses `astream_events(version="v2")` from LangGraph. The frontend consumes SSE events of types: `node_start`, `token`, `tool_call`, `complete`, `error`.

### TXT documents are chunked alongside JSON knowledge
`load_text_documents()` scans `data/*.txt`, splits with `RecursiveCharacterTextSplitter`
(chunk_size=200, chunk_overlap=40, separators=["\n\n", "\n", "。", "、", ""]),
calls `store.add_chunks()`. Both live in the same pgvector table `legal_knowledge_embeddings`;
`store.search()` retrieves from both uniformly via cosine distance. User contracts are NEVER stored — query-only.

### RAG vector store: pgvector (not ChromaDB)
`store.py` uses PostgreSQL pgvector extension with `text-embedding-3-small` (1536 dims).
Embeddings are generated via OpenAI API (httpx direct call, not langchain).
`search()` is sync-compatible and uses direct `asyncpg` querying to avoid event-loop issues during tool calls.
`loader.py` is async and called with `await` from lifespan startup.

### Payment + Report flow
1. User uploads contract → gets pricing → creates order + KOMOJU session
2. KOMOJU webhook marks order as `paid`
3. If the order came from staged image/scanned PDF upload, formal OCR runs only after payment and before SSE review starts
4. User starts SSE review → report saved to DB + cached in Redis + emailed
5. Contract text nullified immediately after analysis (privacy)
6. Redis cache expires in 24h; APScheduler cleans DB hourly

### Cleanup and privacy
- `cleanup.py` runs every hour via APScheduler in lifespan
- Deletes expired reports (past `expires_at`)
- Nullifies `contract_text` for completed orders (defense in depth)
- The frontend may keep a session-only copy of the uploaded contract text in `sessionStorage` for on-device comparison on review/report pages; this does not change the backend rule that contract text is deleted after analysis and is never included in shared links.

### Local startup bootstrap
- `main.py` calls `init_db()` only when `APP_ENV=development`, so local Docker development can create `orders`, `reports`, and `referrals` automatically.
- Production environments should still run Alembic migrations explicitly rather than relying on implicit table creation.

### Environment safety rails
- `APP_ENV` must be either `development` or `production`; default is `development`.
- Dev payment bypass is allowed only in `development` when KOMOJU is not configured.
- In `production`, startup fails if KOMOJU or Resend credentials are missing, or if `FRONTEND_URL` points to `localhost`.
- In `production`, CORS is restricted to `FRONTEND_URL` only.

### Observability
- Payment creation, webhook rejection/ignore, review rejection, report cache hit/miss, and email skip/failure paths emit structured application logs.
- The same critical paths also emit PostHog events when analytics is configured.
- `main.py` initializes application logging at `INFO` level so these backend logs are visible in Docker and deployment logs.

### Report translation language rules
- `referenced_law` (参考法条) is always kept in Japanese original text, regardless of target language.
- `clause_number` is always kept as-is (e.g. 第1条).
- `risk_reason`, `suggestion`, `summary`, `risk_level`, `overall_risk` are translated to the target language.
- The `_translate_report()` function in `nodes.py` explicitly instructs the translator to preserve `referenced_law` and `clause_number` in Japanese.

### Brand identity
- Brand name: **ContractGuard** (unified across all 9 languages, never translated)
- `app.subtitle` is localized per language
- CSS-only brand mark (blue gradient shield via `clip-path: polygon()`)

### Frontend professional structure
- Homepage: hero card + flow steps + example showcase (3 contract scenarios with tab switching) + upload section
- Example reports use i18n keys for `risk_reason`/`suggestion` (key pattern: `examples.{scenario}_c{n}_reason/suggestion`), while `original_text`, `referenced_law`, `clause_number` stay in Japanese in `exampleReports.ts`
- Legal pages (`/privacy`, `/terms`): localized summary at top + hardcoded Japanese legal full text (required by law)
- Layout: sticky header with brand mark + nav links + language selector; footer with nav links to all pages + legal disclaimer + copyright
- Frontend routes should stay lazy-loaded where practical, and analytics/observability SDKs should bootstrap asynchronously so they do not bloat the initial application chunk

### Review/report UX behavior
- The review page should show user-facing progress text during SSE streaming; do not expose raw internal tool names like `analyze_clause_risk` to end users.
- `/api/report/{order_id}` must return the same payload shape whether data comes from Redis or PostgreSQL.
- Report content is fixed in the language chosen at payment time; later UI language switches only affect surrounding page chrome unless an explicit re-translation feature is implemented.
- Same-session original contract comparison should be clause-level and inline with each analysis card, not as a full-document dump at the bottom of the page.
- On larger screens, inline clause comparison can use a split layout, but mobile should preserve a single-column reading flow.
- Original clause text may be present in the SSE completion payload and same-session frontend storage, but must be stripped before database persistence, Redis caching, shared-link rendering, and email delivery.
- The saved report page should read like a concise professional review memo, and print / save-as-PDF from the browser should hide site chrome and preserve the report body cleanly.

### RAG evaluation
`GET /api/eval/rag` runs Recall@K and MRR against `eval_dataset.json`.
Eval only references JSON document IDs; TXT chunk auto-generated IDs do not affect eval.
- `scripts/check_rag_eval.sh` wraps the endpoint with the current local baseline thresholds (`Recall@3 >= 0.5`, `MRR >= 0.6`).

### Regression checks
- `scripts/check_locale_keys.sh` ensures all 9 locale files keep the same translation key set as `frontend/src/i18n/locales/ja.json`.
- `scripts/run_backend_pytests.sh` installs backend dev dependencies in Docker and runs the backend regression tests.
- `scripts/smoke_local_flow.sh` treats curl exit code `18` as acceptable for SSE shutdown and relies on the streamed `complete` / `error` events for pass-fail.

---

## Environment

Requires `.env` at project root:
```
OPENAI_API_KEY=sk-...
```

PostgreSQL data is persisted in Docker volume `pgdata`. RAG knowledge (pgvector embeddings) is loaded from `backend/data/` on startup. Redis is used for report caching (24h TTL).

---

## Development Notes

- Python 3.11+, dependencies in `pyproject.toml`
- Backend hot-reload: add `--reload` flag to uvicorn in `backend/Dockerfile` if needed
- MCP server runs as a separate process: `python -m backend.mcp.server`
- Docker commands should prefer `docker compose exec`; avoid `docker compose run` because it can leave orphan `*-run-*` containers that block `docker compose down`
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
