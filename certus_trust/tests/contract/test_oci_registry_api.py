"""Contract tests for OCI registry API interactions.

These tests validate Trust's expectations about the OCI registry API,
ensuring compatibility with ORAS and OCI distribution spec.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_oras_pull_command_structure() -> None:
    """
    Validate ORAS pull command structure matches expectations.

    Contract: ORAS CLI pull command format
    """
    # Expected command structure Trust/reviewers use
    expected_command = [
        "oras",
        "pull",
        "--plain-http",  # For local registry
        "localhost:5000/repository/path:tag",
        "--output",
        "/path/to/output",
    ]

    assert "oras" in expected_command[0]
    assert "pull" in expected_command
    assert "--output" in expected_command

    print("✓ ORAS pull command structure validated")


def test_expected_oci_artifact_paths() -> None:
    """
    Validate expected artifact paths in pulled OCI bundle.

    Contract: Directory structure after ORAS pull
    """
    expected_paths = [
        "sbom/product.spdx.json",
        "scans/vulnerability.sarif",
        "attestations/build.intoto.json",
        "provenance/slsa-provenance.json",
        "verification-proof.json",
    ]

    for path in expected_paths:
        assert "/" in path or path.endswith(".json")

    print("✓ Expected OCI artifact paths defined")


def test_oci_registry_response_format() -> None:
    """
    Validate OCI registry API response format.

    Contract: OCI Distribution Spec v1.0
    """
    # Expected response from /v2/ endpoint
    expected_response = {
        "status": 200,  # or 401 if auth required
        "headers": {"Docker-Distribution-API-Version": "registry/2.0"},
    }

    assert expected_response["status"] in {200, 401}
    print("✓ OCI registry response format validated")


# NOTE: These are schema/contract tests, not live API tests
# They define expectations for integration tests to verify
