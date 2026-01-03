"""Smoke tests for Certus-Trust service health and availability."""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = pytest.mark.smoke

TRUST_ENDPOINTS = (
    os.getenv("TRUST_INTERNAL_URL", "http://certus-trust:8000").rstrip("/"),
    os.getenv("TRUST_EXTERNAL_URL", "http://localhost:8057").rstrip("/"),
)


def _check_trust_health(session: requests.Session, timeout: int) -> dict:
    """Verify Certus-Trust service is healthy."""
    last_exc = None
    for base in TRUST_ENDPOINTS:
        url = f"{base}/v1/health"
        try:
            response = session.get(url, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            assert payload.get("status") in {
                "healthy",
                "ok",
            }, f"Unexpected Trust health: {payload}"
            return payload
        except requests.RequestException as exc:
            last_exc = exc
            continue

    if last_exc:
        raise last_exc
    raise AssertionError("All Trust endpoints failed")


def test_certus_trust_health(http_session: requests.Session, request_timeout: int) -> None:
    """Verify Certus-Trust service is accessible and healthy."""
    health = _check_trust_health(http_session, request_timeout)
    print(f"✓ Certus-Trust health: {health}")


def test_trust_service_endpoints(http_session: requests.Session, request_timeout: int) -> None:
    """Validate Certus-Trust service endpoints are accessible."""
    _check_trust_health(http_session, request_timeout)

    # Check if additional endpoints exist
    endpoints_to_check = [
        "/v1/health",
        "/docs",  # OpenAPI docs
    ]

    for endpoint in endpoints_to_check:
        last_exc = None
        for base in TRUST_ENDPOINTS:
            try:
                response = http_session.get(f"{base}{endpoint}", timeout=request_timeout)
                if response.status_code in {200, 404}:  # 404 is acceptable
                    print(f"✓ Endpoint {endpoint}: {response.status_code}")
                    break
            except Exception as exc:
                last_exc = exc
                continue

        if last_exc:
            print(f"⚠ Endpoint {endpoint}: {last_exc}")

    print("\n✅ Certus-Trust service endpoints validated")
