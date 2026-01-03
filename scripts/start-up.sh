#!/bin/bash

set -euo pipefail

# Default stack services (can be overridden with command-line arguments)
DEFAULT_SERVICES=(registry opensearch opensearch-dashboards neo4j localstack mlflow ask-certus-backend certus-transform certus-assurance certus-trust otel-collector victoriametrics grafana)
STACK_SERVICES=("${@:-${DEFAULT_SERVICES[@]}}")
COMPOSE_BIN=()
LOCALSTACK_ENDPOINT=${LOCALSTACK_ENDPOINT:-http://localhost:4566}
LOCALSTACK_WAIT_RETRIES=${LOCALSTACK_WAIT_RETRIES:-30}
START_STREAMLIT=${START_STREAMLIT:-true}
STREAMLIT_PORT=${STREAMLIT_PORT:-8501}
STREAMLIT_PID_FILE=${STREAMLIT_PID_FILE:-.streamlit.pid}
STREAMLIT_LOG=${STREAMLIT_LOG:-streamlit.log}

detect_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_BIN=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_BIN=(docker-compose)
    else
        echo "Error: docker compose (v2) or docker-compose (v1) is required."
        exit 1
    fi
}

compose() {
    "${COMPOSE_BIN[@]}" "$@"
}

load_env_file() {
    if [[ -f .env ]]; then
        set -a
        # shellcheck disable=SC1091
        source .env
        set +a
    fi
}

ensure_docker_network() {
    local network_name="opensearch-net"
    if ! docker network inspect "$network_name" >/dev/null 2>&1; then
        echo "Creating docker network $network_name"
        docker network create "$network_name"
    fi
}

start_stack() {
    echo "Starting Ask Certus stack..."
    compose up -d "${STACK_SERVICES[@]}"
}

is_service_in_list() {
    local service=$1
    local item
    for item in "${STACK_SERVICES[@]}"; do
        if [[ "$item" == "$service" ]]; then
            return 0
        fi
    done
    return 1
}

wait_for_localstack() {
    # Only wait for LocalStack if it's being started
    if ! is_service_in_list "localstack"; then
        return 0
    fi

    echo "Waiting for LocalStack to become ready..."
    local attempt=1
    while (( attempt <= LOCALSTACK_WAIT_RETRIES )); do
        if curl -fsS "$LOCALSTACK_ENDPOINT/_localstack/health" >/dev/null 2>&1; then
            echo "LocalStack is ready."
            return 0
        fi
        sleep 2
        ((attempt++))
    done
    echo "LocalStack did not become ready in time." >&2
    exit 1
}

normalize_folder_list() {
    local raw_list=$1
    raw_list=${raw_list:-broker,support,marketing,video,other}
    raw_list=${raw_list#[}
    raw_list=${raw_list%]}
    raw_list=${raw_list//\"/}
    raw_list=${raw_list//\'/}
    raw_list=${raw_list// /}
    printf '%s' "$raw_list"
}

bootstrap_datalake_buckets() {
    # Only bootstrap buckets if localstack is being started
    if ! is_service_in_list "localstack"; then
        return 0
    fi

    local raw_bucket=${DATALAKE_RAW_BUCKET:-raw}
    local golden_bucket=${DATALAKE_GOLDEN_BUCKET:-golden}
    local folders
    folders=$(normalize_folder_list "${DATALAKE_DEFAULT_FOLDERS:-broker,support,marketing,video,other}")

    echo "Ensuring datalake buckets (${raw_bucket}, ${golden_bucket}) exist..."
    compose exec -T localstack awslocal s3 mb "s3://$raw_bucket" >/dev/null 2>&1 || true
    compose exec -T localstack awslocal s3 mb "s3://$golden_bucket" >/dev/null 2>&1 || true

    IFS=',' read -ra folder_array <<< "$folders"
    for folder in "${folder_array[@]}"; do
        [[ -z "$folder" ]] && continue
        compose exec -T localstack awslocal s3api put-object --bucket "$raw_bucket" --key "${folder}/" >/dev/null 2>&1 || true
    done
    echo "Datalake buckets ready."
}

print_status() {
    echo "\nContainer status:"
    compose ps
    printf "\nTail logs with: %s logs -f ask-certus-backend\n" "${COMPOSE_BIN[*]}"
}

start_streamlit_ui() {
    local start_flag
    start_flag=$(printf '%s' "${START_STREAMLIT:-true}" | tr '[:upper:]' '[:lower:]')
    if [[ "$start_flag" != "true" ]]; then
        echo "Skipping Streamlit launch (START_STREAMLIT=${START_STREAMLIT:-unset})"
        return 0
    fi

    if ! command -v uv >/dev/null 2>&1; then
        echo "uv not found in PATH; cannot launch Streamlit."
        return 0
    fi

    if [[ -f "$STREAMLIT_PID_FILE" ]] && kill -0 "$(cat "$STREAMLIT_PID_FILE")" >/dev/null 2>&1; then
        echo "Streamlit already running (PID $(cat "$STREAMLIT_PID_FILE"))."
        return 0
    fi

    echo "Starting Streamlit console on port ${STREAMLIT_PORT}..."
    nohup uv run streamlit run src/certus_tap/streamlit_app.py \
        --server.port "${STREAMLIT_PORT}" \
        --server.headless true \
        >"$STREAMLIT_LOG" 2>&1 &
    STREAMLIT_PID=$!
    echo "$STREAMLIT_PID" >"$STREAMLIT_PID_FILE"
    echo "Streamlit running (PID $STREAMLIT_PID). Logs: $STREAMLIT_LOG"
}

main() {
    detect_compose
    load_env_file
    ensure_docker_network
    start_stack
    wait_for_localstack
    bootstrap_datalake_buckets
    print_status
    start_streamlit_ui
    echo ""
    echo "Access Streamlit UI at: ${STREAMLIT_ENDPOINT:-http://localhost:${STREAMLIT_PORT:-8501}}"
    echo "Set STREAMLIT_PORT or STREAMLIT_ENDPOINT before running 'just up' to customize."
}

main "$@"
