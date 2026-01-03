#!/usr/bin/env bash
# Sign security scan artifacts with cosign
# Usage: ./scripts/sign-security-artifacts.sh <bundle-dir> <cosign-key-path>

set -euo pipefail

BUNDLE_DIR="${1:-build/security-results/latest}"
COSIGN_KEY="${2:-}"

if [ -z "$COSIGN_KEY" ]; then
    echo "Usage: $0 <bundle-dir> <cosign-key-path>"
    echo ""
    echo "Example:"
    echo "  $0 build/security-results/latest /path/to/cosign.key"
    echo ""
    echo "To generate a test key pair:"
    echo "  cosign generate-key-pair"
    exit 1
fi

if [ ! -f "$COSIGN_KEY" ]; then
    echo "Error: Cosign key not found: $COSIGN_KEY"
    exit 1
fi

if [ ! -d "$BUNDLE_DIR" ]; then
    echo "Error: Bundle directory not found: $BUNDLE_DIR"
    exit 1
fi

echo "🔐 Signing security artifacts in $BUNDLE_DIR"
echo ""

# Sign attestation
if [ -f "$BUNDLE_DIR/attestation.intoto.json" ]; then
    echo "📜 Signing attestation..."
    COSIGN_PASSWORD="" cosign sign-blob \
        --key "$COSIGN_KEY" \
        --tlog-upload=false \
        --output-signature "$BUNDLE_DIR/attestation.intoto.json.sig" \
        "$BUNDLE_DIR/attestation.intoto.json" > /dev/null
    echo "   ✓ attestation.intoto.json.sig"
fi

# Sign SBOM files
for sbom in "$BUNDLE_DIR"/sbom.*.json; do
    if [ -f "$sbom" ]; then
        filename=$(basename "$sbom")
        echo "📦 Signing $filename..."
        COSIGN_PASSWORD="" cosign sign-blob \
            --key "$COSIGN_KEY" \
            --tlog-upload=false \
            --output-signature "${sbom}.sig" \
            "$sbom" > /dev/null
        echo "   ✓ ${filename}.sig"
    fi
done

# Sign SARIF files (optional)
for sarif in "$BUNDLE_DIR"/*.sarif.json; do
    if [ -f "$sarif" ]; then
        filename=$(basename "$sarif")
        echo "🔍 Signing $filename..."
        COSIGN_PASSWORD="" cosign sign-blob \
            --key "$COSIGN_KEY" \
            --tlog-upload=false \
            --output-signature "${sarif}.sig" \
            "$sarif" > /dev/null
        echo "   ✓ ${filename}.sig"
    fi
done

echo ""
echo "✅ Successfully signed all artifacts"
echo ""
echo "To verify signatures:"
echo "  cosign verify-blob --key cosign.pub --signature <file>.sig --insecure-ignore-tlog <file>"
