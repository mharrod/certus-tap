#!/bin/bash
set -euo pipefail
FILE=$(mktemp)
echo test > "$FILE"
OUT=$(mktemp)
COSIGN_PASSWORD="" cosign sign-blob --key samples/oci-attestations/keys/cosign.key --output-signature "$OUT" "$FILE"
COSIGN_PASSWORD="" cosign verify-blob --key samples/oci-attestations/keys/cosign.pub --signature "$OUT" "$FILE"
