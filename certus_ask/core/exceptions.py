"""Custom exceptions for Certus-TAP domain-specific errors.

This module defines custom exception classes for domain-specific errors that occur
throughout the application. These exceptions provide semantic meaning about what went wrong,
enabling proper error handling and clear error messages to users.

Exception Hierarchy:
    CertusException (base)
    ├── DocumentProcessingError
    │   ├── DocumentIngestionError
    │   ├── DocumentParseError
    │   └── DocumentValidationError
    ├── PrivacyError
    │   ├── PrivacyViolationError
    │   └── PIIDetectionError
    ├── SearchError
    │   ├── IndexNotFoundError
    │   └── QueryExecutionError
    ├── StorageError
    │   ├── BucketNotFoundError
    │   ├── FileNotFoundError (extends stdlib)
    │   └── FileUploadError
    ├── ExternalServiceError
    │   ├── OpenSearchError
    │   ├── S3Error
    │   ├── LLMError
    │   └── MLflowError
    ├── ConfigurationError
    └── ValidationError
"""


class CertusException(Exception):
    """Base exception for all Certus-TAP domain errors.

    All custom exceptions in the application inherit from this class,
    making it easy to catch all application-specific errors.

    Attributes:
        message: Descriptive error message
        error_code: Machine-readable error identifier
        details: Additional context about the error
    """

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Initialize Certus exception.

        Args:
            message: Descriptive error message for users
            error_code: Machine-readable error code (e.g., 'doc_ingestion_failed')
            details: Additional context dict for debugging

        Example:
            >>> raise DocumentIngestionError(
            ...     message="File format not supported",
            ...     error_code="unsupported_format",
            ...     details={"format": "zip", "supported": ["pdf", "txt"]}
            ... )
        """
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert exception to dictionary for API responses.

        Returns:
            Dictionary with error information suitable for JSON response.
        """
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details if self.details else None,
        }


# ============================================================================
# DOCUMENT PROCESSING ERRORS
# ============================================================================


class DocumentProcessingError(CertusException):
    """Base exception for document processing failures.

    Raised when any step in document processing (ingestion, parsing,
    indexing, or validation) fails.
    """

    pass


class DocumentIngestionError(DocumentProcessingError):
    """Raised when document ingestion fails.

    Reasons might include:
    - Invalid file format
    - File too large
    - Unsupported file type
    - Network failure during upload
    - Disk space exceeded

    Example:
        >>> if file_size > max_size:
        ...     raise DocumentIngestionError(
        ...         message="File exceeds maximum size",
        ...         error_code="file_too_large",
        ...         details={"max_size_mb": 100, "actual_size_mb": 256}
        ...     )
    """

    pass


class DocumentParseError(DocumentProcessingError):
    """Raised when document parsing fails.

    Reasons might include:
    - Corrupted file
    - Invalid encoding
    - Unsupported format version
    - Missing required fields

    Example:
        >>> if not is_valid_json(content):
        ...     raise DocumentParseError(
        ...         message="Invalid JSON format",
        ...         error_code="invalid_json",
        ...         details={"line": 42, "error": "Unexpected token"}
        ...     )
    """

    pass


class DocumentValidationError(DocumentProcessingError):
    """Raised when document validation fails.

    Reasons might include:
    - Required fields missing
    - Invalid field values
    - Schema mismatch
    - Business logic violations

    Example:
        >>> if not document.has_content():
        ...     raise DocumentValidationError(
        ...         message="Document has no extractable content",
        ...         error_code="no_content",
        ...         details={"document_id": doc_id}
        ...     )
    """

    pass


# ============================================================================
# PRIVACY ERRORS
# ============================================================================


class PrivacyError(CertusException):
    """Base exception for privacy-related errors.

    Raised when privacy validation or PII detection fails or is violated.
    """

    pass


