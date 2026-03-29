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

**契約チェッカー** — An AI-powered contract risk analysis service for foreign residents in Japan. Users upload Japanese contracts (photo/PDF/text), pay per use with length-based pricing (`¥75 / 1000 tokens`, minimum `¥200`), and receive a report in their selected language while progress is exposed through a persistent snapshot-plus-event stream flow.

**Target Users:** Chinese people living in Japan (~800K) who need to understand Japanese legal contracts but face language barriers.

**Core Value:** Affordable (price of a coffee), instant, understandable risk analysis of Japanese contracts — filling the gap between "free but unreliable" (social media) and "professional but expensive" (lawyers at ¥30,000–50,000).

Built with LangGraph (agentic loop), PostgreSQL pgvector (RAG), FastAPI (REST + SSE), React/Vite (frontend), Redis, and FastMCP (MCP server).

**Current implemented local MVP pipeline:** `upload_contract → (exact text quote | staged pre-OCR quote) → payment → recognize_text → parse_contract → analyze_risks → generate_report → persist_report`

- `upload_contract`: accepts text / image / PDF, estimates price, detects PII, and stages image/scanned PDF uploads for dual-OCR flow
- `recognize_text`: image OCR with GPT-4o Vision, PDF extraction with OCR fallback, but only after payment for staged OCR uploads
- `analyze_risks`: clause-by-clause analysis; each clause runs internal RAG lookup first, then a compact LLM judgment, and only high/medium risks trigger `generate_suggestion`
- `generate_report`: aggregates results and translates to target language
- `persist_report`: stores report, caches it, emails link, and deletes contract text

**Target MVP pipeline (per DESIGN.md):** `upload_contract → recognize_text (OCR) → parse_contract → analyze_risks → generate_report → output_chinese_report`

Current status as of 2026-03-28:
- Local Docker end-to-end flow is verified through upload, payment creation, persistent analysis-task start, status/event restoration, replayable event streaming, report retrieval, and contract deletion.
- `APP_ENV=development` enables local-only conveniences such as auto table bootstrap and dev payment bypass.
- Dual-OCR groundwork is now in code: text/text-layer PDFs are quoted before payment, while image/scanned PDFs can be staged for local pre-estimation and formal OCR after payment.
- Pre-payment image and scanned-PDF quotes now return OCR quality hints so users can correct blurry captures before paying.
- Exact text and text-layer PDF quotes now also include a lightweight clause-preview extraction so users can confirm the contract structure before they pay.
- Exact quote previews now generate a `quote_token`, cache clause previews by normalized content hash, and reuse those cached previews/cost snapshots when the same contract is uploaded again.
- Upload and preview generation are now both protected by Redis-backed per-IP rate limits so anonymous/scripted traffic cannot burn unbounded pre-payment preview cost.
- Deployment configs ready: `fly.toml` (NRT, force_https) + `vercel.json` (API proxy, security headers) + Alembic migration chain through `008`.
- `frontend/index.html` now includes static OG / Twitter metadata, and `frontend/public/og-image.svg` provides a lightweight branded social preview image.
- RAG knowledge base expanded to 331+ law articles across 10 legal categories (rental, labor, part-time, business outsourcing, sales, etc.).
- Eval dataset expanded to 20 labeled samples covering multiple contract types.
- Integration test suite: 7 router test files covering all API endpoints in the current runtime flow.
- Review progress now restores from persisted `analysis_events` and resumes through `/api/orders/{id}/stream?after_seq=...` rather than relying on client-side event deduplication against a single POST-driven SSE run.
- HomePage split into focused section components (Hero, Flow, Upload), with examples moved to a dedicated `/examples` page.
- RAG embedding batching, database query indexes, and dead code cleanup completed.
- CSS partially migrated to CSS Modules: layout, home, examples, legal use scoped modules; report/review remain global due to cross-page sharing and responsive dependencies.
- Frontend UX polish now includes result lookup, order reminder dialogs, a compact share sheet that silently appends referral codes to report links, direct review-to-report handoff on completion, a redesigned three-zone review progress experience (stage header + segmented progress bar + activity feed + elapsed timer), report risk-level filters, a real backend-generated PDF download action, reveal-on-scroll homepage sections, a curated standalone examples gallery whose report sample layout mirrors the real report page more closely, explicit homepage trust messaging for supported contract types, privacy-flow transparency on the legal page, mobile-specific compact header / left-menu / safe-area refinements, iOS input zoom prevention, top-of-page route resets, and a simplified homepage upload flow (`Upload File` / `Paste Text`).
- The homepage quote flow now gives immediate in-button loading feedback while preview generation runs, and the payment panel explicitly confirms the locked report-generation language before payment. The in-progress review activity feed is also re-localized from raw events, so switching the surrounding site language mid-analysis updates the feed immediately.
- Persistent analysis-task architecture is now the primary runtime flow: `analysis_jobs` / `analysis_events`, event bus, extracted report persistence helpers, new analysis start/status/events/stream routes, and frontend snapshot-plus-replay event restoration are all in code.
- Failed analyses now persist the partial AI cost summary already incurred up to the failure point into `analysis_jobs.cost_summary`, instead of keeping it only in memory/logs.
- Payment-time cost estimation is now persisted separately in `order_cost_estimates`: each order stores an `estimate_snapshot`, later an `actual_snapshot`, and finally a `comparison_snapshot`, all tagged with the estimate version, pricing-policy version, and the planned/actual model mix so pricing accuracy can be audited across future model upgrades.
- Local Docker startup now uses health checks for `postgres`, `redis`, and `backend`, and key frontend pages use a small retry wrapper so brief backend warm-up windows do not surface as user-facing proxy failures.
- Backend containers now auto-apply Alembic migrations to `head` on startup before Uvicorn boots, guarded by a PostgreSQL advisory lock and a legacy-schema detection/stamp path so old Docker volumes can move forward safely without manual migration steps.
- A new read-only operational endpoint, `GET /api/eval/operations`, now exposes margin, estimate-vs-actual deltas, language/input/pricing-model splits, paid-price-band splits, model-signature splits, and recent-order summaries for business monitoring.
- Production credentials and live third-party testing still pending.

