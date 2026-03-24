#!/usr/bin/env bash

set -euo pipefail

command -v docker >/dev/null 2>&1 || {
  echo "[pytest] ERROR: docker is required" >&2
  exit 1
}

echo "[pytest] Installing backend dev dependencies in the running backend container"
docker compose exec -T backend pip install --no-cache-dir '.[dev]'

echo "[pytest] Running backend pytest suite"
docker compose exec -T backend pytest \
  tests/test_generate_report.py \
  tests/test_rag_evaluator.py \
  tests/test_token_estimator.py \
  tests/test_pii_detector.py
