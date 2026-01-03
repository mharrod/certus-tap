# Testing Service Layer Code

This guide explains how to write effective tests for the service layer in Certus Ask.

## Overview

The service layer architecture enables clear separation between unit tests (service logic) and integration tests (HTTP/router layer). This guide covers both approaches.

## Test Structure

```
tests/
├── test_services/
│   └── test_ingestion/
│       ├── test_file_processor.py       # Unit tests for FileProcessor
│       ├── test_security_processor.py   # Unit tests for SecurityProcessor
│       ├── test_neo4j_service.py        # Unit tests for Neo4jService
│       └── test_storage_service.py      # Unit tests for StorageService
└── test_routers/
    └── test_ingestion_router.py         # Integration tests for HTTP layer
```

## Unit Testing Services

Unit tests focus on service business logic in isolation, using mocks for dependencies.

### Basic Unit Test Pattern

```python
"""Tests for MyService."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from certus_ask.services.ingestion import MyService


class TestMyService:
    """Test suite for MyService."""

    @pytest.fixture
    def mock_dependency(self):
        """Create mock dependency."""
        mock = Mock()
        mock.do_something.return_value = "expected_result"
        return mock

    @pytest.fixture
    def service(self, mock_dependency):
        """Create service instance with mocked dependencies."""
        return MyService(dependency=mock_dependency)

    async def test_process_success(self, service, mock_dependency):
        """Test successful processing with valid input."""
        # Arrange
        input_data = {"key": "value"}

        # Act
        result = await service.process(input_data)

        # Assert
        assert result["status"] == "success"
        assert result["data"] is not None
        mock_dependency.do_something.assert_called_once_with("value")

    async def test_process_handles_invalid_input(self, service):
        """Test error handling for invalid input."""
        # Arrange
        invalid_input = {}

        # Act & Assert
        with pytest.raises(ValidationError) as exc_info:
            await service.process(invalid_input)

        assert exc_info.value.error_code == "invalid_input"
        assert "key" in str(exc_info.value)
```

### Testing Async Operations

Use `pytest-asyncio` for testing async service methods:

```python
import pytest


class TestAsyncService:
    """Tests for async service operations."""

    @pytest.mark.asyncio
    async def test_async_operation(self):
        """Test async service method."""
        service = MyService()

        result = await service.async_method()

        assert result is not None

    async def test_async_with_mock(self, service):
        """Test async method with mocked async dependency."""
        # Create async mock
        mock_client = AsyncMock()
        mock_client.fetch_data.return_value = {"data": "value"}

        service.client = mock_client

        result = await service.process_data()

        assert result["data"] == "value"
        mock_client.fetch_data.assert_awaited_once()
```

### Mocking External Dependencies

#### Mocking S3 Client

```python
import pytest
from botocore.exceptions import ClientError


@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing."""
    mock = Mock()
    mock.get_object.return_value = {
        "Body": Mock(read=Mock(return_value=b"file content"))
    }
    return mock


async def test_file_download(service, mock_s3_client):
    """Test file download from S3."""
    service.s3_client = mock_s3_client

    content = await service.download_file("bucket", "key")

    assert content == b"file content"
    mock_s3_client.get_object.assert_called_once_with(
        Bucket="bucket",
        Key="key"
    )


async def test_file_download_not_found(service, mock_s3_client):
    """Test handling of missing file."""
    error = ClientError(
        {"Error": {"Code": "NoSuchKey"}},
        "GetObject"
    )
    mock_s3_client.get_object.side_effect = error

    with pytest.raises(FileNotFoundError):
        await service.download_file("bucket", "missing")
```

#### Mocking Neo4j Service

```python
@pytest.fixture
def mock_neo4j_service():
    """Mock Neo4j service."""
    mock = Mock()
    mock.load_sarif.return_value = "scan-123"
    mock.load_spdx.return_value = "sbom-456"
    return mock


async def test_security_processing_with_neo4j(mock_neo4j_service):
    """Test security processing with Neo4j enabled."""
    processor = SecurityProcessor(neo4j_service=mock_neo4j_service)

    result = await processor.process(
        file_bytes=b"sarif content",
        format="sarif",
        # ... other params
    )

    assert result["neo4j_scan_id"] == "scan-123"
    mock_neo4j_service.load_sarif.assert_called_once()
```

#### Mocking Trust Client

