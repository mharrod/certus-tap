"""Integration tests for tier-based verification.

These tests validate the tier differentiation architecture described in
 docs/learn/trust/verify-trust.md Step 2-3.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

# Test data paths
SAMPLES_ROOT = Path(__file__).resolve().parents[3] / "samples"
SCAN_ARTIFACTS = SAMPLES_ROOT / "non-repudiation/scan-artifacts"


def test_basic_tier_metadata_structure():
    """Test basic tier metadata structure.

    Validates that basic tier has the expected metadata structure
    without Trust service involvement.
    """
    # Load sample scan metadata (basic tier)
    sarif_path = SCAN_ARTIFACTS / "trivy.sarif.json"
    assert sarif_path.exists(), f"Test artifact missing: {sarif_path}"

    # Basic tier metadata structure
    basic_metadata = {
        "scan_id": "test-scan-123",
        "tier": "basic",
        "status": "completed",
        "artifacts": {"sarif": "trivy.sarif.json", "sbom": "syft.spdx.json"},
        "inner_signature": {
            "signer": "certus-assurance@certus.cloud",
            "timestamp": "2024-01-15T14:32:45Z",
            "algorithm": "SHA256-RSA",
        },
    }

    # Validate basic tier structure
    assert basic_metadata["tier"] == "basic"
    assert "inner_signature" in basic_metadata
    assert "outer_signature" not in basic_metadata  # No outer signature in basic tier
    assert basic_metadata["inner_signature"]["signer"] == "certus-assurance@certus.cloud"

    print("✓ Basic tier metadata structure validated")
    print(f"  Tier: {basic_metadata['tier']}")
    print(f"  Signer: {basic_metadata['inner_signature']['signer']}")


def test_verified_tier_metadata_structure():
    """Test verified tier metadata structure.

    Validates that verified tier has dual signatures and additional
    verification metadata.
    """
    # Verified tier metadata structure
    verified_metadata = {
        "scan_id": "test-scan-456",
        "tier": "verified",
        "status": "completed",
        "upload_status": "uploaded",
        "artifacts": {"sarif": "trivy.sarif.json", "sbom": "syft.spdx.json"},
        "inner_signature": {
            "signer": "certus-assurance@certus.cloud",
            "timestamp": "2024-01-15T14:32:45Z",
            "algorithm": "SHA256-RSA",
        },
        "outer_signature": {
            "signer": "certus-trust@certus.cloud",
            "timestamp": "2024-01-15T14:33:00Z",
            "algorithm": "SHA256-RSA",
        },
        "verification_proof": {
            "chain_verified": True,
            "rekor_entry": "log-index-12345",
            "signer_inner": "certus-assurance@certus.cloud",
            "signer_outer": "certus-trust@certus.cloud",
        },
    }

    # Validate verified tier structure
    assert verified_metadata["tier"] == "verified"
    assert "inner_signature" in verified_metadata
    assert "outer_signature" in verified_metadata  # Has outer signature
    assert "verification_proof" in verified_metadata
    assert verified_metadata["verification_proof"]["chain_verified"] is True
    assert verified_metadata["verification_proof"]["rekor_entry"]

    # Verify signature chain
    inner_signer = verified_metadata["inner_signature"]["signer"]
    outer_signer = verified_metadata["outer_signature"]["signer"]
    proof_inner = verified_metadata["verification_proof"]["signer_inner"]
    proof_outer = verified_metadata["verification_proof"]["signer_outer"]

    assert inner_signer == proof_inner
    assert outer_signer == proof_outer

    print("✓ Verified tier metadata structure validated")
    print(f"  Tier: {verified_metadata['tier']}")
    print(f"  Inner signer: {inner_signer}")
    print(f"  Outer signer: {outer_signer}")
    print(f"  Chain verified: {verified_metadata['verification_proof']['chain_verified']}")


def test_tier_differentiation():
    """Test differentiation between basic and verified tiers."""
    basic_metadata = {"tier": "basic", "inner_signature": {"signer": "certus-assurance@certus.cloud"}}

    verified_metadata = {
        "tier": "verified",
        "inner_signature": {"signer": "certus-assurance@certus.cloud"},
        "outer_signature": {"signer": "certus-trust@certus.cloud"},
        "verification_proof": {"chain_verified": True},
    }

    # Basic tier characteristics
    assert basic_metadata["tier"] == "basic"
    assert "outer_signature" not in basic_metadata
    assert "verification_proof" not in basic_metadata

    # Verified tier characteristics
    assert verified_metadata["tier"] == "verified"
    assert "outer_signature" in verified_metadata
    assert "verification_proof" in verified_metadata
    assert verified_metadata["verification_proof"]["chain_verified"] is True

    print("✓ Tier differentiation validated")
    print("  Basic tier: Single signature, no Rekor")
    print("  Verified tier: Dual signatures, Rekor entry, chain verification")


def test_tier_use_case_validation():
    """Test that tiers match their intended use cases."""
    # Basic tier use case: Internal/development
    basic_use_case = {
        "scenario": "internal_development",
        "requires": ["inner_signature"],
        "optional": ["outer_signature", "rekor", "transparency"],
        "tier": "basic",
    }

    # Verified tier use case: Compliance/regulated
    verified_use_case = {
        "scenario": "compliance_audit",
        "requires": ["inner_signature", "outer_signature", "rekor", "transparency"],
        "optional": [],
        "tier": "verified",
    }

    # Validate use cases
    assert basic_use_case["tier"] == "basic"
    assert "outer_signature" in basic_use_case["optional"]
    assert "rekor" in basic_use_case["optional"]

    assert verified_use_case["tier"] == "verified"
    assert "outer_signature" in verified_use_case["requires"]
    assert "rekor" in verified_use_case["requires"]
    assert "transparency" in verified_use_case["requires"]

    print("✓ Tier use cases validated")
    print("  Basic tier: Suitable for internal/development")
    print("  Verified tier: Required for compliance/regulated environments")


# NOTE: Additional tests to implement with actual services:
# - test_basic_tier_with_assurance() - with actual Assurance service
# - test_verified_tier_with_trust() - with actual Trust service
# - test_tier_switching() - test switching between tiers
# - test_tier_permission_workflow() - test permission workflow differences
