#!/usr/bin/env bash

set -euo pipefail

command -v docker >/dev/null 2>&1 || {
  echo "[pytest] ERROR: docker is required" >&2
  exit 1
}

echo "[pytest] Installing backend dev dependencies in the running backend container"
docker compose exec -T backend pip install --no-cache-dir '.[dev]'

echo "[pytest] Running backend pytest suite"
docker compose exec -T backend pytest tests/
