"""Unit tests for response utility functions.

Tests the creation of standardized API responses.
"""

from pydantic import BaseModel

from certus_ask.core.context import clear_context, set_trace_id
from certus_ask.core.response_utils import error_response, success_response
from certus_ask.schemas.responses import StandardResponse


class SampleData(BaseModel):
    """Sample data model for testing."""

    id: str
    name: str
    value: int


class TestSuccessResponse:
    """Tests for success_response function."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_success_response_structure(self):
        """Test that success response has correct structure."""
        data = {"key": "value"}
        response = success_response(data)

        assert isinstance(response, StandardResponse)
        assert response.status == "success"
        assert response.data == data
        assert response.error is None

    def test_success_response_with_dict_data(self):
        """Test success response with dictionary data."""
        data = {"id": "123", "name": "test", "value": 42}
        response = success_response(data)

        assert response.data == data
        assert response.status == "success"

    def test_success_response_with_pydantic_model(self):
        """Test success response with Pydantic model data."""
        data = SampleData(id="123", name="test", value=42)
        response = success_response(data)

        assert response.data == data
        assert response.status == "success"

    def test_success_response_with_list_data(self):
        """Test success response with list data."""
        data = [{"id": "1"}, {"id": "2"}, {"id": "3"}]
        response = success_response(data)

        assert response.data == data
        assert len(response.data) == 3

    def test_success_response_with_string_data(self):
        """Test success response with string data."""
        data = "operation completed successfully"
        response = success_response(data)

        assert response.data == data
        assert isinstance(response.data, str)

    def test_success_response_includes_trace_id(self):
        """Test that success response includes trace ID."""
        data = {"key": "value"}
        response = success_response(data)

        assert response.trace_id is not None
        assert len(response.trace_id) == 36  # UUID length

    def test_success_response_uses_context_trace_id(self):
        """Test that success response uses trace ID from context."""
        test_trace_id = "550e8400-e29b-41d4-a716-446655440000"
        set_trace_id(test_trace_id)

        data = {"key": "value"}
        response = success_response(data)

        assert response.trace_id == test_trace_id

    def test_success_response_includes_timestamp(self):
        """Test that success response includes timestamp."""
        data = {"key": "value"}
        response = success_response(data)

        assert response.timestamp is not None
        assert isinstance(response.timestamp, str)
        # Should be ISO 8601 format
        assert "T" in response.timestamp
        assert "Z" in response.timestamp


class TestErrorResponse:
    """Tests for error_response function."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_error_response_structure(self):
        """Test that error response has correct structure."""
        response = error_response(code="test_error", message="Test error message")

        assert isinstance(response, StandardResponse)
        assert response.status == "error"
        assert response.data is None
        assert response.error is not None

    def test_error_response_includes_error_code(self):
        """Test that error response includes error code."""
        response = error_response(code="validation_failed", message="Validation failed")

        assert response.error.code == "validation_failed"

    def test_error_response_includes_error_message(self):
        """Test that error response includes error message."""
        message = "File exceeds maximum size"
        response = error_response(code="file_too_large", message=message)

        assert response.error.message == message

    def test_error_response_without_context(self):
        """Test error response without context."""
        response = error_response(code="test_error", message="Test message")

        assert response.error.context is None

    def test_error_response_with_context(self):
        """Test error response with context."""
        context = {"max_size_mb": 100, "actual_size_mb": 256}
        response = error_response(code="file_too_large", message="File too large", context=context)

        assert response.error.context == context
        assert response.error.context["max_size_mb"] == 100
        assert response.error.context["actual_size_mb"] == 256

    def test_error_response_includes_trace_id(self):
        """Test that error response includes trace ID."""
        response = error_response(code="test_error", message="Test message")

        assert response.trace_id is not None
        assert len(response.trace_id) == 36  # UUID length

    def test_error_response_uses_context_trace_id(self):
        """Test that error response uses trace ID from context."""
        test_trace_id = "550e8400-e29b-41d4-a716-446655440000"
        set_trace_id(test_trace_id)

        response = error_response(code="test_error", message="Test message")

        assert response.trace_id == test_trace_id

    def test_error_response_includes_timestamp(self):
        """Test that error response includes timestamp."""
        response = error_response(code="test_error", message="Test message")

        assert response.timestamp is not None
        assert isinstance(response.timestamp, str)
        assert "T" in response.timestamp
        assert "Z" in response.timestamp

    def test_error_response_with_complex_context(self):
        """Test error response with complex context data."""
        context = {
            "field": "email",
            "constraints": {"format": "email", "required": True},
            "received_value": "invalid-email",
        }
        response = error_response(code="validation_failed", message="Invalid email format", context=context)

        assert response.error.context["field"] == "email"
        assert response.error.context["constraints"]["format"] == "email"
        assert response.error.context["received_value"] == "invalid-email"


class TestResponseConsistency:
    """Tests for consistency between success and error responses."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_success_and_error_have_same_trace_id_in_context(self):
        """Test that responses use same trace ID when in same context."""
        test_trace_id = "550e8400-e29b-41d4-a716-446655440000"
        set_trace_id(test_trace_id)

        success_resp = success_response({"data": "value"})
        error_resp = error_response(code="error", message="message")

        assert success_resp.trace_id == test_trace_id
        assert error_resp.trace_id == test_trace_id

    def test_both_response_types_have_timestamps(self):
        """Test that both response types include timestamps."""
        success_resp = success_response({"data": "value"})
        error_resp = error_response(code="error", message="message")

        assert success_resp.timestamp is not None
        assert error_resp.timestamp is not None

    def test_success_data_is_none_for_error(self):
        """Test that error response has None data."""
        error_resp = error_response(code="error", message="message")
        assert error_resp.data is None

    def test_error_is_none_for_success(self):
        """Test that success response has None error."""
        success_resp = success_response({"data": "value"})
        assert success_resp.error is None


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def setup_method(self):
        """Clear context before each test."""
        clear_context()

    def teardown_method(self):
        """Clear context after each test."""
        clear_context()

    def test_success_response_with_none_data(self):
        """Test success response with None data."""
        response = success_response(None)
        assert response.data is None
        assert response.status == "success"

    def test_success_response_with_empty_dict(self):
        """Test success response with empty dictionary."""
        response = success_response({})
        assert response.data == {}
        assert response.status == "success"

    def test_error_response_with_empty_string_code(self):
        """Test error response with empty string code."""
        response = error_response(code="", message="test")
        assert response.error.code == ""

    def test_error_response_with_empty_string_message(self):
        """Test error response with empty string message."""
        response = error_response(code="test", message="")
        assert response.error.message == ""

    def test_error_response_with_empty_context_dict(self):
        """Test error response with empty context dictionary."""
        response = error_response(code="test", message="test", context={})
        assert response.error.context == {}
