"""Utilities for creating standardized API responses with trace IDs.

This module provides helper functions for endpoints to easily create
standardized response objects with proper status, data, error, and trace ID.
"""

from typing import Any, Optional, TypeVar

from certus_ask.core.context import get_trace_id
from certus_ask.schemas.responses import StandardResponse

T = TypeVar("T")


def success_response(data: T) -> StandardResponse[T]:
    """Create a success response with the given data.

    This is the standard way for endpoints to return successful results.
    The trace ID is automatically included from the request context.

    Args:
        data: Response payload to include in the response

    Returns:
        StandardResponse with status='success' and the provided data

    Example:
        ```python
        @router.post("/endpoint")
        async def my_endpoint() -> StandardResponse[MyModel]:
            result = do_something()
            return success_response(result)
        ```
    """
    return StandardResponse.success(data=data, trace_id=get_trace_id())


def error_response(
    code: str,
    message: str,
    context: Optional[dict[str, Any]] = None,
) -> StandardResponse:
    """Create an error response with the given error details.

    This is the standard way for endpoints to return errors.
    The trace ID is automatically included from the request context.

    Args:
        code: Machine-readable error code (e.g., 'validation_failed')
        message: User-friendly error message
        context: Optional debugging context (constraints, values, etc.)

    Returns:
        StandardResponse with status='error' and error details

    Example:
        ```python
        @router.post("/endpoint")
        async def my_endpoint(file: UploadFile) -> StandardResponse:
            if file.size > MAX_SIZE:
                return error_response(
                    code="file_too_large",
                    message="File exceeds maximum size",
                    context={"max_size_mb": 100, "actual_size_mb": 256}
                )
        ```
    """
    return StandardResponse.failure(
        code=code,
        message=message,
        trace_id=get_trace_id(),
        context=context,
    )
