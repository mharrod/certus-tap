"""Unit tests for custom exceptions.

Tests the custom exception hierarchy and error handling.
"""

import pytest

from certus_ask.core.exceptions import (
    CertusException,
    ConfigurationError,
    DocumentIngestionError,
    DocumentParseError,
    DocumentProcessingError,
    DocumentValidationError,
    ExternalServiceError,
    IndexNotFoundError,
    LLMError,
    MLflowError,
    OpenSearchError,
    PIIDetectionError,
    PrivacyError,
    PrivacyViolationError,
    QueryExecutionError,
    S3Error,
    SearchError,
    StorageError,
    ValidationError,
)


class TestCertusException:
    """Tests for base CertusException class."""

    def test_certus_exception_creation(self):
        """Test creating a CertusException."""
        exc = CertusException(message="Test error")

        assert exc.message == "Test error"
        assert exc.error_code == "CertusException"  # Default to class name
        assert exc.details == {}

    def test_certus_exception_with_error_code(self):
        """Test CertusException with custom error code."""
        exc = CertusException(message="Test error", error_code="custom_error")

        assert exc.error_code == "custom_error"

    def test_certus_exception_with_details(self):
        """Test CertusException with details."""
        details = {"field": "username", "value": "invalid"}
        exc = CertusException(message="Validation failed", details=details)

        assert exc.details == details
        assert exc.details["field"] == "username"

    def test_certus_exception_str_representation(self):
        """Test string representation of exception."""
        exc = CertusException(message="Test error message")

        assert str(exc) == "Test error message"

    def test_certus_exception_to_dict(self):
        """Test converting exception to dictionary."""
        exc = CertusException(message="Test error", error_code="test_error", details={"key": "value"})

        result = exc.to_dict()

        assert result["error"] == "test_error"
        assert result["message"] == "Test error"
        assert result["details"] == {"key": "value"}

    def test_certus_exception_to_dict_no_details(self):
        """Test to_dict with no details."""
        exc = CertusException(message="Test error")
        result = exc.to_dict()

        assert result["details"] is None

    def test_certus_exception_inherits_from_exception(self):
        """Test that CertusException inherits from Exception."""
        exc = CertusException(message="test")

        assert isinstance(exc, Exception)

    def test_certus_exception_can_be_raised(self):
        """Test that CertusException can be raised and caught."""
        with pytest.raises(CertusException) as exc_info:
            raise CertusException(message="Test error")

        assert exc_info.value.message == "Test error"


class TestDocumentProcessingErrors:
    """Tests for document processing exception hierarchy."""

    def test_document_processing_error_inherits_from_certus(self):
        """Test DocumentProcessingError inherits from CertusException."""
        exc = DocumentProcessingError(message="test")

        assert isinstance(exc, CertusException)
        assert isinstance(exc, DocumentProcessingError)

    def test_document_ingestion_error_creation(self):
        """Test creating DocumentIngestionError."""
        exc = DocumentIngestionError(
            message="File too large", error_code="file_too_large", details={"max_size_mb": 100, "actual_size_mb": 256}
        )

        assert exc.message == "File too large"
        assert exc.error_code == "file_too_large"
        assert exc.details["max_size_mb"] == 100

    def test_document_ingestion_error_inherits_correctly(self):
        """Test DocumentIngestionError inheritance chain."""
        exc = DocumentIngestionError(message="test")

        assert isinstance(exc, DocumentIngestionError)
        assert isinstance(exc, DocumentProcessingError)
        assert isinstance(exc, CertusException)
        assert isinstance(exc, Exception)

    def test_document_parse_error_creation(self):
        """Test creating DocumentParseError."""
        exc = DocumentParseError(
            message="Invalid JSON", error_code="invalid_json", details={"line": 42, "error": "Unexpected token"}
        )

        assert exc.message == "Invalid JSON"
        assert exc.details["line"] == 42

    def test_document_validation_error_creation(self):
        """Test creating DocumentValidationError."""
        exc = DocumentValidationError(
            message="Missing required field", error_code="missing_field", details={"field": "title"}
        )

        assert exc.message == "Missing required field"
        assert exc.details["field"] == "title"


class TestPrivacyErrors:
    """Tests for privacy-related exceptions."""

    def test_privacy_error_creation(self):
        """Test creating PrivacyError."""
        exc = PrivacyError(message="Privacy check failed")

        assert exc.message == "Privacy check failed"
        assert isinstance(exc, CertusException)

    def test_privacy_violation_error_creation(self):
        """Test creating PrivacyViolationError."""
        exc = PrivacyViolationError(
            message="PII detected",
            error_code="pii_detected",
            details={"pii_types": ["EMAIL", "CREDIT_CARD"], "highest_confidence": 0.95},
        )

        assert exc.message == "PII detected"
        assert exc.details["pii_types"] == ["EMAIL", "CREDIT_CARD"]
        assert isinstance(exc, PrivacyError)

    def test_pii_detection_error_creation(self):
        """Test creating PIIDetectionError."""
        exc = PIIDetectionError(message="PII detection service unavailable")

        assert exc.message == "PII detection service unavailable"
        assert isinstance(exc, PrivacyError)


