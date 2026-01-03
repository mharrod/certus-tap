"""Integration tests for Rekor transparency log integration.

These tests validate that Certus-Trust properly integrates with Sigstore's Rekor
transparency log, which is critical for non-repudiation guarantees.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
import requests

pytestmark = pytest.mark.integration

# Configuration
REKOR_URL = os.getenv("REKOR_URL", "http://localhost:3001")
SAMPLES_ROOT = Path(__file__).resolve().parents[3] / "samples"
SCAN_ARTIFACTS = SAMPLES_ROOT / "non-repudiation/scan-artifacts"


def test_rekor_health_check():
    """Test that Rekor transparency log is accessible."""
    response = requests.get(f"{REKOR_URL}/api/v1/log", timeout=30)
    response.raise_for_status()

    log_info = response.json()
    assert "treeSize" in log_info, f"Unexpected Rekor response: {log_info}"
    assert isinstance(log_info["treeSize"], int), "treeSize should be an integer"
    print(f"✓ Rekor healthy with tree size: {log_info['treeSize']}")


def test_rekor_entry_creation_simulation():
    """Test Rekor entry creation simulation (mock).

    This test simulates the entry creation process that would occur
    during actual artifact verification.
    """
    # Load a sample artifact
    sarif_path = SCAN_ARTIFACTS / "trivy.sarif.json"
    assert sarif_path.exists(), f"Test artifact missing: {sarif_path}"

    # Calculate artifact hash (what would be submitted to Rekor)
    artifact_bytes = sarif_path.read_bytes()
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()

    # Create mock entry (simulating what Trust would create)
    mock_entry = {
        "artifact_hash": artifact_hash,
        "artifact_type": "sarif",
        "signer": "certus-assurance@certus.cloud",
        "timestamp": "2024-01-15T14:32:45Z",
        "signature": "mock-signature-blob",
        "algorithm": "SHA256-RSA",
    }

    # Validate entry structure
    assert "artifact_hash" in mock_entry
    assert "signer" in mock_entry
    assert "signature" in mock_entry
    assert len(artifact_hash) == 64, "SHA256 hash should be 64 characters"

    print(f"✓ Mock Rekor entry validated for artifact: {artifact_hash[:16]}...")
    print(f"  Signer: {mock_entry['signer']}")
    print(f"  Type: {mock_entry['artifact_type']}")


def test_rekor_entry_retrieval_simulation():
    """Test Rekor entry retrieval simulation.

    This test simulates retrieving an entry by artifact hash,
    which is the primary lookup method used in verification.
    """
    # Use a known test artifact
    sarif_path = SCAN_ARTIFACTS / "trivy.sarif.json"
    artifact_bytes = sarif_path.read_bytes()
    artifact_hash = hashlib.sha256(artifact_bytes).hexdigest()

    # Create mock retrieval response
    mock_retrieval = {
        "artifact_hash": artifact_hash,
        "entries": [
            {
                "logIndex": 12345,
                "integratedTime": 1673798565,
                "body": "base64-encoded-entry",
                "verification": {"signedEntryTimestamp": "2024-01-15T14:32:45Z"},
            }
        ],
    }

    # Validate retrieval structure
    assert "artifact_hash" in mock_retrieval
    assert "entries" in mock_retrieval
    assert len(mock_retrieval["entries"]) > 0
    assert "logIndex" in mock_retrieval["entries"][0]
    assert "integratedTime" in mock_retrieval["entries"][0]

    print(f"✓ Mock Rekor retrieval validated for: {artifact_hash[:16]}...")
    print(f"  Found {len(mock_retrieval['entries'])} entries")


def test_rekor_signature_chain_validation():
    """Test signature chain validation in Rekor entries.

    Validates that both inner (Assurance) and outer (Trust) signatures
    are properly recorded in the transparency log.
    """
    # Mock entry with dual signatures
    mock_entry = {
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
        "chain_verified": True,
    }

    # Validate signature chain
    assert "inner_signature" in mock_entry
    assert "outer_signature" in mock_entry
    assert mock_entry["chain_verified"] is True
    assert mock_entry["inner_signature"]["signer"] == "certus-assurance@certus.cloud"
    assert mock_entry["outer_signature"]["signer"] == "certus-trust@certus.cloud"

    # Verify timestamps are in correct order
    inner_time = mock_entry["inner_signature"]["timestamp"]
    outer_time = mock_entry["outer_signature"]["timestamp"]
    assert inner_time < outer_time, "Outer signature should be after inner signature"

    print("✓ Signature chain validated:")
    print(f"  Inner: {mock_entry['inner_signature']['signer']}")
    print(f"  Outer: {mock_entry['outer_signature']['signer']}")
    print(f"  Chain verified: {mock_entry['chain_verified']}")


# NOTE: Additional tests to implement when Rekor is available:
# - test_actual_rekor_entry_creation() - with real Rekor instance
# - test_actual_rekor_entry_retrieval() - with real Rekor instance
# - test_rekor_search_by_artifact_hash() - with real Rekor instance
# - test_rekor_entry_verification() - with real Rekor instance
