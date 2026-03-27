# ContractGuard

AI-powered Japanese contract risk analysis for foreign residents in Japan. Users can upload a contract as text, image, or PDF, pay per use, follow analysis progress through a recoverable event stream, and retrieve a report for 24 hours.

[中文文档](./README_CN.md) | [日本語ドキュメント](./README_JA.md)

## Status

As of 2026-03-28, the local MVP flow is working in Docker:

- `upload -> payment/create -> analysis/start -> orders/{id}/status + events/stream -> report retrieval -> contract deletion`
- Text and text-layer PDFs are quoted before payment from extracted text; image/scanned PDF uploads now use a dual-OCR path with temporary staging plus post-payment formal OCR
- `pgvector` RAG is running in PostgreSQL with 331+ law articles across 10 legal categories (rental, labor, part-time, business outsourcing, sales, etc.)
- 9-language frontend with professional branding (ContractGuard), privacy/terms pages, and a dedicated examples gallery with report-style samples
- The standalone `/examples` page now uses a curated chapter-switching layout, and its report sample styling is intentionally closer to the real report page
- Mobile UI now uses a more compact header, a badge-style language switcher, immediate reveal rendering, and example switching that scrolls the refreshed report into view
- Homepage UX now includes reveal-on-scroll sections, auto-scroll into the payment panel after quote generation, and broader spacing/padding cleanup across upload, payment, review, and report surfaces
- The homepage upload flow now uses just two entry modes: `Upload File` and `Paste Text`. Image and PDF uploads are accepted through a single file picker with format guidance.
- A new `/lookup` page lets users reopen payment, analysis, or finished reports by order ID
- Payment success and analysis completion now show an order reminder dialog so users can screenshot or copy their order ID before moving on
- Review now acts as a processing surface only; once analysis finishes, the user is redirected straight into the saved `/report/{orderId}` page
- The saved report page now supports risk-level filtering, denser clause cards, and a more compact one-row summary on desktop
- Report sharing now uses a minimal custom share sheet that generates a referral-tagged report link behind the scenes, then offers copy-link and optional native share actions
- Referral links now return to the homepage with `?ref=` so the referral code is carried into the payment form automatically
- Lookup and report pages now distinguish invalid order IDs, unstable networks, offline states, and retryable loading failures more clearly
- Route-level lazy loading and deferred analytics bootstrap now reduce the initial frontend bundle
- Dev-mode payment works only when `APP_ENV=development` and `KOMOJU_SECRET_KEY` is absent
- Deployment configs ready: `fly.toml` (NRT region, force HTTPS) and `vercel.json` (API proxy, security headers)
- Integration test suite: 7 router test files covering all API endpoints in the current runtime flow
- Persistent analysis tasks now back the review flow, with status snapshots plus replayable event history before subscribing to incremental updates
- Homepage split into focused section components (Hero, Flow, Upload), and examples moved into a dedicated `/examples` gallery page
- RAG embedding batching for reduced API calls
- Dead code cleanup completed (removed unused `analyze_risks_streaming`)
- Database indexes on commonly queried columns (email, payment_status, expires_at, analysis_status)
- CSS partially migrated to CSS Modules: layout, home, examples, legal components use scoped modules with `clsx`; report/review remain global due to cross-page sharing

Still pending outside the repo:

- KOMOJU, Resend, Sentry, and PostHog production credentials and live testing
- Mobile camera/manual cross-device testing
- User feedback collection on report page (P2)
- OG tags and social media sharing optimization (P2)
- CSS Modules migration for report/review pages (kept global due to cross-page sharing)

## Architecture

```text
React/Vite frontend
  -> FastAPI backend
  -> LangGraph pipeline:
     parse_contract
     -> analyze_risks
     -> generate_report

RAG:
  PostgreSQL pgvector + OpenAI embeddings

Persistence:
  PostgreSQL for orders/reports/referrals
  Redis for 24h report cache

Integrations:
  GPT-4o / GPT-4o-mini
  KOMOJU
  Resend
  PostHog
  Sentry
```

## Tech Stack

- Backend: FastAPI, SQLAlchemy async, Alembic, Redis, APScheduler
- Agent: LangGraph, clause-level analysis pipeline
- RAG: PostgreSQL `pgvector`, `text-embedding-3-small`
- Frontend: React, Vite, TypeScript, React Router, i18next
- Infra: Docker Compose, Fly.io config, Vercel config

## Quick Start

Prerequisites:

- Docker Desktop / Docker Engine
- OpenAI API key

Setup:

```bash
cp .env.example .env
# fill OPENAI_API_KEY in .env
# keep APP_ENV=development for local Docker runs

docker compose up --build
```

Docker note:

- Prefer `docker compose exec` over `docker compose run` for local commands inside running services.
- `docker compose run` can leave temporary `*-run-*` containers behind and block `docker compose down`.
- Local OCR dependencies are gated behind `INSTALL_LOCAL_OCR=true` at Docker build time; the default backend image keeps them off for a lighter, safer baseline build.

