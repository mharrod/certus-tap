#!/bin/bash
set -euo pipefail
DEST=${1:-$HOME/corpora/privacy-pack}
mkdir -p "$(dirname "$DEST")"
rsync -a samples/privacy-pack/ "$DEST/"
echo "Copied privacy pack to $DEST"
