# Certus Trust Mock Service - Enhanced Features

This document describes the enhanced mock features added to Certus Trust for AI agent experimentation and testing.

## Overview

The mock service now includes:
1. **Service Statistics** - Track verification activity
2. **Failure Simulation** - Test error handling
3. **Provenance Chains** - Complete audit trails for scans
4. **Mock Scenarios** - Realistic verification states
5. **Merkle Proofs** - Transparency log cryptographic proofs

## 1. Service Statistics

Get real-time statistics about Trust service activity.

### Endpoint

```http
GET /v1/stats
```

### Response

```json
{
  "total_signatures": 42,
  "total_transparency_entries": 38,
  "verification_stats": {
    "total": 156,
    "successful": 142,
    "failed": 14
  },
  "signers": [
    "certus-assurance@certus.cloud",
    "certus-trust@certus.cloud"
  ],
  "timestamp": "2025-12-13T20:00:00Z"
}
```

### Use Cases

- **Debugging**: Check service activity during development
- **Demos**: Show verification rates and activity
- **AI Agents**: Analyze Trust service behavior patterns

### Example

```bash
curl http://localhost:8057/v1/stats | jq
```

## 2. Failure Simulation

Simulate verification failures to test error handling.

### Parameters

- `simulate_failure=true` - Force verification to fail
- `scenario={name}` - Use predefined scenario

### Endpoint

```http
POST /v1/verify?simulate_failure=true
POST /v1/verify?scenario=tampered_scan
```

### Available Scenarios

| Scenario | Description | Inner Sig | Outer Sig | Trust Level | Chain Status |
|----------|-------------|-----------|-----------|-------------|--------------|
| `verified_premium_scan` | Fully verified premium scan | ✅ Valid | ✅ Valid | high | complete |
| `unverified_basic_scan` | Basic tier, no outer sig | ✅ Valid | ❌ Invalid | low | partial |
| `tampered_scan` | Tampered artifact detected | ❌ Invalid | ❌ Invalid | none | broken |
| `expired_certificate` | Certificate has expired | ❌ Invalid | ❌ Invalid | untrusted | broken |
| `invalid_signer` | Wrong signer identity | ❌ Invalid | ❌ Invalid | untrusted | broken |

### Examples

**Simulate generic failure:**

```bash
curl -X POST http://localhost:8057/v1/verify?simulate_failure=true \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123",
    "signature": "mock-sig",
    "identity": "certus-assurance@certus.cloud"
  }' | jq
```

**Use specific scenario:**

```bash
curl -X POST http://localhost:8057/v1/verify?scenario=tampered_scan \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123",
    "signature": "mock-sig"
  }' | jq
```

### Use Cases

- **Testing**: Verify error handling in agents
- **Training**: Teach agents to handle failures
- **Development**: Test failure recovery logic

## 3. Provenance Chain

Get complete provenance history for a scan.

### Endpoint

```http
GET /v1/provenance/{scan_id}
GET /v1/provenance/{scan_id}?scenario={name}
```

### Response

```json
{
  "scan_id": "scan-123",
  "manifest": {
    "version": "v1.2.3",
    "digest": "sha256:abc123def456...",
    "signed_by": "certus-assurance@certus.cloud",
    "signed_at": "2025-12-13T10:00:00Z"
  },
  "scans": [
    {
      "tool": "trivy",
      "version": "0.45.0",
      "signed_by": "certus-assurance@certus.cloud",
      "verified_by": "certus-trust@certus.cloud",
      "timestamp": "2025-12-13T10:01:00Z"
    },
    {
      "tool": "semgrep",
      "version": "1.45.0",
      "signed_by": "certus-assurance@certus.cloud",
      "verified_by": "certus-trust@certus.cloud",
      "timestamp": "2025-12-13T10:02:00Z"
    }
  ],
  "verification_trail": [
    {
      "timestamp": "2025-12-13T10:05:00Z",
      "verifier": "certus-trust@certus.cloud",
      "result": "verified",
      "details": "All signatures valid"
    }
  ],
  "storage_locations": {
    "s3": "s3://raw/scans/scan-123",
    "oci": "registry.certus.cloud/scans/scan-123:latest"
  },
  "chain_status": "complete",
  "trust_level": "high"
}
```

### Examples

**Get provenance for verified scan:**

```bash
curl http://localhost:8057/v1/provenance/scan-123 | jq
```

**Get provenance with tampered scenario:**

```bash
curl http://localhost:8057/v1/provenance/scan-456?scenario=tampered_scan | jq
```

### Use Cases

- **AI Agents**: Understand "where did this scan come from?"
- **Auditing**: Complete audit trail for compliance
- **Debugging**: Trace scan through entire pipeline
- **Research**: Analyze provenance patterns

