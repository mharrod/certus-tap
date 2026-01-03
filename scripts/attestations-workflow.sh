#!/bin/bash

set -euo pipefail

# OCI Attestations Workflow
# Complete workflow: generate → sign → push → verify

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Configuration
OUTPUT_DIR="${OUTPUT_DIR:-$PROJECT_ROOT/samples/oci-attestations/artifacts}"
KEY_PATH="${KEY_PATH:-$PROJECT_ROOT/samples/oci-attestations/keys/cosign.key}"
REGISTRY_URL="${REGISTRY_URL:-http://localhost:5000}"
REGISTRY_USER="${REGISTRY_USER:-}"
REGISTRY_PASS="${REGISTRY_PASS:-}"
REGISTRY_REPO="${REGISTRY_REPO:-product-acquisition/attestations}"
PRODUCT_NAME="${PRODUCT_NAME:-Acme Product}"
PRODUCT_VERSION="${PRODUCT_VERSION:-1.0.0}"

echo "=== OCI Attestations Workflow ==="
echo "Product: $PRODUCT_NAME v$PRODUCT_VERSION"
echo "Output: $OUTPUT_DIR"
echo "Registry: $REGISTRY_URL/$REGISTRY_REPO"
echo ""

# Step 1: Generate artifacts
echo "Step 1: Generating artifacts..."
python3 "$SCRIPT_DIR/oci-attestations.py" generate \
  --output "$OUTPUT_DIR" \
  --product "$PRODUCT_NAME" \
  --version "$PRODUCT_VERSION"
echo ""

# Step 2: Setup keys
echo "Step 2: Setting up cosign keys..."
python3 "$SCRIPT_DIR/oci-attestations.py" setup-keys \
  --key-path "$KEY_PATH"
echo ""

# Step 3: Sign artifacts
echo "Step 3: Signing artifacts..."
python3 "$SCRIPT_DIR/oci-attestations.py" sign \
  --artifacts-dir "$OUTPUT_DIR" \
  --key-path "$KEY_PATH"
echo ""

# Step 4: Verify artifacts locally
echo "Step 4: Verifying signatures locally..."
python3 "$SCRIPT_DIR/oci-attestations.py" verify \
  --artifacts-dir "$OUTPUT_DIR" \
  --key-path "${PROJECT_ROOT}/samples/oci-attestations/keys/cosign.pub"
echo ""

# Step 5: Push to OCI registry (optional)
if command -v oras &> /dev/null; then
  echo "Step 5: Pushing to OCI registry..."
  python3 "$SCRIPT_DIR/oci-attestations.py" push \
    --artifacts-dir "$OUTPUT_DIR" \
    --registry "$REGISTRY_URL" \
    --username "$REGISTRY_USER" \
    --password "$REGISTRY_PASS" \
    --repo "$REGISTRY_REPO"
  echo ""
else
  echo "Step 5: Skipping registry push (oras CLI not installed)"
  echo "        Install with: brew install oras"
  echo ""
fi

echo "=== Workflow Complete ==="
echo ""
echo "Generated Artifacts:"
echo "  SBOM (SPDX 2.3)                    → $OUTPUT_DIR/sbom/product.spdx.json"
echo "  in-toto Build Attestation          → $OUTPUT_DIR/attestations/build.intoto.json"
echo "  Security Scan Results (SARIF)      → $OUTPUT_DIR/scans/vulnerability.sarif"
echo "  SLSA v1.0 Provenance (with SBOM)   → $OUTPUT_DIR/provenance/slsa-provenance.json"
echo ""
echo "All artifacts signed with cosign"
echo ""
echo "Next steps:"
echo "1. Review artifacts in: $OUTPUT_DIR"
echo "2. Verify signatures:"
echo "   python3 $SCRIPT_DIR/oci-attestations.py verify \\"
echo "     --artifacts-dir $OUTPUT_DIR \\"
echo "     --key-path ${PROJECT_ROOT}/samples/oci-attestations/keys/cosign.pub"
echo "3. Push to OCI registry (requires oras):"
echo "   python3 $SCRIPT_DIR/oci-attestations.py push \\"
echo "     --artifacts-dir $OUTPUT_DIR \\"
echo "     --registry http://localhost:5000"
echo "4. Integrate into acquisition review capstone tutorial"
echo "5. Ingest verified artifacts into Certus TAP"
