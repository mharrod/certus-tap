"""Smoke tests for certus_transform service health.

These tests validate:
- Service startup and basic connectivity
- Health endpoint functionality
- Stats endpoint functionality
- Essential service dependencies

These tests should be run before integration tests to ensure the service is operational.
"""

import pytest
import requests


def test_service_responds_to_health_check(
    http_session: requests.Session, transform_base_url: str, request_timeout: int
) -> None:
    """Test that service responds to basic health check.

    Tutorial: docs/learn/transform/getting-started.md
    Validates: Service is running and responding
    """
    response = http_session.get(
        f"{transform_base_url}/health",
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Transform service not available")

    response.raise_for_status()
    data = response.json()

    assert "status" in data
    assert data["status"] == "ok"


def test_health_stats_endpoint_exists(
    http_session: requests.Session, transform_base_url: str, request_timeout: int
) -> None:
    """Test that stats endpoint exists and returns data.

    Tutorial: docs/learn/transform/getting-started.md
    Validates: Stats endpoint implemented (ENHANCEMENTS.md Feature #1)
    """
    response = http_session.get(
        f"{transform_base_url}/health/stats",
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Stats endpoint not available")

    response.raise_for_status()
    data = response.json()

    # Verify all required stats fields exist
    assert "total_uploads" in data
    assert "successful_uploads" in data
    assert "failed_uploads" in data
    assert "privacy_scans" in data
    assert "artifacts_quarantined" in data
    assert "promotion_stats" in data
    assert "uptime_seconds" in data
    assert "timestamp" in data


def test_stats_fields_are_numeric(
    http_session: requests.Session, transform_base_url: str, request_timeout: int
) -> None:
    """Test that stats fields contain numeric values.

    Validates: Stats counters are properly initialized
    """
    response = http_session.get(
        f"{transform_base_url}/health/stats",
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Stats endpoint not available")

    response.raise_for_status()
    data = response.json()

    # Numeric fields
    assert isinstance(data["total_uploads"], int)
    assert isinstance(data["successful_uploads"], int)
    assert isinstance(data["failed_uploads"], int)
    assert isinstance(data["privacy_scans"], int)
    assert isinstance(data["artifacts_quarantined"], int)
    assert isinstance(data["uptime_seconds"], (int, float))

    # Nested promotion stats
    assert isinstance(data["promotion_stats"], dict)
    assert "successful" in data["promotion_stats"]
    assert "failed" in data["promotion_stats"]


def test_stats_counters_non_negative(
    http_session: requests.Session, transform_base_url: str, request_timeout: int
) -> None:
    """Test that stats counters are non-negative.

    Validates: Counters properly initialized (not corrupted)
    """
    response = http_session.get(
        f"{transform_base_url}/health/stats",
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Stats endpoint not available")

    response.raise_for_status()
    data = response.json()

    assert data["total_uploads"] >= 0
    assert data["successful_uploads"] >= 0
    assert data["failed_uploads"] >= 0
    assert data["privacy_scans"] >= 0
    assert data["artifacts_quarantined"] >= 0
    assert data["uptime_seconds"] >= 0
    assert data["promotion_stats"]["successful"] >= 0
    assert data["promotion_stats"]["failed"] >= 0


def test_uptime_increases_over_time(
    http_session: requests.Session, transform_base_url: str, request_timeout: int
) -> None:
    """Test that uptime counter increases over time.

    Validates: Uptime calculation working correctly
    """
    import time

    # Get first uptime reading
    response1 = http_session.get(
        f"{transform_base_url}/health/stats",
        timeout=request_timeout,
    )

    if response1.status_code == 404:
        pytest.skip("Stats endpoint not available")

    response1.raise_for_status()
    uptime1 = response1.json()["uptime_seconds"]

    # Wait 2 seconds
    time.sleep(2)

    # Get second uptime reading
    response2 = http_session.get(
        f"{transform_base_url}/health/stats",
        timeout=request_timeout,
    )
    response2.raise_for_status()
    uptime2 = response2.json()["uptime_seconds"]

    # Uptime should have increased by at least 1 second
    assert uptime2 > uptime1
    assert (uptime2 - uptime1) >= 1.0


def test_all_routers_registered(http_session: requests.Session, transform_base_url: str, request_timeout: int) -> None:
    """Test that all expected routers are registered.

    Validates: Service properly configured with all endpoints
    Expected routers: health, uploads, privacy, promotion, verification, ingest
    """
    response = http_session.get(
        f"{transform_base_url}/openapi.json",
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("OpenAPI schema not available")

    response.raise_for_status()
    openapi = response.json()

    paths = openapi.get("paths", {})

    # Check for key endpoints from each router
    assert "/health" in paths, "Health router not registered"
    assert "/health/stats" in paths, "Stats endpoint not registered"
    assert any("/uploads" in path for path in paths), "Uploads router not registered"
    assert any("/privacy" in path for path in paths), "Privacy router not registered"
    assert any("/promotions" in path for path in paths), "Promotion router not registered"
    assert any("/execute-upload" in path for path in paths), "Verification router not registered"
    assert any("/ingest" in path for path in paths), "Ingest router not registered"


def test_service_has_proper_title_and_version(
    http_session: requests.Session, transform_base_url: str, request_timeout: int
) -> None:
    """Test that service has correct title and version.

    Validates: Service identity configured correctly
    """
    response = http_session.get(
        f"{transform_base_url}/openapi.json",
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("OpenAPI schema not available")

    response.raise_for_status()
    openapi = response.json()

    info = openapi.get("info", {})
    assert "title" in info
    assert "version" in info
    assert "Certus" in info["title"]  # Should contain "Certus" in title


def test_endpoints_return_proper_content_type(
    http_session: requests.Session, transform_base_url: str, request_timeout: int
) -> None:
    """Test that endpoints return JSON content type.

    Validates: Proper HTTP response headers
    """
    response = http_session.get(
        f"{transform_base_url}/health",
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Transform service not available")

    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    assert "application/json" in content_type.lower()


def test_error_responses_return_proper_status_codes(
    http_session: requests.Session, transform_base_url: str, request_timeout: int
) -> None:
    """Test that invalid requests return proper HTTP status codes.

    Validates: Error handling implemented correctly
    """
    # Test 404 for non-existent endpoint
    response = http_session.get(
        f"{transform_base_url}/nonexistent",
        timeout=request_timeout,
    )

    assert response.status_code == 404

    # Test 405 for wrong HTTP method (if GET /execute-upload exists)
    response = http_session.get(
        f"{transform_base_url}/v1/execute-upload",
        timeout=request_timeout,
    )

    # Should be 404 (endpoint doesn't exist for GET) or 405 (method not allowed)
    assert response.status_code in [404, 405]
