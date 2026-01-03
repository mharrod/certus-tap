#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage: ./scripts/setup-security-search.sh [options]

Bootstrap a workspace and seed LocalStack S3 with the sample SARIF/SPDX files
used throughout the keyword, semantic, and hybrid search tutorials.

Options:
  -w, --workspace <id>     Workspace slug to highlight in docs (default: $WORKSPACE_ID or security-search-demo)
      --raw-bucket <name>  Raw bucket name (default: $DATALAKE_RAW_BUCKET or raw)
      --golden-bucket <name>  Golden bucket name (default: $DATALAKE_GOLDEN_BUCKET or golden)
  -s, --s3-endpoint <url>  LocalStack/MinIO endpoint (default: $S3_ENDPOINT_URL or http://localhost:4566)
  -i, --ingest-all         Promote raw/active/* → golden/scans/, ingest every object via the backend, and create aliases
      --backend-url <url>  Ask-Certus backend base URL (default: $BACKEND_URL or http://localhost:8000)
      --opensearch-url <url>  OpenSearch base URL (default: $OPENSEARCH_URL or http://localhost:9200)
  -h, --help               Show this message

Environment variables:
  WORKSPACE_ID, DATALAKE_RAW_BUCKET, DATALAKE_GOLDEN_BUCKET, S3_ENDPOINT_URL, BACKEND_URL, OPENSEARCH_URL
EOF
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        printf "ERROR: Required command '%s' not found in PATH\n" "$1" >&2
        exit 1
    fi
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)

WORKSPACE_ID=${WORKSPACE_ID:-security-search-demo}
RAW_BUCKET=${DATALAKE_RAW_BUCKET:-raw}
GOLDEN_BUCKET=${DATALAKE_GOLDEN_BUCKET:-golden}
S3_ENDPOINT=${S3_ENDPOINT_URL:-http://localhost:4566}
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}
OPENSEARCH_URL=${OPENSEARCH_URL:-http://localhost:9200}
INGEST_ALL=false

while [[ $# -gt 0 ]]; do
    case "$1" in
        -w|--workspace)
            WORKSPACE_ID=$2
            shift 2
            ;;
        --raw-bucket)
            RAW_BUCKET=$2
            shift 2
            ;;
        --golden-bucket)
            GOLDEN_BUCKET=$2
            shift 2
            ;;
        -s|--s3-endpoint)
            S3_ENDPOINT=$2
            shift 2
            ;;
        -i|--ingest-all)
            INGEST_ALL=true
            shift 1
            ;;
        --backend-url)
            BACKEND_URL=$2
            shift 2
            ;;
        --opensearch-url)
            OPENSEARCH_URL=$2
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            printf "Unknown option: %s\n\n" "$1" >&2
            usage
            exit 1
            ;;
    esac
done

require_cmd aws

printf "Bootstrapping workspace '%s'\n" "$WORKSPACE_ID"
printf "Raw bucket: %s | Golden bucket: %s | Endpoint: %s\n" "$RAW_BUCKET" "$GOLDEN_BUCKET" "$S3_ENDPOINT"

aws --endpoint-url "$S3_ENDPOINT" s3 mb "s3://$RAW_BUCKET" 2>/dev/null || true
aws --endpoint-url "$S3_ENDPOINT" s3 mb "s3://$GOLDEN_BUCKET" 2>/dev/null || true

mkdir -p "$REPO_ROOT/tmp" >/dev/null 2>&1 || true

for prefix in "active/" "quarantine/"; do
    aws --endpoint-url "$S3_ENDPOINT" s3api put-object --bucket "$RAW_BUCKET" --key "$prefix" >/dev/null 2>&1 || true
done

aws --endpoint-url "$S3_ENDPOINT" s3api put-object --bucket "$GOLDEN_BUCKET" --key "scans/" >/dev/null 2>&1 || true

SAMPLES_DIR="$REPO_ROOT/samples/security-scans"
declare -a SAMPLE_MAP=(
    "sarif/security-findings.sarif:bandit-scan.sarif"
    "spdx/sbom-example.spdx.json:sbom.spdx.json"
)

for entry in "${SAMPLE_MAP[@]}"; do
    IFS=':' read -r relative_path destination <<<"$entry"
    source_path="$SAMPLES_DIR/$relative_path"

    if [[ ! -f "$source_path" ]]; then
        printf "WARNING: Sample file not found: %s (skipping)\n" "$source_path" >&2
        continue
    fi

    target_uri="s3://$RAW_BUCKET/active/$destination"
    printf "Uploading %s → %s\n" "$source_path" "$target_uri"
    aws --endpoint-url "$S3_ENDPOINT" s3 cp "$source_path" "$target_uri" >/dev/null
done

printf "\nWorkspace bootstrap complete.\n"
printf "Next steps:\n"
printf "  1. Export WORKSPACE_ID (e.g., 'export WORKSPACE_ID=%s').\n" "$WORKSPACE_ID"
printf "  2. Run privacy scan + promotion workflows as needed.\n"
printf "  3. Ingest from golden bucket using your preferred tutorial.\n"

if [[ "$INGEST_ALL" == true ]]; then
    printf "\n[ingest] Promoting objects from s3://%s/active/ → s3://%s/scans/ …\n" "$RAW_BUCKET" "$GOLDEN_BUCKET"
    ACTIVE_RAW=$(aws --endpoint-url "$S3_ENDPOINT" s3api list-objects-v2 \
        --bucket "$RAW_BUCKET" \
        --prefix "active/" \
        --query 'Contents[].Key' \
        --output text | tr '\t' '\n')

    while IFS= read -r key; do
        [[ -z "$key" || "$key" == "None" ]] && continue
        base=${key#active/}
        [[ -z "$base" ]] && continue
        aws --endpoint-url "$S3_ENDPOINT" s3 cp "s3://$RAW_BUCKET/$key" "s3://$GOLDEN_BUCKET/scans/$base" >/dev/null
        printf "  • %s → scans/%s\n" "$key" "$base"
    done <<< "$ACTIVE_RAW"

    require_cmd curl

    printf "[ingest] Streaming golden/scans/* into workspace '%s' via %s …\n" "$WORKSPACE_ID" "$BACKEND_URL"
    GOLDEN_RAW=$(aws --endpoint-url "$S3_ENDPOINT" s3api list-objects-v2 \
        --bucket "$GOLDEN_BUCKET" \
        --prefix "scans/" \
        --query 'Contents[].Key' \
        --output text | tr '\t' '\n')

    while IFS= read -r key; do
        [[ -z "$key" || "$key" == "None" || "$key" == "scans/" ]] && continue
        payload=$(printf '{"bucket_name":"%s","key":"%s"}' "$GOLDEN_BUCKET" "$key")
        curl -s -X POST "$BACKEND_URL/v1/${WORKSPACE_ID}/index/security/s3" \
            -H 'Content-Type: application/json' \
            -d "$payload" >/dev/null
        printf "  • Ingested %s\n" "$key"
    done <<< "$GOLDEN_RAW"

    printf "[ingest] Loading Neo4j graph data directly (ensures Location nodes are created) …\n"
    docker exec ask-certus-backend bash -c \
      "source .venv/bin/activate && python /app/scripts/load_security_into_neo4j.py \
      --workspace neo4j-${WORKSPACE_ID} \
      --neo4j-uri neo4j://neo4j:7687" >/dev/null 2>&1 || \
      printf "  [warning] Direct Neo4j load failed (container may not be running or Neo4j unavailable)\n"

    printf "[ingest] Creating OpenSearch aliases pointing to ask_certus_%s …\n" "$WORKSPACE_ID"
    curl -s -X POST "${OPENSEARCH_URL}/_aliases" \
        -H 'Content-Type: application/json' \
        -d '{
              "actions": [
                {"add": {"index": "ask_certus_'"${WORKSPACE_ID}"'", "alias": "security-findings"}},
                {"add": {"index": "ask_certus_'"${WORKSPACE_ID}"'", "alias": "sbom-packages"}}
              ]
            }' >/dev/null || true
    printf "[ingest] Complete. Verify with: curl -s \"%s/_cat/indices/ask_certus_%s?v\"\n" "$OPENSEARCH_URL" "$WORKSPACE_ID"
fi