```python
@pytest.fixture
def mock_trust_client():
    """Mock trust verification client."""
    mock = AsyncMock()
    mock.verify_signatures.return_value = {
        "verified": True,
        "trust_level": "high",
    }
    return mock


async def test_premium_verification(mock_trust_client):
    """Test premium tier trust verification."""
    processor = SecurityProcessor(trust_client=mock_trust_client)

    result = await processor.verify_trust_chain(
        signatures={"sig": "data"},
        artifact_locations={"s3": [...]},
    )

    assert result["verified"] is True
    mock_trust_client.verify_signatures.assert_awaited_once()
```

### Testing Error Paths

Always test error handling:

```python
from certus_ask.core.exceptions import (
    DocumentParseError,
    ValidationError,
)


class TestErrorHandling:
    """Test error handling in services."""

    async def test_invalid_format_raises_error(self, service):
        """Test that invalid format raises appropriate error."""
        with pytest.raises(DocumentParseError) as exc_info:
            await service.process(
                file_bytes=b"invalid",
                format="unknown_format",
            )

        assert exc_info.value.error_code == "unknown_format"

    async def test_missing_required_field(self, service):
        """Test validation of required fields."""
        with pytest.raises(ValidationError) as exc_info:
            await service.process(data={})  # Missing required fields

        assert "required" in str(exc_info.value).lower()

    async def test_dependency_failure_propagates(self, service):
        """Test that dependency failures propagate correctly."""
        service.dependency.method.side_effect = RuntimeError("Dep failed")

        with pytest.raises(RuntimeError) as exc_info:
            await service.process(data={"key": "value"})

        assert "Dep failed" in str(exc_info.value)
```

## Integration Testing Routers

Integration tests verify that routers correctly delegate to services and handle HTTP concerns.

### Router Test Pattern

```python
"""Integration tests for ingestion router."""

import pytest
from fastapi.testclient import TestClient


class TestIngestionRouter:
    """Integration tests for /v1/{workspace_id}/index/ endpoints."""

    def test_index_document_success(self, test_client, fake_preprocessing_pipeline):
        """Test successful document upload and indexing."""
        # Arrange
        file_content = b"test document content"

        # Act
        response = test_client.post(
            "/v1/demo/index/",
            files={"uploaded_file": ("test.txt", file_content, "text/plain")},
        )

        # Assert
        assert response.status_code == 200
        payload = response.json()
        assert payload["message"].startswith("Indexed document")
        assert "ingestion_id" in payload
        assert payload["document_count"] > 0

    def test_index_document_file_too_large(self, test_client, monkeypatch):
        """Test rejection of files exceeding size limit."""
        # Arrange
        monkeypatch.setattr("certus_ask.routers.ingestion.MAX_UPLOAD_SIZE_BYTES", 1)

        # Act
        response = test_client.post(
            "/v1/demo/index/",
            files={"uploaded_file": ("large.txt", b"too big", "text/plain")},
        )

        # Assert
        assert response.status_code == 400
        assert "exceeds maximum size" in response.json()["detail"]
```

### Mocking Services in Router Tests

When testing routers, mock the service layer:

```python
@pytest.fixture
def mock_file_processor(monkeypatch):
    """Mock FileProcessor for router tests."""
    mock = AsyncMock()
    mock.process_file.return_value = {
        "documents_written": 5,
        "metadata_preview": [{"id": "1"}],
        "quarantined": [],
    }

    # Patch the service class
    monkeypatch.setattr(
        "certus_ask.routers.ingestion.FileProcessor",
        lambda **kwargs: mock
    )
    return mock


def test_endpoint_uses_service(test_client, mock_file_processor):
    """Test that router delegates to service."""
    response = test_client.post(
        "/v1/demo/index/",
        files={"uploaded_file": ("test.txt", b"content", "text/plain")},
    )

    assert response.status_code == 200
    mock_file_processor.process_file.assert_called_once()
```

### Testing HTTP Error Responses

```python
def test_validation_error_returns_400(test_client):
    """Test that validation errors return 400 Bad Request."""
    response = test_client.post(
        "/v1/demo/index/security",
        json={},  # Missing required fields
    )

    assert response.status_code == 400
    error = response.json()
    assert error["error_code"] == "validation_failed"


def test_internal_error_returns_500(test_client, mock_service):
    """Test that internal errors return 500."""
    mock_service.process.side_effect = RuntimeError("Internal error")

    response = test_client.post("/v1/demo/index/", ...)

    assert response.status_code == 500
```

## Testing Utilities

