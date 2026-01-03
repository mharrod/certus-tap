"""Request/response logging middleware for FastAPI."""

import time
import uuid
from typing import Callable

import structlog
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for structured HTTP request/response logging.

    This middleware:
    - Generates unique request IDs for tracing
    - Logs request method, path, query params
    - Logs response status and duration
    - Binds request context to all logs within that request
    - Captures errors and their context
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request and response with logging.

        Args:
            request: The incoming HTTP request
            call_next: The next middleware/handler in the chain

        Returns:
            The HTTP response
        """
        # Generate unique request ID for tracing
        request_id = str(uuid.uuid4())

        # Store request_id in request state for access in handlers/services
        request.state.request_id = request_id

        # Get logger and bind request context
        logger = structlog.get_logger()
        logger = logger.bind(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            client_ip=request.client.host if request.client else "unknown",
        )

        # Log request start
        start_time = time.time()
        query_params = dict(request.query_params) if request.query_params else {}

        logger.info(
            "request.start",
            query_params=query_params,
        )

        try:
            # Call the next middleware/handler
            response = await call_next(request)

        except Exception as exc:
            # Log error and re-raise
            logger.error(
                "request.error",
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            raise

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            "request.end",
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response
