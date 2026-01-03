# Test Suite Reference

Comprehensive reference for all testing commands, types, and targets in Certus-TAP.

## Quick Reference Table

| Command                 | Type        | Duration | Requires Docker | Coverage           | Description                                 |
| ----------------------- | ----------- | -------- | --------------- | ------------------ | ------------------------------------------- |
| `just test`             | Full        | 5-10 min | Yes             | All suites         | Complete test suite with coverage report    |
| `just test-fast`        | Mixed       | 1-3 min  | Partial         | Unit + Integration | Fast tests excluding smoke                  |
| `just test-smoke`       | E2E         | 5-10 min | Yes             | Smoke              | End-to-end Docker stack validation          |
| `just preflight`        | E2E         | 2-3 min  | Yes             | Stack health       | Docker stack health and connectivity checks |
| `just test-services`    | Unit        | 30-60s   | No (mocked)     | Service layer      | Service module tests                        |
| `just test-routers`     | Integration | 1-2 min  | Partial         | API layer          | FastAPI router/endpoint tests               |
| `just test-integration` | Integration | 2-3 min  | Yes             | Integration        | Docker/moto dependent tests                 |
| `just test-privacy`     | Mixed       | 1-2 min  | Partial         | Privacy            | Privacy-focused test cases                  |
| `just test-assurance`   | Mixed       | ~1 min   | No              | Certus Assurance   | Pipeline/API/storage/job manifest tests     |

## Security Testing Commands

| Command                          | Profile     | Tools                          | Duration | Description                      |
| -------------------------------- | ----------- | ------------------------------ | -------- | -------------------------------- |
| `just test-security-smoke`       | Smoke       | Ruff                           | ~20s     | Fastest profile for quick checks |
| `just test-security-fast`        | Fast        | Ruff, Bandit, detect-secrets   | ~2 min   | Pre-commit recommended           |
| `just test-security-medium`      | Medium      | Fast + OpenGrep                | ~4 min   | Pre-push recommended             |
| `just test-security-standard`    | Standard    | Medium + Trivy                 | ~8 min   | CI recommended                   |
| `just test-security-full`        | Full        | Standard + Privacy             | ~12 min  | Release recommended              |
| `just test-security-javascript`  | JavaScript  | ESLint, retire.js, Trivy, SBOM | ~3 min   | Node.js/JavaScript projects      |
| `just test-security-attestation` | Attestation | Ruff, SBOM, attestation        | ~30s     | SBOM + attestation validation    |

## Certus Assurance Tests

| Command               | Scope                       | Description                                                                                    |
| --------------------- | --------------------------- | ---------------------------------------------------------------------------------------------- |
| `just test-assurance` | Pipeline/API/storage + jobs | Runs the targeted `tests/certus_assurance/` suites (pipeline, API, storage, jobs) via `uv run` |

These tests cover the manifest fetch/verify workflow, log streaming surfaces, S3/registry upload adapters, and the
job manager contract. Use them whenever you modify Certus Assurance or the shared `security_module` integration. The
command expands to:

```bash
uv run pytest \
  tests/certus_assurance/test_pipeline.py \
  tests/certus_assurance/test_api.py \
  tests/certus_assurance/test_storage.py \
  tests/certus_assurance/test_jobs.py
```

All tests are hermetic (no Docker dependencies) and expect manifests/signatures to be stubbed by the fixtures.

## Test Categories by Marker

| Pytest Marker | Command                 | Count | Description                   |
| ------------- | ----------------------- | ----- | ----------------------------- |
| `smoke`       | `pytest -m smoke`       | ~12   | End-to-end Docker stack tests |
| `integration` | `pytest -m integration` | ~151  | Tests requiring Docker/moto   |
| `privacy`     | `pytest -m privacy`     | ~20   | Privacy-focused test cases    |
| `slow`        | `pytest -m slow`        | ~15   | Long-running tests            |
| (no marker)   | `pytest -m "not smoke"` | ~300  | Fast unit tests               |

