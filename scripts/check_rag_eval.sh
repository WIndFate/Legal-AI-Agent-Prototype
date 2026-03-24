#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
K="${K:-3}"
MIN_RECALL="${MIN_RECALL:-0.5}"
MIN_MRR="${MIN_MRR:-0.6}"

command -v curl >/dev/null 2>&1 || {
  echo "[rag-eval] ERROR: curl is required" >&2
  exit 1
}
command -v jq >/dev/null 2>&1 || {
  echo "[rag-eval] ERROR: jq is required" >&2
  exit 1
}

response="$(curl -sS "${API_BASE_URL}/api/eval/rag?k=${K}")"
mean_recall="$(printf '%s' "$response" | jq -r '.mean_recall_at_k')"
mrr="$(printf '%s' "$response" | jq -r '.mrr')"

awk -v actual="$mean_recall" -v minimum="$MIN_RECALL" 'BEGIN { exit !(actual + 0 >= minimum + 0) }' \
  || {
    echo "[rag-eval] ERROR: mean_recall_at_k=${mean_recall} is below threshold ${MIN_RECALL}" >&2
    exit 1
  }

awk -v actual="$mrr" -v minimum="$MIN_MRR" 'BEGIN { exit !(actual + 0 >= minimum + 0) }' \
  || {
    echo "[rag-eval] ERROR: mrr=${mrr} is below threshold ${MIN_MRR}" >&2
    exit 1
  }

echo "[rag-eval] Passed with mean_recall_at_k=${mean_recall}, mrr=${mrr}, k=${K}"
