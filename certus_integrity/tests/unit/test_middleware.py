from unittest.mock import MagicMock, patch

import pytest
from starlette.requests import Request
from starlette.responses import Response

from certus_integrity import IntegrityMiddleware


# Mock OTel to capture spans
@pytest.fixture
def mock_tracer():
    with patch("certus_integrity.middleware.tracer") as mock:
        yield mock


@pytest.mark.asyncio
async def test_middleware_pass_through(mock_tracer):
    # Setup
    middleware = IntegrityMiddleware(app=MagicMock())

    async def mock_call_next(request):
        return Response("ok")

    request = MagicMock(spec=Request)

    # Execute
    response = await middleware.dispatch(request, mock_call_next)

    # Verify
    assert response.body == b"ok"


@pytest.mark.asyncio
async def test_tracing_attributes(mock_tracer):
    # Setup
    middleware = IntegrityMiddleware(app=MagicMock())
    span = MagicMock()

    # Mock the context manager
    mock_context = MagicMock()
    mock_context.__enter__ = MagicMock(return_value=span)
    mock_context.__exit__ = MagicMock(return_value=None)
    mock_tracer.start_as_current_span.return_value = mock_context

    async def mock_call_next(request):
        return Response("ok")

    request = MagicMock(spec=Request)
    request.client = MagicMock()
    request.client.host = "127.0.0.1"
    request.url = MagicMock()
    request.url.path = "/test"

    # Execute
    await middleware.dispatch(request, mock_call_next)

    # Verify span attributes were set
    span.set_attributes.assert_called()
    call_args = span.set_attributes.call_args[0][0]
    assert call_args["integrity.decision"] == "allowed"
