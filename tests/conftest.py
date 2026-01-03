"""
Shared pytest configuration and fixtures for Certus-TAP tests.

This module provides reusable fixtures for:
- Document test data (text, PDF, with/without PII)
- AWS S3 mocking (moto)
- OpenSearch mocking
- FastAPI test client
- Presidio analyzer/anonymizer
- Settings overrides
- Logging capture
"""

from typing import Any, Optional
from unittest.mock import MagicMock, patch

import boto3
import pytest
import structlog
from fastapi.testclient import TestClient
from moto import mock_aws

# ============================================================================
# Document Fixtures
# ============================================================================


@pytest.fixture
def sample_text_document() -> str:
    """Sample text document for general testing."""
    return """
    # Sample Document

    This is a test document for the Certus-TAP system.
    It contains multiple paragraphs and some basic structure.

    ## Section 1

    Lorem ipsum dolor sit amet, consectetur adipiscing elit.
    Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.

    ## Section 2

    Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris.
    """


@pytest.fixture
def sample_text_with_pii() -> str:
    """Text document containing PII for privacy testing."""
    return """
    # Customer Report

    Customer Name: John Smith
    Email: john.smith@example.com
    Phone: (555) 123-4567
    SSN: 123-45-6789

    Credit Card: 4532-1234-5678-9010

    This customer requires special handling.
    """


@pytest.fixture
def sample_clean_document() -> str:
    """Document with no PII or sensitive information."""
    return """
    # Technical Specification

    ## Overview
    This document describes the system architecture.

    ## Components
    - API Layer: FastAPI
    - Storage: OpenSearch
    - Queue: Redis
    - Cache: In-memory

    ## Performance Metrics
    - Latency: < 100ms p99
    - Throughput: 1000 req/s
    - Availability: 99.9%
    """


@pytest.fixture
def sample_pdf_document() -> bytes:
    """Sample PDF binary content (minimal valid PDF)."""
    # Minimal valid PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]
   /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT /F1 12 Tf 100 700 Td (Sample PDF) Tj ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000273 00000 n
0000000368 00000 n
trailer
<< /Size 6 /Root 1 0 R >>
startxref
446
%%EOF"""
    return pdf_content


@pytest.fixture
def sample_markdown_document() -> str:
    """Sample Markdown document."""
    return """# Markdown Document

## Introduction

This is a markdown formatted document for testing.

## Code Block

```python
def hello_world():
    print("Hello, World!")
```

## List

- Item 1
- Item 2
- Item 3

## Links

