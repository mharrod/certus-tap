#!/bin/bash
#
# Ensure the LocalStack datalake buckets exist (raw + golden) and seed default folders.
# Usage: ./scripts/bootstrap-datalake.sh [compose-file]

set -euo pipefail

COMPOSE_FILE=${1:-docker-compose.full-dev.yml}
LOCALSTACK_SERVICE=${LOCALSTACK_SERVICE:-localstack}
RAW_BUCKET=${DATALAKE_RAW_BUCKET:-raw}
GOLDEN_BUCKET=${DATALAKE_GOLDEN_BUCKET:-golden}
DEFAULT_FOLDERS=${DATALAKE_DEFAULT_FOLDERS:-broker,support,marketing,video,other}
RETRY_LIMIT=${BOOTSTRAP_RETRIES:-30}

if ! command -v docker >/dev/null 2>&1; then
    echo "docker command not found; skipping datalake bootstrap." >&2
    exit 0
fi

if ! docker compose -f "$COMPOSE_FILE" config --services >/dev/null 2>&1; then
    echo "Compose file '$COMPOSE_FILE' not found; skipping datalake bootstrap." >&2
    exit 0
fi

if ! docker compose -f "$COMPOSE_FILE" config --services | grep -qx "$LOCALSTACK_SERVICE"; then
    echo "Compose file '$COMPOSE_FILE' does not define service '$LOCALSTACK_SERVICE'; skipping datalake bootstrap."
    exit 0
fi

# Check if LocalStack container is running (use docker ps instead of docker compose ps for reliability)
LOCALSTACK_ID=$(docker ps -q -f name="^${LOCALSTACK_SERVICE}$")
if [ -z "$LOCALSTACK_ID" ]; then
    echo "LocalStack container '$LOCALSTACK_SERVICE' is not running; skipping datalake bootstrap."
    exit 0
fi

normalize_folders() {
    local raw_list=$1
    raw_list=${raw_list#[}
    raw_list=${raw_list%]}
    raw_list=${raw_list//\"/}
    raw_list=${raw_list//\'/}
    raw_list=${raw_list// /}
    printf '%s' "$raw_list"
}

wait_for_localstack() {
    local attempt=1
    while (( attempt <= RETRY_LIMIT )); do
        if docker exec "$LOCALSTACK_SERVICE" awslocal s3 ls >/dev/null 2>&1; then
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    echo "LocalStack did not become ready after ${RETRY_LIMIT} attempts; skipping datalake bootstrap." >&2
    return 1
}

echo "Bootstrapping datalake buckets using compose file '$COMPOSE_FILE'..."
if ! wait_for_localstack; then
    exit 1
fi

docker exec "$LOCALSTACK_SERVICE" awslocal s3 mb "s3://${RAW_BUCKET}" >/dev/null 2>&1 || true
docker exec "$LOCALSTACK_SERVICE" awslocal s3 mb "s3://${GOLDEN_BUCKET}" >/dev/null 2>&1 || true

FOLDERS=$(normalize_folders "$DEFAULT_FOLDERS")
IFS=',' read -ra FOLDER_ARRAY <<< "$FOLDERS"
for folder in "${FOLDER_ARRAY[@]}"; do
    [[ -z "$folder" ]] && continue
    docker exec "$LOCALSTACK_SERVICE" awslocal s3api put-object --bucket "$RAW_BUCKET" --key "${folder}/" >/dev/null 2>&1 || true
done

echo "Datalake buckets ensured (${RAW_BUCKET}, ${GOLDEN_BUCKET}) with default folders."
