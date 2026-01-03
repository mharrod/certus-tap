# Vendor Review Tutorial Test Coverage

This document maps test coverage to the `docs/learn/trust/vendor-review.md` tutorial.

## Overview

The vendor review tutorial describes how auditors/customers validate vendor security posture after Certus-Trust approval. Tests validate each step of this workflow.

## Test Coverage Map

| Tutorial Step | Test File | Test Functions | Status |
|--------------|-----------|----------------|--------|
| **Step 1: Confirm Trust Results** | `test_vendor_review_oci.py` | `test_confirm_trust_verification_results` | ⏭️ Stub |
| **Step 2: Pull OCI Bundle** | `test_vendor_review_oci.py` | `test_pull_signed_bundle_from_oci`<br>`test_validate_oci_bundle_structure`<br>`test_oci_registry_health` | ⏭️ Stub<br>⏭️ Stub<br>✅ Working |
| **Step 3: Re-Verify Signatures** | `certus_trust/tests/integration/test_signature_reverification.py` | `test_reverify_sbom_signature`<br>`test_reverify_sarif_signature`<br>`test_reverify_provenance_signature`<br>`test_validate_dual_signature_chain`<br>`test_compare_sbom_digest_with_provenance` | ⏭️ Stub<br>⏭️ Stub<br>⏭️ Stub<br>⏭️ Stub<br>✅ Working |
| **Step 4: Inspect Artifacts** | `test_vendor_review_oci.py` | `test_verification_proof_structure` | ⏭️ Stub |
| **Step 5: Ingest into TAP** | `certus_ask/tests/integration/test_verified_artifact_ingestion.py` | `test_ingest_sbom_from_verified_bundle`<br>`test_ingest_sarif_from_verified_bundle`<br>`test_ingest_provenance_from_verified_bundle`<br>`test_validate_ingestion_audit_trail` | ⏭️ Stub<br>⏭️ Stub<br>⏭️ Stub<br>⏭️ Stub |
| **Step 6: Ask Questions** | `certus_ask/tests/integration/test_supply_chain_queries.py` | `test_query_sbom_packages_and_licenses`<br>`test_query_slsa_provenance`<br>`test_query_high_severity_vulnerabilities` | ⏭️ Stub<br>⏭️ Stub<br>⏭️ Stub |
| **Step 7: Compliance Reports** | `test_compliance_reporting.py` | `test_create_compliance_findings_json`<br>`test_generate_compliance_report`<br>`test_sign_compliance_report`<br>`test_verify_signed_compliance_report`<br>`test_upload_compliance_report_to_oci` | ✅ Working<br>⏭️ Stub<br>⏭️ Stub<br>⏭️ Stub<br>⏭️ Stub |
| **Step 8: Audit Trail** | `test_verification_manifest.py` | `test_create_verification_manifest`<br>`test_sign_verification_manifest`<br>`test_upload_verification_manifest_to_oci`<br>`test_verify_complete_audit_trail` | ✅ Working<br>⏭️ Stub<br>⏭️ Stub<br>⏭️ Stub |

**Legend:**
- ✅ **Working**: Test has working implementation
- ⏭️ **Stub**: Test skeleton with `pytest.skip()` - needs implementation
- ❌ **Missing**: No test exists

## Test Files Created

### Integration Tests (Cross-Service)

```
tests/integration/workflows/
├── test_vendor_review_oci.py          # OCI registry pull/validation
├── test_compliance_reporting.py       # Report generation/signing
└── test_verification_manifest.py      # Audit trail creation
```

### Service-Level Integration Tests

```
certus_trust/tests/integration/
└── test_signature_reverification.py   # Independent signature verification

certus_ask/tests/integration/
├── test_verified_artifact_ingestion.py # TAP ingestion from verified bundle
└── test_supply_chain_queries.py        # RAG queries for compliance
```

### Contract Tests

```
certus_trust/tests/contract/
└── test_oci_registry_api.py           # OCI API expectations
```

## Running Vendor Review Tests

### All Vendor Review Tests

```bash
# Run all tests related to vendor review workflow
pytest tests/integration/workflows/test_vendor_review_oci.py \
       tests/integration/workflows/test_compliance_reporting.py \
       tests/integration/workflows/test_verification_manifest.py \
       certus_trust/tests/integration/test_signature_reverification.py \
       certus_ask/tests/integration/test_verified_artifact_ingestion.py \
       certus_ask/tests/integration/test_supply_chain_queries.py \
       -v
```

