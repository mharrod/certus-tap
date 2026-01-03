"""Standardized response wrapper models for all API endpoints.

All API responses follow a consistent format with status, data, error, and timestamp.
This ensures predictable client-side handling and clear error semantics.

Response Format:
    {
        "status": "success" | "error",
        "data": {...},           # Present only on success
        "error": null | {...},   # Present only on error
        "timestamp": "ISO8601",  # UTC timestamp
        "trace_id": "uuid"       # Request trace ID for debugging
    }
"""

from datetime import datetime, timezone
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Error details included in error responses.

    Attributes:
        code: Machine-readable error code (e.g., 'validation_failed')
        message: User-friendly error message
        context: Optional debugging context
    """

    code: str = Field(
        ...,
        description="Machine-readable error code",
        examples=["validation_failed", "file_not_found", "service_unavailable"],
    )
    message: str = Field(
        ...,
        description="User-friendly error message",
        examples=["File exceeds maximum size", "Resource not found"],
    )
    context: Optional[dict[str, Any]] = Field(
        None,
        description="Optional debugging context (constraints, values, etc.)",
        examples=[{"max_size_mb": 100, "actual_size_mb": 256}],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "code": "validation_failed",
                "message": "File exceeds maximum size of 100MB",
                "context": {
                    "max_size_mb": 100,
                    "actual_size_mb": 256,
                },
            }
        }
    }


class StandardResponse(BaseModel, Generic[T]):
    """Standard response wrapper for all API endpoints.

    This model wraps all endpoint responses in a consistent format, ensuring
    predictable error handling and status tracking across the entire API.

    Attributes:
        status: Either "success" or "error" indicating operation result
        data: Response payload (present only on success, None on error)
        error: Error details (present only on error, None on success)
        timestamp: ISO8601 UTC timestamp of when response was generated
        trace_id: Unique request identifier for tracking and debugging

    Examples:
        Success response:
            {
                "status": "success",
                "data": {"ingestion_id": "...", "message": "..."},
                "error": null,
                "timestamp": "2024-11-14T12:34:56.789Z",
                "trace_id": "550e8400-e29b-41d4-a716-446655440000"
            }

        Error response:
            {
                "status": "error",
                "data": null,
                "error": {
                    "code": "file_too_large",
                    "message": "File exceeds maximum size of 100MB",
                    "context": {"max_size_mb": 100, "actual_size_mb": 256}
                },
                "timestamp": "2024-11-14T12:34:56.789Z",
                "trace_id": "550e8400-e29b-41d4-a716-446655440001"
            }
    """

    status: str = Field(
        ...,
        description="Operation result: 'success' or 'error'",
        pattern="^(success|error)$",
        examples=["success", "error"],
    )
    data: Optional[T] = Field(
        None,
        description="Response payload (present on success, null on error)",
    )
    error: Optional[ErrorDetail] = Field(
        None,
        description="Error details (present on error, null on success)",
    )
    timestamp: str = Field(
        ...,
        description="ISO8601 UTC timestamp of response generation",
        examples=["2024-11-14T12:34:56.789Z"],
    )
    trace_id: str = Field(
        ...,
        description="Unique request identifier for tracking and debugging",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "status": "success",
                "data": {
                    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
                    "message": "Indexed document document.pdf",
                    "document_count": 42,
                },
                "error": None,
                "timestamp": "2024-11-14T12:34:56.789Z",
                "trace_id": "550e8400-e29b-41d4-a716-446655440000",
            }
        }
    }

    @classmethod
    def success(cls, data: T, trace_id: str) -> "StandardResponse[T]":
        """Create a success response.

        Args:
            data: Response payload to include
            trace_id: Trace ID for request tracking

        Returns:
            StandardResponse with status='success'
        """
        return cls(
            status="success",
            data=data,
            error=None,
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            trace_id=trace_id,
        )

    @classmethod
    def failure(
        cls,
        code: str,
        message: str,
        trace_id: str,
        context: Optional[dict[str, Any]] = None,
    ) -> "StandardResponse[T]":
        """Create an error response.

        Args:
            code: Machine-readable error code
            message: User-friendly error message
            trace_id: Trace ID for request tracking
            context: Optional debugging context

        Returns:
            StandardResponse with status='error'
        """
        return cls(
            status="error",
            data=None,
            error=ErrorDetail(code=code, message=message, context=context),
            timestamp=datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            trace_id=trace_id,
        )


# Alias for convenience
APIResponse = StandardResponse
