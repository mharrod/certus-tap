"""Integration tests for vendor review OCI registry workflow.

This test suite validates the OCI-based artifact distribution workflow described in
docs/learn/trust/vendor-review.md, including:

1. Pulling signed bundles from OCI registry
2. Validating artifact structure and contents
3. Comparing OCI vs S3 artifact sources

Tutorial reference: docs/learn/trust/vendor-review.md (Steps 1-2)
"""

from __future__ import annotations

import os
import subprocess

import pytest
import requests

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# Configuration
OCI_REGISTRY = os.getenv("OCI_REGISTRY", "localhost:5000")
OCI_REPOSITORY = "product-acquisition/attestations"
S3_ENDPOINT_URL = os.getenv("S3_ENDPOINT_URL", "http://localhost:4566")
ASSURANCE_URL = os.getenv("ASSURANCE_URL", "http://localhost:8056")

# Expected artifacts in OCI bundle
EXPECTED_ARTIFACTS = [
    "sbom/product.spdx.json",
    "scans/vulnerability.sarif",
    "attestations/build.intoto.json",
    "provenance/slsa-provenance.json",
    "verification-proof.json",
]


def _check_oras_available() -> bool:
    """Check if ORAS CLI is installed."""
    try:
        result = subprocess.run(
            ["oras", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def _check_cosign_available() -> bool:
    """Check if cosign CLI is installed."""
    try:
        result = subprocess.run(
            ["cosign", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def test_oras_cli_available() -> None:
    """Verify ORAS CLI is installed and accessible."""
    if not _check_oras_available():
        pytest.skip("ORAS CLI not installed")

    result = subprocess.run(
        ["oras", "version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "version" in result.stdout.lower()
    print(f"✓ ORAS version: {result.stdout.strip()}")


def test_cosign_cli_available() -> None:
    """Verify cosign CLI is installed and accessible."""
    if not _check_cosign_available():
        pytest.skip("cosign CLI not installed")

    result = subprocess.run(
        ["cosign", "version"],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    print(f"✓ cosign available: {result.stdout.strip()}")


def test_confirm_trust_verification_results(
    http_session: requests.Session,
) -> None:
    """
    Test Step 1: Confirm Trust verification results.

    Validates:
    - Scan status is SUCCEEDED
    - Upload status is "uploaded"
    - Verification proof exists
    - Upload permission ID exists
    """
    # TODO: This requires a completed scan from verify-trust workflow
    # For now, skip if no scan available
    pytest.skip("Requires completed scan with upload_status='uploaded'")

    # Example implementation when scan_id is available:
    # scan_id = os.getenv("TEST_SCAN_ID")
    # response = http_session.get(
    #     f"{ASSURANCE_URL}/v1/security-scans/{scan_id}"
    # )
    # response.raise_for_status()
    # scan_data = response.json()
    #
    # assert scan_data["status"] == "SUCCEEDED"
    # assert scan_data["upload_status"] == "uploaded"
    # assert scan_data["verification_proof"] is not None
    # assert scan_data["upload_permission_id"] is not None


def test_pull_signed_bundle_from_oci() -> None:
    """
    Test Step 2: Pull signed bundle from OCI registry.

    Validates:
    - ORAS pull succeeds
    - Expected directory structure created
    - All required artifacts present
    """
    if not _check_oras_available():
        pytest.skip("ORAS CLI not installed")

    # TODO: Requires OCI registry with pushed artifacts
    # This test validates the pull mechanism works
    pytest.skip("Requires OCI registry with test artifacts")

    # Example implementation:
    # scan_id = "test-scan-123"
    # output_dir = Path(f"/tmp/test-acquired-artifacts/{scan_id}")
    # output_dir.mkdir(parents=True, exist_ok=True)
    #
    # result = subprocess.run(
    #     [
    #         "oras", "pull", "--plain-http",
    #         f"{OCI_REGISTRY}/{OCI_REPOSITORY}:latest",
    #         "--output", str(output_dir),
    #     ],
    #     capture_output=True,
    #     text=True,
    # )
    #
    # assert result.returncode == 0, f"ORAS pull failed: {result.stderr}"
    #
    # # Verify expected artifacts
    # for artifact in EXPECTED_ARTIFACTS:
    #     artifact_path = output_dir / artifact
    #     assert artifact_path.exists(), f"Missing artifact: {artifact}"
    #
    # print(f"✓ OCI bundle pulled to {output_dir}")


def test_validate_oci_bundle_structure() -> None:
    """
    Validate pulled OCI bundle has expected structure.

    Validates:
    - Directory layout matches expected structure
    - Files are non-empty
    - JSON files are valid JSON
    """
    pytest.skip("Requires pulled OCI bundle - implement after test_pull_signed_bundle_from_oci")

    # Example implementation:
    # bundle_dir = Path("/tmp/test-acquired-artifacts/test-scan-123")
    #
    # # Check directories exist
    # assert (bundle_dir / "sbom").is_dir()
    # assert (bundle_dir / "scans").is_dir()
    # assert (bundle_dir / "attestations").is_dir()
    # assert (bundle_dir / "provenance").is_dir()
    #
    # # Validate JSON files
    # for artifact in EXPECTED_ARTIFACTS:
    #     if artifact.endswith(".json"):
    #         artifact_path = bundle_dir / artifact
    #         with artifact_path.open() as f:
    #             data = json.load(f)
    #         assert data, f"{artifact} is empty or invalid JSON"


def test_compare_oci_vs_s3_artifacts() -> None:
    """
    Compare artifacts from OCI vs S3 sources.

    Validates:
    - Same artifacts available in both locations
    - Content is identical
    - Hashes match
    """
    pytest.skip("Requires both OCI and S3 artifacts - implement when both sources ready")

    # Example implementation:
    # import hashlib
    # from boto3 import client
    #
    # s3_client = client("s3", endpoint_url=S3_ENDPOINT_URL)
    # scan_id = "test-scan-123"
    #
    # # Compare SBOM from OCI vs S3
    # oci_sbom = Path(f"/tmp/test-acquired-artifacts/{scan_id}/sbom/product.spdx.json")
    # oci_hash = hashlib.sha256(oci_sbom.read_bytes()).hexdigest()
    #
    # s3_response = s3_client.get_object(
    #     Bucket="raw",
    #     Key=f"security-scans/{scan_id}/{scan_id}/sbom/product.spdx.json"
    # )
    # s3_hash = hashlib.sha256(s3_response["Body"].read()).hexdigest()
    #
    # assert oci_hash == s3_hash, "OCI and S3 artifacts differ"


def test_verification_proof_structure() -> None:
    """
    Validate verification-proof.json structure.

    Validates:
    - Required fields present
    - Dual-signature chain (inner + outer)
    - Signer identities correct
    - Timestamps present
    """
    pytest.skip("Requires pulled OCI bundle with verification proof")

    # Example implementation:
    # proof_path = Path("/tmp/test-acquired-artifacts/test-scan-123/verification-proof.json")
    # with proof_path.open() as f:
    #     proof = json.load(f)
    #
    # # Validate required fields
    # assert proof["chain_verified"] is True
    # assert proof["inner_signature_valid"] is True
    # assert proof["outer_signature_valid"] is True
    # assert proof["signer_inner"] == "certus-assurance@certus.cloud"
    # assert proof["signer_outer"] == "certus-trust@certus.cloud"
    # assert "sigstore_timestamp" in proof
    # assert "verification_timestamp" in proof
    #
    # print("✓ Verification proof structure validated")


def test_oci_registry_health() -> None:
    """
    Verify OCI registry is accessible and healthy.

    Validates:
    - Registry responds to health check
    - Can list repositories
    """
    # Simple HTTP check to registry
    try:
        response = requests.get(
            f"http://{OCI_REGISTRY}/v2/",
            timeout=5,
        )
        # OCI registry returns 200 or 401 (if auth required)
        assert response.status_code in {200, 401}
        print(f"✓ OCI registry accessible at {OCI_REGISTRY}")
    except requests.RequestException as e:
        pytest.skip(f"OCI registry not accessible: {e}")


# NOTE: Additional tests to implement when OCI registry is fully set up:
# - test_pull_with_specific_tag()
# - test_pull_with_digest()
# - test_concurrent_pulls()
# - test_pull_large_bundle()
# - test_registry_authentication()