class PrivacyViolationError(PrivacyError):
    """Raised when document contains PII that violates privacy policy.

    In strict mode (quarantine), documents with high-confidence PII
    are rejected and raise this error.

    Attributes:
        pii_types: List of PII types detected
        confidence_scores: Dict mapping PII type to confidence

    Example:
        >>> if has_high_confidence_pii(doc):
        ...     raise PrivacyViolationError(
        ...         message="Document contains sensitive PII",
        ...         error_code="pii_detected",
        ...         details={
        ...             "pii_types": ["EMAIL", "CREDIT_CARD"],
        ...             "highest_confidence": 0.95
        ...         }
        ...     )
    """

    pass


class PIIDetectionError(PrivacyError):
    """Raised when PII detection service fails.

    Reasons might include:
    - Presidio service unavailable
    - Invalid analyzer configuration
    - Detection timeout
    - Malformed text input

    Example:
        >>> try:
        ...     results = analyzer.analyze(text)
        ... except AnalyzerError as e:
        ...     raise PIIDetectionError(
        ...         message="PII detection service failed",
        ...         error_code="detection_failed",
        ...         details={"service": "presidio", "error": str(e)}
        ...     ) from e
    """

    pass


# ============================================================================
# SEARCH AND INDEXING ERRORS
# ============================================================================


class SearchError(CertusException):
    """Base exception for search operation failures.

    Raised when document search, query execution, or index operations fail.
    """

    pass


class IndexNotFoundError(SearchError):
    """Raised when requested index does not exist.

    Reasons might include:
    - Index name typo
    - Index not yet created
    - Index deleted
    - Wrong environment

    Example:
        >>> if not index_exists("documents_v2"):
        ...     raise IndexNotFoundError(
        ...         message="Search index not found",
        ...         error_code="index_not_found",
        ...         details={"index_name": "documents_v2"}
        ...     )
    """

    pass


class QueryExecutionError(SearchError):
    """Raised when query execution fails.

    Reasons might include:
    - Invalid query syntax
    - Timeout during execution
    - OpenSearch service error
    - Resource exhaustion

    Example:
        >>> try:
        ...     results = client.search(index=idx, body=query)
        ... except TimeoutError as e:
        ...     raise QueryExecutionError(
        ...         message="Search query timed out",
        ...         error_code="query_timeout",
        ...         details={"timeout_ms": 5000}
        ...     ) from e
    """

    pass


# ============================================================================
# STORAGE ERRORS
# ============================================================================


class StorageError(CertusException):
    """Base exception for storage operation failures.

    Raised when S3, file system, or other storage operations fail.
    """

    pass


class BucketNotFoundError(StorageError):
    """Raised when S3 bucket does not exist or is not accessible.

    Reasons might include:
    - Bucket name typo
    - Bucket deleted
    - Insufficient permissions
    - Wrong AWS region

    Example:
        >>> try:
        ...     client.head_bucket(Bucket="my-bucket")
        ... except ClientError as e:
        ...     if e.response['Error']['Code'] == '404':
        ...         raise BucketNotFoundError(
        ...             message="S3 bucket not found",
        ...             error_code="bucket_not_found",
        ...             details={"bucket_name": "my-bucket"}
        ...         ) from e
    """

    pass


class StorageFileNotFoundError(StorageError, FileNotFoundError):  # type: ignore[misc]
    """Raised when file does not exist in storage.

    Extends both StorageError and stdlib FileNotFoundError for compatibility.

    Example:
        >>> if not source_path.exists():
        ...     raise StorageFileNotFoundError(
        ...         message="Source file does not exist",
        ...         error_code="file_not_found",
        ...         details={"path": str(source_path)}
        ...     )
    """

    pass


# Backwards compatibility alias for legacy imports
FileNotFoundError = StorageFileNotFoundError  # noqa: A001


class FileUploadError(StorageError):
    """Raised when file upload fails.

    Reasons might include:
    - Network interruption
    - Disk space exceeded
    - Invalid file permissions
    - Multipart upload failure
    - File size exceeds limit

    Example:
        >>> if file_size > max_allowed:
        ...     raise FileUploadError(
        ...         message="File exceeds maximum upload size",
        ...         error_code="upload_size_exceeded",
        ...         details={
        ...             "max_size_mb": 1024,
        ...             "actual_size_mb": 2048
        ...         }
        ...     )
    """

    pass