---

## Running the Project

**All services run via Docker. Never try to run Python directly for verification.**

**Docker execution discipline for humans and AI tools:**
- Prefer `docker compose exec` for commands inside existing services.
- Avoid `docker compose run` unless there is no running service that can be reused.
- If `docker compose run` is unavoidable, use `--rm` and clean up immediately after use.
- If `docker compose down` reports that the network is still in use, inspect and remove leftover `*-run-*` containers before retrying cleanup.
- Compose startup now depends on service health: `backend` waits for healthy `postgres` / `redis`, and `frontend` waits for a healthy `backend`.

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
    loader.py     # async load_legal_knowledge() for e-Gov JSON ingestion
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
    order.py      # Order model (UUID pk, pricing_model, payment_status, analysis_status, contract_deleted_at)
    order_cost_estimate.py # Persisted estimate/actual/comparison cost snapshots per order
    report.py     # Report model (JSONB clause_analyses, 72h expires_at)
    referral.py   # Referral model (referral_code, uses_count, discount_jpy)
  schemas/
    analysis.py   # Analysis start/status/events/stream schemas
    payment.py    # PaymentCreateRequest/Response
    report.py     # Report response schema
    upload.py     # UploadResponse
  routers/
    health.py     # GET /api/health
    upload.py     # POST /api/upload (image/PDF/text + OCR + PII + pricing)
    payment.py    # POST /api/payment/create + /api/payment/webhook
    analysis.py   # POST /api/analysis/start + GET status/events/stream
    report.py     # GET /api/report/{order_id} + /api/report/{order_id}/pdf
    referral.py   # POST /api/referral/generate + GET /api/referral/{code}
    eval.py       # GET /api/eval/rag + /api/eval/costs + /api/eval/operations
  services/
    analysis_executor.py # In-process persistent analysis runner + event persistence
    costing.py        # Model pricing table + usage extraction + structured cost logging
    cost_analysis.py  # Persisted cost-summary aggregation + pricing recommendation logic
    order_cost_estimate.py # Payment-time estimate snapshots + actual/comparison snapshot builders
    quote_guard.py    # Exact-quote cache tokens + content-hash reuse + per-IP preview/upload rate limits
    report_pdf.py     # Build downloadable PDF reports from saved report payloads
    event_bus.py      # In-process pub/sub for incremental analysis events
    local_ocr.py      # Optional PaddleOCR-based pre-payment quote estimation
    ocr.py            # GPT-4o Vision OCR
    pdf_extractor.py  # pypdf + OCR fallback
    temp_uploads.py   # Temporary upload staging for pre-payment OCR flows
    token_estimator.py # tiktoken + linear token pricing (`¥75 / 1k`, minimum `¥200`) + internal page-count fallback
    pii_detector.py   # Regex PII detection (phone, email, mynumber, address, postal)
    payment.py        # KOMOJU API client + HMAC webhook verification
    email.py          # Resend API client (9-language subjects)
    report_cache.py   # Redis report cache (72h TTL)
    cleanup.py        # APScheduler: expired reports + contract nullification
  data/
    cost_samples_seed.json # Seeded cost baseline used until enough real cost samples exist
    egov_laws.json     # e-Gov API sourced law article corpus for RAG
    eval_dataset.json  # Hand-labeled eval test set (20 samples)
    pricing_policy.json # Runtime pricing table loaded by token_estimator
