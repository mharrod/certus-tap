#!/bin/bash
# Preflight checks for Transform tutorials
# Tests: ingestion, datalake, golden bucket workflows

set -euo pipefail

API_BASE=${API_BASE:-http://localhost:8000}
WORKSPACE_ID=${WORKSPACE_ID:-transform-preflight}
HEALTH_BASE=${HEALTH_BASE:-$API_BASE/v1/health}
OS_ENDPOINT=${OS_ENDPOINT:-http://localhost:9200}
NEO4J_URI=${NEO4J_URI:-neo4j://localhost:7687}
NEO4J_BROWSER=${NEO4J_BROWSER:-http://localhost:7474}
LOCALSTACK_ENDPOINT=${LOCALSTACK_ENDPOINT:-http://localhost:4566}

log() {
    printf '[preflight-transform] %s\n' "$1"
}

fail() {
    printf '[preflight-transform] ERROR: %s\n' "$1" >&2
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

log "========== TRANSFORM TUTORIAL PREFLIGHT =========="
log "Checking minimal services for Transform tutorials..."
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

log "Checking S3 buckets"
if ! aws --endpoint-url "$LOCALSTACK_ENDPOINT" s3 ls s3://raw >/dev/null 2>&1; then
    fail "S3 raw bucket not accessible"
fi
log "✅ S3 raw bucket OK"

if ! aws --endpoint-url "$LOCALSTACK_ENDPOINT" s3 ls s3://golden >/dev/null 2>&1; then
    fail "S3 golden bucket not accessible"
fi
log "✅ S3 golden bucket OK"

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
log "========== ALL TRANSFORM CHECKS PASSED =========="
log "Ready for Transform tutorials:"
log "  - docs/learn/transform/ingestion-pipelines.md"
log "  - docs/learn/transform/sample-datalake-upload.md"
log "  - docs/learn/transform/golden-bucket.md"
log ""
