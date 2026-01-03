"""Request context utilities for tracing requests across services."""

import uuid
from contextvars import ContextVar

# Context variable to store request ID throughout async context
_request_id_ctx_var: ContextVar[str | None] = ContextVar("request_id", default=None)


def get_request_id() -> str:
    """
    Get or generate a request ID for the current request.

    Returns a unique request ID that can be used to correlate:
    - HTTP responses to clients
    - Log entries
    - External service calls (Trust, Neo4j)

    Returns:
        str: UUID-based request ID
    """
    request_id = _request_id_ctx_var.get()
    if request_id is None:
        request_id = str(uuid.uuid4())
        _request_id_ctx_var.set(request_id)
    return request_id


def set_request_id(request_id: str) -> None:
    """
    Set the request ID for the current async context.

    Typically called by middleware at the start of request processing.

    Args:
        request_id: The request ID to set
    """
    _request_id_ctx_var.set(request_id)


def clear_request_id() -> None:
    """Clear the request ID from the current context."""
    _request_id_ctx_var.set(None)
