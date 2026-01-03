"""Smoke tests for scan submission endpoints.

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


def test_scan_endpoint_accepts_valid_request(
    http_session: requests.Session,
    assurance_base_url: str,
    mock_scan_request: dict,
    request_timeout: int,
):
    """Test that POST /scan accepts a valid scan request."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    response = http_session.post(
        f"{assurance_base_url}/scan",
        json=mock_scan_request,
        timeout=request_timeout,
    )

    # Should return 200 OK or 202 Accepted
    assert response.status_code in [200, 202]
    data = response.json()

    # Response should include key identifiers
    assert "assessment_id" in data
    assert "workspace_id" in data
    assert "component_id" in data
    assert "status" in data

    # Status should be queued or running
    assert data["status"] in ["queued", "running", "completed"]


def test_scan_endpoint_rejects_missing_workspace_id(
    http_session: requests.Session,
    assurance_base_url: str,
    mock_scan_request: dict,
    request_timeout: int,
):
    """Test that POST /scan rejects requests without workspace_id."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    invalid_request = mock_scan_request.copy()
    del invalid_request["workspace_id"]

    response = http_session.post(
        f"{assurance_base_url}/scan",
        json=invalid_request,
        timeout=request_timeout,
    )

    # Should return 422 Unprocessable Entity (validation error)
    assert response.status_code == 422


def test_scan_endpoint_rejects_missing_component_id(
    http_session: requests.Session,
    assurance_base_url: str,
    mock_scan_request: dict,
    request_timeout: int,
):
    """Test that POST /scan rejects requests without component_id."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    invalid_request = mock_scan_request.copy()
    del invalid_request["component_id"]

    response = http_session.post(
        f"{assurance_base_url}/scan",
        json=invalid_request,
        timeout=request_timeout,
    )

    assert response.status_code == 422


def test_scan_endpoint_rejects_missing_repository_url(
    http_session: requests.Session,
    assurance_base_url: str,
    mock_scan_request: dict,
    request_timeout: int,
):
    """Test that POST /scan rejects requests without repository_url."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    invalid_request = mock_scan_request.copy()
    del invalid_request["repository_url"]

    response = http_session.post(
        f"{assurance_base_url}/scan",
        json=invalid_request,
        timeout=request_timeout,
    )

    assert response.status_code == 422


def test_scan_endpoint_accepts_optional_manifest(
    http_session: requests.Session,
    assurance_base_url: str,
    mock_scan_request: dict,
    request_timeout: int,
):
    """Test that manifest parameter is optional."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    request_without_manifest = mock_scan_request.copy()
    if "manifest" in request_without_manifest:
        del request_without_manifest["manifest"]

    response = http_session.post(
        f"{assurance_base_url}/scan",
        json=request_without_manifest,
        timeout=request_timeout,
    )

    # Should still accept the request
    assert response.status_code in [200, 202]