Endpoints:

- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- Health: `http://localhost:8000/api/health`

Smoke regression:

```bash
docker compose up -d backend postgres redis
./scripts/smoke_local_flow.sh
./scripts/check_locale_keys.sh
./scripts/check_rag_eval.sh
./scripts/run_backend_pytests.sh
```

## Local Flow

1. Open the frontend and upload contract text, image, or PDF.
2. Review token estimate, pricing, and PII warnings. Image and scanned PDF uploads now explicitly show that the price is an estimate before payment.
3. Create payment.
4. In local dev, if `APP_ENV=development` and `KOMOJU_SECRET_KEY` is empty, the order is auto-marked as paid and redirected to review.
5. `/review/:orderId` starts or resumes the persistent analysis task, restores saved progress events, and then subscribes to new updates.
6. When analysis completes, the UI redirects directly into `/report/:orderId`.
7. The saved report page supports risk-level filtering so long reports can be narrowed to high / medium / low findings.
8. During the live review, the UI now shows user-facing progress text instead of raw internal tool names.
9. The saved report keeps the language chosen at payment time; switching the site language later only changes the page chrome.
10. Each clause analysis can expand its matching original clause excerpt inline for direct comparison throughout the 24-hour report lifetime, including reopened report links.
11. Expanded clause comparison is optimized for readability: mobile keeps a stacked reading flow, while larger screens place the original clause beside the analysis content.
11. The standalone `/examples` page presents three contract scenarios (rental, employment, part-time) as a gallery-style report showcase with localized clause analysis in all 9 languages.
12. Privacy policy (`/privacy`) and Terms of service (`/terms`) pages combine localized summaries with hardcoded Japanese legal text.
13. Referenced law citations (`referenced_law`) in reports are always kept in Japanese original text, regardless of the user's selected language.
14. The saved report page is now styled as a more document-like review report and also has print-friendly layout rules for browser print / save-as-PDF flows.
15. Homepage anchor navigation (`Home` / `Examples`) now scrolls to explicit page sections, and the hero pricing copy no longer hardcodes a visible maximum price.
16. After a quote is generated, the homepage automatically scrolls to the payment panel and highlights the next-step area so users do not miss that the flow has advanced.
17. Payment success and review completion now open a reminder dialog that emphasizes saving the order ID for later lookup.
18. A dedicated `/lookup` page can reopen pending-payment, in-progress review, or finished report states from the same order ID.
20. The report page now opens a compact custom share sheet first, silently appends the personal referral code to the report URL, and exposes only copy-link plus optional native-share actions.
21. Referral links now return to the homepage with `?ref=` so the referral code is prefilled for the next user.
22. Lookup and report pages now surface clearer weak-network states, retry actions, offline banners, timeout-aware loading feedback, and a dedicated expired-report fallback back to home.

## Important Implementation Notes

