#!/bin/bash
# Preflight checks for Integrity tutorials
# Tests: compliance reporting, incident investigation, rate limiting

set -euo pipefail

API_BASE=${API_BASE:-http://localhost:8000}
HEALTH_BASE=${HEALTH_BASE:-$API_BASE/v1/health}
VICTORIAMETRICS_ENDPOINT=${VICTORIAMETRICS_ENDPOINT:-http://localhost:8428}
OTEL_OTLP_HTTP_PORT=${OTEL_OTLP_HTTP_PORT:-4318}
OS_ENDPOINT=${OS_ENDPOINT:-http://localhost:9200}

log() {
    printf '[preflight-integrity] %s\n' "$1"
}

fail() {
    printf '[preflight-integrity] ERROR: %s\n' "$1" >&2
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

check_tcp() {
    local host=$1
    local port=$2
    local name=$3
    if timeout 3 bash -c "cat < /dev/null > /dev/tcp/${host}/${port}" >/dev/null 2>&1; then
        log "✅ ${name} OK"
    else
        fail "${name} check failed for ${host}:${port}"
    fi
}

log "========== INTEGRITY TUTORIAL PREFLIGHT =========="
log "Checking minimal services for Integrity tutorials..."
log ""

log "Checking FastAPI backend (ask-certus-backend with integrity middleware)"
check_http "$HEALTH_BASE" "FastAPI health"

log "Checking VictoriaMetrics (required for metrics storage)"
check_http "$VICTORIAMETRICS_ENDPOINT" "VictoriaMetrics"

log "Checking OpenTelemetry Collector (required for metrics collection)"
# Check Prometheus metrics endpoint instead of OTLP (which returns 405 for GET)
if curl -fsS "http://localhost:8889/metrics" >/dev/null 2>&1; then
    log "✅ OpenTelemetry Collector OK"
else
    fail "OpenTelemetry Collector check failed for localhost:8889/metrics"
fi

log "Checking OpenSearch (optional, for log correlation)"
if ! curl -fsS "$OS_ENDPOINT" >/dev/null 2>&1; then
    log "⚠️  OpenSearch not available (log correlation limited)"
else
    log "✅ OpenSearch OK"
fi

log "Checking Grafana (optional, for dashboards)"
GRAFANA_ENDPOINT=${GRAFANA_ENDPOINT:-http://localhost:3002}
if ! curl -fsS "$GRAFANA_ENDPOINT" >/dev/null 2>&1; then
    log "⚠️  Grafana not available (visual dashboards not available)"
else
    log "✅ Grafana OK"
fi

log ""
log "Checking Integrity environment configuration..."
if [ -z "${INTEGRITY_SHADOW_MODE:-}" ]; then
    log "⚠️  INTEGRITY_SHADOW_MODE not set (will use default)"
else
    log "✅ INTEGRITY_SHADOW_MODE=${INTEGRITY_SHADOW_MODE}"
fi

if [ -z "${INTEGRITY_RATE_LIMIT_PER_MIN:-}" ]; then
    log "⚠️  INTEGRITY_RATE_LIMIT_PER_MIN not set (will use default)"
else
    log "✅ INTEGRITY_RATE_LIMIT_PER_MIN=${INTEGRITY_RATE_LIMIT_PER_MIN}"
fi

log ""
log "========== ALL INTEGRITY CHECKS PASSED =========="
log "Ready for Integrity tutorials:"
log "  - docs/learn/integrity/compliance-reporting.md"
log "  - docs/learn/integrity/investigating-incidents.md"
log "  - docs/learn/integrity/testing-rate-limits.md"
log ""
log "Note: Integrity is a library embedded in ask-certus-backend"
log "Evidence bundles are written to /tmp/evidence/ locally"
log ""