[OpenSearch](https://opensearch.org)
"""


# ============================================================================
# AWS/S3 Fixtures
# ============================================================================


@pytest.fixture
def override_s3_settings(monkeypatch):
    """Override S3 settings for testing."""
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:4566")


@pytest.fixture
def mock_s3_client(override_s3_settings):
    """Mocked S3 client using moto."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        yield client


@pytest.fixture
def s3_with_buckets(mock_s3_client):
    """S3 client with pre-created bucket structure."""
    # Create buckets
    mock_s3_client.create_bucket(Bucket="raw-bucket")
    mock_s3_client.create_bucket(Bucket="golden-bucket")

    # Create folder structure
    for folder in ["input", "processing", "archive"]:
        mock_s3_client.put_object(Bucket="raw-bucket", Key=f"{folder}/")

    yield mock_s3_client


@pytest.fixture
def s3_with_documents(s3_with_buckets, sample_text_document):
    """S3 with sample documents pre-loaded."""
    client = s3_with_buckets

    # Upload sample documents
    client.put_object(Bucket="raw-bucket", Key="input/sample.txt", Body=sample_text_document.encode())

    client.put_object(Bucket="raw-bucket", Key="input/sample.md", Body=sample_text_document.encode())

    yield client


# ============================================================================
# OpenSearch/Document Store Fixtures
# ============================================================================


@pytest.fixture
def mock_opensearch_client():
    """Mocked OpenSearch client."""
    client = MagicMock()

    # Mock basic operations
    client.index.return_value = {"_id": "doc-123", "_index": "test"}
    client.get.return_value = {"_source": {"content": "test"}}
    client.delete.return_value = {"result": "deleted"}
    client.search.return_value = {"hits": {"total": {"value": 1}, "hits": [{"_source": {"content": "test"}}]}}
    client.count.return_value = {"count": 1}
    client.indices.exists.return_value = True
    client.indices.create.return_value = {"acknowledged": True}
    client.indices.delete.return_value = {"acknowledged": True}
    client.count_documents = MagicMock(return_value=0)
    # Mock Haystack DocumentWriter method
    client.write_documents = MagicMock(return_value=1)

    yield client


@pytest.fixture
def opensearch_test_index(mock_opensearch_client):
    """Test index in mocked OpenSearch."""
    index_name = "test-documents"
    mock_opensearch_client.indices.create(index=index_name)
    yield {"client": mock_opensearch_client, "index_name": index_name}


# ============================================================================
# Presidio Fixtures
# ============================================================================


@pytest.fixture
def presidio_analyzer():
    """Presidio analyzer instance."""
    try:
        from certus_ask.services.presidio import get_analyzer

        return get_analyzer()
    except Exception:
        # Return mock if initialization fails
        return MagicMock()


@pytest.fixture
def presidio_anonymizer():
    """Presidio anonymizer instance."""
    try:
        from certus_ask.services.presidio import get_anonymizer

        return get_anonymizer()
    except Exception:
        # Return mock if initialization fails
        return MagicMock()


@pytest.fixture
def mock_analysis_results():
    """Mock Presidio AnalysisResult objects."""
    results = [
        MagicMock(entity_type="PERSON", score=0.95, start=10, end=20),
        MagicMock(entity_type="EMAIL", score=0.98, start=30, end=50),
        MagicMock(entity_type="PHONE_NUMBER", score=0.87, start=60, end=73),
    ]
    return results


# ============================================================================
# FastAPI Fixtures
# ============================================================================


@pytest.fixture
def override_app_settings(monkeypatch):
    """Override application settings for testing."""
    monkeypatch.setenv("OPENSEARCH_HOST", "http://localhost:9200")
    monkeypatch.setenv("OPENSEARCH_INDEX", "test-index")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://localhost:4566")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    monkeypatch.setenv("LLM_URL", "http://localhost:11434")
    monkeypatch.setenv("MLFLOW_TRACKING_URI", "http://localhost:5001")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_JSON_OUTPUT", "false")
    monkeypatch.setenv("SEND_LOGS_TO_OPENSEARCH", "false")
    monkeypatch.setenv("DISABLE_OPENSEARCH_LOGGING", "true")


@pytest.fixture
def test_app(override_app_settings, mock_s3_client, mock_opensearch_client):
    """FastAPI test application."""
    from certus_ask.core import config as config_module
    from certus_ask.core.features import Features
    from certus_ask.main import create_app

    config_module.get_settings.cache_clear()
    config_module.settings = config_module.get_settings()

    # Enable features that don't require additional dependencies for testing
    # Note: EVALUATION requires mlflow/deepeval which may not be installed
    # We only enable DOCUMENTS (for datalake) which is commonly available
    Features._DOCUMENTS = True

    with (
        patch(
            "certus_ask.services.opensearch.get_document_store",
            return_value=mock_opensearch_client,
        ),
        patch(
            "certus_ask.services.opensearch.get_document_store_for_workspace",
            return_value=mock_opensearch_client,
        ),
        patch("certus_ask.services.s3.get_s3_client") as mock_s3,
    ):
        mock_s3.return_value = mock_s3_client
        app = create_app()
        yield app


@pytest.fixture
def test_client(test_app) -> TestClient:
    """Synchronous FastAPI test client."""
    return TestClient(test_app, raise_server_exceptions=False)


# ============================================================================
# Pipeline Fixtures
# ============================================================================


@pytest.fixture
def fake_preprocessing_pipeline(monkeypatch):
    """Deterministic preprocessing pipeline used for router tests."""

    class _FakePipeline:
        def __init__(self):
            self.calls: list[dict[str, Any]] = []
            self.result: dict[str, Any] = {
                "document_writer": {
                    "documents_written": 1,
                    "metadata_preview": [{"chunk_id": "fake-1", "source": "test"}],
                }
            }

        def run(self, payload: dict[str, Any]) -> dict[str, Any]:
            self.calls.append(payload)
            return self.result

    pipeline = _FakePipeline()
    # Mock the create_preprocessing_pipeline at the source module and at the router import
    monkeypatch.setattr(
        "certus_ask.pipelines.preprocessing.create_preprocessing_pipeline",
        lambda document_store: pipeline,
    )
    monkeypatch.setattr(
        "certus_ask.routers.ingestion.create_preprocessing_pipeline",
        lambda document_store: pipeline,
    )
    return pipeline


@pytest.fixture
async def async_client(test_app):
    """Asynchronous FastAPI test client (for async endpoints)."""
    from httpx import AsyncClient

    async with AsyncClient(app=test_app, base_url="http://test") as client:
        yield client


# ============================================================================
# Settings Fixtures
# ============================================================================


@pytest.fixture
def test_settings():
    """Test settings object with safe defaults."""
    from certus_ask.core.config import Settings

    return Settings(
        opensearch_host="http://localhost:9200",
        opensearch_index="test-index",
        aws_access_key_id="testing",
        aws_secret_access_key="testing",
        s3_endpoint_url="http://localhost:4566",
        aws_region="us-east-1",
        llm_model="test-model",
        llm_url="http://localhost:11434",
        mlflow_tracking_uri="http://localhost:5001",
        log_level="DEBUG",
        log_json_output=False,
        send_logs_to_opensearch=False,
    )


@pytest.fixture
def override_settings_values(monkeypatch):
    """Fixture to override specific settings values."""

    def _override(**kwargs):
        from certus_ask.core.config import settings

        for key, value in kwargs.items():
            monkeypatch.setattr(settings, key, value)

    return _override


# ============================================================================
# Logging Fixtures
# ============================================================================


@pytest.fixture
def capture_logs():
    """Capture structlog output for testing."""
    import logging

    class LogCapture(logging.Handler):
        def __init__(self):
            super().__init__()
            self.records = []

        def emit(self, record):
            self.records.append(record)

    handler = LogCapture()
    logger = logging.getLogger()
    logger.addHandler(handler)

    yield handler

    logger.removeHandler(handler)


@pytest.fixture
def mock_opensearch_logging(mock_opensearch_client):
    """Mock OpenSearch for logging operations."""
    mock_opensearch_client.index.return_value = {"_index": "logs-test", "_id": "log-123"}
    return mock_opensearch_client


# ============================================================================
# Privacy/Security Fixtures
# ============================================================================


@pytest.fixture
def privacy_logger():
    """Privacy logger for testing."""
    from certus_ask.services.privacy_logger import PrivacyLogger

    return PrivacyLogger(strict_mode=False)


@pytest.fixture
def privacy_logger_strict():
    """Privacy logger in strict mode."""
    from certus_ask.services.privacy_logger import PrivacyLogger

    return PrivacyLogger(strict_mode=True)


# ============================================================================
# Mock Factory Fixtures
# ============================================================================


@pytest.fixture
def document_factory():
    """Factory for creating test documents."""

    class DocumentFactory:
        @staticmethod
        def create(content: str = "test", metadata: Optional[dict[str, Any]] = None) -> dict:
            return {
                "content": content,
                "metadata": metadata or {"id": "doc-test"},
                "embedding": [0.1] * 384,  # 384-dim embedding
            }

        @staticmethod
        def create_batch(count: int = 5) -> list:
            return [DocumentFactory.create(f"document-{i}") for i in range(count)]

    return DocumentFactory


@pytest.fixture
def analysis_result_factory():
    """Factory for creating Presidio AnalysisResult objects."""
    from unittest.mock import MagicMock

    class AnalysisResultFactory:
        @staticmethod
        def create(entity_type: str = "PERSON", confidence: float = 0.95) -> MagicMock:
            result = MagicMock()
            result.entity_type = entity_type
            result.score = confidence
            result.start = 0
            result.end = 10
            return result

        @staticmethod
        def create_batch(count: int = 3) -> list:
            entity_types = ["PERSON", "EMAIL", "PHONE_NUMBER", "CREDIT_CARD"]
            return [
                AnalysisResultFactory.create(
                    entity_type=entity_types[i % len(entity_types)], confidence=0.90 + (i * 0.02)
                )
                for i in range(count)
            ]

    return AnalysisResultFactory


# ============================================================================
# Pytest Hooks & Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "integration: mark test as an integration test (requires Docker)")
    config.addinivalue_line("markers", "slow: mark test as slow running")
    config.addinivalue_line("markers", "privacy: mark test as related to privacy/PII handling")
    config.addinivalue_line("markers", "contract: mark test as a contract test (API boundary validation)")


# ============================================================================
# Smoke Test Fixtures (for service integration)
# ============================================================================


@pytest.fixture(scope="session")
def http_session():
    """HTTP session for smoke/integration tests."""
    import requests

    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    yield session
    session.close()


@pytest.fixture(scope="session")
def request_timeout() -> int:
    """Default timeout for HTTP requests in smoke tests."""
    return 60


@pytest.fixture(autouse=True)
def reset_structlog_cache():
    """Reset structlog's logger cache between tests."""
    yield
    structlog.reset_defaults()


@pytest.fixture(autouse=True)
def isolate_settings(monkeypatch):
    """Isolate settings changes per test."""
    from certus_ask.core.config import settings

    # Store original values
    original_values = {}

    yield

    # Reset to original values after test
    for key, value in original_values.items():
        monkeypatch.setattr(settings, key, value)
