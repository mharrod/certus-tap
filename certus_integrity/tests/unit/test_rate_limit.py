import time

import pytest
from starlette.responses import Response

from certus_integrity.middleware import IntegrityMiddleware


class MockApp:
    async def __call__(self, scope, receive, send):
        return Response("OK")


@pytest.fixture
def middleware():
    app = MockApp()
    mw = IntegrityMiddleware(app)
    # Reset internal state
    mw._request_history.clear()
    return mw


def test_rate_limiter_logic(middleware):
    """Test that rate limiter allows requests up to limit and rejects after."""
    middleware.rate_limit = 5
    ip = "127.0.0.1"

    # Send 5 requests (allowed)
    for _ in range(5):
        is_limited, _ = middleware._is_rate_limited(ip)
        assert not is_limited

    # 6th request (denied)
    is_limited, _remaining = middleware._is_rate_limited(ip)
    assert is_limited


def test_rate_limiter_sliding_window(middleware):
    """Test that old requests expire."""
    middleware.rate_limit = 2
    ip = "127.0.0.1"

    # 2 requests
    is_limited, _ = middleware._is_rate_limited(ip)
    assert not is_limited
    is_limited, _ = middleware._is_rate_limited(ip)
    assert not is_limited

    # 3rd request denied
    is_limited, _ = middleware._is_rate_limited(ip)
    assert is_limited

    # Simulate time passing (mock time?)
    # Since we use time.time() in middleware, we can mock time.time or just modify history manually

    # Manually backdate history
    # The middleware stores timestamps in _request_history[ip] (Deque)
    from collections import deque

    middleware._request_history[ip] = deque([time.time() - 61, time.time() - 61])

    # Now should be allowed again
    is_limited, _remaining = middleware._is_rate_limited(ip)
    assert not is_limited
