"""Error response schemas for consistent API error handling.

These Pydantic models standardize error responses across all API endpoints,
enabling clients to reliably parse error details and handle different error
scenarios programmatically.
"""

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetailResponse(BaseModel):
    """Detailed error response with context and debugging information.

    Used for 4xx and 5xx error responses to provide clients with structured
    error information including the error code, user-friendly message, and
    optional additional context for debugging.

    Attributes:
        error: Machine-readable error code (e.g., 'doc_ingestion_failed')
        message: User-friendly error message
        detail: Optional additional context for debugging or user action

    Example:
        >>> error = ErrorDetailResponse(
        ...     error="file_too_large",
        ...     message="Uploaded file exceeds maximum size",
        ...     detail={"max_size_mb": 100, "actual_size_mb": 256}
        ... )
    """

    error: str = Field(
        ...,
        description="Machine-readable error code identifying the error type",
        examples=["doc_ingestion_failed", "privacy_violation", "service_unavailable"],
    )
    message: str = Field(
        ...,
        description="User-friendly error message explaining what went wrong",
        examples=["File format not supported", "Document contains sensitive PII"],
    )
    detail: dict[str, Any] | None = Field(
        None,
        description="Optional additional context including constraints, requirements, or debugging info",
        examples=[
            {"supported_formats": ["pdf", "txt", "docx"]},
            {"max_size_mb": 100, "actual_size_mb": 256},
        ],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "error": "validation_failed",
                "message": "Input validation failed",
                "detail": {
                    "field": "num_questions",
                    "constraint": "must be between 1 and 100",
                    "received": 150,
                },
            }
        }
    }


class ValidationErrorDetail(BaseModel):
    """Validation error for a single field (compatible with Pydantic ValidationError).

    Used when Pydantic request validation fails to provide details about
    which field failed and why.

    Attributes:
        loc: Location of the error as a tuple (field path)
        msg: Error message
        type: Error type code
    """

    loc: tuple[int | str, ...] = Field(..., description="Field path where error occurred")
    msg: str = Field(..., description="Error message")
    type: str = Field(..., description="Error type (e.g., 'value_error', 'type_error')")


class ValidationErrorResponse(BaseModel):
    """Response for request validation errors (HTTP 422).

    Wraps multiple field validation errors in a consistent format that
    clients can use to highlight problematic fields.

    Attributes:
        detail: List of validation errors for each field

    Example:
        >>> response = ValidationErrorResponse(
        ...     detail=[
        ...         ValidationErrorDetail(
        ...             loc=("body", "num_questions"),
        ...             msg="ensure this value is less than or equal to 100",
        ...             type="value_error.number.not_le"
        ...         )
        ...     ]
        ... )
    """

    detail: list[ValidationErrorDetail] = Field(
        ...,
        description="List of validation errors for each field",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "detail": [
                    {
                        "loc": ["body", "num_questions"],
                        "msg": "ensure this value is less than or equal to 100",
                        "type": "value_error.number.not_le",
                    }
                ]
            }
        }
    }


class NotFoundErrorResponse(ErrorDetailResponse):
    """Response for not found errors (HTTP 404).

    Indicates that a requested resource (document, index, file, etc.) does not exist.

    Example:
        >>> error = NotFoundErrorResponse(
        ...     error="index_not_found",
        ...     message="Search index does not exist",
        ...     detail={"index_name": "documents_v2"}
        ... )
    """

    pass


class ConflictErrorResponse(ErrorDetailResponse):
    """Response for conflict errors (HTTP 409).

    Indicates a conflict in the current state, such as attempting to create
    a resource that already exists or an invalid state transition.

    Example:
        >>> error = ConflictErrorResponse(
        ...     error="duplicate_resource",
        ...     message="Resource with this ID already exists",
        ...     detail={"resource_type": "bucket", "name": "my-bucket"}
        ... )
    """

    pass


class BadRequestErrorResponse(ErrorDetailResponse):
    """Response for bad request errors (HTTP 400).

    Indicates malformed request data, invalid parameters, or validation failures
    at the business logic level (not schema validation).

    Example:
        >>> error = BadRequestErrorResponse(
        ...     error="invalid_format",
        ...     message="Uploaded file must be valid JSON",
        ...     detail={"error_at_line": 42}
        ... )
    """

    pass


class InternalServerErrorResponse(ErrorDetailResponse):
    """Response for internal server errors (HTTP 500).

    Indicates an unexpected error during processing. The error message should
    be user-friendly without exposing internal details. Additional context
    may be provided for debugging.

    Example:
        >>> error = InternalServerErrorResponse(
        ...     error="processing_failed",
        ...     message="An unexpected error occurred while processing your request",
        ...     detail={"error_id": "req_12345", "contact": "support@example.com"}
        ... )
    """

    pass


class ServiceUnavailableErrorResponse(ErrorDetailResponse):
    """Response for service unavailable errors (HTTP 503).

    Indicates that a required external service (OpenSearch, S3, LLM, etc.)
    is temporarily unavailable.

    Example:
        >>> error = ServiceUnavailableErrorResponse(
        ...     error="opensearch_unavailable",
        ...     message="Search service is temporarily unavailable",
        ...     detail={
        ...         "service": "opensearch",
        ...         "retry_after_seconds": 30
        ...     }
        ... )
    """

    pass


# Response examples for documentation
ERROR_RESPONSES = {
    400: {
        "model": BadRequestErrorResponse,
        "description": "Bad Request - Invalid input or malformed data",
    },
    404: {
        "model": NotFoundErrorResponse,
        "description": "Not Found - Resource does not exist",
    },
    409: {
        "model": ConflictErrorResponse,
        "description": "Conflict - State conflict or duplicate resource",
    },
    422: {
        "model": ValidationErrorResponse,
        "description": "Unprocessable Entity - Request validation failed",
    },
    500: {
        "model": InternalServerErrorResponse,
        "description": "Internal Server Error - Unexpected processing failure",
    },
    503: {
        "model": ServiceUnavailableErrorResponse,
        "description": "Service Unavailable - Required service is temporarily down",
    },
}
