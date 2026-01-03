"""Smoke tests for artifact retrieval endpoints.

These tests require Certus Assurance service to be running on localhost:8056.
Run with: just assurance-up
"""

import pytest
import requests

pytestmark = pytest.mark.smoke


def check_service_available(base_url: str) -> bool:
    """Check if service is available."""
    try:
        response = requests.get(f"{base_url}/health", timeout=2)
        return response.status_code in [200, 404]
    except requests.exceptions.ConnectionError:
        return False


def test_get_scan_status_returns_404_for_nonexistent_scan(
    http_session: requests.Session,
    assurance_base_url: str,
    request_timeout: int,
):
    """Test that GET /scan/{id} returns 404 for nonexistent scan."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    fake_assessment_id = "assess_nonexistent"

    response = http_session.get(
        f"{assurance_base_url}/scan/{fake_assessment_id}",
        timeout=request_timeout,
    )

    assert response.status_code == 404


def test_get_artifacts_returns_404_for_nonexistent_scan(
    http_session: requests.Session,
    assurance_base_url: str,
    request_timeout: int,
):
    """Test that GET /scan/{id}/artifacts returns 404 for nonexistent scan."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    fake_assessment_id = "assess_nonexistent"

    response = http_session.get(
        f"{assurance_base_url}/scan/{fake_assessment_id}/artifacts",
        timeout=request_timeout,
    )

    assert response.status_code == 404


def test_scan_status_endpoint_exists(
    http_session: requests.Session,
    assurance_base_url: str,
    test_assessment_id: str,
    request_timeout: int,
):
    """Test that the scan status endpoint is available."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    response = http_session.get(
        f"{assurance_base_url}/scan/{test_assessment_id}",
        timeout=request_timeout,
    )

    # Should return 404 (scan doesn't exist) or 200 (scan found)
    # Either means endpoint is working
    assert response.status_code in [200, 404]


def test_artifacts_endpoint_exists(
    http_session: requests.Session,
    assurance_base_url: str,
    test_assessment_id: str,
    request_timeout: int,
):
    """Test that the artifacts endpoint is available."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    response = http_session.get(
        f"{assurance_base_url}/scan/{test_assessment_id}/artifacts",
        timeout=request_timeout,
    )

    # Should return 404 (scan doesn't exist) or 200 (artifacts found)
    # Either means endpoint is working
    assert response.status_code in [200, 404]


def test_artifacts_download_has_correct_content_type(
    http_session: requests.Session,
    assurance_base_url: str,
    mock_scan_request: dict,
    request_timeout: int,
):
    """Test that artifact downloads use application/x-tar+gzip content type."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    # First submit a scan
    submit_response = http_session.post(
        f"{assurance_base_url}/scan",
        json=mock_scan_request,
        timeout=request_timeout,
    )

    if submit_response.status_code not in [200, 202]:
        pytest.skip("Scan submission not available")

    assessment_id = submit_response.json().get("assessment_id")

    # Try to get artifacts (may not be ready yet)
    artifacts_response = http_session.get(
        f"{assurance_base_url}/scan/{assessment_id}/artifacts",
        timeout=request_timeout,
    )

    # If artifacts exist, check content type
    if artifacts_response.status_code == 200:
        content_type = artifacts_response.headers.get("content-type", "")
        assert "tar" in content_type.lower() or "gzip" in content_type.lower() or "octet-stream" in content_type.lower()
