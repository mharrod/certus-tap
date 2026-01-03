# Integration Tests: Verify-Trust Workflow

This directory contains integration tests for the complete verify-trust workflow described in `docs/learn/trust/verify-trust.md`.

## Overview

These tests validate the **end-to-end verification-first pipeline**, including:

1. **Scan Initiation** - Submit security scans via Certus-Assurance
2. **Upload Permission** - Request and receive verification from Certus-Trust
3. **Artifact Storage** - Validate S3 storage of verified artifacts
4. **Promotion Workflow** - Move artifacts through raw → quarantine → golden
5. **Provenance Ingestion** - Ingest with verification metadata
6. **Audit Trail** - Query provenance in Neo4j and OpenSearch

## Difference from Smoke Tests

| Aspect | Smoke Tests | Integration Tests |
|--------|-------------|------------------|
| **Location** | `tests/smoke/security_workflows/` | `tests/integration/security_workflows/` |
| **Focus** | Component-level validation | End-to-end workflow validation |
| **Speed** | Fast (<5s per test) | Slower (30s-2min per test) |
| **Services** | Single service or mocked | Multiple services required |
| **Markers** | `@pytest.mark.smoke` | `@pytest.mark.integration`, `@pytest.mark.slow` |
| **Purpose** | Quick health checks | Complete workflow validation |

## Running Integration Tests

### Prerequisites

All services must be running:

```bash
just up
```

Verify services are healthy:

```bash
# Certus-Assurance
curl http://localhost:8056/health

# Certus-Trust
curl http://localhost:8057/v1/health

# Certus-Transform
curl http://localhost:8100/health

# Certus-Ask
curl http://localhost:8000/health
```

### Run All Integration Tests

```bash
# Run all integration tests
pytest tests/integration/ -v

# Run only verify-trust workflow tests
pytest tests/integration/security_workflows/test_verify_trust_workflow.py -v

# Run with markers
pytest -m integration -v
pytest -m "integration and not slow" -v
```

### Run Specific Tests

```bash
# Test service prerequisites
pytest tests/integration/security_workflows/test_verify_trust_workflow.py::test_service_prerequisites -v

# Test golden bucket ingestion
pytest tests/integration/security_workflows/test_verify_trust_workflow.py::test_golden_bucket_ingestion_with_provenance -v

# Test Neo4j queries
pytest tests/integration/security_workflows/test_verify_trust_workflow.py::test_neo4j_provenance_query_chain_verification -v
```

## Test Coverage Map

Each test validates specific steps from `docs/learn/trust/verify-trust.md`:

| Test | Tutorial Steps | What It Validates |
|------|----------------|-------------------|
| `test_service_prerequisites` | Prerequisite | All services healthy |
| `test_scan_initiation_workflow` | Step 4 | Scan submission and completion |
| `test_upload_request_verified_tier` | Steps 5-6 | Upload permission flow |
| `test_upload_rejection_invalid_signer` | Step 7b | Rejection scenarios |
| `test_s3_artifact_storage_validation` | Step 6b | S3 artifact validation |
| `test_promotion_workflow_raw_to_golden` | Step 9 | Bucket promotion |
| `test_golden_bucket_ingestion_with_provenance` | Step 10 | Ingestion with metadata |
| `test_neo4j_provenance_query_chain_verification` | Step 11 | Audit trail queries |
| `test_tier_comparison_basic_vs_verified` | Steps 2-3 | Tier behavior differences |
| `test_complete_audit_trail_end_to_end` | All steps | Full golden path |

## Test Implementation Status

### ✅ Implemented and Passing

- `test_golden_bucket_ingestion_with_provenance` - Tests SARIF/SBOM ingestion
- `test_neo4j_provenance_query_chain_verification` - Tests provenance queries

### 🚧 Implemented but Skipped (Requires Full Stack)

- `test_service_prerequisites` - Requires all services running
- `test_scan_initiation_workflow` - Requires Certus-Assurance API
- `test_upload_request_verified_tier` - Requires scan completion
- `test_upload_rejection_invalid_signer` - Requires upload flow

### 📝 Placeholder (To Be Implemented)

- `test_s3_artifact_storage_validation` - Needs boto3 S3 client
- `test_promotion_workflow_raw_to_golden` - Needs promotion script/API
- `test_tier_comparison_basic_vs_verified` - Needs tier selection
- `test_complete_audit_trail_end_to_end` - Needs full workflow

## Environment Variables

Override service URLs for testing:

```bash
export ASSURANCE_URL="http://localhost:8056"
export TRUST_URL="http://localhost:8057"
export TRANSFORM_URL="http://localhost:8100"
export ASK_URL="http://localhost:8000"
export NEO4J_URI="neo4j://localhost:7687"
export S3_ENDPOINT_URL="http://localhost:4566"
```

## Development Workflow

### Adding New Integration Tests

1. **Create test function** in `test_verify_trust_workflow.py`
2. **Add tutorial reference** in docstring (e.g., "Test Step 5: ...")
3. **Use fixtures** (`integration_session`, `verify_services`)
4. **Mark appropriately** (`@pytest.mark.integration`, `@pytest.mark.slow`)
5. **Skip gracefully** if services unavailable

Example:

```python
def test_new_workflow_step(
    integration_session: requests.Session, verify_services: dict[str, Any]
) -> None:
    """
    Test Step X: Description from tutorial.

    Validates:
    1. First thing
    2. Second thing
    """
    # Implementation
    if response.status_code == 404:
        pytest.skip("Service endpoint not implemented")
```

### Running Tests During Development

```bash
# Fast feedback loop - skip integration tests
pytest tests/smoke/ -v

# Full validation - run everything
pytest tests/ -v

# Only integration tests
pytest tests/integration/ -v
```

## Troubleshooting

### Tests Skip Immediately

**Problem**: All tests skip with "service not available"

**Solution**: Ensure services are running with `just up`

### Tests Timeout

**Problem**: Tests hang waiting for service responses

**Solution**: Check service logs and reduce timeout values for faster feedback

### Neo4j Connection Failed

**Problem**: Neo4j driver import or connection errors

**Solution**:
- Install neo4j driver: `pip install neo4j`
- Verify Neo4j is running: `docker ps | grep neo4j`
- Check connection: `cypher-shell -u neo4j -p password`

### S3/LocalStack Issues

**Problem**: S3 operations fail

**Solution**:
- Install boto3: `pip install boto3`
- Verify LocalStack: `curl http://localhost:4566/_localstack/health`
- Check buckets: `aws s3 ls --endpoint-url http://localhost:4566`

## Next Steps

1. **Implement S3 validation tests** - Add boto3 client for artifact verification
2. **Add shared fixtures** - Create reusable scan submission fixture
3. **Complete end-to-end test** - Implement full golden path test
4. **Add performance benchmarks** - Track workflow timing
5. **CI/CD integration** - Run integration tests in CI pipeline

## References

- Tutorial: `docs/learn/trust/verify-trust.md`
- Smoke tests: `tests/smoke/security_workflows/test_certus_trust_scans.py`
- Service docs: `docs/services/`
