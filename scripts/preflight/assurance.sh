#!/bin/bash
# Preflight checks for Assurance tutorials (basic tier)
# Tests: CLI workflow, manifest-driven security scans

set -euo pipefail

ASSURANCE_API=${ASSURANCE_API:-http://localhost:8056}
LOCALSTACK_ENDPOINT=${LOCALSTACK_ENDPOINT:-http://localhost:4566}
VICTORIAMETRICS_ENDPOINT=${VICTORIAMETRICS_ENDPOINT:-http://localhost:8428}
OPENTELEMETRY_ENDPOINT=${OPENTELEMETRY_ENDPOINT:-http://localhost:4318}

log() {
    printf '[preflight-assurance] %s\n' "$1"
}

fail() {
    printf '[preflight-assurance] ERROR: %s\n' "$1" >&2
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

log "========== ASSURANCE TUTORIAL PREFLIGHT (BASIC TIER) =========="
log "Checking minimal services for Assurance tutorials..."
log ""

log "Checking Certus Assurance service"
check_http "$ASSURANCE_API/v1/health" "Certus Assurance"

log "Checking LocalStack S3 (for artifact storage)"
if ! curl -fsS "$LOCALSTACK_ENDPOINT/_localstack/health" >/dev/null; then
    fail "LocalStack check failed"
fi
log "✅ LocalStack OK"

log "Checking VictoriaMetrics"
if ! curl -fsS "$VICTORIAMETRICS_ENDPOINT" >/dev/null 2>&1; then
    log "⚠️  VictoriaMetrics not available (observability limited)"
else
    log "✅ VictoriaMetrics OK"
fi

log "Checking OpenTelemetry Collector"
if ! curl -fsS "$OPENTELEMETRY_ENDPOINT" >/dev/null 2>&1; then
    log "⚠️  OpenTelemetry Collector not available (tracing limited)"
else
    log "✅ OpenTelemetry Collector OK"
fi

log ""
log "========== ALL ASSURANCE CHECKS PASSED (BASIC TIER) =========="
log "Ready for Assurance tutorials:"
log "  - docs/learn/assurance/quick start/cli-workflow.md"
log "  - docs/learn/assurance/quick start/manifest-driven-security-scans.md"
log ""
log "Note: This is basic tier (no verification)."
log "For verified tier with provenance, run: just assurance-verified-up"
log "Then check with: just preflight-assurance-verified"
log ""
