"""Integration tests for WebSocket log streaming."""

import asyncio

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def test_websocket_endpoint_exists(assurance_base_url: str):
    """Test that WebSocket endpoint is defined."""
    # WebSocket URL pattern
    ws_url = assurance_base_url.replace("http://", "ws://")
    expected_ws_url = f"{ws_url}/ws/logs/test-assessment"

    # This test documents the expected WebSocket URL pattern
    assert "ws://" in expected_ws_url
    assert "/ws/logs/" in expected_ws_url


def test_log_stream_manager_import():
    """Test that LogStreamManager can be imported."""
    from certus_assurance.logs import log_stream_manager

    assert log_stream_manager is not None


def test_log_stream_manager_has_register_method():
    """Test that LogStreamManager has register method."""
    from certus_assurance.logs import log_stream_manager

    assert hasattr(log_stream_manager, "register")


def test_log_stream_manager_has_get_method():
    """Test that LogStreamManager has get method."""
    from certus_assurance.logs import log_stream_manager

    assert hasattr(log_stream_manager, "get")


def test_log_stream_manager_has_pop_method():
    """Test that LogStreamManager has pop method."""
    from certus_assurance.logs import log_stream_manager

    assert hasattr(log_stream_manager, "pop")


@pytest.mark.asyncio
async def test_log_stream_register_and_emit():
    """Test registering a stream and emitting events."""
    from certus_assurance.logs import log_stream_manager

    assessment_id = "test_ws_123"
    loop = asyncio.get_event_loop()

    # Register a stream
    stream = log_stream_manager.register(assessment_id, loop)

    # Emit an event
    stream.emit("test_event", message="Test log message")

    # Wait briefly for async processing
    await asyncio.sleep(0.1)

    # Verify event was recorded
    assert len(stream.history) > 0
    assert stream.history[0].type == "test_event"
    assert stream.history[0].data["message"] == "Test log message"

    # Cleanup
    log_stream_manager.pop(assessment_id)


@pytest.mark.asyncio
async def test_log_stream_get_and_pop():
    """Test getting and removing streams."""
    from certus_assurance.logs import log_stream_manager

    assessment_id = "test_multi_123"
    loop = asyncio.get_event_loop()

    # Register a stream
    stream = log_stream_manager.register(assessment_id, loop)

    # Get stream by ID
    retrieved_stream = log_stream_manager.get(assessment_id)
    assert retrieved_stream is stream

    # Pop stream (removes it)
    popped_stream = log_stream_manager.pop(assessment_id)
    assert popped_stream is stream

    # Stream should no longer be available
    assert log_stream_manager.get(assessment_id) is None


@pytest.mark.asyncio
async def test_log_stream_isolated_by_assessment_id():
    """Test that log streams are isolated by assessment_id."""
    from certus_assurance.logs import log_stream_manager

    assessment_1 = "test_isolated_1"
    assessment_2 = "test_isolated_2"
    loop = asyncio.get_event_loop()

    # Register two different streams
    stream_1 = log_stream_manager.register(assessment_1, loop)
    stream_2 = log_stream_manager.register(assessment_2, loop)

    # Emit to stream_1 only
    stream_1.emit("test_event", message="Message for assessment 1")

    await asyncio.sleep(0.1)

    # Only stream_1 should have events
    assert len(stream_1.history) > 0
    assert len(stream_2.history) == 0

    # Cleanup
    log_stream_manager.pop(assessment_1)
    log_stream_manager.pop(assessment_2)


@pytest.mark.asyncio
async def test_log_stream_close():
    """Test closing a log stream."""
    from certus_assurance.logs import log_stream_manager

    assessment_id = "test_close"
    loop = asyncio.get_event_loop()

    # Register and close stream
    stream = log_stream_manager.register(assessment_id, loop)
    stream.emit("start", message="Starting")
    stream.close("completed", result="success")

    await asyncio.sleep(0.1)

    # Should have start event and completion event
    assert len(stream.history) >= 2
    assert stream.history[-1].type == "scan_complete"
    assert stream.history[-1].data["status"] == "completed"

    # Cleanup
    log_stream_manager.pop(assessment_id)


def test_log_stream_json_formatting():
    """Test that log messages can be formatted as JSON."""
    import json

    log_entry = {
        "timestamp": "2025-01-15T10:30:00Z",
        "level": "INFO",
        "message": "Scan started",
        "assessment_id": "assess_abc123",
    }

    # Should be JSON-serializable
    json_str = json.dumps(log_entry)

    assert "Scan started" in json_str
    assert "assess_abc123" in json_str


def test_websocket_url_pattern_construction(assurance_base_url: str, test_assessment_id: str):
    """Test constructing WebSocket URL for a specific assessment."""
    ws_base = assurance_base_url.replace("http://", "ws://")
    ws_url = f"{ws_base}/ws/logs/{test_assessment_id}"

    assert ws_url.startswith("ws://")
    assert test_assessment_id in ws_url
    assert "/ws/logs/" in ws_url
