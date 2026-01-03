# Test Organization Guide

This document explains how tests are organized in the Certus-TAP repository and how to maintain this structure as services evolve toward separate repositories.

## Overview

Tests are organized **first by test type, then by service** to support both current monorepo development and future service separation.

```
certus-TAP/
│
├── certus_assurance/              # Service code
│   └── tests/                     # Service-owned tests
│       ├── unit/                  # Pure unit tests (no external deps)
│       ├── integration/           # Internal service integration tests
│       ├── smoke/                 # Service health and API tests
│       └── contract/              # API contract tests (expectations from other services)
│
├── certus_trust/                  # Service code
│   └── tests/                     # Service-owned tests
│       ├── unit/
│       ├── integration/
│       ├── smoke/
│       └── contract/
│
├── certus_ask/                    # Service code
│   └── tests/                     # Service-owned tests
│       └── ...
│
└── tests/                         # Cross-service tests ONLY
    ├── integration/               # Multi-service workflow tests
    │   └── workflows/
    │       ├── test_verify_trust_workflow.py
    │       └── test_basic_scan_workflow.py
    │
    ├── e2e/                       # End-to-end system tests (future)
    │
    └── conftest.py                # Shared fixtures
```

## Test Types Explained

### Unit Tests (`*/tests/unit/`)

**Purpose**: Test individual functions/classes in isolation

**Characteristics**:
- No external dependencies (databases, APIs, services)
- Fast (<1s per test)
- Mock all I/O operations
- Test business logic only

**Example**:
```python
# certus_trust/tests/unit/test_signature_validation.py
def test_verify_signature_valid():
    signature = "mock-signature-blob"
    public_key = "mock-public-key"
    payload = {"scan_id": "test"}

    result = verify_signature(signature, public_key, payload)

    assert result is True
```

**Run command**:
```bash
pytest certus_trust/tests/unit/ -v
```

---

### Integration Tests (`*/tests/integration/`)

**Purpose**: Test service internals with real dependencies

**Characteristics**:
- Uses real databases/queues but NOT other Certus services
- May use Docker containers for dependencies
- Tests service-internal workflows
- Slower (5-30s per test)

**Example**:
```python
# certus_trust/tests/integration/test_rekor_integration.py
def test_submit_to_rekor_transparency_log():
    # Uses real Rekor instance (Docker container)
    artifact_hash = "sha256:abc123"

    entry_uuid = submit_to_rekor(artifact_hash)

    # Verify in real Rekor
    assert entry_uuid is not None
    assert get_rekor_entry(entry_uuid)["hash"] == artifact_hash
```

**Run command**:
```bash
pytest certus_trust/tests/integration/ -v
```

---

### Smoke Tests (`*/tests/smoke/`)

**Purpose**: Quick health checks for service components

**Characteristics**:
- Fast (<5s per test)
- Validates service is running and responding
- Tests critical endpoints/functionality
- Uses mock data when possible
- Can run against local or deployed services

**Example**:
```python
# certus_trust/tests/smoke/test_health.py
def test_certus_trust_health():
    response = requests.get("http://localhost:8057/v1/health")

    assert response.status_code == 200
    assert response.json()["status"] in {"healthy", "ok"}
```

**Run command**:
```bash
pytest certus_trust/tests/smoke/ -v
```

---

### Contract Tests (`*/tests/contract/`)

**Purpose**: Validate API boundaries between services

**Characteristics**:
- Tests expectations, not implementations
- Validates request/response schemas
- Consumer-driven (service tests what IT expects from others)
- Prevents breaking changes
- Can use Pact, OpenAPI, or schema validation

**Example**:
```python
# certus_assurance/tests/contract/test_trust_api.py
def test_trust_verify_endpoint_accepts_our_request():
    """Verify Trust API accepts the request format we send."""

    # This is what Assurance sends to Trust
    our_request = {
        "scan_id": "scan_123",
        "tier": "verified",
        "inner_signature": {...}
    }

    # Validate schema (not actual request)
    assert validate_schema(our_request, TRUST_VERIFY_SCHEMA)

    # If this fails, either:
    # - We're sending wrong format (our bug)
    # - Trust changed API (breaking change)
```

