#!/bin/bash
set -euo pipefail
API_BASE=${API_BASE:-http://localhost:8000}
TARGET_FOLDER=${TARGET_FOLDER:-samples}
SOURCE_PATH=${SOURCE_PATH:-./samples/datalake-demo}

# Datalake router lives under /v1
curl -fsS -X POST "$API_BASE/v1/datalake/upload" \
  -H 'Content-Type: application/json' \
  -d "{\"source_path\":\"$SOURCE_PATH\",\"target_folder\":\"$TARGET_FOLDER\"}"

echo "Uploaded sample bundle from $SOURCE_PATH to $TARGET_FOLDER"
