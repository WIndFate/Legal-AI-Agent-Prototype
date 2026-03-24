# Contract Checker

AI-powered Japanese contract risk analysis for foreign residents in Japan. Users can upload a contract as text, image, or PDF, pay per use, watch the analysis through SSE streaming, and retrieve a report for 24 hours.

[中文文档](./README_CN.md) | [日本語ドキュメント](./README_JA.md)

## Status

As of 2026-03-24, the local MVP flow is working in Docker:

- `upload -> payment/create -> review/stream -> report retrieval -> contract deletion`
- `pgvector` RAG is running in PostgreSQL
- 9-language frontend is implemented
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
- Agent: LangGraph, LangChain tool calling
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
2. Review token estimate, pricing, and PII warnings.
3. Create payment.
4. In local dev, if `APP_ENV=development` and `KOMOJU_SECRET_KEY` is empty, the order is auto-marked as paid and redirected to review.
5. Watch SSE analysis on `/review/:orderId`.
6. Retrieve the saved report on `/report/:orderId`.

## Important Implementation Notes

- User contract text is never stored in the vector database.
- After analysis completes, `orders.contract_text` is set to `NULL`.
- Reports are cached in Redis for 24 hours and stored in PostgreSQL with expiry metadata.
- The backend bootstraps relational tables on startup for local Docker development. Production should still run Alembic migrations explicitly.
- Production startup now fails fast if KOMOJU/Resend credentials are missing or `FRONTEND_URL` still points to `localhost`.
- Payment, review, email, and report retrieval paths now emit structured application logs and PostHog events for easier integration debugging.
- `analyze_clause_risk` performs RAG lookup internally; there is no separate retrieval node.
- `scripts/smoke_local_flow.sh` is the repeatable local regression entrypoint for `health -> upload -> payment -> review -> report -> contract deletion`.
- `scripts/check_locale_keys.sh` verifies that all 9 locale files keep the same translation key set as `ja.json`.
- `scripts/check_rag_eval.sh` checks `/api/eval/rag` against the current local baseline thresholds (`Recall@3 >= 0.5`, `MRR >= 0.6`).
- `scripts/run_backend_pytests.sh` runs the backend regression tests inside Docker after installing dev dependencies in the running backend container.

## Repo Pointers

- [`backend/main.py`](./backend/main.py): app startup, routers, Sentry/PostHog, cleanup scheduler
- [`backend/routers/review.py`](./backend/routers/review.py): SSE review, report persistence, privacy cleanup
- [`backend/rag/store.py`](./backend/rag/store.py): pgvector storage and search
- [`backend/eval/evaluator.py`](./backend/eval/evaluator.py): RAG evaluation metrics and dataset runner
- [`scripts/smoke_local_flow.sh`](./scripts/smoke_local_flow.sh): end-to-end local smoke/regression flow
- [`scripts/check_locale_keys.sh`](./scripts/check_locale_keys.sh): locale key consistency check
- [`scripts/check_rag_eval.sh`](./scripts/check_rag_eval.sh): local RAG metric regression check
- [`scripts/run_backend_pytests.sh`](./scripts/run_backend_pytests.sh): Docker-based backend pytest runner
- [`frontend/src/main.tsx`](./frontend/src/main.tsx): router entry, i18n, analytics bootstrap
- [`SPEC.md`](./SPEC.md): detailed implementation status, pending work, and risks
- [`DESIGN.md`](./DESIGN.md): product rationale and go-to-market plan
