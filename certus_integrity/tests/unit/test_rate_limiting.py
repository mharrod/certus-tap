"""Unit tests for IntegrityMiddleware rate limiting logic."""

import time
from collections import deque
from unittest.mock import AsyncMock, Mock, patch

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from certus_integrity.middleware import IntegrityMiddleware


@pytest.fixture
def middleware():
    """Create middleware instance for testing."""
    app = Mock()
    middleware = IntegrityMiddleware(app)
    middleware.rate_limit = 10  # Lower limit for testing
    middleware.burst_limit = 15  # Higher than rate limit to test rate limit independently
    middleware.shadow_mode = False  # Test enforcement
    return middleware


@pytest.fixture
def mock_request():
    """Create mock request."""
    request = Mock(spec=Request)
    request.client = Mock()
    request.client.host = "192.168.1.100"
    request.url = Mock()
    request.url.path = "/v1/test"
    return request


@pytest.fixture
def mock_trace():
    """Create properly configured trace mock."""
    mock_span_context = Mock()
    mock_span_context.trace_id = 123456789
    mock_span_context.span_id = 987654321

    mock_span = Mock()
    mock_span.get_span_context.return_value = mock_span_context
    mock_span.set_attributes = Mock()

    mock_tracer = Mock()
    mock_tracer.start_as_current_span.return_value.__enter__ = Mock(return_value=mock_span)
    mock_tracer.start_as_current_span.return_value.__exit__ = Mock(return_value=False)

    with patch("certus_integrity.middleware.trace") as trace_patch:
        trace_patch.get_current_span.return_value = mock_span
        trace_patch.get_tracer.return_value = mock_tracer
        yield trace_patch


class TestRateLimitLogic:
    """Test the core rate limiting logic."""

    def test_rate_limit_not_exceeded(self, middleware):
        """Test that requests under limit are allowed."""
        is_limited, remaining = middleware._is_rate_limited("192.168.1.1")

        assert is_limited is False
        assert remaining == 9  # 10 - 1 = 9 remaining

    def test_rate_limit_exactly_at_limit(self, middleware):
        """Test behavior when exactly at rate limit."""
        ip = "192.168.1.2"

        # Make 10 requests (exactly at limit)
        for i in range(10):
            is_limited, remaining = middleware._is_rate_limited(ip)
            assert is_limited is False, f"Request {i + 1} should not be limited"

        # 11th request should be limited
        is_limited, remaining = middleware._is_rate_limited(ip)
        assert is_limited is True
        assert remaining == 0

    def test_rate_limit_exceeded(self, middleware):
        """Test that requests over limit are blocked."""
        ip = "192.168.1.3"

        # Exhaust the limit
        for _ in range(10):
            middleware._is_rate_limited(ip)

        # This should be blocked
        is_limited, remaining = middleware._is_rate_limited(ip)
        assert is_limited is True
        assert remaining == 0

    def test_sliding_window_expiration(self, middleware):
        """Test that old requests expire after 60 seconds."""
        ip = "192.168.1.4"

        # Add 10 old requests (61 seconds ago)
        now = time.time()
        old_time = now - 61
        middleware._request_history[ip] = deque([old_time] * 10)

        # New request should be allowed (old ones expired)
        is_limited, _remaining = middleware._is_rate_limited(ip)
        assert is_limited is False
        assert len(middleware._request_history[ip]) == 1  # Only new request

    def test_burst_protection(self, middleware):
        """Test burst protection (max requests in 10 seconds)."""
        # Use a separate middleware with low burst limit
        app = Mock()
        burst_middleware = IntegrityMiddleware(app)
        burst_middleware.rate_limit = 100  # High rate limit
        burst_middleware.burst_limit = 3  # Low burst limit

        ip = "192.168.1.5"
        now = time.time()

        # Add 3 requests in last 5 seconds (at burst limit)
        burst_middleware._request_history[ip] = deque([now - 5, now - 3, now - 1])

        # 4th request in burst window should be blocked
        is_limited, _remaining = burst_middleware._is_rate_limited(ip)
        assert is_limited is True

    def test_multiple_ips_independent(self, middleware):
        """Test that different IPs have independent rate limits."""
        ip1 = "192.168.1.6"
        ip2 = "192.168.1.7"

        # Exhaust limit for ip1
        for _ in range(10):
            middleware._is_rate_limited(ip1)

        # ip1 should be limited
        is_limited, _ = middleware._is_rate_limited(ip1)
        assert is_limited is True

        # ip2 should not be limited
        is_limited, _ = middleware._is_rate_limited(ip2)
        assert is_limited is False

    def test_whitelist_bypass(self, middleware):
        """Test that whitelisted IPs bypass rate limiting."""
        whitelisted_ip = "127.0.0.1"
        middleware.whitelist.add(whitelisted_ip)

        # Should never be rate limited
        assert middleware._is_whitelisted(whitelisted_ip) is True

    def test_whitelist_cidr_range(self, middleware):
        """Test CIDR range whitelisting."""
        middleware.whitelist.add("172.18.0.0/16")

        # IP in range should be whitelisted
        assert middleware._is_whitelisted("172.18.0.5") is True
        assert middleware._is_whitelisted("172.18.255.255") is True

        # IP outside range should not be whitelisted
        assert middleware._is_whitelisted("172.19.0.1") is False

    def test_memory_leak_prevention(self, middleware):
        """Test that empty IP entries are cleaned up."""
        # Add some IPs with old requests
        now = time.time()
        old_time = now - 61

        middleware._request_history["192.168.1.10"] = deque([old_time])
        middleware._request_history["192.168.1.11"] = deque([old_time])
        middleware._request_history["192.168.1.12"] = deque([old_time])

        # Trigger cleanup
        middleware._last_cleanup = now - 301  # Force cleanup
        middleware._cleanup_old_entries()

        # Check that entries still exist (cleanup only removes empty)
        assert len(middleware._request_history) == 3

        # Now trigger rate limit check to expire old timestamps
        for ip in ["192.168.1.10", "192.168.1.11", "192.168.1.12"]:
            middleware._is_rate_limited(ip)

        # After another cleanup, empty entries should be removed
        middleware._last_cleanup = now - 301
        middleware._cleanup_old_entries()

        # Should only have entries with recent requests
        assert all(len(hist) > 0 for hist in middleware._request_history.values())

    def test_disabled_rate_limit(self, middleware):
        """Test that rate_limit=0 disables rate limiting."""
        middleware.rate_limit = 0

        # Should never be limited
        for _ in range(1000):
            is_limited, _ = middleware._is_rate_limited("192.168.1.13")
            assert is_limited is False