### By Tutorial Step

```bash
# Step 2: OCI Pull
pytest tests/integration/workflows/test_vendor_review_oci.py::test_pull_signed_bundle_from_oci -v

# Step 3: Signature Re-Verification
pytest certus_trust/tests/integration/test_signature_reverification.py -v

# Step 5: TAP Ingestion
pytest certus_ask/tests/integration/test_verified_artifact_ingestion.py -v

# Step 6: Supply Chain Queries
pytest certus_ask/tests/integration/test_supply_chain_queries.py -v

# Step 7: Compliance Reports
pytest tests/integration/workflows/test_compliance_reporting.py -v

# Step 8: Verification Manifest
pytest tests/integration/workflows/test_verification_manifest.py -v
```

### Working Tests Only

```bash
# Run only implemented tests (skip stubs)
pytest tests/integration/workflows/ \
       certus_trust/tests/integration/test_signature_reverification.py::test_compare_sbom_digest_with_provenance \
       certus_ask/tests/integration/ \
       -v --tb=short
```

## Prerequisites for Full Test Execution

To run all tests successfully, you need:

### Required Tools
- ✅ **ORAS CLI** - `brew install oras` or download from https://oras.land
- ✅ **cosign** - `brew install cosign` or download from https://github.com/sigstore/cosign
- ✅ **jq** - `brew install jq`
- ✅ **AWS CLI** - For S3 operations

### Required Services
- ✅ **OCI Registry** - Running on `localhost:5000`
- ✅ **LocalStack S3** - Running on `localhost:4566`
- ✅ **Certus-Assurance** - Running on `localhost:8056`
- ✅ **Certus-Trust** - Running on `localhost:8057`
- ✅ **Certus-Ask** - Running on `localhost:8000`

### Required Artifacts
- ✅ **Signed SBOM** - `samples/oci-attestations/artifacts/sbom/product.spdx.json`
- ✅ **Signed SARIF** - `samples/oci-attestations/artifacts/scans/vulnerability.sarif`
- ✅ **SLSA Provenance** - `samples/oci-attestations/artifacts/provenance/slsa-provenance.json`
- ✅ **Cosign Keys** - `samples/oci-attestations/keys/cosign.{pub,key}`

### Quick Setup

```bash
# Start all services
just up

# Verify services
just preflight

# Generate attestation artifacts (if missing)
just attestations-workflow "Acme Corporation Product" "2.5.0"

# Run Trust workflow to populate OCI/S3
scripts/reset-trust-demo.sh

# Export scan ID
export SCAN_ID=<scan-id-from-reset-script>
```

## Implementation Priority

### Phase 1: Critical Path (Week 1)
**Goal**: Enable basic OCI pull and signature verification

1. ✅ `test_oci_registry_health` - Already working
2. ✅ `test_compare_sbom_digest_with_provenance` - Already working
3. 🔨 `test_pull_signed_bundle_from_oci` - Implement ORAS pull
4. 🔨 `test_reverify_sbom_signature` - Implement cosign verification
5. 🔨 `test_reverify_sarif_signature` - Implement cosign verification

### Phase 2: TAP Integration (Week 2)
**Goal**: Enable artifact ingestion and querying

6. 🔨 `test_ingest_sbom_from_verified_bundle` - Implement TAP ingestion
7. 🔨 `test_ingest_sarif_from_verified_bundle` - Implement SARIF ingestion
8. 🔨 `test_query_sbom_packages_and_licenses` - Implement RAG queries
9. 🔨 `test_query_high_severity_vulnerabilities` - Implement security queries

### Phase 3: Compliance Workflow (Week 3)
**Goal**: Enable report generation and distribution

10. 🔨 `test_generate_compliance_report` - Implement report generation
11. 🔨 `test_sign_compliance_report` - Implement report signing
12. 🔨 `test_upload_compliance_report_to_oci` - Implement OCI upload

### Phase 4: Audit Trail (Week 4)
**Goal**: Complete end-to-end audit trail

13. 🔨 `test_sign_verification_manifest` - Implement manifest signing
14. 🔨 `test_verify_complete_audit_trail` - Implement full validation
15. 🔨 `test_compare_oci_vs_s3_artifacts` - Implement source comparison

## Test Implementation Guidelines

### Adding Test Implementation

