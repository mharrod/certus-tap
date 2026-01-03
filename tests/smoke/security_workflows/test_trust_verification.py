from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(os.getenv("SMOKE_REPO_ROOT", Path(__file__).resolve().parents[3]))
SAMPLES_ROOT = Path(os.getenv("SMOKE_SAMPLES_ROOT", REPO_ROOT / "samples"))
SCAN_ARTIFACTS = Path(os.getenv("SCAN_ARTIFACTS", SAMPLES_ROOT / "non-repudiation/scan-artifacts"))
ASSURANCE_ENDPOINTS = (
    os.getenv("ASSURANCE_INTERNAL_URL", "http://certus-assurance:8000").rstrip("/"),
    os.getenv("ASSURANCE_EXTERNAL_URL", "http://localhost:8056").rstrip("/"),
)
TRUST_ENDPOINTS = (
    os.getenv("TRUST_INTERNAL_URL", "http://certus-trust:8000").rstrip("/"),
    os.getenv("TRUST_EXTERNAL_URL", "http://localhost:8057").rstrip("/"),
)


# Check service availability at module level
def _check_service_available(url: str, timeout: int = 2) -> bool:
    """Check if a service is available."""
    try:
        requests.get(url, timeout=timeout)
        return True
    except (requests.RequestException, Exception):
        return False


ASSURANCE_AVAILABLE = any(_check_service_available(f"{endpoint}/health") for endpoint in ASSURANCE_ENDPOINTS)
TRUST_AVAILABLE = any(_check_service_available(f"{endpoint}/health") for endpoint in TRUST_ENDPOINTS)

SERVICES_AVAILABLE = ASSURANCE_AVAILABLE and TRUST_AVAILABLE
REQUESTED_BY = os.getenv("SMOKE_TRUST_REQUESTER", "smoke-tests@certus.cloud")
DEFAULT_GIT_URL = os.getenv("SMOKE_TRUST_REPO")
if not DEFAULT_GIT_URL:
    sample_repo = Path(os.getenv("SMOKE_TRUST_SAMPLE_REPO", "samples/trust-smoke-repo.git")).expanduser()
    # Relative paths allow both local uvicorn and Dockerized services to resolve the repo.
    DEFAULT_GIT_URL = sample_repo.as_posix()
DEFAULT_BRANCH = os.getenv("SMOKE_TRUST_BRANCH", "main")


def _request_with_fallback(
    session: requests.Session,
    method: str,
    endpoints: tuple[str, str],
    path: str,
    timeout: int,
    **kwargs: Any,
) -> requests.Response:
    """Attempt a request against internal and host-mapped endpoints."""
    last_exc: Exception | None = None
    for base in endpoints:
        url = f"{base}{path}"
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            continue
        return response

    if last_exc:
        raise last_exc
    raise AssertionError(f"All endpoints failed for {method} {path}")


def _submit_scan(session: requests.Session, timeout: int) -> str:
    payload = {
        "workspace_id": "smoke-test",
        "component_id": "certus-tap",
        "assessment_id": "smoke-assessment",
        "git_url": DEFAULT_GIT_URL,
        "branch": DEFAULT_BRANCH,
        "requested_by": REQUESTED_BY,
        "manifest": {"version": "1.0", "tools": ["bandit", "trivy"]},
    }
    response = _request_with_fallback(
        session,
        "post",
        ASSURANCE_ENDPOINTS,
        "/v1/security-scans",
        timeout,
        json=payload,
    )
    response.raise_for_status()
    scan_id = response.json().get("test_id")
    assert scan_id, "Certus-Assurance did not return test_id"
    return scan_id


def _fetch_scan(session: requests.Session, scan_id: str, timeout: int) -> dict[str, Any]:
    response = _request_with_fallback(
        session,
        "get",
        ASSURANCE_ENDPOINTS,
        f"/v1/security-scans/{scan_id}",
        timeout,
    )
    response.raise_for_status()
    return response.json()


def _await_status(
    session: requests.Session,
    scan_id: str,
    field: str,
    target: str,
    timeout: int,
    poll_interval: float = 2.0,
) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        data = _fetch_scan(session, scan_id, timeout)
        value = (data.get(field) or "").lower()
        if value == target.lower():
            return data
        if value in {"failed", "denied", "upload_failed"}:
            pytest.fail(f"Scan {scan_id} reached terminal state '{value}' with payload: {data}")
        time.sleep(poll_interval)
    pytest.fail(f"Timed out waiting for {field}={target} on scan {scan_id}")


def _request_upload(session: requests.Session, scan_id: str, timeout: int) -> dict[str, Any]:
    response = _request_with_fallback(
        session,
        "post",
        ASSURANCE_ENDPOINTS,
        f"/v1/security-scans/{scan_id}/upload-request",
        timeout,
        json={"tier": "verified", "requested_by": REQUESTED_BY},
    )
    response.raise_for_status()
    return response.json()


def _check_trust_health(session: requests.Session, timeout: int) -> None:
    response = _request_with_fallback(
        session,
        "get",
        TRUST_ENDPOINTS,
        "/v1/health",
        timeout,
    )
    response.raise_for_status()
    payload = response.json()
    assert payload.get("status") in {"healthy", "ok"}, f"Unexpected Trust health payload: {payload}"


@pytest.mark.skipif(not SERVICES_AVAILABLE, reason="Certus-Assurance or Certus-Trust service not available")
def test_trust_verification_flow(http_session: requests.Session, request_timeout: int) -> None:
    """
    Mirror docs/learn/provenance/trust-verification.md.

    Validates the verification-first workflow against live Certus-Assurance + Trust services.
    """
    assert SCAN_ARTIFACTS.exists(), "Non-repudiation sample artifacts missing"
    _check_trust_health(http_session, request_timeout)

    scan_id = _submit_scan(http_session, request_timeout)
    scan_data = _await_status(http_session, scan_id, "status", "SUCCEEDED", timeout=request_timeout * 3)
    assert scan_data.get("status") == "SUCCEEDED", f"Scan did not finish successfully: {scan_data}"

    upload_ack = _request_upload(http_session, scan_id, request_timeout)
    assert upload_ack.get("upload_permission_id"), "Upload request did not return permission identifier"
    assert upload_ack.get("upload_status") in {"pending", "permitted", "uploaded"}, (
        f"Unexpected initial upload status: {upload_ack}"
    )

    upload_data = _await_status(http_session, scan_id, "upload_status", "uploaded", timeout=request_timeout * 3)
    assert upload_data.get("upload_permission_id"), "Upload permission was not persisted on scan status"

    verification_proof = upload_data.get("verification_proof") or {}
    assert verification_proof.get("chain_verified"), "Verification proof missing chain_verified flag"
    assert verification_proof.get("signer_inner") == "certus-assurance@certus.cloud", (
        f"Unexpected signer in verification proof: {verification_proof}"
    )

    remote_artifacts = upload_data.get("remote_artifacts") or {}
    assert isinstance(remote_artifacts, dict) and remote_artifacts, "S3 upload results missing for verified scan"
    assert any(key.endswith(".sarif.json") for key in remote_artifacts), (
        "Expected SARIF artifact not uploaded to S3"
    )
