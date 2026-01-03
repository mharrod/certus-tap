#!/usr/bin/env bash
set -euo pipefail

# Always run from repo root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Check if zellij is installed
if ! command -v zellij &> /dev/null; then
  echo "❌ zellij not found. Install with: brew install zellij"
  exit 1
fi

# Launch zellij with the agent workspace layout
echo "🚀 Launching agent workspace..."
exec zellij --layout ".context/zellij.kdl"
