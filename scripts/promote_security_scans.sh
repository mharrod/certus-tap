#!/usr/bin/env bash
set -euo pipefail

# Promote security scan artifacts from raw/quarantine to golden bucket
# This script handles the promotion workflow described in verify-trust.md

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
API_BASE="${DOCOPS_API:-http://localhost:8000}"
ENDPOINT="${AWS_ENDPOINT_URL:-http://localhost:4566}"
RAW_BUCKET="${DATALAKE_RAW_BUCKET:-raw}"
GOLDEN_BUCKET="${DATALAKE_GOLDEN_BUCKET:-golden}"

usage() {
  cat <<EOF
Usage: $0 <SCAN_ID>

Promotes security scan artifacts from incoming to golden bucket.

This script:
  1. Verifies the scan exists in raw bucket
  2. Checks for verification-proof.json
  3. Copies artifacts from raw/security-scans/SCAN_ID/incoming/ to golden/security-scans/SCAN_ID/golden/
  4. Copies verification proof from raw/security-scans/SCAN_ID/SCAN_ID/ to golden/

Environment Variables:
  DOCOPS_API         - API base URL (default: http://localhost:8000)
  AWS_ENDPOINT_URL   - S3 endpoint (default: http://localhost:4566)
  DATALAKE_RAW_BUCKET    - Raw bucket name (default: raw)
  DATALAKE_GOLDEN_BUCKET - Golden bucket name (default: golden)

Example:
  $0 scan_73c5ff9a4478

EOF
  exit 1
}

if [ $# -ne 1 ]; then
  usage
fi

SCAN_ID="$1"

echo "=== Promoting Security Scan: $SCAN_ID ==="
echo "Raw bucket: $RAW_BUCKET"
echo "Golden bucket: $GOLDEN_BUCKET"
echo "Endpoint: $ENDPOINT"
echo ""

# Check if AWS CLI is available
if ! command -v aws >/dev/null 2>&1; then
  echo "ERROR: aws CLI is required" >&2
  exit 1
fi

# Step 1: Check if scan exists in raw bucket
echo "Step 1: Verifying scan exists in raw bucket..."
if ! aws s3 ls "s3://$RAW_BUCKET/security-scans/$SCAN_ID/" --endpoint-url "$ENDPOINT" >/dev/null 2>&1; then
  echo "ERROR: Scan $SCAN_ID not found in raw bucket" >&2
  exit 1
fi
echo "✓ Scan found in raw bucket"
echo ""

# Step 2: Check for verification proof
echo "Step 2: Checking for verification proof..."
VERIFICATION_PROOF_PATH="s3://$RAW_BUCKET/security-scans/$SCAN_ID/incoming/verification-proof.json"
if ! aws s3 ls "$VERIFICATION_PROOF_PATH" --endpoint-url "$ENDPOINT" >/dev/null 2>&1; then
  echo "WARNING: verification-proof.json not found at $VERIFICATION_PROOF_PATH" >&2
  echo "This scan may not have been verified by Certus Trust" >&2
  read -p "Continue anyway? (y/N): " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Promotion cancelled"
    exit 1
  fi
else
  echo "✓ Verification proof found"
fi
echo ""

# Step 3: List artifacts in incoming
echo "Step 3: Listing artifacts in incoming..."
INCOMING_PATH="s3://$RAW_BUCKET/security-scans/$SCAN_ID/incoming/"
echo "Incoming location: $INCOMING_PATH"
aws s3 ls "$INCOMING_PATH" --endpoint-url "$ENDPOINT" --recursive || {
  echo "ERROR: No artifacts found in incoming" >&2
  exit 1
}
echo ""

# Step 4: Promote artifacts from incoming to golden
echo "Step 4: Promoting artifacts to golden bucket..."

# Key artifacts to promote
ARTIFACTS=(
  "reports/sast/trivy.sarif.json"
  "reports/sbom/syft.spdx.json"
  "cosign.attestation.jsonl"
  "reports/dast/zap-report.json"
  "zap-report.html"
  "artifacts/image.txt"
  "artifacts/image.digest"
  "logs/runner.log"
)

PROMOTED_COUNT=0
FAILED_COUNT=0

for artifact in "${ARTIFACTS[@]}"; do
  SOURCE="s3://$RAW_BUCKET/security-scans/$SCAN_ID/incoming/$artifact"
  DEST="s3://$GOLDEN_BUCKET/security-scans/$SCAN_ID/golden/$artifact"

  # Check if source exists
  if aws s3 ls "$SOURCE" --endpoint-url "$ENDPOINT" >/dev/null 2>&1; then
    echo "  Promoting: $artifact"
    if aws s3 cp "$SOURCE" "$DEST" --endpoint-url "$ENDPOINT" >/dev/null; then
      echo "    ✓ Copied to golden bucket"
      ((PROMOTED_COUNT++))
    else
      echo "    ✗ Failed to copy" >&2
      ((FAILED_COUNT++))
    fi
  else
    echo "  ⊘ Skipping: $artifact (not found in incoming)"
  fi
done

echo ""

# Step 5: Promote verification proof
echo "Step 5: Promoting verification proof..."
if aws s3 ls "$VERIFICATION_PROOF_PATH" --endpoint-url "$ENDPOINT" >/dev/null 2>&1; then
  DEST_PROOF="s3://$GOLDEN_BUCKET/security-scans/$SCAN_ID/golden/verification-proof.json"
  if aws s3 cp "$VERIFICATION_PROOF_PATH" "$DEST_PROOF" --endpoint-url "$ENDPOINT"; then
    echo "  ✓ Verification proof promoted"
    ((PROMOTED_COUNT++))
  else
    echo "  ✗ Failed to promote verification proof" >&2
    ((FAILED_COUNT++))
  fi
else
  echo "  ⊘ No verification proof to promote"
fi

echo ""

# Step 6: Promote scan.json metadata if exists
echo "Step 6: Promoting scan metadata..."
SCAN_JSON_PATH="s3://$RAW_BUCKET/security-scans/$SCAN_ID/incoming/scan.json"
if aws s3 ls "$SCAN_JSON_PATH" --endpoint-url "$ENDPOINT" >/dev/null 2>&1; then
  DEST_SCAN="s3://$GOLDEN_BUCKET/security-scans/$SCAN_ID/golden/scan.json"
  if aws s3 cp "$SCAN_JSON_PATH" "$DEST_SCAN" --endpoint-url "$ENDPOINT"; then
    echo "  ✓ Scan metadata promoted"
    ((PROMOTED_COUNT++))
  else
    echo "  ✗ Failed to promote scan metadata" >&2
    ((FAILED_COUNT++))
  fi
else
  echo "  ⊘ No scan metadata to promote"
fi

echo ""

# Step 7: Verify golden bucket contents
echo "Step 7: Verifying golden bucket..."
GOLDEN_PATH="s3://$GOLDEN_BUCKET/security-scans/$SCAN_ID/golden/"
echo "Golden location: $GOLDEN_PATH"
aws s3 ls "$GOLDEN_PATH" --endpoint-url "$ENDPOINT" --recursive

echo ""
echo "=== Promotion Summary ==="
echo "Promoted: $PROMOTED_COUNT files"
echo "Failed: $FAILED_COUNT files"
echo ""

if [ $FAILED_COUNT -gt 0 ]; then
  echo "⚠️  Some files failed to promote. Check errors above."
  exit 1
fi

echo "✓ Promotion completed successfully!"
echo ""
echo "Next steps:"
echo "  1. Review golden bucket contents above"
echo "  2. Run ingestion with:"
echo "     export SCAN_ID=\"$SCAN_ID\""
echo "     # See verify-trust.md Step 10 for ingestion commands"
