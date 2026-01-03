"""Smoke tests for Certus Assurance health endpoints.

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
        return response.status_code in [200, 404]  # Service is up
    except requests.exceptions.ConnectionError:
        return False


def test_health_endpoint_returns_ok(http_session: requests.Session, assurance_base_url: str, request_timeout: int):
    """Test that the /health endpoint returns 200 OK."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    response = http_session.get(f"{assurance_base_url}/health", timeout=request_timeout)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "healthy"]


def test_health_endpoint_includes_scanning_mode(
    http_session: requests.Session, assurance_base_url: str, request_timeout: int
):
    """Test that health endpoint reports scanning mode."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    response = http_session.get(f"{assurance_base_url}/health", timeout=request_timeout)

    assert response.status_code == 200
    data = response.json()
    assert "scanning_mode" in data
    assert data["scanning_mode"] in ["sample", "production"]


def test_health_endpoint_includes_security_module_status(
    http_session: requests.Session, assurance_base_url: str, request_timeout: int
):
    """Test that health endpoint reports security_module availability."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    response = http_session.get(f"{assurance_base_url}/health", timeout=request_timeout)

    assert response.status_code == 200
    data = response.json()
    assert "security_module_available" in data
    assert data["security_module_available"] in ["True", "False"]


def test_health_endpoint_responds_quickly(
    http_session: requests.Session, assurance_base_url: str, request_timeout: int
):
    """Test that health endpoint responds in under 2 seconds."""
    if not check_service_available(assurance_base_url):
        pytest.skip("Service not available")

    response = http_session.get(f"{assurance_base_url}/health", timeout=2)

    assert response.status_code == 200
    assert response.elapsed.total_seconds() < 2
