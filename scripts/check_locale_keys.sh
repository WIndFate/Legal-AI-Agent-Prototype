#!/usr/bin/env bash

set -euo pipefail

BASE_LOCALE="${BASE_LOCALE:-frontend/src/i18n/locales/ja.json}"
LOCALES_DIR="${LOCALES_DIR:-frontend/src/i18n/locales}"

command -v jq >/dev/null 2>&1 || {
  echo "[locale-check] ERROR: jq is required" >&2
  exit 1
}

tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

extract_keys() {
  local file="$1"
  jq -r 'paths(scalars) | map(tostring) | join(".")' "$file" | sort
}

base_keys="$tmp_dir/base.keys"
extract_keys "$BASE_LOCALE" >"$base_keys"

for locale_file in "$LOCALES_DIR"/*.json; do
  if [ "$locale_file" = "$BASE_LOCALE" ]; then
    continue
  fi

  locale_name="$(basename "$locale_file")"
  locale_keys="$tmp_dir/${locale_name}.keys"
  extract_keys "$locale_file" >"$locale_keys"

  if ! diff -u "$base_keys" "$locale_keys" >"$tmp_dir/${locale_name}.diff"; then
    echo "[locale-check] ERROR: locale key mismatch in ${locale_name}" >&2
    cat "$tmp_dir/${locale_name}.diff" >&2
    exit 1
  fi
done

echo "[locale-check] All locale files match ${BASE_LOCALE}"