tests/
  test_cost_analysis.py    # Cost aggregation + pricing recommendation unit tests
  test_token_estimator.py  # Token estimation + pricing unit tests
  test_pii_detector.py     # PII detection unit tests
  test_router_health.py    # Health endpoint integration test
  test_router_upload.py    # Upload endpoint integration tests
  test_router_payment.py   # Payment endpoint integration tests
  test_router_analysis.py  # Persistent analysis routes integration tests
  test_router_report.py    # Report retrieval integration tests
  test_router_referral.py  # Referral endpoint integration tests
  test_router_eval.py      # Eval endpoint integration tests
frontend/
  src/
    main.tsx      # Router entry + i18n + lazy route loading + deferred analytics bootstrap
    lib/
      fetchWithRetry.ts # Timeout-aware retry wrapper for key frontend API calls
    data/
      exampleReports.ts  # Example report data (JP clause text + i18n key refs)
    components/
      Layout.tsx    # Header (brand + nav + lang) + footer (links + disclaimer)
      common/       # RevealSection + OrderReminderDialog + ShareSheet
      home/         # HomeHeroSection + HomeFlowSection + HomeExamplesSection + HomeUploadSection
    pages/
      HomePage.tsx          # Homepage container composing hero/flow/upload sections
      ExamplesPage.tsx      # Dedicated examples gallery / report sample page
      LookupPage.tsx        # Order-ID based result lookup page
      PaymentPage.tsx       # Payment polling + order reminder prompt
      ReviewPage.tsx        # Snapshot + replayed events + incremental progress + completion prompt
      ReportPage.tsx        # Saved report page + custom share sheet
      PrivacyPage.tsx       # Privacy policy (i18n summary + JP legal text)
      TermsPage.tsx         # Terms of service (i18n summary + JP legal text)
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

### Clause-level analysis pattern
- `analyze_clause_risk` and `generate_suggestion` remain the only two analysis helpers.
- Use `get_store().search()` directly in `analyze_clause_risk`. Do NOT add a `search_legal_knowledge` tool back.
- `analyze_risks` no longer keeps one growing whole-contract tool-calling conversation. It analyzes clauses one by one to cap prompt size and cost.
- The per-clause flow is:
  1. `analyze_clause_risk` returns compact RAG-backed legal context
  2. `gpt-4o` classifies that single clause into `高/中/低` with `risk_reason` and `referenced_law`
  3. `generate_suggestion` runs only for `高` / `中`