When implementing a stubbed test:

1. **Remove `pytest.skip()`**
2. **Add real assertions**
3. **Update status in this doc** (⏭️ → ✅)
4. **Add to CI/CD pipeline**

Example:

```python
# BEFORE (stub)
def test_pull_signed_bundle_from_oci() -> None:
    pytest.skip("Requires OCI registry with test artifacts")

# AFTER (implemented)
def test_pull_signed_bundle_from_oci() -> None:
    """Pull signed bundle from OCI registry."""
    scan_id = os.getenv("TEST_SCAN_ID", "test-scan-123")
    output_dir = Path(f"/tmp/test-acquired-artifacts/{scan_id}")

    result = subprocess.run([
        "oras", "pull", "--plain-http",
        f"localhost:5000/product-acquisition/attestations:latest",
        "--output", str(output_dir),
    ], capture_output=True, text=True)

    assert result.returncode == 0, f"ORAS pull failed: {result.stderr}"

    for artifact in EXPECTED_ARTIFACTS:
        assert (output_dir / artifact).exists()

    print(f"✓ OCI bundle pulled: {len(EXPECTED_ARTIFACTS)} artifacts")
```

### Test Data Management

Use consistent test data across all vendor review tests:

```python
# Shared configuration
TEST_SCAN_ID = os.getenv("TEST_SCAN_ID", "test-scan-123")
TEST_VENDOR = "Acme Corporation"
TEST_PRODUCT = "Acme Product v2.5.0"
TEST_WORKSPACE = "oci-attestations-review"
```

### Handling Missing Dependencies

Tests should gracefully skip when dependencies unavailable:

```python
if not _check_oras_available():
    pytest.skip("ORAS CLI not installed")

if not OCI_BUNDLE_DIR.exists():
    pytest.skip("OCI bundle not pulled - run test_pull_signed_bundle_from_oci first")
```

## Test Output Examples

### Successful Run

```
tests/integration/workflows/test_vendor_review_oci.py::test_oci_registry_health PASSED
✓ OCI registry accessible at localhost:5000

tests/integration/workflows/test_vendor_review_oci.py::test_pull_signed_bundle_from_oci PASSED
✓ OCI bundle pulled: 5 artifacts

certus_trust/tests/integration/test_signature_reverification.py::test_reverify_sbom_signature PASSED
✓ SBOM signature verified successfully

certus_trust/tests/integration/test_signature_reverification.py::test_compare_sbom_digest_with_provenance PASSED
✓ SBOM digest matches provenance: a1b2c3d4e5f6...

certus_ask/tests/integration/test_supply_chain_queries.py::test_query_sbom_packages_and_licenses PASSED
✓ SBOM query response: {"answer": "The SBOM contains 5 packages..."}
```

### Skipped Tests

```
tests/integration/workflows/test_compliance_reporting.py::test_generate_compliance_report SKIPPED
Requires compliance report generation script

tests/integration/workflows/test_vendor_review_oci.py::test_pull_signed_bundle_from_oci SKIPPED
ORAS CLI not installed
```

## Troubleshooting

### ORAS Pull Fails

**Problem**: `oras pull` returns non-zero exit code

**Solutions**:
- Verify OCI registry running: `curl http://localhost:5000/v2/`
- Check artifacts exist: `oras repo ls --plain-http localhost:5000`
- Use `--debug` flag: `oras pull --debug ...`

### Signature Verification Fails

**Problem**: `cosign verify-blob` fails

**Solutions**:
- Verify public key exists: `ls samples/oci-attestations/keys/cosign.pub`
- Check signature file: `ls <artifact>.sig`
- Use `--insecure-ignore-tlog` for local testing

### Ingestion Returns 422

**Problem**: TAP ingestion endpoint returns 422 Unprocessable Entity

**Solutions**:
- Verify workspace exists
- Check artifact format is correct
- Ensure required metadata present

## Related Documentation

- **Tutorial**: `docs/learn/trust/vendor-review.md`
- **Test Structure**: `tests/TEST-ORGANIZATION.md`
- **Integration Tests**: `tests/integration/workflows/README.md`
- **Trust Tests**: `certus_trust/tests/README.md` (if exists)

## Contributing

When adding tests for new vendor review features:

1. Update this coverage map
2. Follow existing test patterns
3. Add graceful skipping for missing deps
4. Include clear docstrings
5. Update implementation status