**Run command**:
```bash
pytest certus_assurance/tests/contract/ -v
```

---

### Workflow Tests (`tests/integration/workflows/`)

**Purpose**: Test complete workflows across multiple services

**Characteristics**:
- Requires multiple Certus services running
- Tests end-to-end user journeys
- Maps to tutorial/documentation flows
- Slowest tests (30s-2min)
- Lives in root `tests/` (cross-service)

**Example**:
```python
# tests/integration/workflows/test_verify_trust_workflow.py
def test_complete_scan_to_verification_workflow():
    # Step 1: Submit scan to Assurance
    scan_id = submit_scan_to_assurance(...)

    # Step 2: Request verification from Trust
    permission = request_upload_permission(scan_id)

    # Step 3: Upload to S3 via Transform
    upload_result = upload_artifacts(permission)

    # Step 4: Query from Ask
    findings = query_findings(scan_id)

    assert len(findings) > 0
```

**Run command**:
```bash
pytest tests/integration/workflows/ -v
```

---

## Test Markers

Use pytest markers to categorize and run specific test types:

```python
import pytest

pytestmark = pytest.mark.smoke           # All tests in this file are smoke tests
pytestmark = [pytest.mark.integration, pytest.mark.slow]  # Multiple markers
```

### Available Markers

| Marker | Purpose | Example |
|--------|---------|---------|
| `@pytest.mark.smoke` | Quick health checks | Service availability |
| `@pytest.mark.integration` | Multi-service tests | Workflow validation |
| `@pytest.mark.slow` | Tests >30s | End-to-end workflows |
| `@pytest.mark.contract` | API boundary tests | Schema validation |
| `@pytest.mark.privacy` | PII/privacy tests | Presidio anonymization |

### Running Tests by Marker

```bash
# Run only smoke tests
pytest -m smoke -v

# Run integration tests
pytest -m integration -v

# Run smoke tests, skip slow tests
pytest -m "smoke and not slow" -v

# Run all contract tests across all services
pytest -m contract -v
```

---

## Migration Path: Monorepo → Separate Repos

### Phase 1: Current Monorepo (Now)

```
certus-TAP/
├── certus_trust/tests/          # Trust-owned tests
├── certus_assurance/tests/      # Assurance-owned tests
└── tests/integration/workflows/ # Cross-service tests
```

**When services split**:
1. Service tests move with service code
2. Cross-service tests move to `certus-system-tests` repo

### Phase 2: After Repo Split (Future)

```
certus-trust/                    # Separate repo
└── tests/
    ├── unit/
    ├── integration/
    ├── smoke/
    └── contract/

certus-assurance/                # Separate repo
└── tests/
    └── ...

certus-system-tests/             # New repo
└── tests/
    ├── integration/workflows/   # Moved from certus-TAP/tests/
    └── e2e/
```

**Benefits**:
- Each service owns and runs its own tests
- Contract tests prevent breaking changes
- System tests validate complete platform
- Clear ownership boundaries

---

## Running Tests

### By Service

```bash
# All Trust tests
pytest certus_trust/tests/ -v

# All Assurance tests
pytest certus_assurance/tests/ -v

# All Ask tests
pytest certus_ask/tests/ -v
```

### By Test Type

```bash
# All smoke tests (fast)
pytest -m smoke -v

# All unit tests across all services
pytest */tests/unit/ -v

# All integration tests (requires Docker)
pytest */tests/integration/ -v
pytest tests/integration/ -v
```

### By Service + Test Type

```bash
# Trust smoke tests only
pytest certus_trust/tests/smoke/ -v

# Assurance contract tests only
pytest certus_assurance/tests/contract/ -v

# Ask integration tests only
pytest certus_ask/tests/integration/ -v
```

### Fast Feedback Loop (Development)

```bash
# Quick validation (unit + smoke)
pytest */tests/unit/ */tests/smoke/ -v

# Full validation (everything)
pytest tests/ certus_*/tests/ -v
```