# ============================================================================
# EXTERNAL SERVICE ERRORS
# ============================================================================


class ExternalServiceError(CertusException):
    """Base exception for external service failures.

    Raised when calls to external services fail (OpenSearch, S3, LLM, etc.).
    """

    pass


class OpenSearchError(ExternalServiceError):
    """Raised when OpenSearch operation fails.

    Reasons might include:
    - Connection refused
    - Service timeout
    - Cluster unhealthy
    - Index shard failures
    - Query too complex

    Example:
        >>> try:
        ...     result = client.search(index=idx, body=query)
        ... except ConnectionError as e:
        ...     raise OpenSearchError(
        ...         message="OpenSearch cluster unavailable",
        ...         error_code="opensearch_unavailable",
        ...         details={"host": "opensearch:9200"}
        ...     ) from e
    """

    pass


class S3Error(ExternalServiceError):
    """Raised when S3 operation fails.

    Reasons might include:
    - Access denied
    - Bucket policy violation
    - Region mismatch
    - Throttling
    - Corrupted upload

    Example:
        >>> try:
        ...     client.put_object(Bucket=bucket, Key=key, Body=data)
        ... except ClientError as e:
        ...     raise S3Error(
        ...         message="S3 upload failed",
        ...         error_code="s3_upload_failed",
        ...         details={"bucket": bucket, "key": key}
        ...     ) from e
    """

    pass


class LLMError(ExternalServiceError):
    """Raised when LLM service fails.

    Reasons might include:
    - Service unavailable
    - Invalid model name
    - Context length exceeded
    - Rate limited
    - Generation timeout

    Example:
        >>> try:
        ...     response = client.generate(model=model, prompt=prompt)
        ... except TimeoutError as e:
        ...     raise LLMError(
        ...         message="LLM generation timed out",
        ...         error_code="llm_timeout",
        ...         details={"model": model, "timeout_ms": 30000}
        ...     ) from e
    """

    pass


class MLflowError(ExternalServiceError):
    """Raised when MLflow operation fails.

    Reasons might include:
    - Tracking server unavailable
    - Invalid experiment name
    - Artifact upload failed
    - Run state error

    Example:
        >>> try:
        ...     mlflow.log_metric("accuracy", score)
        ... except Exception as e:
        ...     raise MLflowError(
        ...         message="MLflow logging failed",
        ...         error_code="mlflow_failed",
        ...         details={"metric": "accuracy", "value": score}
        ...     ) from e
    """

    pass


# ============================================================================
# CONFIGURATION ERRORS
# ============================================================================


class ConfigurationError(CertusException):
    """Raised when configuration is invalid or missing.

    Reasons might include:
    - Missing required environment variables
    - Invalid configuration values
    - Configuration conflict
    - Startup validation failed

    Example:
        >>> if not opensearch_host:
        ...     raise ConfigurationError(
        ...         message="OpenSearch host not configured",
        ...         error_code="missing_config",
        ...         details={"required_env": "OPENSEARCH_HOST"}
        ...     )
    """

    pass


# ============================================================================
# VALIDATION ERRORS
# ============================================================================


class ValidationError(CertusException):
    """Raised when input validation fails.

    This is distinct from pydantic ValidationError - it's for custom
    business logic validation after basic schema validation.

    Reasons might include:
    - Business rule violation
    - Invalid state transition
    - Constraint violation
    - Cross-field validation failure

    Example:
        >>> if num_questions > max_allowed:
        ...     raise ValidationError(
        ...         message="Number of questions exceeds limit",
        ...         error_code="validation_failed",
        ...         details={
        ...             "field": "num_questions",
        ...             "max": max_allowed,
        ...             "requested": num_questions
        ...         }
        ...     )
    """

    pass
