#!/usr/bin/env bash
set -euo pipefail

# Promote curated documents from the raw bucket into the golden bucket via
# the datalake preprocess API. Run this after reviewing/approving content
# under s3://raw/{prefix} and before workspace ingestion.

API_BASE="${DOCOPS_API:-http://localhost:8000}"
RAW_BUCKET="${DATALAKE_RAW_BUCKET:-raw}"
GOLDEN_BUCKET="${DATALAKE_GOLDEN_BUCKET:-golden}"

DEFAULT_PREFIXES=(
  "product-acquisition/frameworks"
  "product-acquisition/policies"
  "product-acquisition/privacy"
  "product-acquisition/security"
)

if (($# > 0)); then
  PREFIXES=("$@")
else
  PREFIXES=("${DEFAULT_PREFIXES[@]}")
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required to call the datalake API." >&2
  exit 1
fi

for prefix in "${PREFIXES[@]}"; do
  SOURCE_PREFIX="${prefix#/}"  # trim leading slash if present
  DESTINATION_PREFIX="${SOURCE_PREFIX}"

  SOURCE_PATH="s3://${RAW_BUCKET}/${SOURCE_PREFIX}"
  DESTINATION_PATH="s3://${GOLDEN_BUCKET}/${DESTINATION_PREFIX}"

  PAYLOAD=$(cat <<JSON
{
  "source_prefix": "${SOURCE_PREFIX}",
  "destination_prefix": "${DESTINATION_PREFIX}"
}
JSON
)

  echo "Promoting ${SOURCE_PATH} -> ${DESTINATION_PATH} ..."
  set -x
  curl -sS -X POST "${API_BASE}/v1/datalake/preprocess/batch" \
    -H "Content-Type: application/json" \
    -d "${PAYLOAD}"
  set +x
done
