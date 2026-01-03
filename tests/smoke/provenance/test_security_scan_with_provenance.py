from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest
import requests

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(os.getenv("SMOKE_REPO_ROOT", Path(__file__).resolve().parents[3]))
SAMPLES_ROOT = Path(os.getenv("SMOKE_SAMPLES_ROOT", REPO_ROOT / "samples"))
ASSURANCE_ENDPOINTS = (
    os.getenv("ASSURANCE_INTERNAL_URL", "http://certus-assurance:8000").rstrip("/"),
    os.getenv("ASSURANCE_EXTERNAL_URL", "http://localhost:8056").rstrip("/"),
)


# Check service availability at module level
def _check_assurance_available() -> bool:
    """Check if Certus-Assurance service is available."""
    for endpoint in ASSURANCE_ENDPOINTS:
        try:
            response = requests.get(f"{endpoint}/health", timeout=2)
            if response.status_code < 500:  # Service responded
                return True
        except (requests.RequestException, Exception):
            continue
    return False


ASSURANCE_AVAILABLE = _check_assurance_available()
ARTIFACT_ROOT = Path(os.getenv("ARTIFACT_ROOT", REPO_ROOT / ".artifacts/certus-assurance"))
CASE_STUDY_SOURCE = Path(os.getenv("CASE_STUDY_SOURCE", SAMPLES_ROOT / "non-repudiation/scan-artifacts"))
EXPECTED_REPORTS = {
    "sarif": Path("reports/sast/trivy.sarif.json"),
    "sbom": Path("reports/sbom/syft.spdx.json"),
    "dast_json": Path("reports/dast/zap-report.json"),
}
EXPECTED_SIGNER = "certus-assurance@certus.cloud"


def _request_with_fallback(
    session: requests.Session,
    method: str,
    path: str,
    timeout: int,
    **kwargs: Any,
) -> requests.Response:
    last_exc: Exception | None = None
    for base in ASSURANCE_ENDPOINTS:
        url = f"{base}{path}"
        try:
            response = session.request(method, url, timeout=timeout, **kwargs)
        except requests.RequestException as exc:
            last_exc = exc
            continue
        return response
    if last_exc:
        raise last_exc
    raise AssertionError(f"All Assurance endpoints failed for {method} {path}")


def _submit_scan(session: requests.Session, timeout: int) -> str:
    payload = {
        "workspace_id": "smoke-test",
        "component_id": "certus-tap",
        "assessment_id": "smoke-assessment",
        "git_url": "https://github.com/octocat/Hello-World.git",
        "branch": "master",
        "requested_by": "smoke-tests@certus.cloud",
        "manifest": {"version": "1.0", "tools": ["bandit", "trivy"]},
    }
    response = _request_with_fallback(session, "post", "/v1/security-scans", timeout, json=payload)
    response.raise_for_status()
    scan_id = response.json().get("test_id")
    assert scan_id, "Certus-Assurance did not return test_id"
    return scan_id


def _fetch_scan(session: requests.Session, scan_id: str, timeout: int) -> dict[str, Any]:
    response = _request_with_fallback(session, "get", f"/v1/security-scans/{scan_id}", timeout)
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
        payload = _fetch_scan(session, scan_id, timeout)
        value = (payload.get(field) or "").lower()
        if value == target.lower():
            return payload
        if value in {"failed", "error"}:
            pytest.fail(f"Scan {scan_id} failed with payload: {payload}")
        time.sleep(poll_interval)
    pytest.fail(f"Timed out waiting for {field}={target} on scan {scan_id}")


def _validate_artifacts(scan_dir: Path) -> None:
    for rel_path in EXPECTED_REPORTS.values():
        target = scan_dir / rel_path
        assert target.exists(), f"Expected tutorial artifact missing: {target}"
        assert target.stat().st_size > 0, f"Artifact {target} is empty"


@pytest.mark.skipif(not ASSURANCE_AVAILABLE, reason="Certus-Assurance service not available")
def test_security_scan_with_provenance(http_session: requests.Session, request_timeout: int) -> None:
    """
    Mirror docs/learn/provenance/security-scan-with-provenance.md.

    Runs a mock scan via Certus-Assurance and validates provenance artifacts/signatures.
    """
    assert CASE_STUDY_SOURCE.exists(), "Case study samples missing; run from repo root with samples present"
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)

    scan_id = _submit_scan(http_session, request_timeout)
    scan_data = _await_status(http_session, scan_id, "status", "SUCCEEDED", timeout=request_timeout * 3)

    scan_dir = ARTIFACT_ROOT / scan_id
    assert scan_dir.exists(), f"Scan directory not created: {scan_dir}"

    metadata_path = scan_dir / "scan.json"
    assert metadata_path.exists(), f"scan.json missing for scan {scan_id}"
    metadata = json.loads(metadata_path.read_text())
    assert metadata.get("status") == "SUCCEEDED", f"Unexpected metadata status: {metadata}"
    assert metadata.get("git_url") == "https://github.com/octocat/Hello-World.git"

    inner_signature = metadata.get("inner_signature")
    if inner_signature:
        assert inner_signature.get("signer") == EXPECTED_SIGNER, f"Unexpected signer: {inner_signature}"
        assert inner_signature.get("signature"), "Inner signature missing signature blob"
        assert inner_signature.get("timestamp"), "Inner signature missing timestamp"
    else:
        attestations = metadata.get("artifacts", {}).get("attestations") or []
        assert attestations, "Scan metadata missing attestation reference when inner signature absent"
        for rel_path in attestations:
            attestation_file = scan_dir / rel_path
            assert attestation_file.exists(), f"Attestation file missing: {attestation_file}"
            assert attestation_file.stat().st_size > 0, f"Attestation file empty: {attestation_file}"

    _validate_artifacts(scan_dir)

    reported_artifacts = scan_data.get("artifacts") or {}
    for key, rel_path in EXPECTED_REPORTS.items():
        assert reported_artifacts.get(key) == rel_path.as_posix(), (
            f"Scan metadata missing {key} pointer; payload: {reported_artifacts}"
        )
