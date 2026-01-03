#!/usr/bin/env bash
set -euo pipefail

# Helper to replay the vendor review workflow:
# 1. Pull Trust-approved artifacts from S3 (and optional OCI)
# 2. Verify signatures/provenance
# 3. Ingest into Certus TAP
# 4. Generate + sign compliance report
# 5. (Optional) run privacy scan

SCAN_ID="${SCAN_ID:-}"
WORKSPACE_ID="${WORKSPACE_ID:-oci-attestations-review}"
ARTIFACT_ROOT="/tmp/acquired-artifacts/${SCAN_ID}"
S3_ENDPOINT="${S3_ENDPOINT:-http://localhost:4566}"
OCI_PULL="${OCI_PULL:-false}"
RUN_PRIVACY_SCAN="${RUN_PRIVACY_SCAN:-false}"
AWS_CMD="${AWS_CMD:-aws}"
COSIGN_YES=true
export COSIGN_YES

require() {
  command -v "$1" >/dev/null || { echo "$1 is required"; exit 1; }
}

require jq
require curl
require "$AWS_CMD"
require oras
require cosign

if [[ -z "$SCAN_ID" ]]; then
  echo "SCAN_ID must be set (output from trust-verification workflow)."
  exit 1
fi

mkdir -p "$ARTIFACT_ROOT"

echo "[vendor-helper] Syncing artifacts from S3 for scan $SCAN_ID"
"$AWS_CMD" s3 sync "s3://raw/security-scans/${SCAN_ID}/${SCAN_ID}/" \
  "$ARTIFACT_ROOT" --endpoint-url "$S3_ENDPOINT"

if [[ "$OCI_PULL" == "true" ]]; then
  echo "[vendor-helper] Pulling OCI bundle"
  oras pull --plain-http \
    localhost:5000/product-acquisition/attestations:latest \
    --output "$ARTIFACT_ROOT"
fi

echo "[vendor-helper] Verifying signatures"
cp samples/oci-attestations/keys/cosign.pub /tmp/acquired-artifacts/ 2>/dev/null || true
pushd "$ARTIFACT_ROOT" >/dev/null
just verify-attestations || {
  echo "Verification failed"; exit 1;
}
popd >/dev/null

echo "[vendor-helper] Checking SLSA provenance digest"
SBOM="${ARTIFACT_ROOT}/samples/oci-attestations/artifacts/sbom/product.spdx.json"
PROV="${ARTIFACT_ROOT}/samples/oci-attestations/artifacts/provenance/slsa-provenance.json"
SBOM_DIGEST=$(sha256sum "$SBOM" | cut -d' ' -f1)
PROV_DIGEST=$(jq -r '.predicate.buildDefinition.internalParameters.SBOM.digest.sha256' "$PROV")
if [[ "$SBOM_DIGEST" != "$PROV_DIGEST" ]]; then
  echo "SBOM digest mismatch"; exit 1;
fi

echo "[vendor-helper] Ingesting artifacts into workspace $WORKSPACE_ID"
curl -s -X POST "http://localhost:8000/v1/${WORKSPACE_ID}/index/" \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${SBOM}" >/dev/null

curl -s -X POST "http://localhost:8000/v1/${WORKSPACE_ID}/index/" \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/samples/oci-attestations/artifacts/attestations/build.intoto.json" >/dev/null

curl -s -X POST "http://localhost:8000/v1/${WORKSPACE_ID}/index/security" \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/samples/oci-attestations/artifacts/scans/vulnerability.sarif" >/dev/null

curl -s -X POST "http://localhost:8000/v1/${WORKSPACE_ID}/index/" \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${PROV}" >/dev/null

echo "[vendor-helper] Generating compliance findings JSON"
cat > /tmp/compliance-findings.json <<EOF
{
  "signatureVerification": {
    "status": "PASS",
    "details": "Artifacts verified locally and permitted by Trust",
    "trustUploadPermission": "$(jq -r '.upload_permission_id // empty' <<<"$(curl -s http://localhost:8056/v1/security-scans/${SCAN_ID})")"
  },
  "sbomAnalysis": { "status": "PASS", "packageCount": 5 },
  "provenanceValidation": { "status": "PASS", "reproducible": true },
  "vulnerabilityAssessment": {
    "status": "CONDITIONAL",
    "highCount": 2,
    "findings": [
      {"id": "CWE-89", "title": "SQL Injection", "severity": "HIGH"},
      {"id": "CWE-78", "title": "Shell Injection", "severity": "HIGH"}
    ]
  },
  "licenseCompliance": { "status": "PASS" }
}
EOF

just generate-compliance-report \
  "Acme Corporation Product" \
  "ACME Corp" \
  "Security Review Team" \
  "Your Organization" \
  /tmp/compliance-findings.json \
  samples/oci-attestations/reports

REPORT_FILE=$(ls -t samples/oci-attestations/reports/*.json | head -1)
just sign-compliance-report "$REPORT_FILE" samples/oci-attestations/keys/cosign.key

echo "[vendor-helper] Uploading report to OCI registry"
just upload-compliance-report \
  "$REPORT_FILE" \
  "${REPORT_FILE}.sig" \
  http://localhost:5000 "" "" \
  product-acquisition/compliance-reports

if [[ "$RUN_PRIVACY_SCAN" == "true" ]]; then
  echo "[vendor-helper] Running privacy scan"
  PYTHONPATH=. uv run python scripts/privacy_scan_s3.py \
    --scan-id "$SCAN_ID" \
    --endpoint "$S3_ENDPOINT" \
    --report-path "/tmp/privacy_scan_${SCAN_ID}.txt"
fi

echo "[vendor-helper] Completed vendor review workflow for SCAN_ID=${SCAN_ID}"