class TestSearchErrors:
    """Tests for search-related exceptions."""

    def test_search_error_creation(self):
        """Test creating SearchError."""
        exc = SearchError(message="Search failed")

        assert exc.message == "Search failed"
        assert isinstance(exc, CertusException)

    def test_index_not_found_error_creation(self):
        """Test creating IndexNotFoundError."""
        exc = IndexNotFoundError(
            message="Index not found", error_code="index_not_found", details={"index": "documents"}
        )

        assert exc.message == "Index not found"
        assert exc.details["index"] == "documents"
        assert isinstance(exc, SearchError)

    def test_query_execution_error_creation(self):
        """Test creating QueryExecutionError."""
        exc = QueryExecutionError(message="Query failed", error_code="query_failed", details={"query": "SELECT *"})

        assert exc.message == "Query failed"
        assert isinstance(exc, SearchError)


class TestStorageErrors:
    """Tests for storage-related exceptions."""

    def test_storage_error_creation(self):
        """Test creating StorageError."""
        exc = StorageError(message="Storage operation failed")

        assert exc.message == "Storage operation failed"
        assert isinstance(exc, CertusException)

    def test_s3_error_creation(self):
        """Test creating S3Error."""
        exc = S3Error(
            message="S3 upload failed",
            error_code="s3_upload_failed",
            details={"bucket": "my-bucket", "key": "file.txt"},
        )

        assert exc.message == "S3 upload failed"
        assert exc.details["bucket"] == "my-bucket"
        assert isinstance(exc, ExternalServiceError)


class TestExternalServiceErrors:
    """Tests for external service exceptions."""

    def test_external_service_error_creation(self):
        """Test creating ExternalServiceError."""
        exc = ExternalServiceError(message="Service unavailable")

        assert exc.message == "Service unavailable"
        assert isinstance(exc, CertusException)

    def test_opensearch_error_creation(self):
        """Test creating OpenSearchError."""
        exc = OpenSearchError(
            message="OpenSearch connection failed",
            error_code="opensearch_connection_failed",
            details={"host": "localhost:9200"},
        )

        assert exc.message == "OpenSearch connection failed"
        assert exc.details["host"] == "localhost:9200"
        assert isinstance(exc, ExternalServiceError)

    def test_llm_error_creation(self):
        """Test creating LLMError."""
        exc = LLMError(message="LLM request timed out", error_code="llm_timeout")

        assert exc.message == "LLM request timed out"
        assert isinstance(exc, ExternalServiceError)

    def test_mlflow_error_creation(self):
        """Test creating MLflowError."""
        exc = MLflowError(message="MLflow tracking failed")

        assert exc.message == "MLflow tracking failed"
        assert isinstance(exc, ExternalServiceError)


class TestConfigurationAndValidationErrors:
    """Tests for configuration and validation exceptions."""

    def test_configuration_error_creation(self):
        """Test creating ConfigurationError."""
        exc = ConfigurationError(
            message="Invalid configuration",
            error_code="invalid_config",
            details={"field": "api_key", "issue": "missing"},
        )

        assert exc.message == "Invalid configuration"
        assert exc.details["field"] == "api_key"
        assert isinstance(exc, CertusException)

    def test_validation_error_creation(self):
        """Test creating ValidationError."""
        exc = ValidationError(
            message="Validation failed", error_code="validation_failed", details={"errors": ["field1", "field2"]}
        )

        assert exc.message == "Validation failed"
        assert isinstance(exc, CertusException)


class TestExceptionHierarchy:
    """Tests for exception hierarchy relationships."""

    def test_catch_all_certus_exceptions(self):
        """Test that all custom exceptions can be caught as CertusException."""
        exceptions = [
            DocumentIngestionError(message="test"),
            DocumentParseError(message="test"),
            PrivacyViolationError(message="test"),
            SearchError(message="test"),
            StorageError(message="test"),
            ExternalServiceError(message="test"),
            ConfigurationError(message="test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, CertusException)

    def test_exception_hierarchy_specificity(self):
        """Test catching exceptions at different hierarchy levels."""
        exc = DocumentIngestionError(message="test")

        # Should be catchable at any level
        try:
            raise exc
        except DocumentIngestionError:
            pass  # Most specific

        try:
            raise exc
        except DocumentProcessingError:
            pass  # Parent class

        try:
            raise exc
        except CertusException:
            pass  # Base class

        try:
            raise exc
        except Exception:
            pass  # Python base


class TestExceptionEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_exception_with_empty_message(self):
        """Test exception with empty message."""
        exc = CertusException(message="")

        assert exc.message == ""
        assert str(exc) == ""

    def test_exception_with_none_details(self):
        """Test exception with explicitly None details."""
        exc = CertusException(message="test", details=None)

        assert exc.details == {}

    def test_exception_with_complex_details(self):
        """Test exception with complex nested details."""
        details = {
            "request": {"method": "POST", "url": "/api/v1/documents"},
            "validation_errors": [{"field": "title", "error": "required"}, {"field": "content", "error": "too_long"}],
            "metadata": {"timestamp": "2024-01-01T00:00:00Z", "user_id": "user123"},
        }

        exc = CertusException(message="Complex error", details=details)

        assert exc.details["request"]["method"] == "POST"
        assert len(exc.details["validation_errors"]) == 2
        assert exc.details["metadata"]["user_id"] == "user123"

    def test_exception_to_dict_preserves_structure(self):
        """Test that to_dict preserves complex details structure."""
        details = {"nested": {"key": "value"}}
        exc = CertusException(message="test", error_code="test", details=details)

        result = exc.to_dict()
        assert result["details"]["nested"]["key"] == "value"
