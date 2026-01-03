"""Unit tests for request context management.

Tests the context variable management for trace IDs and request IDs.
"""

import uuid

from certus_ask.core.context import (
    clear_context,
    generate_trace_id,
    get_request_id,
    get_trace_id,
    set_request_id,
    set_trace_id,
)


class TestGenerateTraceId:
    """Tests for generate_trace_id function."""

    def test_generate_trace_id_format(self):
        """Test that generated trace ID is a valid UUID4 format."""
        trace_id = generate_trace_id()

        # Should be a valid UUID
        uuid_obj = uuid.UUID(trace_id)
        assert str(uuid_obj) == trace_id
        assert uuid_obj.version == 4

    def test_generate_trace_id_length(self):
        """Test that generated trace ID has correct length."""
        trace_id = generate_trace_id()
        assert len(trace_id) == 36  # UUID4 string length with hyphens

    def test_generate_trace_id_uniqueness(self):
        """Test that multiple calls generate unique trace IDs."""
        trace_ids = [generate_trace_id() for _ in range(100)]

        # All should be unique
        assert len(set(trace_ids)) == 100

    def test_generate_trace_id_returns_string(self):
        """Test that generate_trace_id returns a string."""
        trace_id = generate_trace_id()
        assert isinstance(trace_id, str)


class TestTraceIdContext:
    """Tests for trace ID context management."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_set_and_get_trace_id(self):
        """Test setting and getting trace ID."""
        test_trace_id = "550e8400-e29b-41d4-a716-446655440000"

        set_trace_id(test_trace_id)
        result = get_trace_id()

        assert result == test_trace_id

    def test_get_trace_id_auto_generates_when_not_set(self):
        """Test that get_trace_id auto-generates if not set."""
        # Don't set a trace ID
        trace_id = get_trace_id()

        # Should have auto-generated one
        assert trace_id is not None
        assert len(trace_id) == 36

        # Should be consistent on subsequent calls
        trace_id2 = get_trace_id()
        assert trace_id2 == trace_id

    def test_set_trace_id_overwrites_previous(self):
        """Test that setting trace ID overwrites previous value."""
        first_id = "550e8400-e29b-41d4-a716-446655440000"
        second_id = "660e8400-e29b-41d4-a716-446655440001"

        set_trace_id(first_id)
        assert get_trace_id() == first_id

        set_trace_id(second_id)
        assert get_trace_id() == second_id


class TestRequestIdContext:
    """Tests for request ID context management."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        test_request_id = "external-request-123"

        set_request_id(test_request_id)
        result = get_request_id()

        assert result == test_request_id

    def test_get_request_id_returns_none_when_not_set(self):
        """Test that get_request_id returns None if not set."""
        result = get_request_id()
        assert result is None

    def test_set_request_id_overwrites_previous(self):
        """Test that setting request ID overwrites previous value."""
        first_id = "request-1"
        second_id = "request-2"

        set_request_id(first_id)
        assert get_request_id() == first_id

        set_request_id(second_id)
        assert get_request_id() == second_id


class TestClearContext:
    """Tests for clear_context function."""

    def test_clear_context_resets_trace_id(self):
        """Test that clear_context resets trace ID."""
        set_trace_id("550e8400-e29b-41d4-a716-446655440000")
        clear_context()

        # After clearing, get_trace_id should auto-generate a new one
        new_trace_id = get_trace_id()
        assert new_trace_id != "550e8400-e29b-41d4-a716-446655440000"

    def test_clear_context_resets_request_id(self):
        """Test that clear_context resets request ID."""
        set_request_id("request-123")
        clear_context()

        result = get_request_id()
        assert result is None

    def test_clear_context_resets_all(self):
        """Test that clear_context resets all context variables."""
        set_trace_id("trace-123")
        set_request_id("request-123")

        clear_context()

        # Trace ID auto-generates, request ID returns None
        assert get_trace_id() != "trace-123"
        assert get_request_id() is None


class TestContextIsolation:
    """Tests for context isolation between different contexts."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_trace_id_and_request_id_are_independent(self):
        """Test that trace ID and request ID are independent."""
        trace_id = "trace-123"
        request_id = "request-456"

        set_trace_id(trace_id)
        set_request_id(request_id)

        assert get_trace_id() == trace_id
        assert get_request_id() == request_id

        # Clearing one shouldn't affect the other
        # (Note: clear_context clears both, so we test independence via setting)
        set_trace_id("new-trace")
        assert get_trace_id() == "new-trace"
        assert get_request_id() == request_id  # Should be unchanged


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_set_trace_id_with_empty_string(self):
        """Test setting trace ID with empty string."""
        set_trace_id("")
        result = get_trace_id()
        assert result == ""

    def test_set_request_id_with_empty_string(self):
        """Test setting request ID with empty string."""
        set_request_id("")
        result = get_request_id()
        assert result == ""

    def test_set_trace_id_with_non_uuid_string(self):
        """Test that trace ID can be set to non-UUID string."""
        custom_id = "my-custom-trace-id"
        set_trace_id(custom_id)
        assert get_trace_id() == custom_id

    def test_multiple_get_trace_id_calls_return_same_value(self):
        """Test that multiple get_trace_id calls return consistent value."""
        trace_id1 = get_trace_id()
        trace_id2 = get_trace_id()
        trace_id3 = get_trace_id()

        assert trace_id1 == trace_id2 == trace_id3
