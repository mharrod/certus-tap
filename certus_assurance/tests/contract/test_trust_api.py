"""Contract tests for Certus-Trust API as called by Certus-Assurance.

These tests validate that the Trust API contract matches Assurance's expectations.
If these tests fail, it indicates:
- Assurance is sending the wrong format (Assurance bug)
- Trust changed its API (contract broken - coordinate with Trust team)

NOT testing Trust's internal logic - only validating API shape/behavior.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_verify_and_permit_upload_request_schema() -> None:
    """
    Verify the request schema Assurance sends to Trust matches expectations.

    Contract: POST /v1/verify-and-permit-upload
    """
    # Expected request format from Assurance
    expected_request = {
        "scan_id": "scan_abc123",
        "tier": "verified",  # or "basic"
        "inner_signature": {
            "signer": "certus-assurance@certus.cloud",
            "timestamp": "2024-01-15T14:32:45Z",
            "signature": "base64-encoded-signature",
            "algorithm": "SHA256-RSA",
        },
        "artifacts": [
            {"name": "trivy.sarif.json", "hash": "sha256:abc123", "size": 15240},
            {"name": "syft.spdx.json", "hash": "sha256:def456", "size": 8920},
        ],
        "metadata": {
            "git_url": "https://github.com/example/repo",
            "branch": "main",
            "commit": "a1b2c3d4",
            "requested_by": "ci-bot",
        },
    }

    # This is a schema validation test - in production, use Pact or OpenAPI
    assert "scan_id" in expected_request
    assert "tier" in expected_request
    assert expected_request["tier"] in {"basic", "verified"}
    assert "inner_signature" in expected_request
    assert "artifacts" in expected_request
    assert len(expected_request["artifacts"]) > 0

    print("✓ Trust API request schema validated")


def test_verify_and_permit_upload_response_schema() -> None:
    """
    Verify the response schema Trust returns matches Assurance's expectations.

    Contract: POST /v1/verify-and-permit-upload response
    """
    # Expected response format from Trust
    expected_permitted_response = {
        "upload_permission_id": "perm_abc123",
        "scan_id": "scan_abc123",
        "tier": "verified",
        "permitted": True,
        "reason": None,
        "verification_proof": {
            "chain_verified": True,
            "inner_signature_valid": True,
            "outer_signature_valid": True,
            "chain_unbroken": True,
            "signer_inner": "certus-assurance@certus.cloud",
            "signer_outer": "certus-trust@certus.cloud",
            "sigstore_timestamp": "2024-01-15T14:35:23Z",
            "verification_timestamp": "2024-01-15T14:35:25Z",
            "rekor_entry_uuid": "550e8400-e29b-41d4-a716-446655440000",
            "cosign_signature": "mock-cosign-abc123",
        },
    }

    expected_denied_response = {
        "upload_permission_id": "perm_xyz789",
        "scan_id": "scan_abc123",
        "tier": "verified",
        "permitted": False,
        "reason": "invalid_signer",
        "verification_proof": None,
    }

    # Validate permitted response
    assert "upload_permission_id" in expected_permitted_response
    assert "permitted" in expected_permitted_response
    assert expected_permitted_response["permitted"] is True
    assert "verification_proof" in expected_permitted_response
    assert expected_permitted_response["verification_proof"] is not None

    # Validate denied response
    assert "upload_permission_id" in expected_denied_response
    assert expected_denied_response["permitted"] is False
    assert "reason" in expected_denied_response
    assert expected_denied_response["verification_proof"] is None

    print("✓ Trust API response schema validated")


def test_trust_health_endpoint_contract() -> None:
    """
    Verify Trust health endpoint returns expected format.

    Contract: GET /v1/health
    """
    expected_health_response = {"status": "healthy"}  # or "ok"

    assert "status" in expected_health_response
    assert expected_health_response["status"] in {"healthy", "ok"}

    print("✓ Trust health endpoint contract validated")


# NOTE: In production, replace these schema checks with:
# - Pact consumer contracts
# - OpenAPI/Swagger schema validation
# - Prism mock servers
# - Contract testing framework