## 4. Merkle Proof Simulation

Get cryptographic proofs from transparency log.

### Endpoint

```http
GET /v1/transparency/{entry_id}
GET /v1/transparency/{entry_id}?include_proof=true
```

### Response

```json
{
  "entry_id": "abc-123",
  "artifact": "sha256:def456",
  "timestamp": "2025-12-13T10:00:00Z",
  "signer": "certus-assurance@certus.cloud",
  "signature": "mock-signature-abc123",
  "proof": {
    "tree_size": 15,
    "leaf_index": 7,
    "hashes": [
      "sha256:hash1...",
      "sha256:hash2...",
      "sha256:hash3..."
    ],
    "root_hash": "sha256:root..."
  }
}
```

### Examples

**Get entry with proof:**

```bash
curl http://localhost:8057/v1/transparency/abc-123?include_proof=true | jq
```

**Get entry without proof (faster):**

```bash
curl http://localhost:8057/v1/transparency/abc-123?include_proof=false | jq
```

### Use Cases

- **Learning**: Understand Merkle tree structure
- **Verification**: Show how transparency proofs work
- **Demos**: Demonstrate cryptographic audit trails

## Integration with AI Agents

### Agent Use Case 1: Analyze Scan Provenance

```python
# Agent queries provenance to understand scan context
provenance = get_provenance("scan-123")

# Agent reasons about trust level
if provenance["trust_level"] == "high":
    print("Scan is fully verified and trustworthy")
elif provenance["chain_status"] == "broken":
    print("WARNING: Provenance chain is broken!")

# Agent traces who verified what
for entry in provenance["verification_trail"]:
    print(f"{entry['verifier']} verified at {entry['timestamp']}")
```

### Agent Use Case 2: Handle Verification Failures

```python
# Agent tests both success and failure paths
result_success = verify(artifact, signature)
result_failure = verify(artifact, signature, simulate_failure=True)

# Agent learns to handle different scenarios
for scenario in ["verified_premium_scan", "tampered_scan", "expired_certificate"]:
    result = verify(artifact, signature, scenario=scenario)
    agent.learn_from_result(scenario, result)
```

### Agent Use Case 3: Monitor Trust Service

```python
# Agent monitors Trust service health
stats = get_stats()

failure_rate = stats["verification_stats"]["failed"] / stats["verification_stats"]["total"]
if failure_rate > 0.1:
    print(f"WARNING: High failure rate: {failure_rate:.1%}")
```

## Testing the Features

### Quick Test Script

```bash
#!/bin/bash

BASE_URL="http://localhost:8057"

echo "=== Testing Stats Endpoint ==="
curl $BASE_URL/v1/stats | jq

echo "\n=== Testing Provenance Chain ==="
curl $BASE_URL/v1/provenance/test-scan-001 | jq

echo "\n=== Testing Provenance with Tampered Scenario ==="
curl "$BASE_URL/v1/provenance/test-scan-002?scenario=tampered_scan" | jq

echo "\n=== Testing Failure Simulation ==="
curl -X POST "$BASE_URL/v1/verify?simulate_failure=true" \
  -H "Content-Type: application/json" \
  -d '{"artifact": "sha256:test", "signature": "test-sig"}' | jq

echo "\n=== Testing Scenario-Based Verification ==="
curl -X POST "$BASE_URL/v1/verify?scenario=expired_certificate" \
  -H "Content-Type: application/json" \
  -d '{"artifact": "sha256:test", "signature": "test-sig"}' | jq
```

## Next Steps

These mock features are sufficient for:
- ✅ Tier 1 AI agent development
- ✅ Tutorial demonstrations
- ✅ Development and testing
- ✅ Research experiments

Real Sigstore integration (cosign, rekor, fulcio) can be deferred to Tier 3 when:
- Publishing research requiring cryptographic proofs
- External collaboration needing verification
- Production deployment

## Summary of Enhancements

| Feature | Purpose | Endpoint | Status |
|---------|---------|----------|--------|
| **Service Stats** | Monitor activity | `GET /v1/stats` | ✅ Complete |
| **Failure Simulation** | Test error handling | `POST /v1/verify?simulate_failure=true` | ✅ Complete |
| **Provenance Chain** | Full audit trail | `GET /v1/provenance/{scan_id}` | ✅ Complete |
| **Mock Scenarios** | Realistic states | `?scenario={name}` on verify/provenance | ✅ Complete |
| **Merkle Proofs** | Transparency proofs | `GET /v1/transparency/{id}?include_proof=true` | ✅ Complete |

All features are **production-ready for Tier 1 AI agent experimentation**.