## Test Structure by Directory

| Directory                         | Test Type   | Count | Mock/Real  | Description                              |
| --------------------------------- | ----------- | ----- | ---------- | ---------------------------------------- |
| `tests/test_services/`            | Unit        | ~100  | Mock       | Service layer (OpenSearch, S3, Presidio) |
| `tests/test_routers/`             | Integration | ~80   | TestClient | API endpoints and validation             |
| `tests/test_pipelines/`           | Unit        | ~60   | Mock       | Haystack pipeline components             |
| `tests/smoke/basics/`             | E2E         | ~3    | Real       | Golden bucket, ingestion, datalake       |
| `tests/smoke/provenance/`         | E2E         | ~3    | Real       | Attestations, security scans, trust      |
| `tests/smoke/security_workflows/` | E2E         | ~4    | Real       | Search workflows, Neo4j ingestion        |
| `tests/integration/`              | Integration | ~50   | Real       | Cross-service integration                |

## Smoke Test Suite Details

### Basics Suite (`tests/smoke/basics/`)

| Test                                 | File                             | Dependencies                  | Description                            |
| ------------------------------------ | -------------------------------- | ----------------------------- | -------------------------------------- |
| `test_golden_bucket_privacy_flow`    | `test_golden_bucket.py`          | LocalStack S3, OpenSearch     | Privacy pack ingestion and querying    |
| `test_ingestion_tutorial_end_to_end` | `test_ingestion_pipelines.py`    | Ask-Certus API, OpenSearch    | Single doc + folder ingestion tutorial |
| `test_sample_datalake_upload_flow`   | `test_sample_datalake_upload.py` | LocalStack S3, Ask-Certus API | S3 upload and indexing workflow        |

### Provenance Suite (`tests/smoke/provenance/`)

| Test                                 | File                                    | Dependencies                     | Description                                |
| ------------------------------------ | --------------------------------------- | -------------------------------- | ------------------------------------------ |
| `test_oci_attestations_workflow`     | `test_oci_attestations.py`              | OCI Registry, cosign, Ask-Certus | OCI attestation generation and signing     |
| `test_security_scan_with_provenance` | `test_security_scan_with_provenance.py` | Certus-Assurance                 | Security scanning with provenance tracking |
| `test_trust_verification_flow`       | `test_trust_verification.py`            | Certus-Trust, Certus-Assurance   | Trust verification workflow                |

### Security Workflows Suite (`tests/smoke/security_workflows/`)

| Test                              | File                            | Dependencies           | Description                        |
| --------------------------------- | ------------------------------- | ---------------------- | ---------------------------------- |
| `test_hybrid_search_workflow`     | `test_hybrid_search.py`         | OpenSearch, Neo4j      | Hybrid keyword + semantic search   |
| `test_keyword_search_workflow`    | `test_keyword_search.py`        | OpenSearch             | Deterministic keyword queries      |
| `test_neo4j_local_ingestion`      | `test_neo4j_local_ingestion.py` | Neo4j, Ask-Certus      | Local SARIF/SPDX → Neo4j ingestion |
| `test_semantic_search_embeddings` | `test_semantic_search.py`       | OpenSearch, Embeddings | Vector embedding validation        |

## Coverage Targets

| Component     | Target   | Current  | Status     |
| ------------- | -------- | -------- | ---------- |
| Service Layer | 85%+     | ~85%     | ✅ Met     |
| Routers/API   | 85%+     | ~85%     | ✅ Met     |
| Pipelines     | 80%+     | ~80%     | ✅ Met     |
| Edge Cases    | 80%+     | ~80%     | ✅ Met     |
| **Overall**   | **80%+** | **~82%** | ✅ **Met** |

## Preflight Testing

Preflight is a Docker stack health check that validates all services are running and accessible before running smoke tests.

### Preflight Checks

