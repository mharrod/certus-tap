#!/usr/bin/env bash
set -euo pipefail

# Quick helper to rerun the Certus-Trust verification workflow and repopulate
# S3/OCI artifacts if the learner cleared the environment.

ASSURANCE_ENDPOINT="${ASSURANCE_ENDPOINT:-http://localhost:8056}"
GIT_URL="${GIT_URL:-https://github.com/mharrod/certus-TAP.git}"
BRANCH="${BRANCH:-main}"
REQUESTED_BY="${REQUESTED_BY:-security-team@example.com}"
TIER="${TIER:-verified}"
POLL_DELAY="${POLL_DELAY:-5}"

command -v curl >/dev/null || { echo "curl is required"; exit 1; }
command -v jq >/dev/null || { echo "jq is required"; exit 1; }

log() { printf '[trust-demo] %s\n' "$*"; }

get_scan_status() {
  curl -s "${ASSURANCE_ENDPOINT}/v1/security-scans/${1}"
}

submit_scan() {
  curl -s -X POST "${ASSURANCE_ENDPOINT}/v1/security-scans" \
    -H 'Content-Type: application/json' \
    -d '{
      "git_url": "'${GIT_URL}'",
      "branch": "'${BRANCH}'",
      "requested_by": "'${REQUESTED_BY}'"
    }'
}

request_upload() {
  curl -s -X POST "${ASSURANCE_ENDPOINT}/v1/security-scans/${1}/upload-request" \
    -H 'Content-Type: application/json' \
    -d '{
      "tier": "'${TIER}'",
      "requested_by": "'${REQUESTED_BY}'"
    }'
}

create_new_scan() {
  log "Submitting new scan for ${GIT_URL}@${BRANCH}"
  RESP=$(submit_scan)
  SCAN_ID=$(echo "$RESP" | jq -r '.scan_id')
  if [[ -z "$SCAN_ID" || "$SCAN_ID" == "null" ]]; then
    echo "Failed to create scan: $RESP"
    exit 1
  fi
  export SCAN_ID
}

if [[ -z "${SCAN_ID:-}" ]]; then
  create_new_scan
else
  log "Using existing SCAN_ID=${SCAN_ID}"
  STATUS_PAYLOAD=$(get_scan_status "$SCAN_ID")
  STATUS_VALUE=$(echo "$STATUS_PAYLOAD" | jq -r '.status // empty')
  if [[ -z "$STATUS_VALUE" ]]; then
    log "Existing scan not found (service restart?). Creating a new scan."
    create_new_scan
  fi
fi

log "Waiting for scan ${SCAN_ID} to complete..."
while true; do
  STATUS_PAYLOAD=$(get_scan_status "$SCAN_ID")
  STATUS=$(echo "$STATUS_PAYLOAD" | jq -r '.status')
  echo "$STATUS_PAYLOAD" | jq '{status, upload_status, updated_at}' 2>/dev/null || true
  case "$STATUS" in
    SUCCEEDED) break ;;
    FAILED) echo "Scan failed, exiting"; exit 1 ;;
  esac
  sleep "$POLL_DELAY"
done

log "Scan succeeded. Requesting Trust upload permission (${TIER})."
UPLOAD_RESPONSE=$(request_upload "$SCAN_ID")
echo "$UPLOAD_RESPONSE"

PERMISSION_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.upload_permission_id // empty')
if [[ -n "$PERMISSION_ID" ]]; then
  log "Upload permission: $PERMISSION_ID"
fi

log "Waiting for upload to reach 'uploaded' state..."
while true; do
  STATUS_PAYLOAD=$(get_scan_status "$SCAN_ID")
  UPLOAD_STATUS=$(echo "$STATUS_PAYLOAD" | jq -r '.upload_status')
  echo "$STATUS_PAYLOAD" | jq '{status, upload_status, verification_proof}' 2>/dev/null || true
  case "$UPLOAD_STATUS" in
    uploaded) break ;;
    denied) echo "Trust denied upload" ; exit 1 ;;
  esac
  sleep "$POLL_DELAY"
done

log "Refreshing OCI registry artifacts from samples/oci-attestations"
just push-to-registry \
  http://localhost:5000 \
  "" "" \
  product-acquisition/attestations >/dev/null
log "OCI registry push complete."

log "Artifacts restored for scan ${SCAN_ID}."
cat <<EOF
Next steps:
  * Pull verified assets from S3: aws s3 ls s3://raw/security-scans/${SCAN_ID}/${SCAN_ID}/ --endpoint-url http://localhost:4566
  * Or pull from OCI registry via: oras pull --plain-http localhost:5000/product-acquisition/attestations:latest --output /tmp/acquired-artifacts/${SCAN_ID}
Reuse SCAN_ID=${SCAN_ID} with vendor-review.md.
Export it in your shell with:
  export SCAN_ID=${SCAN_ID}
EOF
