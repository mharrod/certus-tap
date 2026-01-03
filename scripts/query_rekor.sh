#!/bin/bash
# Query Rekor transparency log via HTTP API
# Usage: ./query_rekor.sh [artifact_hash]

set -euo pipefail

REKOR_URL="${REKOR_URL:-http://localhost:3001}"

echo "=== Rekor Transparency Log Query ==="
echo "Server: $REKOR_URL"
echo ""

# Get log info
echo "📊 Log Information:"
LOG_INFO=$(curl -s "$REKOR_URL/api/v1/log")
TREE_SIZE=$(echo "$LOG_INFO" | jq -r '.treeSize')
ROOT_HASH=$(echo "$LOG_INFO" | jq -r '.rootHash')
echo "  Tree Size: $TREE_SIZE entries"
echo "  Root Hash: $ROOT_HASH"
echo ""

# Search by hash if provided
if [ $# -ge 1 ]; then
    ARTIFACT_HASH="$1"
    echo "🔍 Searching for artifact hash: sha256:$ARTIFACT_HASH"

    SEARCH_RESULT=$(curl -s -X POST "$REKOR_URL/api/v1/index/retrieve" \
        -H "Content-Type: application/json" \
        -d "{\"hash\":\"sha256:$ARTIFACT_HASH\"}" || echo "{}")

    if echo "$SEARCH_RESULT" | jq -e '.[]' >/dev/null 2>&1; then
        echo "✅ Found entries:"
        echo "$SEARCH_RESULT" | jq '.'

        # Get entry details
        UUIDS=$(echo "$SEARCH_RESULT" | jq -r '.[]')
        for UUID in $UUIDS; do
            echo ""
            echo "📄 Entry Details for $UUID:"
            curl -s "$REKOR_URL/api/v1/log/entries/$UUID" | jq '.'
        done
    else
        echo "❌ No entries found for this hash"
    fi
else
    echo "💡 Usage: $0 <artifact_hash>"
    echo "   Example: $0 abc123def456..."
    echo ""

    if [ "$TREE_SIZE" -gt 0 ]; then
        echo "📋 Fetching latest entry (index $((TREE_SIZE - 1))):"
        curl -s "$REKOR_URL/api/v1/log/entries?logIndex=$((TREE_SIZE - 1))" | jq '.'
    else
        echo "ℹ️  No entries in the log yet"
    fi
fi

echo ""
echo "🔑 Rekor Public Key:"
curl -s "$REKOR_URL/api/v1/log/publicKey"
echo ""
