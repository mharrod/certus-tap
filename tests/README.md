# Testing Guide for Certus-TAP

Complete guide for writing, running, and maintaining tests in Certus-TAP.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Test Structure](#test-structure)
3. [Running Tests](#running-tests)
4. [Writing Tests](#writing-tests)
5. [Using Fixtures](#using-fixtures)
6. [Mocking Patterns](#mocking-patterns)
7. [Docker Integration Tests](#docker-integration-tests)
8. [Coverage Goals](#coverage-goals)
9. [CI/CD Integration](#cicd-integration)
10. [Troubleshooting](#troubleshooting)

## Quick Start

### Install Test Dependencies

```bash
# Using uv
uv sync --group dev

# Or pip
pip install pytest pytest-asyncio pytest-mock moto testcontainers faker
```

### Run All Tests

```bash
# Run all tests with coverage
just test

# Fast unit/integration selection
just test-fast

# Smoke suites (Docker stack required)
just test-smoke

# Tutorial suites
just test-tutorial

# Security scans (Dagger module with 5 profiles)
just test-security-smoke      # Quick toolchain check (~20 sec)
just test-security-fast       # Pre-commit scan (~2 min)
just test-security-medium     # Pre-push scan (~4 min)
just test-security-standard   # CI/PR gate (~8 min)
just test-security-full       # Release gate (~12 min)

# Run specific test file/class
uv run python -m pytest tests/test_services/test_presidio_example.py::TestPresidioAnalyzer
```

### Run Different Test Categories

```bash
# Run only fast tests (skip slow)
uv run python -m pytest -m "not slow"

uv run python -m pytest -m privacy

uv run python -m pytest -m integration

# Run end-to-end smoke suites (require Docker + LocalStack)
uv run python -m pytest -m smoke

# Skip smoke suites (default for pull requests)
uv run python -m pytest -m "not smoke"

# Run published tutorial walkthroughs
uv run python -m pytest -m tutorial

# Run unit tests only (exclude integration)
uv run python -m pytest -m "not integration"
```

## Environment & Sample Setup

- **Service URLs:** Test fixtures automatically prefer docker-network hosts (e.g., `ask-certus-backend`) when resolvable; otherwise they fall back to `localhost` ports. Override via `API_BASE`, `OS_ENDPOINT`, `LOCALSTACK_ENDPOINT`, `NEO4J_BOLT_URI`, `ASSURANCE_INTERNAL_URL`, etc., to target specific deployments.
- **Sample Paths:** Smoke fixtures default to the repository `samples/` tree. Override with `SMOKE_REPO_ROOT` or `SMOKE_SAMPLES_ROOT` if you relocate the sample data.
- **LocalStack Seeding:** A session-scoped autouse fixture now uploads the datalake and privacy sample bundles to LocalStack S3 before smoke tests run, so `just test-fast` no longer requires manual `just datalake-upload-samples`.
- **Bucket Creation:** `raw` and `golden` buckets are created on demand when missing; set `SMOKE_RAW_BUCKET`/`SMOKE_GOLDEN_BUCKET` to test alternate prefixes.

## Test Structure

### Directory Organization

```
tests/
├── conftest.py                    # Shared fixtures
├── README.md                      # This file
│
├── test_services/                 # Service layer tests
│   ├── test_opensearch.py
│   ├── test_presidio_example.py   # Example with fixtures
│   ├── test_s3.py
│   └── test_privacy_logger.py
│
├── test_routers/                  # Route handler tests
│   ├── test_ingestion.py
│   ├── test_query.py
│   ├── test_health.py
│   └── test_datalake.py
│
├── test_pipelines/                # Pipeline processing tests
│   ├── test_preprocessing.py
│   ├── test_rag.py
│   └── test_sarif.py
│
├── test_edge_cases.py             # Edge cases and error scenarios
│
├── test_integration/              # Full-stack integration tests
│   ├── test_full_stack.py
│   └── test_resilience.py
│
└── test_performance/              # Performance benchmarks
    └── test_benchmarks.py
```

### File Naming Convention

- Test files: `test_*.py` (required by pytest discovery)
- Test classes: `Test*` (e.g., `TestPresidioAnalyzer`)
- Test methods: `test_*` (e.g., `test_analyze_clean_document`)

### Test Class Organization

Group related tests into classes for organization:

```python
class TestPresidioAnalyzer:
    """Tests for Presidio analyzer functionality."""

    def test_simple_case(self):
        """One assertion per test for clarity."""
        pass

    def test_complex_case(self):
        """Can have multiple assertions if logically related."""
        pass


class TestPresidioAnonymizer:
    """Tests for Presidio anonymizer functionality."""
    pass
```

## Running Tests

### Basic Commands

```bash
# Run all tests
uv run python -m pytest

# Run with verbose output showing each test
uv run python -m pytest -v

# Run with very verbose output (show print statements)
uv run python -m pytest -vv

# Show local variables on failure
uv run python -m pytest -l

# Stop on first failure
uv run python -m pytest -x

# Stop after N failures
uv run python -m pytest --maxfail=3

# Show top 10 slowest tests
uv run python -m pytest --durations=10
```

### Filtering Tests

```bash
# Run tests matching pattern
uv run python -m pytest -k "test_analyze"

# Run tests in specific file
uv run python -m pytest tests/test_services/test_presidio_example.py

# Run tests in specific class
uv run python -m pytest tests/test_services/test_presidio_example.py::TestPresidioAnalyzer

# Run specific test
uv run python -m pytest tests/test_services/test_presidio_example.py::TestPresidioAnalyzer::test_analyze_clean_document

# Run with markers
pytest -m privacy                # Only privacy tests
pytest -m "not slow"             # Skip slow tests
pytest -m "privacy and not slow" # Privacy tests that aren't slow
```

### Coverage Reports

```bash
# Generate coverage report
uv run python -m pytest --cov=certus_ask --cov-report=html

# View HTML report
open htmlcov/index.html

# Show coverage in terminal
uv run python -m pytest --cov=certus_ask

# Coverage for specific module
uv run python -m pytest --cov=certus_ask.services --cov-report=term-missing
```

### Parallel Testing

```bash
# Install pytest-xdist
pip install pytest-xdist

# Run tests in parallel
pytest -n auto           # Use all CPU cores
pytest -n 4             # Use 4 processes
```

## Writing Tests

### Basic Test Structure

```python
import pytest

class TestMyFeature:
    """Test class for my feature."""

    def test_happy_path(self):
        """Test the normal/happy path."""
        # Arrange
        input_data = "test"

        # Act
        result = my_function(input_data)

        # Assert
        assert result == "expected"

    def test_error_case(self):
        """Test error handling."""
        with pytest.raises(ValueError):
            my_function(None)
```

### Test Naming

Good test names describe **what** is being tested and **what** the expected result is:

```python
# ✅ Good
def test_analyze_clean_document_returns_empty_list():
    pass

def test_anonymize_with_high_confidence_excludes_low_confidence():
    pass

def test_upload_missing_file_raises_file_not_found():
    pass

# ❌ Bad
def test_analyze():
    pass

def test_it_works():
    pass

def test_error():
    pass
```

### One Assertion per Test

Keep tests focused:

```python
# ✅ Good - one logical assertion
def test_document_creation():
    doc = create_document("test")
    assert doc is not None
    assert doc.id > 0
    assert doc.created_at is not None  # All related to document creation

# ❌ Not ideal - testing multiple unrelated things
def test_everything():
    doc = create_document("test")
    assert doc is not None

    user = create_user("test")
    assert user is not None

    result = search(doc)
    assert result is not None
```

### Test Docstrings

Include docstrings explaining the test:

```python
def test_analyze_document_with_pii(self, sample_text_with_pii):
    """
    Test that Presidio analyzer detects PII in documents.

    Given a document containing personal information,
    When analyzing with Presidio,
    Then should return non-empty results.
    """
    # Test code
```

## Using Fixtures

### What are Fixtures?

Fixtures are reusable pieces of test setup/data. They're defined in `conftest.py`:

```python
@pytest.fixture
def sample_document():
    """Reusable sample document."""
    return "Sample document text"
```

Then used in tests by adding as parameter:

```python
def test_something(sample_document):
    assert len(sample_document) > 0
```

### Available Fixtures

#### Document Fixtures

```python
def test_with_clean_doc(sample_clean_document):
    """Test with document that has no PII."""
    assert "Social Security" not in sample_clean_document

def test_with_pii_doc(sample_text_with_pii):
    """Test with document containing PII."""
    assert "@example.com" in sample_text_with_pii

def test_with_text(sample_text_document):
    """Test with general text document."""
    pass

def test_with_markdown(sample_markdown_document):
    """Test with markdown format."""
    pass

def test_with_pdf(sample_pdf_document):
    """Test with PDF binary."""
    pass
```

#### AWS/S3 Fixtures

```python
def test_s3_operations(s3_with_buckets):
    """S3 client with pre-created buckets."""
    s3_with_buckets.put_object(
        Bucket="raw-bucket",
        Key="test.txt",
        Body=b"content"
    )

def test_with_documents(s3_with_documents):
    """S3 with sample documents pre-loaded."""
    response = s3_with_documents.get_object(
        Bucket="raw-bucket",
        Key="input/sample.txt"
    )
```

#### Service Fixtures

```python
def test_presidio_analysis(presidio_analyzer):
    """Test with Presidio analyzer."""
    results = presidio_analyzer.analyze(text="test")

def test_anonymization(presidio_anonymizer):
    """Test with Presidio anonymizer."""
    pass

def test_privacy_logging(privacy_logger):
    """Test with privacy logger."""
    incident = privacy_logger.log_pii_detection(...)
```

#### FastAPI Fixtures

```python
def test_endpoint(test_client):
    """Test endpoint with TestClient."""
    response = test_client.get("/v1/health")
    assert response.status_code == 200

@pytest.mark.asyncio
async def test_async_endpoint(async_client):
    """Test async endpoint."""
    async with async_client as client:
        response = await client.get("/v1/health")
```

#### Factory Fixtures

```python
def test_document_creation(document_factory):
    """Create test documents dynamically."""
    single = document_factory.create(content="test")
    batch = document_factory.create_batch(count=10)

def test_analysis_results(analysis_result_factory):
    """Create mock analysis results."""
    single = analysis_result_factory.create(entity_type="EMAIL")
    batch = analysis_result_factory.create_batch(count=5)
```

### Creating Custom Fixtures

Add to `tests/conftest.py`:

```python
@pytest.fixture
def my_custom_fixture():
    """Description of fixture."""
    # Setup
    data = setup_something()

    yield data  # Provide to test

    # Cleanup
    teardown_something()
```

Using in test:

```python
def test_with_custom(my_custom_fixture):
    assert my_custom_fixture is not None
```

### Fixture Scope

```python
@pytest.fixture(scope="function")  # Default: new instance per test
def per_test():
    pass

@pytest.fixture(scope="class")     # Same instance for whole class
def per_class():
    pass

@pytest.fixture(scope="module")    # Same instance for whole module
def per_module():
    pass

@pytest.fixture(scope="session")   # Same instance for whole test session
def per_session():
    pass
```

## Mocking Patterns

### Mock Simple Return Values

```python
from unittest.mock import MagicMock, patch

def test_with_mock(mocker):
    """Mock using pytest-mock."""
    mock_client = mocker.patch("module.Client")
    mock_client.search.return_value = {"results": []}

    # Use mock_client in test
```

### Mock Entire Module

```python
def test_with_patched_module():
    """Patch entire module."""
    with patch("certus_ask.services.opensearch.OpenSearch") as mock_os:
        mock_os.return_value.search.return_value = {}
        # Test code
```

### Mock Context Manager

```python
def test_s3_upload(mock_s3_client):
    """Test using mocked S3 from fixture."""
    # mock_s3_client is already mocked via moto
    mock_s3_client.put_object(Bucket="test", Key="test", Body=b"data")
```

### Mock with Side Effects

```python
def test_retry_logic(mocker):
    """Test with side effects (failures then success)."""
    mock_func = mocker.MagicMock()
    mock_func.side_effect = [
        ConnectionError("failed"),
        ConnectionError("failed"),
        {"status": "success"}  # Success on third try
    ]

    # Test retry logic
```

## Docker Integration Tests

### Running Integration Tests

```bash
# Run all tests including Docker-based integration tests
pytest -m integration

# Run only integration tests
pytest tests/test_integration/

# Run integration tests with verbose output
pytest -m integration -v
```

### Writing Integration Tests

```python
import pytest

@pytest.mark.integration
class TestFullStackIntegration:
    """Tests requiring real services (Docker containers)."""

    def test_upload_to_opensearch(self, opensearch_container, s3_container):
        """Test real upload flow."""
        # This test requires:
        # 1. OpenSearch container running (opensearch_container fixture)
        # 2. S3 container running (s3_container fixture)
        pass
```

### Container Setup

Fixtures for containers are in `tests/conftest.py`:

```python
@pytest.fixture(scope="session")
def opensearch_container():
    """Start OpenSearch container for testing."""
    # testcontainers automatically handles start/stop
    pass
```

## Security Testing

### Security Scanning via Dagger Module

The project uses a dedicated Dagger security module (`dagger_modules/security`) that provides 5 profiles for different stages of development:

| Profile    | Duration | Tools                            | When to Run            |
| ---------- | -------- | -------------------------------- | ---------------------- |
| `smoke`    | ~20 sec  | Ruff                             | CI health check        |
| `fast`     | ~2 min   | Ruff + Bandit + detect-secrets   | Pre-commit hook        |
| `medium`   | ~4 min   | fast + Opengrep (Semgrep rules)  | Pre-push check         |
| `standard` | ~8 min   | medium + Trivy (vulnerabilities) | **PR gate (required)** |
| `full`     | ~12 min  | standard + privacy detection     | Release/main merge     |

### Running Security Scans

```bash
# Quick pre-commit scan
just test-security-fast

# Pre-push sanity check
just test-security-medium

# Full CI scan (runs automatically on PRs)
just test-security-standard

# Comprehensive release scan
just test-security-full
```

### Security Scan Outputs

Results are stored in `build/security-results/<bundle_id>/`:

```
build/security-results/
├── 20251209-204606-cfe67f6/    # Timestamped bundle
│   ├── ruff.txt                # Linting issues
│   ├── bandit.json             # Python security issues
│   ├── detect-secrets.json     # Detected secrets
│   ├── opengrep.sarif.json     # Pattern-based findings
│   ├── trivy.sarif.json        # Vulnerabilities
│   ├── privacy-findings.json   # PII detections
│   └── summary.json            # Tool versions + metadata
└── latest -> 20251209-204606-cfe67f6/
```

### Customizing Scans

To exclude large directories (ML models, datasets, custom venvs):

1. Edit `dagger_modules/security/security_module/constants.py`
2. Add patterns to the `EXCLUDES` list
3. Run scans as normal

See [Security Scanning Reference](../docs/reference/testing/security-scanning.md) for detailed documentation.

## Coverage Goals

### Current Targets

| Component  | Target |
| ---------- | ------ |
| Services   | 85%+   |
| Routers    | 85%+   |
| Pipelines  | 85%+   |
| Edge Cases | 80%+   |
| Overall    | 80%+   |

### Checking Coverage

```bash
# Generate coverage report
pytest --cov=certus_ask --cov-report=html

# View missing lines
pytest --cov=certus_ask --cov-report=term-missing

# Coverage for specific module
pytest --cov=certus_ask.services --cov-report=term-missing
```

### Coverage-Driven Development

1. **Write test first** - TDD approach
2. **Run test** - Should fail
3. **Write minimal code** - Make test pass
4. **Check coverage** - Identify untested paths
5. **Add more tests** - Cover edge cases
6. **Refactor** - Improve code quality

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -e ".[dev]"

      - name: Run tests
        run: pytest --cov=certus_ask

      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

### Pre-commit Hooks

Add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: pytest
      name: pytest
      entry: pytest
      language: system
      types: [python]
      stages: [commit]
```

## Troubleshooting

### Common Issues

#### "pytest: command not found"

```bash
# Install pytest
pip install pytest

# Or reinstall environment
uv sync --group dev
```

#### "ModuleNotFoundError" in Tests

```bash
# Ensure tests can find modules
export PYTHONPATH=$(pwd):$PYTHONPATH
pytest

# Or add to conftest.py (already done)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
```

#### Fixture Not Found

```bash
# Check fixture is in conftest.py
# Or imported in test file
# Or use full path: tests.conftest.my_fixture
```

#### Async Test Failures

```python
# Make sure to mark async tests
@pytest.mark.asyncio
async def test_async_function():
    pass

# Use async fixtures correctly
@pytest.fixture
async def async_fixture():
    yield value
```

#### Mock Not Working

```python
# Patch where it's USED, not where it's defined
# Wrong:
with patch("certus_ask.services.opensearch.OpenSearch"):
    pass

# Correct:
with patch("certus_ask.routers.ingestion.get_opensearch_client"):
    pass
```

### Debug Mode

```bash
# Drop into debugger on failure
pytest --pdb

# Print detailed failure info
pytest -vv --tb=long

# Show print statements
pytest -s

# Show test setup/teardown
pytest --setup-show
```

### Performance Issues

```bash
# Profile slow tests
pytest --durations=10

# Run tests in parallel
pytest -n auto

# Skip slow tests during development
pytest -m "not slow"
```

## Best Practices

### ✅ Do

- ✅ One logical assertion per test
- ✅ Use descriptive test names
- ✅ Use fixtures to avoid duplication
- ✅ Test both happy path and error cases
- ✅ Mock external dependencies
- ✅ Keep tests focused and fast
- ✅ Use markers for test categorization
- ✅ Test edge cases (empty, None, very large)

### ❌ Don't

- ❌ Don't test implementation details
- ❌ Don't use hardcoded paths
- ❌ Don't depend on test execution order
- ❌ Don't sleep in tests (use mocks instead)
- ❌ Don't make real network calls
- ❌ Don't create files on disk (use fixtures)
- ❌ Don't write tests that modify each other's state
- ❌ Don't test third-party libraries

## Additional Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-mock](https://pytest-mock.readthedocs.io/)
- [moto Documentation](https://docs.getmoto.org/)
- [testcontainers-python](https://testcontainers-python.readthedocs.io/)
