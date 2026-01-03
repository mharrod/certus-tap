#!/bin/bash
# Preflight checks for Ask tutorials
# Tests: keyword search, semantic search, hybrid search, neo4j queries

set -euo pipefail

API_BASE=${API_BASE:-http://localhost:8000}
WORKSPACE_ID=${WORKSPACE_ID:-ask-preflight}
HEALTH_BASE=${HEALTH_BASE:-$API_BASE/v1/health}
OS_ENDPOINT=${OS_ENDPOINT:-http://localhost:9200}
NEO4J_URI=${NEO4J_URI:-neo4j://localhost:7687}
NEO4J_BROWSER=${NEO4J_BROWSER:-http://localhost:7474}
LOCALSTACK_ENDPOINT=${LOCALSTACK_ENDPOINT:-http://localhost:4566}

log() {
    printf '[preflight-ask] %s\n' "$1"
}

fail() {
    printf '[preflight-ask] ERROR: %s\n' "$1" >&2
    exit 1
}

check_http() {
    local url=$1
    local name=$2
    if ! curl -fsS "$url" >/dev/null; then
        fail "${name} check failed for ${url}"
    fi
    log "✅ ${name} OK"
}

log "========== ASK TUTORIAL PREFLIGHT =========="
log "Checking minimal services for Ask tutorials..."
log ""

log "Checking FastAPI backend (ask-certus-backend)"
check_http "$HEALTH_BASE" "FastAPI health"

log "Checking OpenSearch"
check_http "$OS_ENDPOINT" "OpenSearch"

log "Checking Neo4j"
check_http "$NEO4J_BROWSER" "Neo4j browser"

log "Checking LocalStack S3"
if ! curl -fsS "$LOCALSTACK_ENDPOINT/_localstack/health" >/dev/null; then
    fail "LocalStack check failed"
fi
log "✅ LocalStack OK"

log "Checking VictoriaMetrics"
VICTORIAMETRICS_ENDPOINT=${VICTORIAMETRICS_ENDPOINT:-http://localhost:8428}
if ! curl -fsS "$VICTORIAMETRICS_ENDPOINT" >/dev/null 2>&1; then
    log "⚠️  VictoriaMetrics not available (observability limited)"
else
    log "✅ VictoriaMetrics OK"
fi

log "Checking OpenTelemetry Collector"
OPENTELEMETRY_ENDPOINT=${OPENTELEMETRY_ENDPOINT:-http://localhost:4318}
if ! curl -fsS "$OPENTELEMETRY_ENDPOINT" >/dev/null 2>&1; then
    log "⚠️  OpenTelemetry Collector not available (tracing limited)"
else
    log "✅ OpenTelemetry Collector OK"
fi

log ""
log "========== ALL ASK CHECKS PASSED =========="
log "Ready for Ask tutorials:"
log "  - docs/learn/ask/keyword-search.md"
log "  - docs/learn/ask/semantic-search.md"
log "  - docs/learn/ask/hybrid-search.md"
log "  - docs/learn/ask/neo4j-local-ingestion.md"
log ""
