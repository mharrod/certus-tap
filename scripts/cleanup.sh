#!/bin/bash

set -euo pipefail

STREAMLIT_PID_FILE=${STREAMLIT_PID_FILE:-.streamlit.pid}
CLEANUP_MODE=${CLEANUP_MODE:-basic}  # Options: basic, aggressive, nuclear

stop_streamlit() {
    if [[ -f "$STREAMLIT_PID_FILE" ]]; then
        STREAMLIT_PID=$(cat "$STREAMLIT_PID_FILE")
        if kill -0 "$STREAMLIT_PID" >/dev/null 2>&1; then
            printf '[cleanup] Stopping Streamlit (PID %s)\n' "$STREAMLIT_PID"
            kill "$STREAMLIT_PID" >/dev/null 2>&1 || true
        fi
        rm -f "$STREAMLIT_PID_FILE"
    fi
}

cleanup_docker() {
    case "$CLEANUP_MODE" in
        basic)
            printf '[cleanup] Basic mode: Stopping stack, removing containers (volumes retained)\n'
            docker compose down --remove-orphans || true
            ;;
        aggressive)
            printf '[cleanup] Aggressive mode: Stopping stack, removing containers and volumes\n'
            docker compose down --remove-orphans --volumes || true

            printf '[cleanup] Removing dangling images and build cache\n'
            docker image prune -f
            docker builder prune -f
            ;;
        nuclear)
            printf '[cleanup] Nuclear mode: Complete system cleanup\n'
            docker compose down --remove-orphans --volumes || true

            printf '[cleanup] Removing ALL unused containers, networks, images, and volumes\n'
            docker system prune -a --volumes -f

            printf '[cleanup] Removing old images (older than 24 hours)\n'
            docker image prune -a --filter "until=24h" -f

            printf '[cleanup] Removing build cache\n'
            docker builder prune -f
            ;;
        *)
            echo "Unknown cleanup mode: $CLEANUP_MODE"
            exit 1
            ;;
    esac
}

printf '[cleanup] Starting cleanup in %s mode\n' "$CLEANUP_MODE"
cleanup_docker
stop_streamlit
printf '[cleanup] Done.\n'
