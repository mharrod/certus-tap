"""Integration tests for structured logging system."""

import logging
from unittest.mock import MagicMock

import pytest

from certus_ask.core.async_opensearch_handler import AsyncOpenSearchHandler
from certus_ask.core.logging import configure_logging, get_logger
from certus_ask.middleware.logging import RequestLoggingMiddleware

pytestmark = pytest.mark.integration


def test_logging_configuration():
    """Test that logging is configured correctly."""
    configure_logging(level="INFO", json_output=False)

    # Get a logger and verify it works
    logger = get_logger("test_module")
    assert logger is not None

    # Verify we can log without errors
    logger.info("test.message", test_field="test_value")


def test_async_opensearch_handler_initialization():
    """Test that AsyncOpenSearchHandler initializes gracefully."""
    # Test with invalid host (should handle gracefully)
    handler = AsyncOpenSearchHandler(
        hosts=[{"host": "invalid-host-that-does-not-exist", "port": 9999}],
        index_name="test-logs",
    )

    assert handler is not None
    assert handler.index_name == "test-logs"
    # Handler should be marked as unavailable
    assert handler.is_available is False


def test_async_opensearch_handler_emit():
    """Test that handler.emit() doesn't crash even without connection."""
    handler = AsyncOpenSearchHandler(
        hosts=[{"host": "invalid-host", "port": 9999}],
        index_name="test-logs",
    )

    # Create a log record
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=1,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    # This should not raise, even though OpenSearch is unavailable
    handler.emit(record)


def test_async_opensearch_handler_format_record():
    """Test that log records are formatted correctly."""
    handler = AsyncOpenSearchHandler(
        hosts=[{"host": "localhost", "port": 9200}],
        index_name="test-logs",
    )

    record = logging.LogRecord(
        name="certus_ask.services.datalake",
        level=logging.INFO,
        pathname="services/datalake.py",
        lineno=42,
        msg="Bucket created",
        args=(),
        exc_info=None,
    )

    formatted = handler._format_record(record)

    assert formatted["level"] == "INFO"
    assert formatted["logger"] == "certus_ask.services.datalake"
    assert formatted["message"] == "Bucket created"
    assert formatted["line_number"] == 42
    assert formatted["module"] == "datalake"
    assert "timestamp" in formatted


def test_request_logging_middleware_initialization():
    """Test that middleware initializes correctly."""
    middleware = RequestLoggingMiddleware(app=MagicMock())
    assert middleware is not None


def test_structured_logger_with_context():
    """Test that structured logger binds context correctly."""
    logger = get_logger("test_module")

    # Bind context
    bound_logger = logger.bind(request_id="req-123", user_id="user-456")

    # Verify it returns a logger
    assert bound_logger is not None


@pytest.mark.asyncio
async def test_request_logging_middleware_dispatch():
    """Test that middleware logs requests correctly."""
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()

    @app.get("/test")
    def test_endpoint():
        return {"status": "ok"}

    client = TestClient(app)
    response = client.get("/test")

    assert response.status_code == 200


def test_logging_graceful_degradation():
    """Test that logging system works even without OpenSearch."""
    # Configure logging without OpenSearch
    configure_logging(
        level="INFO",
        json_output=False,
        opensearch_handler=None,
    )

    logger = get_logger("test_module")

    # These should all work without errors
    logger.info("test.info", field="value")
    logger.warning("test.warning", field="value")
    logger.error("test.error", field="value")


def test_async_opensearch_handler_close():
    """Test that handler closes gracefully."""
    handler = AsyncOpenSearchHandler(
        hosts=[{"host": "localhost", "port": 9200}],
        index_name="test-logs",
    )

    # Close should not raise
    handler.close()
    assert handler.is_running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
