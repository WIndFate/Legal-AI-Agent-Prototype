# ContractGuard

AI-powered Japanese contract risk analysis for foreign residents in Japan. Users can upload a contract as text, image, or PDF, pay per use, watch the analysis through SSE streaming, and retrieve a report for 24 hours.

[中文文档](./README_CN.md) | [日本語ドキュメント](./README_JA.md)

## Status

As of 2026-03-26, the local MVP flow is working in Docker:

- `upload -> payment/create -> review/stream -> report retrieval -> contract deletion`
- Text and text-layer PDFs are quoted before payment from extracted text; image/scanned PDF uploads now use a dual-OCR path with temporary staging plus post-payment formal OCR
- `pgvector` RAG is running in PostgreSQL
- 9-language frontend with professional branding (ContractGuard), privacy/terms pages, and interactive example showcase
- Route-level lazy loading and deferred analytics bootstrap now reduce the initial frontend bundle
- Dev-mode payment works only when `APP_ENV=development` and `KOMOJU_SECRET_KEY` is absent

Still pending outside the repo:

- Fly.io / Vercel / Supabase production deployment
- KOMOJU, Resend, Sentry, and PostHog production credentials
- Mobile camera/manual cross-device testing

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
5. Watch SSE analysis on `/review/:orderId`.
6. Retrieve the saved report on `/report/:orderId`.
7. During the live review, the UI now shows user-facing progress text instead of raw internal tool names.
8. The saved report keeps the language chosen at payment time; switching the site language later only changes the page chrome.
9. On the same device session that uploaded the contract, each clause analysis can expand its matching original clause inline for direct comparison. Shared links and emailed links do not include that original text.
10. Expanded clause comparison is optimized for readability: mobile keeps a stacked reading flow, while larger screens place the original clause beside the analysis content.
11. The homepage includes an interactive example showcase with three contract scenarios (rental, employment, part-time), each with localized clause analysis in all 9 languages.
12. Privacy policy (`/privacy`) and Terms of service (`/terms`) pages combine localized summaries with hardcoded Japanese legal text.
13. Referenced law citations (`referenced_law`) in reports are always kept in Japanese original text, regardless of the user's selected language.
14. The saved report page is now styled as a more document-like review report and also has print-friendly layout rules for browser print / save-as-PDF flows.
15. Homepage anchor navigation (`Home` / `Examples`) now scrolls to explicit page sections, and the hero pricing copy no longer hardcodes a visible maximum price.

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
- `PARSE_MODEL` and `SUGGESTION_MODEL` are now configurable and default to `gpt-4o-mini`, while formal OCR and per-clause risk classification remain on `gpt-4o` by default.
- `analyze_risks` now runs clause by clause instead of maintaining one growing multi-round tool-calling conversation, which materially reduces prompt growth and per-order cost.
- `analyze_clause_risk` now returns a compact RAG summary instead of replaying long source chunks back into the classifier prompt.
- `generate_suggestion` now adjusts verbosity by risk level: medium-risk clauses get shorter suggestions, while high-risk clauses can return more detailed rewrite guidance.
- The backend bootstraps relational tables on startup for local Docker development. Production should still run Alembic migrations explicitly.
- Production startup now fails fast if KOMOJU/Resend credentials are missing or `FRONTEND_URL` still points to `localhost`.
- Payment, review, email, and report retrieval paths now emit structured application logs and PostHog events for easier integration debugging.
- Frontend route pages are lazy-loaded, and analytics libraries are bootstrapped asynchronously so they do not bloat the initial application chunk.
- `/api/report/{order_id}` now returns the same payload shape for both Redis cache hits and PostgreSQL fallback reads.
- `analyze_clause_risk` performs RAG lookup internally; there is no separate retrieval node.
- `scripts/smoke_local_flow.sh` is the repeatable local regression entrypoint for `health -> upload -> payment -> review -> report -> contract deletion`.
- `scripts/smoke_local_flow.sh` tolerates curl exit code `18` on SSE shutdown and validates success from the actual streamed events instead.
- Original clause text is available only in the live review payload and same-device session storage; persisted reports, Redis cache, shared links, and emailed links do not store or expose it.
- `scripts/check_locale_keys.sh` verifies that all 9 locale files keep the same translation key set as `ja.json`.
- `scripts/check_rag_eval.sh` checks `/api/eval/rag` against the current local baseline thresholds (`Recall@3 >= 0.5`, `MRR >= 0.6`).
- `scripts/run_backend_pytests.sh` runs the backend regression tests inside Docker after installing dev dependencies in the running backend container, and now executes the full `tests/` suite.

## Repo Pointers

- [`backend/main.py`](./backend/main.py): app startup, routers, Sentry/PostHog, cleanup scheduler
- [`backend/routers/review.py`](./backend/routers/review.py): SSE review, report persistence, privacy cleanup
- [`backend/rag/store.py`](./backend/rag/store.py): pgvector storage and search
- [`backend/eval/evaluator.py`](./backend/eval/evaluator.py): RAG evaluation metrics and dataset runner
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh): end-to-end local smoke/regression flow
- [`scripts/check_locale_keys.sh`](./scripts/check_locale_keys.sh): locale key consistency check
- [`scripts/check_rag_eval.sh`](./scripts/check_rag_eval.sh): local RAG metric regression check
- [`scripts/run_backend_pytests.sh`](./scripts/run_backend_pytests.sh): Docker-based backend pytest runner
- [`frontend/src/main.tsx`](./frontend/src/main.tsx): router entry, i18n, lazy route loading, deferred analytics bootstrap
- [`SPEC.md`](./SPEC.md): detailed implementation status, pending work, and risks
- [`DESIGN.md`](./DESIGN.md): product rationale and go-to-market plan
