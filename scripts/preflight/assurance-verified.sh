#!/bin/bash
# Preflight checks for Assurance tutorials (verified tier with trust)
# Tests: CLI workflow with provenance verification

set -euo pipefail

ASSURANCE_API=${ASSURANCE_API:-http://localhost:8056}
TRUST_API=${TRUST_API:-http://localhost:8057}
LOCALSTACK_ENDPOINT=${LOCALSTACK_ENDPOINT:-http://localhost:4566}
OCI_REGISTRY_ENDPOINT=${OCI_REGISTRY_ENDPOINT:-http://localhost:5000}
VICTORIAMETRICS_ENDPOINT=${VICTORIAMETRICS_ENDPOINT:-http://localhost:8428}
OPENTELEMETRY_ENDPOINT=${OPENTELEMETRY_ENDPOINT:-http://localhost:4318}

log() {
    printf '[preflight-assurance-verified] %s\n' "$1"
}

fail() {
    printf '[preflight-assurance-verified] ERROR: %s\n' "$1" >&2
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

log "========== ASSURANCE TUTORIAL PREFLIGHT (VERIFIED TIER) =========="
log "Checking services for verified Assurance tutorials with provenance..."
log ""

log "Checking Certus Assurance service"
check_http "$ASSURANCE_API/v1/health" "Certus Assurance"

log "Checking Certus Trust service (for verification)"
check_http "$TRUST_API/v1/health" "Certus Trust"

log "Checking LocalStack S3 (for artifact storage)"
if ! curl -fsS "$LOCALSTACK_ENDPOINT/_localstack/health" >/dev/null; then
    fail "LocalStack check failed"
fi
log "✅ LocalStack OK"

log "Checking OCI Registry (for attestation storage)"
if ! curl -fsS "$OCI_REGISTRY_ENDPOINT/v2/_catalog" >/dev/null 2>&1; then
    log "⚠️  OCI registry not available (attestation storage limited)"
else
    log "✅ OCI registry OK"
fi

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
log "========== ALL ASSURANCE CHECKS PASSED (VERIFIED TIER) =========="
log "Ready for verified Assurance tutorials with provenance:"
log "  - docs/learn/assurance/quick start/cli-workflow.md (with verification)"
log "  - docs/learn/assurance/quick start/manifest-driven-security-scans.md (with verification)"
log ""