- Medium-risk suggestions should stay concise; high-risk suggestions can be more detailed.
- `generate_suggestion` internally invokes a dedicated configurable suggestion model (currently defaulting to `gpt-4o-mini`) and returns the concrete suggestion text.

### State fields
`AgentState` has exactly: `contract_text`, `clauses`, `risk_analysis`, `review_report`, `messages`, `target_language`.
Do NOT add `rag_results` or `current_clause_index` back — they were removed as dead fields.

### Streaming
`run_review_stream` still uses `astream_events(version="v2")` from LangGraph, but HTTP no longer starts analysis directly from one SSE POST. The executor persists high-value events into `analysis_events`, and the frontend restores history before subscribing to `/api/orders/{id}/stream?after_seq=...` for incremental updates.

### e-Gov law corpus is the current RAG source of truth
`load_legal_knowledge()` reads `backend/data/egov_laws.json`, a curated export generated by `scripts/fetch_egov_laws.py`.
At startup the app upserts that official law corpus into `legal_knowledge_embeddings`.
User contracts are NEVER stored in the vector table — query-only.

### RAG vector store: pgvector (not ChromaDB)
`store.py` uses PostgreSQL pgvector extension with `text-embedding-3-small` (1536 dims).
Embeddings are generated via OpenAI API (httpx direct call, not langchain).
`search()` is sync-compatible and uses direct `asyncpg` querying to avoid event-loop issues during tool calls.
`loader.py` is async and called with `await` from lifespan startup.

### Payment + Report flow
1. User uploads contract → gets pricing → creates order + KOMOJU session
2. KOMOJU webhook marks order as `paid`
3. If the order came from staged image/scanned PDF upload, formal OCR runs only after payment and before persistent analysis starts
4. `/review/:orderId` starts or resumes the persistent analysis task, restores saved event history, and subscribes to incremental updates
5. Contract text nullified immediately after analysis (privacy)
6. Redis cache expires in 72h; APScheduler cleans DB hourly

### Runtime pricing policy
- Upload pricing is no longer hardcoded directly in Python constants.
- `token_estimator.py` loads the active linear pricing policy from `backend/data/pricing_policy.json`.
- The current runtime policy is `¥75 / 1000 tokens` with a `¥200` minimum charge. Internally, page estimates remain only as a guardrail for upload limits and OCR planning.
- Exact quote uploads now emit a `quote_token`; Redis caches the resulting clause preview and `prepayment_snapshot` by normalized `content_hash`, so repeated uploads of the same contract reuse that preview instead of re-running the preview LLM call.
- The upload flow applies separate per-IP rate limits to raw upload requests and preview generation, preventing the exact-quote preview endpoint from being abused to generate unlimited anonymous LLM cost.
- Each paid order now also stores a payment-time estimate snapshot keyed by `COST_ESTIMATE_VERSION` and `pricing_policy_version`, including predicted clause counts, step-level estimated costs, quoted margin, and the planned model mix (`ocr/parse/analyze/suggestion/translation/embedding`).
- When an exact quote generated a pre-payment clause preview, that preview cost is persisted as `prepayment_snapshot` and merged into both the predicted and actual total cost snapshots.
- Analysis completion or failure now updates that same record with an `actual_snapshot` and `comparison_snapshot`, so pricing accuracy can be analyzed as “predicted vs actual” instead of only looking at final realized cost.
- `GET /api/eval/costs` mixes persisted `reports.cost_summary` with seeded baseline samples from `backend/data/cost_samples_seed.json` until at least 10 samples are available, so early pricing analysis is not based on a single order.
- `GET /api/eval/costs` returns both `recommended_price_jpy_cost_floor` and `recommended_price_jpy_target_margin`; the latter folds in `target_margin_rate` (currently default `0.75`) so pricing reviews can reason about profit targets, not just raw API cost.
- `GET /api/eval/costs` now also exposes estimate-vs-actual deltas plus grouping by `estimate_version` and model signature, so future model swaps can be compared on margin impact.
- `GET /api/eval/operations` is intentionally read-only and excludes seeded samples; it returns real-order aggregates for revenue, actual cost, actual margin, estimate deltas, recent orders, and splits by pricing model, paid-price band, input type, quote mode, target language, estimate version, and model signature.