| Check              | Service                   | Validation                  | Description                 |
| ------------------ | ------------------------- | --------------------------- | --------------------------- |
| OpenSearch Health  | `opensearch:9200`         | Cluster status GREEN/YELLOW | Search engine availability  |
| Neo4j Connectivity | `neo4j:7687`              | Bolt protocol handshake     | Graph database connection   |
| LocalStack S3      | `localstack:4566`         | List buckets operation      | Object storage access       |
| Ask-Certus API     | `ask-certus-backend:8000` | `/health` endpoint          | Main API availability       |
| Certus-Assurance   | `certus-assurance:8000`   | `/health` endpoint          | Security scanning service   |
| Certus-Trust       | `certus-trust:8000`       | `/health` endpoint          | Trust verification service  |
| Certus-Transform   | `certus-transform:8100`   | `/health` endpoint          | Data transformation service |

### Preflight Workflow

```bash
# Run preflight checks
just preflight

# What it does:
# 1. Waits for all containers to be healthy
# 2. Validates service endpoints are responsive
# 3. Checks OpenSearch cluster health
# 4. Verifies Neo4j connectivity
# 5. Tests LocalStack S3 access
# 6. Validates API health endpoints
```

### Preflight vs Smoke Tests

| Aspect          | Preflight                           | Smoke Tests                    |
| --------------- | ----------------------------------- | ------------------------------ |
| **Purpose**     | Service health validation           | End-to-end workflow validation |
| **Depth**       | Connectivity checks                 | Full business logic testing    |
| **Duration**    | 2-3 min                             | 3-5 min                        |
| **When to Run** | After `just up`, before smoke tests | After preflight passes         |
| **Failures**    | Infrastructure/config issues        | Application logic bugs         |

## CI/CD Workflows

| Workflow            | Trigger          | Tests Run                   | Duration |
| ------------------- | ---------------- | --------------------------- | -------- |
| `test.yml`          | PR, Push to main | `pytest -m "not smoke"`     | 3-5 min  |
| `smoke-tests.yml`   | Nightly, Manual  | `pytest -m smoke`           | 5-10 min |
| `security-scan.yml` | PR, Push to main | Security profile (standard) | 8-10 min |

## Environment Variables

### Test Configuration

| Variable                | Default                       | Description                    |
| ----------------------- | ----------------------------- | ------------------------------ |
| `SMOKE_WORKSPACE`       | `smoke-ingestion-{timestamp}` | Workspace ID for smoke tests   |
| `SMOKE_REPO_ROOT`       | Auto-detected                 | Repository root path           |
| `SMOKE_SAMPLES_ROOT`    | `{REPO_ROOT}/samples`         | Sample files location          |
| `SMOKE_REQUEST_TIMEOUT` | `60`                          | HTTP request timeout (seconds) |

### Service Endpoints

| Variable                 | Container Default                      | Host Default                               | Description               |
| ------------------------ | -------------------------------------- | ------------------------------------------ | ------------------------- |
| `API_BASE`               | `http://ask-certus-backend:8000`       | `http://localhost:8000`                    | Ask-Certus API endpoint   |
| `OS_ENDPOINT`            | `http://opensearch:9200`               | `http://localhost:9200`                    | OpenSearch endpoint       |
| `LOCALSTACK_ENDPOINT`    | `http://localstack:4566`               | `http://localhost:4566`                    | LocalStack S3 endpoint    |
| `NEO4J_BOLT_URI`         | `neo4j://neo4j:7687`                   | `neo4j://localhost:7687`                   | Neo4j Bolt URI            |
| `NEO4J_HTTP_URL`         | `http://neo4j:7474/db/neo4j/tx/commit` | `http://localhost:7474/db/neo4j/tx/commit` | Neo4j HTTP endpoint       |
| `ASSURANCE_INTERNAL_URL` | `http://certus-assurance:8000`         | `http://localhost:8056`                    | Certus-Assurance endpoint |
| `TRUST_INTERNAL_URL`     | `http://certus-trust:8000`             | `http://localhost:8057`                    | Certus-Trust endpoint     |

## Fixture Reference

