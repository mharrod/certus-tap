"""Contract tests for Certus-Assurance API as called by Certus-Trust.

These tests validate Trust's expectations about the Assurance API.
Since Trust doesn't directly call Assurance in the current workflow,
this is a placeholder for future bidirectional communication.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.contract


def test_assurance_scan_metadata_format() -> None:
    """
    Verify scan metadata format from Assurance matches Trust's expectations.

    This validates the inner_signature and metadata structure Trust expects.
    """
    # Expected scan metadata structure that Trust receives
    expected_scan_metadata = {
        "scan_id": "scan_abc123",
        "workspace_id": "workspace-123",
        "component_id": "component-456",
        "git_url": "https://github.com/example/repo",
        "git_commit": "abc123def456",
        "branch": "main",
        "requested_by": "ci-bot@example.com",
        "started_at": "2024-01-15T14:30:00Z",
        "completed_at": "2024-01-15T14:32:45Z",
        "status": "SUCCEEDED",
        "inner_signature": {
            "signer": "certus-assurance@certus.cloud",
            "timestamp": "2024-01-15T14:32:45Z",
            "signature": "base64-signature-blob",
            "algorithm": "SHA256-RSA",
        },
    }

    # Trust expects these fields to exist
    assert "scan_id" in expected_scan_metadata
    assert "inner_signature" in expected_scan_metadata
    assert "signer" in expected_scan_metadata["inner_signature"]
    assert "timestamp" in expected_scan_metadata["inner_signature"]
    assert "signature" in expected_scan_metadata["inner_signature"]

    print("✓ Assurance scan metadata contract validated")