@pytest.mark.asyncio
class TestMiddlewareIntegration:
    """Integration tests for the middleware dispatch."""

    async def test_allowed_request(self, middleware, mock_request, mock_trace):
        """Test that requests under limit are allowed through."""
        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("certus_integrity.middleware.asyncio.create_task"):
            response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 200
        assert call_next.called

    async def test_rate_limited_request(self, middleware, mock_request, mock_trace):
        """Test that requests over limit are blocked with 429."""
        # Exhaust the rate limit
        ip = mock_request.client.host
        for _ in range(10):
            middleware._is_rate_limited(ip)

        call_next = AsyncMock()

        with patch("certus_integrity.middleware.asyncio.create_task"):
            response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 429
        assert not call_next.called  # Should not reach application

        # Check response content
        assert isinstance(response, JSONResponse)

    async def test_rate_limit_headers_on_success(self, middleware, mock_request, mock_trace):
        """Test that rate limit headers are added to successful responses."""
        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("certus_integrity.middleware.asyncio.create_task"):
            response = await middleware.dispatch(mock_request, call_next)

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    async def test_rate_limit_headers_on_429(self, middleware, mock_request, mock_trace):
        """Test that rate limit headers are added to 429 responses."""
        # Exhaust the rate limit
        ip = mock_request.client.host
        for _ in range(10):
            middleware._is_rate_limited(ip)

        call_next = AsyncMock()

        with patch("certus_integrity.middleware.asyncio.create_task"):
            response = await middleware.dispatch(mock_request, call_next)

        assert response.status_code == 429
        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Remaining" in response.headers
        assert response.headers["X-RateLimit-Remaining"] == "0"
        assert "Retry-After" in response.headers

    async def test_shadow_mode_allows_violations(self, middleware, mock_request, mock_trace):
        """Test that shadow mode allows rate limit violations."""
        middleware.shadow_mode = True

        # Exhaust the rate limit
        ip = mock_request.client.host
        for _ in range(10):
            middleware._is_rate_limited(ip)

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("certus_integrity.middleware.asyncio.create_task"):
            response = await middleware.dispatch(mock_request, call_next)

        # Should be allowed in shadow mode
        assert response.status_code == 200
        assert call_next.called

    async def test_whitelisted_ip_bypasses_limit(self, middleware, mock_request, mock_trace):
        """Test that whitelisted IPs bypass rate limiting."""
        middleware.whitelist.add(mock_request.client.host)

        # Exhaust what would be the limit
        ip = mock_request.client.host
        for _ in range(20):  # Way over limit
            middleware._is_rate_limited(ip)

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("certus_integrity.middleware.asyncio.create_task"):
            response = await middleware.dispatch(mock_request, call_next)

        # Should still be allowed
        assert response.status_code == 200

    async def test_unknown_client_ip(self, middleware, mock_trace):
        """Test handling of requests without client IP."""
        request = Mock(spec=Request)
        request.client = None
        request.url = Mock()
        request.url.path = "/v1/test"

        call_next = AsyncMock(return_value=Response(status_code=200))

        with patch("certus_integrity.middleware.asyncio.create_task"):
            response = await middleware.dispatch(request, call_next)

        # Should handle gracefully
        assert response.status_code == 200


class TestEdgeCases:
    """Test edge cases and corner scenarios."""

    def test_concurrent_requests_same_ip(self, middleware):
        """Test that concurrent requests from same IP are counted correctly."""
        import threading

        ip = "192.168.1.20"
        results = []

        def make_request():
            is_limited, _ = middleware._is_rate_limited(ip)
            results.append(is_limited)

        # Simulate 15 concurrent requests
        threads = [threading.Thread(target=make_request) for _ in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # First 10 should succeed, rest should fail
        assert results.count(False) <= 10
        assert results.count(True) >= 5

    def test_rate_limit_recovery_after_window(self, middleware):
        """Test that rate limit recovers after sliding window expires."""
        ip = "192.168.1.21"

        # Exhaust limit
        for _ in range(10):
            middleware._is_rate_limited(ip)

        # Should be limited
        is_limited, _ = middleware._is_rate_limited(ip)
        assert is_limited is True

        # Simulate 61 seconds passing (manually clear old timestamps)
        middleware._request_history[ip].clear()

        # Should be allowed again
        is_limited, _ = middleware._is_rate_limited(ip)
        assert is_limited is False