- User contract text is never stored in the vector database.
- After analysis completes, `orders.contract_text` is set to `NULL`.
- Image and scanned-PDF uploads can now be staged temporarily before payment; the staged file is deleted after analysis or by scheduled cleanup for stale unpaid orders.
- Reports are cached in Redis for 24 hours and stored in PostgreSQL with expiry metadata.
- `backend/services/costing.py` now emits structured per-step cost logs for formal OCR, parse, analyze, suggestion, and translation calls.
- Embedding requests now emit cost logs too, and review completion logs include an in-memory per-order cost summary with quote mode, input type, and clause counts.
- That order-level cost summary is now also persisted to `reports.cost_summary` for later inspection without relying only on logs.
- `GET /api/eval/costs` now aggregates persisted `reports.cost_summary` samples and, when live data is still sparse, backfills to a 10-sample baseline from `backend/data/cost_samples_seed.json`.
- Runtime pricing is now loaded from `backend/data/pricing_policy.json` instead of being hardcoded in Python. The current provisional table remains `¥299 / ¥499 / ¥799 / ¥1599`.
- `/api/eval/costs` now reports both a cost-floor recommendation and a target-margin recommendation (`target_margin_rate`, default `0.75`) so pricing reviews can distinguish “minimum safe price” from “commercial target price”.
- `PARSE_MODEL` and `SUGGESTION_MODEL` are now configurable and default to `gpt-4o-mini`, while formal OCR and per-clause risk classification remain on `gpt-4o` by default.
- `analyze_risks` now runs clause by clause instead of maintaining one growing multi-round tool-calling conversation, which materially reduces prompt growth and per-order cost.
- `analyze_clause_risk` now returns a compact RAG summary instead of replaying long source chunks back into the classifier prompt.
- `generate_suggestion` now adjusts verbosity by risk level: medium-risk clauses get shorter suggestions, while high-risk clauses can return more detailed rewrite guidance.
- The backend bootstraps relational tables on startup for local Docker development. Production should still run Alembic migrations explicitly.
- Production startup now fails fast if KOMOJU/Resend credentials are missing or `FRONTEND_URL` still points to `localhost`.
- Payment, review, email, and report retrieval paths now emit structured application logs and PostHog events for easier integration debugging.
- Frontend route pages are lazy-loaded, and analytics libraries are bootstrapped asynchronously so they do not bloat the initial application chunk.
- Frontend UX now includes reusable `RevealSection`, `OrderReminderDialog`, and `ShareSheet` components for scroll reveal, order-saving prompts, and custom sharing.
- `/api/report/{order_id}` now returns the same payload shape for both Redis cache hits and PostgreSQL fallback reads.
- `analyze_clause_risk` performs RAG lookup internally; there is no separate retrieval node.
- `scripts/smoke_local_flow.sh` now exercises the persistent-analysis flow end to end: health -> upload -> payment -> analysis/start -> orders/{id}/stream -> report -> contract deletion.
- Full contract text is never persisted after analysis, but each saved 24-hour report now keeps only the clause-level original excerpts tied to findings so reopened links and shared reports retain inline comparison.
- `scripts/check_locale_keys.sh` verifies that all 9 locale files keep the same translation key set as `ja.json`.
- The backend now loads the official e-Gov law corpus from `backend/data/egov_laws.json` on startup, covering 10 legal categories with 331+ articles. The local eval dataset has been expanded to 20 labeled samples covering damages, non-compete, termination, NDAs, lease, and more.
- `scripts/check_rag_eval.sh` checks `/api/eval/rag` against the current local baseline thresholds (`Recall@5 >= 0.45`, `MRR >= 0.45`).
- `scripts/run_backend_pytests.sh` runs the backend regression tests inside Docker after installing dev dependencies in the running backend container, and now executes the full `tests/` suite.
- Integration tests cover all 7 API routers (health, upload, payment, analysis, report, referral, eval).
- `frontend/src/pages/HomePage.tsx` now acts as a container page and delegates the hero, flow, and upload/payment areas to focused home components (`HomeHeroSection`, `HomeFlowSection`, `HomeUploadSection`), while `/examples` renders the standalone example showcase.
- The review flow now uses a single status snapshot endpoint plus replayable event history and incremental stream updates rather than starting analysis from one POST-driven SSE request.
- RAG embedding requests are batched via `_get_embeddings_batch_sync()` and `search_batch()` to reduce API calls.

## Repo Pointers

- [`backend/main.py`](./backend/main.py): app startup, routers, Sentry/PostHog, cleanup scheduler
- [`backend/routers/analysis.py`](./backend/routers/analysis.py): analysis start, order status snapshot, historical events, incremental event stream
- [`backend/services/analysis_executor.py`](./backend/services/analysis_executor.py): in-process persistent analysis executor and event persistence
- [`backend/rag/store.py`](./backend/rag/store.py): pgvector storage and search
- [`backend/eval/evaluator.py`](./backend/eval/evaluator.py): RAG evaluation metrics and dataset runner
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh): end-to-end local smoke/regression flow
- [`scripts/check_locale_keys.sh`](./scripts/check_locale_keys.sh): locale key consistency check
- [`scripts/check_rag_eval.sh`](./scripts/check_rag_eval.sh): local RAG metric regression check
- [`scripts/run_backend_pytests.sh`](./scripts/run_backend_pytests.sh): Docker-based backend pytest runner
- [`frontend/src/main.tsx`](./frontend/src/main.tsx): router entry, i18n, lazy route loading, deferred analytics bootstrap
- [`frontend/src/components/home/HomeHeroSection.tsx`](./frontend/src/components/home/HomeHeroSection.tsx): homepage hero section component
- [`frontend/src/components/home/HomeFlowSection.tsx`](./frontend/src/components/home/HomeFlowSection.tsx): homepage flow steps component
- [`frontend/src/components/home/HomeExamplesSection.tsx`](./frontend/src/components/home/HomeExamplesSection.tsx): homepage example showcase component
- [`frontend/src/components/home/HomeUploadSection.tsx`](./frontend/src/components/home/HomeUploadSection.tsx): homepage upload interface component
- [`frontend/src/pages/ExamplesPage.tsx`](./frontend/src/pages/ExamplesPage.tsx): dedicated examples gallery / report sample page
- [`frontend/src/pages/LookupPage.tsx`](./frontend/src/pages/LookupPage.tsx): order-ID based result lookup page
- [`frontend/src/components/common/OrderReminderDialog.tsx`](./frontend/src/components/common/OrderReminderDialog.tsx): modal prompting users to save order details
- [`frontend/src/components/common/ShareSheet.tsx`](./frontend/src/components/common/ShareSheet.tsx): custom share panel with copy/native-share actions
- [`tests/`](./tests/): integration tests for all 7 API routers + unit tests
- [`SPEC.md`](./SPEC.md): detailed implementation status, pending work, and risks
- [`DESIGN.md`](./DESIGN.md): product rationale and go-to-market plan
