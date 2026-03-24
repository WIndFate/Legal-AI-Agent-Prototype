#!/usr/bin/env bash

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
DB_CONTAINER="${DB_CONTAINER:-postgres}"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

log() {
  printf '[smoke] %s\n' "$1"
}

fail() {
  printf '[smoke] ERROR: %s\n' "$1" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_cmd curl
require_cmd jq
require_cmd docker

wait_for_api() {
  local attempts="${1:-30}"
  local delay_seconds="${2:-1}"
  local i=1

  while [ "$i" -le "$attempts" ]; do
    if curl -sS "${API_BASE_URL}/api/health" >"$HEALTH_JSON"; then
      return 0
    fi
    sleep "$delay_seconds"
    i=$((i + 1))
  done

  return 1
}

CONTRACT_TEXT='第1条（目的）本契約は業務委託について定める。第2条（報酬）報酬は月末締め翌月末払いとする。第3条（解除）乙は30日前通知なく解除できない。'

HEALTH_JSON="$TMP_DIR/health.json"
UPLOAD_JSON="$TMP_DIR/upload.json"
PAYMENT_JSON="$TMP_DIR/payment.json"
STATUS_JSON="$TMP_DIR/status.json"
REVIEW_SSE="$TMP_DIR/review.sse"
REPORT_JSON="$TMP_DIR/report.json"

log "Checking API health"
wait_for_api || fail "API did not become healthy at ${API_BASE_URL}"
jq -e '.status == "ok"' "$HEALTH_JSON" >/dev/null || fail "Health check failed"

log "Uploading contract text"
curl -sS -X POST "${API_BASE_URL}/api/upload" \
  -F input_type=text \
  -F "text=${CONTRACT_TEXT}" \
  >"$UPLOAD_JSON"

jq -e '.contract_text | length > 0' "$UPLOAD_JSON" >/dev/null || fail "Upload returned empty contract_text"
jq -e '.price_jpy > 0' "$UPLOAD_JSON" >/dev/null || fail "Upload returned invalid price"

ESTIMATED_TOKENS="$(jq -r '.estimated_tokens' "$UPLOAD_JSON")"
PRICE_TIER="$(jq -r '.price_tier' "$UPLOAD_JSON")"
PRICE_JPY="$(jq -r '.price_jpy' "$UPLOAD_JSON")"
CONTRACT_TEXT_JSON="$(jq -r '.contract_text' "$UPLOAD_JSON")"

log "Creating payment order"
jq -n \
  --arg email "smoke-test@example.com" \
  --arg contract_text "$CONTRACT_TEXT_JSON" \
  --arg input_type "text" \
  --arg price_tier "$PRICE_TIER" \
  --arg target_language "zh-CN" \
  --argjson estimated_tokens "$ESTIMATED_TOKENS" \
  --argjson price_jpy "$PRICE_JPY" \
  '{
    email: $email,
    contract_text: $contract_text,
    input_type: $input_type,
    estimated_tokens: $estimated_tokens,
    price_tier: $price_tier,
    price_jpy: $price_jpy,
    target_language: $target_language
  }' \
  | curl -sS -X POST "${API_BASE_URL}/api/payment/create" \
      -H "Content-Type: application/json" \
      -d @- \
      >"$PAYMENT_JSON"

ORDER_ID="$(jq -r '.order_id' "$PAYMENT_JSON")"
[ -n "$ORDER_ID" ] && [ "$ORDER_ID" != "null" ] || fail "Payment create did not return order_id"

log "Checking payment status"
curl -sS "${API_BASE_URL}/api/payment/status/${ORDER_ID}" >"$STATUS_JSON"
jq -e '.status == "paid"' "$STATUS_JSON" >/dev/null || fail "Order is not paid in local dev mode"

log "Starting review stream"
set +e
jq -n --arg order_id "$ORDER_ID" '{order_id: $order_id}' \
  | curl -N -sS -X POST "${API_BASE_URL}/api/review/stream" \
      -H "Content-Type: application/json" \
      -d @- \
      >"$REVIEW_SSE"
REVIEW_STREAM_EXIT_CODE=$?
set -e

if [ "$REVIEW_STREAM_EXIT_CODE" -ne 0 ] && [ "$REVIEW_STREAM_EXIT_CODE" -ne 18 ]; then
  fail "Review stream request failed with curl exit code ${REVIEW_STREAM_EXIT_CODE}"
fi

grep -q '"type": "complete"' "$REVIEW_SSE" || fail "Review stream did not complete"
if grep -q '"type": "error"' "$REVIEW_SSE"; then
  fail "Review stream emitted an error event"
fi

log "Fetching saved report"
curl -sS "${API_BASE_URL}/api/report/${ORDER_ID}" >"$REPORT_JSON"
jq -e '(.report.summary // .summary // "") | length > 0' "$REPORT_JSON" >/dev/null || fail "Report summary is empty"
jq -e '(.report.clause_analyses // .clause_analyses // []) | length > 0' "$REPORT_JSON" >/dev/null || fail "Report clauses are empty"

log "Checking contract deletion and completion status in PostgreSQL"
DB_ROW="$(
  docker compose exec -T "$DB_CONTAINER" \
    psql -U postgres -d contract_checker -t -A \
    -c "SELECT o.payment_status || '|' || o.analysis_status || '|' || COALESCE(o.contract_text, '__NULL__') || '|' || CASE WHEN o.contract_deleted_at IS NULL THEN '__NULL__' ELSE 'deleted' END || '|' || COALESCE(r.language, '__NULL__') || '|' || CASE WHEN r.id IS NULL THEN '__NULL__' ELSE 'present' END FROM orders o LEFT JOIN reports r ON r.order_id = o.id WHERE o.id = '${ORDER_ID}';"
)"

[ -n "$DB_ROW" ] || fail "Order row not found in database"

PAYMENT_STATUS="$(printf '%s' "$DB_ROW" | cut -d'|' -f1)"
ANALYSIS_STATUS="$(printf '%s' "$DB_ROW" | cut -d'|' -f2)"
CONTRACT_TEXT_STATE="$(printf '%s' "$DB_ROW" | cut -d'|' -f3)"
DELETED_AT_STATE="$(printf '%s' "$DB_ROW" | cut -d'|' -f4)"
REPORT_LANGUAGE="$(printf '%s' "$DB_ROW" | cut -d'|' -f5)"
REPORT_STATE="$(printf '%s' "$DB_ROW" | cut -d'|' -f6)"

[ "$PAYMENT_STATUS" = "paid" ] || fail "Database payment_status is not paid"
[ "$ANALYSIS_STATUS" = "completed" ] || fail "Database analysis_status is not completed"
[ "$CONTRACT_TEXT_STATE" = "__NULL__" ] || fail "contract_text was not deleted"
[ "$DELETED_AT_STATE" = "deleted" ] || fail "contract_deleted_at was not set"
[ "$REPORT_LANGUAGE" = "zh-CN" ] || fail "Stored report language mismatch"
[ "$REPORT_STATE" = "present" ] || fail "Report row was not saved"

log "Smoke flow passed for order ${ORDER_ID}"