### Cleanup and privacy
- `cleanup.py` runs every hour via APScheduler in lifespan
- Deletes expired reports (past `expires_at`)
- Nullifies `contract_text` for completed orders (defense in depth)
- The backend still deletes full contract text after analysis, but each 72-hour report may retain only clause-level original excerpts tied to findings so reopened links can preserve inline comparison without storing the full contract body.

### Local and production startup migrations
- Backend Docker startup now runs `python -m backend.start`, which waits for PostgreSQL, acquires a PostgreSQL advisory lock, and runs `alembic upgrade head` before launching Uvicorn.
- If a legacy Docker volume contains pre-Alembic / create_all-style tables, startup first repairs additive fields and indexes (including current `orders.pricing_model` expectations), stamps the detected schema revision, and only then upgrades forward, so old local data can be preserved.
- This auto-migration flow is used for both local Docker and production containers; manual migration is no longer the primary path for normal container boots.

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
- Homepage: hero card + flow steps + upload section, plus a guided entry point to the standalone examples gallery page
- The standalone examples page should feel like a curated report sample gallery, using chapter-like scenario switching and report-card spacing that stays visually close to the real saved report page
- Example reports use i18n keys for `risk_reason`/`suggestion` (key pattern: `examples.{scenario}_c{n}_reason/suggestion`), while `original_text`, `referenced_law`, `clause_number` stay in Japanese in `exampleReports.ts`
- Legal pages (`/privacy`, `/terms`): localized summary at top + hardcoded Japanese legal full text (required by law)
- Layout: sticky header with brand mark + nav links + language selector on desktop, plus a mobile left-menu / centered-logo variant; footer is intentionally reduced to Home / Privacy / Terms plus legal disclaimer and copyright
- Homepage reveal motion should stay restrained: fade/up reveal plus payment-panel spotlight is acceptable; avoid heavy parallax or novelty animations.
- Frontend routes should stay lazy-loaded where practical, and analytics/observability SDKs should bootstrap asynchronously so they do not bloat the initial application chunk

### Review/report UX behavior
- The review page is now a processing-only surface. It should show user-facing progress text during persistent event-stream playback and redirect into `/report/:orderId` once the saved report is ready; do not expose raw internal tool names like `analyze_clause_risk` to end users.
- If parse determines the uploaded content is not a contract, the analysis should terminate immediately with a dedicated `non_contract_document` failure state instead of continuing through full risk review.
- If parse determines the uploaded content is not a contract, the analysis should terminate immediately with a dedicated `non_contract_document` failure state instead of continuing through full risk review.
- `/api/report/{order_id}` must return the same payload shape whether data comes from Redis or PostgreSQL.
- Report content is fixed in the language chosen at payment time; later UI language switches only affect surrounding page chrome unless an explicit re-translation feature is implemented.
- Original contract comparison should be clause-level and inline with each analysis card, not as a full-document dump at the bottom of the page.
- On larger screens, inline clause comparison can use a split layout, but mobile should preserve a single-column reading flow.
- Full contract text must still be stripped after analysis, but clause-level original excerpts tied to findings may remain inside the 72-hour persisted report, Redis cache, shared-link rendering, and emailed report links.
- The saved report page should read like a concise professional review memo, and it should also support direct download of a backend-generated PDF built from the saved report payload.
- After quote generation, the homepage should visibly advance the user to the payment area instead of leaving the next step off-screen.
- After payment success and after review completion, the UI should prompt the user to save the order ID for later lookup.
- A dedicated lookup page should allow reopening payment, in-progress review, or the completed report from the order ID.
- Sharing should open a first-party share sheet before optional native share, keep the UI minimal, and generate a referral-tagged report URL behind the scenes while exposing only copy-link and optional native-share actions.
- The saved report page should support multi-select filtering by risk level so long reports can be narrowed to high / medium / low findings without changing the stored report data.
- Lookup/report pages should explicitly handle weak-network states: invalid order IDs, offline banners, timeout-aware loading, and one-tap retry actions.
- Lookup/report pages should explicitly handle weak-network states: invalid order IDs, offline banners, timeout-aware loading, and one-tap retry actions.
- On mobile Safari, critical text inputs such as order lookup should avoid focus-triggered zoom; use at least 16px input text where needed.
- Route changes to standalone pages such as privacy/terms should reset scroll to the top unless the navigation explicitly targets a hash anchor.