---

## Adding New Tests

### 1. Determine Test Type

Ask yourself:
- **Does it test a single function/class?** → Unit test
- **Does it test service internals with real deps?** → Integration test
- **Is it a quick health check?** → Smoke test
- **Does it validate API contract?** → Contract test
- **Does it test multiple services together?** → Workflow test (root `tests/`)

### 2. Place in Correct Directory

```python
# Testing Trust's signature validation logic
certus_trust/tests/unit/test_signature_utils.py

# Testing Trust's Rekor integration
certus_trust/tests/integration/test_rekor_submission.py

# Testing Trust's health endpoint
certus_trust/tests/smoke/test_health.py

# Testing what Assurance expects from Trust API
certus_assurance/tests/contract/test_trust_api.py

# Testing Assurance → Trust → Transform workflow
tests/integration/workflows/test_scan_to_upload_workflow.py
```

### 3. Add Appropriate Markers

```python
import pytest

pytestmark = pytest.mark.smoke  # For smoke tests
pytestmark = [pytest.mark.integration, pytest.mark.slow]  # For integration tests
pytestmark = pytest.mark.contract  # For contract tests
```

### 4. Use Shared Fixtures

Leverage fixtures from `tests/conftest.py`:

```python
def test_my_feature(http_session, request_timeout):
    """Use shared fixtures instead of creating new ones."""
    response = http_session.get(
        "http://localhost:8057/v1/health",
        timeout=request_timeout
    )
    assert response.status_code == 200
```

---

## Legacy Tests

Some tests from before the reorganization remain in `tests/smoke/security_workflows/`:

```
tests/smoke/security_workflows/
└── test_certus_trust_scans.py       # Original monolithic test file
```

**Migration strategy**:
- Keep existing tests for backward compatibility
- New tests go in service directories
- Gradually migrate old tests as they're updated

---

## Test Execution in CI/CD

### Recommended Pipeline Stages

```yaml
# .github/workflows/test.yml (example)

stages:
  - unit-tests:           # Fast, no Docker required
      pytest */tests/unit/ -v

  - smoke-tests:          # Quick, requires services
      just up
      pytest */tests/smoke/ -m smoke -v

  - integration-tests:    # Slower, full stack
      just up
      pytest */tests/integration/ -m integration -v
      pytest tests/integration/ -m integration -v

  - contract-tests:       # API boundary validation
      pytest */tests/contract/ -m contract -v
```

### Service-Level CI

When services split into separate repos, each runs:

```bash
# In certus-trust repo
pytest certus_trust/tests/unit/ -v
pytest certus_trust/tests/smoke/ -v
pytest certus_trust/tests/contract/ -v
```

---

## Quick Reference

| Test Location | What It Tests | Dependencies | Speed |
|--------------|---------------|--------------|-------|
| `*/tests/unit/` | Function/class logic | None (mocked) | <1s |
| `*/tests/integration/` | Service internals | Real DB/queue, no other services | 5-30s |
| `*/tests/smoke/` | Service health | Service running | <5s |
| `*/tests/contract/` | API schemas | None (schema validation) | <1s |
| `tests/integration/workflows/` | Multi-service flows | All services | 30s-2min |

## Common Commands

```bash
# Fast local validation
pytest */tests/unit/ */tests/smoke/ -v

# Full service test suite
pytest certus_trust/tests/ -v

# All contract tests
pytest -m contract -v

# Cross-service workflows
pytest tests/integration/workflows/ -v

# Everything
pytest --co  # List all tests
pytest -v    # Run all tests
```

---

## Questions?

- **Where do I put tests for a new feature?** → In the service directory under the appropriate test type
- **How do I test interaction between services?** → `tests/integration/workflows/`
- **How do I prevent breaking API changes?** → Contract tests in `*/tests/contract/`
- **Can I run tests without Docker?** → Yes: `pytest */tests/unit/ -v`
- **How do I run only fast tests?** → `pytest -m "smoke and not slow" -v`

For more examples, see existing test files in each service directory.