Utilities in `certus_ask/services/ingestion/utils.py` should have their own unit tests:

```python
"""Tests for ingestion utilities."""

from certus_ask.services.ingestion import (
    compute_sha256_digest,
    extract_filename_from_source,
    match_expected_digest,
)


class TestUtilities:
    """Test utility functions."""

    def test_compute_sha256_digest(self):
        """Test SHA256 digest computation."""
        payload = b"test data"

        digest = compute_sha256_digest(payload)

        assert digest.startswith("sha256:")
        assert len(digest) == 71  # sha256: + 64 hex chars

    def test_extract_filename_from_s3_path(self):
        """Test filename extraction from S3 path."""
        s3_path = "reports/security/scan.sarif"

        filename = extract_filename_from_source(s3_path)

        assert filename == "scan.sarif"

    def test_match_expected_digest_with_uri(self):
        """Test digest matching with URI-based artifact locations."""
        artifact_locations = {
            "s3": [
                {
                    "uri": "s3://bucket/path/to/file",
                    "digest": "sha256:abc123",
                }
            ]
        }

        result = match_expected_digest(
            artifact_locations,
            "bucket",
            "path/to/file/scan.sarif"
        )

        assert result == "sha256:abc123"
```

## Best Practices

### Test Organization

1. **One test class per service class**
2. **Group related tests** using descriptive class names
3. **Use descriptive test names** that explain the scenario
4. **Follow AAA pattern**: Arrange, Act, Assert

### Fixtures

1. **Create reusable fixtures** for common dependencies
2. **Use fixture scope** appropriately (function, class, module, session)
3. **Keep fixtures simple** and focused

```python
@pytest.fixture(scope="module")
def mock_document_store():
    """Module-scoped mock document store."""
    return Mock()


@pytest.fixture
def service(mock_document_store):
    """Function-scoped service instance."""
    return MyService(document_store=mock_document_store)
```

### Assertions

1. **Test one thing per test** (single assertion when possible)
2. **Use specific assertions** (not just `assert result`)
3. **Check error details**, not just that an exception was raised

```python
# Good
assert result["status"] == "success"
assert result["count"] == 5
assert "data" in result

# Better
expected = {"status": "success", "count": 5}
assert result["status"] == expected["status"]
assert result["count"] == expected["count"]
assert result["data"] is not None
```

### Coverage Goals

- **Services**: Aim for 90%+ coverage
- **Routers**: Test all endpoints and error paths
- **Utilities**: 100% coverage for pure functions

Run coverage reports:

```bash
uv run pytest --cov=certus_ask/services/ingestion --cov-report=html
```

## Common Testing Patterns

### Testing with Real Files

```python
import tempfile
from pathlib import Path


async def test_with_temp_file(service, tmp_path):
    """Test service with temporary file."""
    # Create temp file
    test_file = tmp_path / "test.txt"
    test_file.write_text("test content")

    result = await service.process_file(test_file)

    assert result is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("format,expected", [
    ("sarif", "security_scan"),
    ("spdx", "sbom"),
    ("cyclonedx", "sbom"),
])
async def test_format_detection(service, format, expected):
    """Test format detection for various formats."""
    result = service.detect_format(format)
    assert result == expected
```

### Testing Retries and Timeouts

```python
import asyncio


async def test_operation_timeout(service):
    """Test that long operations timeout appropriately."""
    service.dependency.slow_method = AsyncMock(
        side_effect=asyncio.TimeoutError()
    )

    with pytest.raises(asyncio.TimeoutError):
        await service.process_with_timeout(timeout=1)
```

## Debugging Tests

### Use pytest options:

```bash
# Run specific test
uv run pytest tests/test_services/test_ingestion/test_file_processor.py::TestFileProcessor::test_process_success

# Show print statements
uv run pytest -s

# Stop on first failure
uv run pytest -x

# Show local variables on failure
uv run pytest -l

# Verbose output
uv run pytest -vv
```

### Add debugging output:

```python
async def test_with_debug_output(service, capsys):
    """Test with debug output."""
    import sys
    print(f"DEBUG: Testing with input {input_data}", file=sys.stderr)

    result = await service.process(input_data)

    captured = capsys.readouterr()
    assert "DEBUG:" in captured.err
```

## Related Guides

- [Adding a New Ingestion Service](adding-ingestion-service.md)
- [Dependency Injection Patterns](dependency-injection.md)

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [unittest.mock documentation](https://docs.python.org/3/library/unittest.mock.html)
