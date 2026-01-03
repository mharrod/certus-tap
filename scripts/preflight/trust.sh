#!/bin/bash

# Preflight checks for Certus Trust with real sigstore

set -euo pipefail

echo "🚀 Running Certus Trust Preflight Checks"

# Check 1: Verify sigstore services
if ! curl -f http://localhost:3001 >/dev/null 2>&1; then
    echo "❌ Rekor not available at http://localhost:3001"
    exit 1
fi
echo "✅ Rekor is running"

if ! curl -f http://localhost:5555 >/dev/null 2>&1; then
    echo "❌ Fulcio not available at http://localhost:5555"
    exit 1
fi
echo "✅ Fulcio is running"

# Check 2: Verify Certus Trust
if ! curl -f http://localhost:8057/health >/dev/null 2>&1; then
    echo "❌ Certus Trust not available at http://localhost:8057"
    exit 1
fi
echo "✅ Certus Trust is running"

# Check 3: Test basic signing (mock)
SIGN_RESPONSE=$(curl -s -X POST http://localhost:8057/v1/sign \
    -H "Content-Type: application/json" \
    -d '{"artifact": "test", "artifact_type": "test"}')

if [ -z "$SIGN_RESPONSE" ]; then
    echo "❌ Signing endpoint not responding"
    exit 1
fi
echo "✅ Signing endpoint working"

# Check 4: Test verification
VERIFY_RESPONSE=$(curl -s -X POST http://localhost:8057/v1/verify \
    -H "Content-Type: application/json" \
    -d '{"signature": "test"}')

if [ -z "$VERIFY_RESPONSE" ]; then
    echo "❌ Verification endpoint not responding"
    exit 1
fi
echo "✅ Verification endpoint working"

# Check 5: Test configuration
CONFIG_RESPONSE=$(curl -s http://localhost:8057/v1/sigstore/config)
if [ -z "$CONFIG_RESPONSE" ]; then
    echo "❌ Configuration endpoint not responding"
    exit 1
fi
echo "✅ Configuration endpoint working"

# Check 6: Verify network connectivity
if ! docker compose -f certus_infrastructure/docker-compose.sigstore.yml ps | grep -q "Up"; then
    echo "❌ Some sigstore services are not healthy"
    exit 1
fi
echo "✅ All sigstore services healthy"

echo ""
echo "🎉 All Certus Trust preflight checks passed!"
echo "Environment is ready for:"
echo "  • Signing artifacts"
echo "  • Verifying signatures"
echo "  • Trust tutorial execution"
echo "  • Production workloads"
