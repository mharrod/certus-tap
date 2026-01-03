"""Custom middleware for the application."""

import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from certus_ask.core.request_context import set_request_id


class RequestIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate and track request IDs for distributed tracing.

    The request ID is available in async context via get_request_id() and
    is automatically added to response headers as X-Request-ID.
    """

    async def dispatch(self, request: Request, call_next):
        """
        Process request and inject request ID.

        Checks for X-Request-ID header from client, otherwise generates new ID.
        Adds request ID to response headers for client correlation.
        """
        # Get request ID from header or generate new one
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

        # Store in context for this request
        set_request_id(request_id)

        # Process request
        response = await call_next(request)

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response


# Alias for compatibility with existing code
TraceIDMiddleware = RequestIDMiddleware