### RAG evaluation
`GET /api/eval/rag` runs Recall@K and MRR against `eval_dataset.json`.
`GET /api/eval/costs` aggregates persisted `reports.cost_summary` samples and returns pricing-oriented cost summaries.
Eval references the explicit document IDs in `egov_laws.json`.
- `scripts/check_rag_eval.sh` wraps the endpoint with the current local baseline thresholds (`Recall@5 >= 0.45`, `MRR >= 0.45`).

### Recoverable Event Streaming
- `ReviewPage.tsx` now restores `/api/orders/{id}/status`, replays `/api/orders/{id}/events?after_seq=...`, and then subscribes to `/api/orders/{id}/stream?after_seq=...`.
- Reconnection uses `lastSeq` rather than client-side event indexes, so resumed sessions do not depend on a single in-memory SSE run.
- Terminal states (`completed`, `failed`) are represented in persisted job state, so lookup can route directly to the correct page even after the browser closes.

### RAG embedding batching
- `store.py` implements `_get_embeddings_batch_sync()` for batched embedding API calls.
- `search_batch()` enables multiple clause searches in a single batch to reduce API round-trips.
- Batch results preserve original ordering by index for correct clause-to-result mapping.

### Integration test coverage
- 7 router test files covering all API endpoints: health, upload, payment, analysis, report, referral, eval.
- Test coverage includes persistent analysis start/status/events/stream behavior and report persistence helpers.
- Tests use FastAPI `TestClient` with mocked dependencies (DB, Redis, external APIs).

### CSS Modules strategy
- Component-scoped styles use Vite CSS Modules (`*.module.css`) with `clsx` for dynamic class composition.
- **Migrated to modules:** `layout.module.css` (Layout header/footer/nav), `home.module.css` (hero/flow/upload internals), `examples.module.css` (example showcase), `legal.module.css` (privacy/terms pages).
- **Kept global:** `base.css` (variables, reset, keyframes), `home.css` (card shells, tabs referenced by responsive.css), `layout.css` (page, section-kicker used across all pages), `report.css` and `review.css` (shared between ReviewPage/ReportPage + responsive/print dependencies + dynamic `step-${status}` class patterns), `responsive.css` (media queries targeting global classes).
- New frontend components should prefer CSS Modules for page-specific styling; shared cross-page patterns stay global.

### Regression checks
- `scripts/check_locale_keys.sh` ensures all 9 locale files keep the same translation key set as `frontend/src/i18n/locales/ja.json`.
- `scripts/run_backend_pytests.sh` installs backend dev dependencies in Docker and runs the full backend regression test suite.
- `scripts/smoke_local_flow.sh` now drives `analysis/start` plus `/api/orders/{id}/stream` and relies on persisted `complete` / `error` event records for pass-fail.

---

## Environment

Requires `.env` at project root:
```
OPENAI_API_KEY=sk-...
```

PostgreSQL data is persisted in Docker volume `pgdata`. RAG knowledge (pgvector embeddings) is loaded from `backend/data/` on startup. Redis is used for report caching (72h TTL).

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
- **Contracts are never stored** — deleted immediately after analysis, reports cached 72h then auto-deleted
- **Legal disclaimer required** on every page: 「本サービスは法律相談ではありません。具体的な法的判断は弁護士にご相談ください」
- **No assertive legal language** — never use "违法" "无效", only "可能存在风险" "建议确认" "建议咨询专业人士"
