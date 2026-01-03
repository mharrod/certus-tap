#!/bin/bash

set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$SCRIPT_DIR/.." && pwd)
cd "$REPO_ROOT"

STREAMLIT_PID_FILE=${STREAMLIT_PID_FILE:-.streamlit.pid}

COMPOSE_BIN=()

detect_compose() {
    if docker compose version >/dev/null 2>&1; then
        COMPOSE_BIN=(docker compose)
    elif command -v docker-compose >/dev/null 2>&1; then
        COMPOSE_BIN=(docker-compose)
    else
        echo "[shutdown] Error: docker compose (v2) or docker-compose (v1) is required." >&2
        exit 1
    fi
}

compose() {
    "${COMPOSE_BIN[@]}" "$@"
}

stop_streamlit() {
    if [[ -f "$STREAMLIT_PID_FILE" ]]; then
        STREAMLIT_PID=$(cat "$STREAMLIT_PID_FILE")
        if kill -0 "$STREAMLIT_PID" >/dev/null 2>&1; then
            printf '[shutdown] Stopping Streamlit console (PID %s)\n' "$STREAMLIT_PID"
            kill "$STREAMLIT_PID" >/dev/null 2>&1 || true
        fi
        rm -f "$STREAMLIT_PID_FILE"
    fi
}

bring_down_stack() {
    local compose_file=$1
    local project_flag=${2:-}
    if [[ ! -f "$compose_file" ]]; then
        printf '[shutdown] Skipping missing compose file: %s\n' "$compose_file"
        return 0
    fi
    if [[ -n "$project_flag" ]]; then
        printf '[shutdown] docker compose -p %s -f %s down --remove-orphans\n' "$project_flag" "$compose_file"
        compose -p "$project_flag" -f "$compose_file" down --remove-orphans || true
    else
        printf '[shutdown] docker compose -f %s down --remove-orphans\n' "$compose_file"
        compose -f "$compose_file" down --remove-orphans || true
    fi
}

main() {
    detect_compose

    printf '[shutdown] Stopping application services\n'
    bring_down_stack certus_ask/deploy/docker-compose.yml
    bring_down_stack certus_trust/deploy/docker-compose.prod.yml
    bring_down_stack certus_assurance/deploy/docker-compose.yml
    bring_down_stack certus_transform/deploy/docker-compose.yml

    printf '[shutdown] Stopping sigstore dependencies\n'
    bring_down_stack certus_infrastructure/docker-compose.sigstore.yml certus

    printf '[shutdown] Stopping shared infrastructure services\n'
    bring_down_stack certus_infrastructure/docker-compose.yml certus

    stop_streamlit
    printf '[shutdown] Done. All compose stacks stopped.\n'
}

main "$@"