### Session-Scoped Fixtures

| Fixture           | Scope   | Type   | Description                  |
| ----------------- | ------- | ------ | ---------------------------- |
| `http_session`    | session | Real   | Reusable requests.Session    |
| `api_base`        | session | Config | Ask-Certus API base URL      |
| `os_endpoint`     | session | Config | OpenSearch endpoint URL      |
| `s3_client`       | session | Real   | Boto3 S3 client (LocalStack) |
| `workspace_id`    | session | Data   | Unique workspace identifier  |
| `wait_for_phrase` | session | Helper | Poll OpenSearch for phrase   |

### Function-Scoped Fixtures

| Fixture                  | Scope    | Type    | Description              |
| ------------------------ | -------- | ------- | ------------------------ |
| `mock_opensearch_client` | function | Mock    | Mocked OpenSearch client |
| `mock_s3_client`         | function | Mock    | Mocked boto3 S3 client   |
| `mock_presidio_analyzer` | function | Mock    | Mocked Presidio analyzer |
| `sample_document`        | function | Factory | Generate test documents  |

## Common Test Patterns

### Running Specific Tests

```bash
# Single test file
pytest tests/smoke/basics/test_golden_bucket.py

# Single test function
pytest tests/smoke/basics/test_golden_bucket.py::test_golden_bucket_privacy_flow

# By marker
pytest -m smoke
pytest -m "smoke and not slow"

# By keyword
pytest -k "ingestion"
pytest -k "test_hybrid or test_keyword"

# Verbose output
pytest -v tests/smoke/

# Show print statements
pytest -s tests/smoke/

# Stop on first failure
pytest -x tests/smoke/
```

### Coverage Reports

```bash
# Generate coverage report
just test

# HTML coverage report
pytest --cov --cov-report=html
open htmlcov/index.html

# Terminal coverage report
pytest --cov --cov-report=term-missing

# Coverage for specific module
pytest --cov=certus_ask/services tests/test_services/
```

## Troubleshooting

### Common Issues

| Issue                         | Solution                         |
| ----------------------------- | -------------------------------- |
| OpenSearch disk full          | `just destroy && just up`        |
| Tests timeout                 | Increase `SMOKE_REQUEST_TIMEOUT` |
| LocalStack connection refused | Check `docker compose ps`        |
| Import errors                 | Run `uv sync`                    |
| Stale test data               | `just destroy` to clear volumes  |

### Debug Commands

```bash
# Check Docker services
docker compose ps

# View service logs
docker compose logs ask-certus-backend --tail=50
docker compose logs opensearch --tail=50

# OpenSearch health
curl http://localhost:9200/_cluster/health

# List indices
curl http://localhost:9200/_cat/indices?v

# Clear read-only blocks
curl -X PUT "http://localhost:9200/*/_settings" -H 'Content-Type: application/json' -d'
{
  "index.blocks.read_only_allow_delete": null
}
'
```

## Best Practices

### Test Isolation

- ✅ Use unique workspace IDs per test
- ✅ Clean up resources in teardown
- ✅ Don't depend on test execution order
- ✅ Use fixtures for setup/teardown

### Performance

- ✅ Use session-scoped fixtures for expensive setup
- ✅ Mock external services in unit tests
- ✅ Mark slow tests with `@pytest.mark.slow`
- ✅ Run fast tests frequently, slow tests in CI

### Maintainability

- ✅ Keep tests focused on one behavior
- ✅ Use descriptive test names
- ✅ Document complex test scenarios
- ✅ Update tests when changing code

## Related Documentation

- [Testing Overview](overview.md) - Testing strategy and architecture
- [Fixtures Guide](fixtures.md) - Complete fixture catalog
- [Best Practices](best-practices.md) - Testing guidelines
- [Service Playbook](service-playbook.md) - Service and router testing patterns
- [Preflight Deep Dive](preflight-deep-dive.md) - Docker stack validation
- [Security Scanning](security-scanning.md) - SAST/DAST pipeline
