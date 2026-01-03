#!/bin/bash

set -euo pipefail

STREAMLIT_PID_FILE=${STREAMLIT_PID_FILE:-.streamlit.pid}
DESTROY_MODE=${DESTROY_MODE:-complete}  # Options: basic, complete, nuclear

stop_streamlit() {
    if [[ -f "$STREAMLIT_PID_FILE" ]]; then
        STREAMLIT_PID=$(cat "$STREAMLIT_PID_FILE")
        if kill -0 "$STREAMLIT_PID" >/dev/null 2>&1; then
            printf '[destroy] Stopping Streamlit (PID %s)\n' "$STREAMLIT_PID"
            kill "$STREAMLIT_PID" >/dev/null 2>&1 || true
        fi
        rm -f "$STREAMLIT_PID_FILE"
    fi
}

destroy_docker() {
    case "$DESTROY_MODE" in
        basic)
            printf '[destroy] Basic mode: Stopping stack and removing volumes\n'
            # Stop application services
            docker compose -f certus_ask/deploy/docker-compose.yml down --volumes --remove-orphans || true
            docker compose -f certus_trust/deploy/docker-compose.prod.yml down --volumes --remove-orphans || true
            docker compose -f certus_assurance/deploy/docker-compose.yml down --volumes --remove-orphans || true
            docker compose -f certus_transform/deploy/docker-compose.yml down --volumes --remove-orphans || true
            # Stop infrastructure with correct project name
            docker compose -p certus -f certus_infrastructure/docker-compose.sigstore.yml down --volumes --remove-orphans || true
            docker compose -p certus -f certus_infrastructure/docker-compose.yml down --volumes --remove-orphans || true
            ;;
        complete)
            printf '[destroy] Complete mode: Stopping stack, removing volumes, and cleaning artifacts\n'
            # Stop application services
            docker compose -f certus_ask/deploy/docker-compose.yml down --volumes --remove-orphans || true
            docker compose -f certus_trust/deploy/docker-compose.prod.yml down --volumes --remove-orphans || true
            docker compose -f certus_assurance/deploy/docker-compose.yml down --volumes --remove-orphans || true
            docker compose -f certus_transform/deploy/docker-compose.yml down --volumes --remove-orphans || true
            # Stop infrastructure with correct project name
            docker compose -p certus -f certus_infrastructure/docker-compose.sigstore.yml down --volumes --remove-orphans || true
            docker compose -p certus -f certus_infrastructure/docker-compose.yml down --volumes --remove-orphans || true

            # Remove named volumes explicitly in case compose project name changed
            for volume in opensearch-data localstack-volume mlflow-data registry-data hf-cache neo4j-data neo4j-logs victoriametrics-data grafana-data rekor-db trillian-log-db certus_opensearch-data certus_localstack-volume certus_registry-data certus_neo4j-data certus_neo4j-logs certus_victoriametrics-data certus_grafana-data certus-ask-cache certus_infrastructure_trillian-log-db-data certus_trillian-log-db-data; do
              if docker volume inspect "$volume" >/dev/null 2>&1; then
                printf '[destroy] Removing volume %s\n' "$volume"
                docker volume rm "$volume" >/dev/null || true
              fi
            done
            ;;
        nuclear)
            printf '[destroy] Nuclear mode: Complete system cleanup including Docker images\n'
            # Stop application services
            docker compose -f certus_ask/deploy/docker-compose.yml down --volumes --remove-orphans || true
            docker compose -f certus_trust/deploy/docker-compose.prod.yml down --volumes --remove-orphans || true
            docker compose -f certus_assurance/deploy/docker-compose.yml down --volumes --remove-orphans || true
            docker compose -f certus_transform/deploy/docker-compose.yml down --volumes --remove-orphans || true
            # Stop infrastructure with correct project name
            docker compose -p certus -f certus_infrastructure/docker-compose.sigstore.yml down --volumes --remove-orphans || true
            docker compose -p certus -f certus_infrastructure/docker-compose.yml down --volumes --remove-orphans || true

            # Remove all volumes
            for volume in opensearch-data localstack-volume mlflow-data registry-data hf-cache neo4j-data neo4j-logs victoriametrics-data grafana-data rekor-db trillian-log-db certus_opensearch-data certus_localstack-volume certus_registry-data certus_neo4j-data certus_neo4j-logs certus_victoriametrics-data certus_grafana-data certus-ask-cache certus_infrastructure_trillian-log-db-data certus_trillian-log-db-data; do
              if docker volume inspect "$volume" >/dev/null 2>&1; then
                printf '[destroy] Removing volume %s\n' "$volume"
                docker volume rm "$volume" >/dev/null || true
              fi
            done

            # Clean up Docker system
            printf '[destroy] Removing dangling images and build cache\n'
            docker image prune -f
            docker builder prune -f
            ;;
        *)
            echo "Unknown destroy mode: $DESTROY_MODE"
            exit 1
            ;;
    esac
}

cleanup_artifacts() {
    # Clean up local upload artifacts if present
    if [ -d "uploads" ]; then
        printf '[destroy] Removing local uploads directory\n'
        rm -rf uploads
    fi

    # Remove generated attestation artifacts (simulate vendor payload)
    if [ -d "samples/oci-attestations/artifacts" ]; then
        printf '[destroy] Removing generated attestation artifacts\n'
        rm -rf samples/oci-attestations/artifacts
    fi

    # Remove other temporary files
    if [ -d ".artifacts" ]; then
        printf '[destroy] Removing .artifacts directory\n'
        rm -rf .artifacts
    fi

    if [ -f ".streamlit.pid" ]; then
        printf '[destroy] Removing streamlit pid file\n'
        rm -f .streamlit.pid
    fi
}

printf '[destroy] Starting destruction in %s mode\n' "$DESTROY_MODE"
destroy_docker
cleanup_artifacts
stop_streamlit
printf '[destroy] Done. Stack resources removed.\n'
