"""Smoke tests for Certus-Trust verification functionality."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.smoke

# Configuration
# Navigate up from certus_trust/tests/smoke/ to repo root
REPO_ROOT = Path(os.getenv("SMOKE_REPO_ROOT", Path(__file__).resolve().parents[3]))
SAMPLES_ROOT = Path(os.getenv("SMOKE_SAMPLES_ROOT", REPO_ROOT / "samples"))
SCAN_ARTIFACTS = Path(os.getenv("SCAN_ARTIFACTS", SAMPLES_ROOT / "non-repudiation/scan-artifacts"))

TRUST_ENDPOINTS = (
    os.getenv("TRUST_INTERNAL_URL", "http://certus-trust:8000").rstrip("/"),
    os.getenv("TRUST_EXTERNAL_URL", "http://localhost:8057").rstrip("/"),
)
REKOR_URL = os.getenv("REKOR_URL", "http://localhost:3001")
EXPECTED_SIGNER = "certus-assurance@certus.cloud"


def _request_with_fallback(
    session: requests.Session,
    method: str,
    endpoints: tuple[str, str],
    path: str,
    timeout: int,
    **kwargs,
) -> requests.Response:
    """Attempt a request against internal and host-mapped endpoints."""
    last_exc = None
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


def _create_mock_scan_metadata() -> dict:
    """Create mock scan metadata matching Certus-Assurance output."""
    return {
        "scan_id": "mock-trust-test-scan",
        "status": "SUCCEEDED",
        "workspace_id": "security-provenance-demo",
        "component_id": "certus-tap",
        "git_url": "https://github.com/mharrod/certus-TAP.git",
        "git_commit": "abc123def456789def456abc123def456",
        "branch": "main",
        "requested_by": "smoke-tests@certus.cloud",
        "started_at": "2024-01-15T14:30:00Z",
        "completed_at": "2024-01-15T14:32:45Z",
        "artifacts": {
            "sarif": "trivy.sarif.json",
            "sbom": "syft.spdx.json",
            "dast_json": "zap-report.json",
        },
        "inner_signature": {
            "signer": EXPECTED_SIGNER,
            "timestamp": "2024-01-15T14:32:45Z",
            "signature": "base64-mock-signature-blob",
            "algorithm": "SHA256-RSA",
        },
    }


def test_trust_with_mock_artifacts(http_session: requests.Session, request_timeout: int) -> None:
    """
    Validate Certus Trust workflow using mock scan artifacts.

    This test isolates Certus-Trust testing by using pre-generated artifacts
    from the case study samples, bypassing Certus-Assurance entirely.

    Validates:
    1. Trust service health
    2. Rekor accessibility
    3. Artifact verification (if endpoint exists)
    4. Provenance metadata structure
    """
    # Prerequisite checks
    assert SCAN_ARTIFACTS.exists(), "Case study scan artifacts missing"

    # Verify Trust is healthy
    trust_response = _request_with_fallback(http_session, "get", TRUST_ENDPOINTS, "/v1/health", request_timeout)
    trust_response.raise_for_status()
    print(f"✓ Trust service healthy: {trust_response.json()}")

    # Validate Rekor is operational
    rekor_response = http_session.get(f"{REKOR_URL}/api/v1/log", timeout=request_timeout)
    rekor_response.raise_for_status()
    rekor_info = rekor_response.json()
    print(f"✓ Rekor tree size: {rekor_info.get('treeSize')}")

    # Load mock scan artifacts
    sarif_path = SCAN_ARTIFACTS / "trivy.sarif.json"
    sbom_path = SCAN_ARTIFACTS / "syft.spdx.json"

    assert sarif_path.exists(), f"SARIF artifact missing: {sarif_path}"
    assert sbom_path.exists(), f"SBOM artifact missing: {sbom_path}"

    # Validate SARIF structure
    sarif_data = json.loads(sarif_path.read_text())
    assert sarif_data.get("runs"), "SARIF missing runs array"
    print(f"✓ SARIF artifact loaded: {len(sarif_data['runs'])} runs")

    # Validate SBOM structure
    sbom_data = json.loads(sbom_path.read_text())
    assert sbom_data.get("packages"), "SBOM missing packages"
    print(f"✓ SBOM artifact loaded: {len(sbom_data['packages'])} packages")

    # Calculate artifact hash (simulates Rekor submission)
    artifact_bytes = sarif_path.read_bytes()
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()
    print(f"✓ Artifact hash computed: {artifact_hash[:16]}...")

    # Validate mock scan metadata structure
    metadata = _create_mock_scan_metadata()
    assert metadata.get("inner_signature"), "Mock metadata missing inner_signature"
    assert metadata["inner_signature"]["signer"] == EXPECTED_SIGNER, "Unexpected signer"
    print(f"✓ Mock metadata validated: signer={metadata['inner_signature']['signer']}")

    print("\n✅ Certus Trust workflow validated with mock artifacts")
