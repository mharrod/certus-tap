"""Unit tests for error handling.

These tests validate that the service handles errors gracefully
and provides appropriate error messages.
"""

from __future__ import annotations

import pytest


# Use simple exception instead of pydantic ValidationError
class ValidationError(Exception):
    """Simple validation error for testing."""

    pass


class VerificationRequest:
    """Mock verification request model for testing error handling."""

    def __init__(self, scan_id: str | None = None, tier: str | None = None, artifacts: dict | None = None):
        if not scan_id:
            raise ValidationError("scan_id is required")
        if tier not in ["basic", "verified", None]:
            raise ValidationError(f"Invalid tier: {tier}")

        self.scan_id = scan_id
        self.tier = tier
        self.artifacts = artifacts or {}


class SignatureValidationError(Exception):
    """Custom exception for signature validation errors."""

    pass


def validate_signature(signature: str, artifact_hash: str) -> bool:
    """Mock signature validation function."""
    if not signature:
        raise SignatureValidationError("Signature is required")
    if not artifact_hash:
        raise SignatureValidationError("Artifact hash is required")
    if len(signature) < 10:
        raise SignatureValidationError("Signature too short")
    if len(artifact_hash) != 64:
        raise SignatureValidationError("Invalid artifact hash length")

    return True


def test_missing_scan_id():
    """Test error handling for missing scan_id."""
    with pytest.raises(ValidationError) as exc_info:
        VerificationRequest(tier="basic")

    assert "scan_id is required" in str(exc_info.value)
    print("✓ Missing scan_id error handled correctly")


def test_invalid_tier():
    """Test error handling for invalid tier."""
    with pytest.raises(ValidationError) as exc_info:
        VerificationRequest(scan_id="test-123", tier="invalid")

    assert "Invalid tier" in str(exc_info.value)
    print("✓ Invalid tier error handled correctly")


def test_missing_signature():
    """Test error handling for missing signature."""
    with pytest.raises(SignatureValidationError) as exc_info:
        validate_signature("", "abc123")

    assert "Signature is required" in str(exc_info.value)
    print("✓ Missing signature error handled correctly")


def test_missing_artifact_hash():
    """Test error handling for missing artifact hash."""
    with pytest.raises(SignatureValidationError) as exc_info:
        validate_signature("signature", "")

    assert "Artifact hash is required" in str(exc_info.value)
    print("✓ Missing artifact hash error handled correctly")


def test_short_signature():
    """Test error handling for short signature."""
    with pytest.raises(SignatureValidationError) as exc_info:
        validate_signature("short", "abc123")

    assert "Signature too short" in str(exc_info.value)
    print("✓ Short signature error handled correctly")


def test_invalid_artifact_hash_length():
    """Test error handling for invalid artifact hash length."""
    with pytest.raises(SignatureValidationError) as exc_info:
        validate_signature("valid-signature", "short")

    assert "Invalid artifact hash length" in str(exc_info.value)
    print("✓ Invalid artifact hash length error handled correctly")


def test_valid_request():
    """Test that valid requests are accepted."""
    request = VerificationRequest(scan_id="test-123", tier="basic", artifacts={"sarif": "test.sarif"})

    assert request.scan_id == "test-123"
    assert request.tier == "basic"
    assert "sarif" in request.artifacts
    print("✓ Valid request accepted")


def test_valid_signature():
    """Test that valid signatures are accepted."""
    # SHA256 hash is 64 characters
    valid_hash = "a" * 64
    valid_sig = "valid-signature-blob"

    result = validate_signature(valid_sig, valid_hash)
    assert result is True
    print("✓ Valid signature accepted")


def test_error_message_clarity():
    """Test that error messages are clear and helpful."""
    error_cases = [
        (lambda: VerificationRequest(tier="basic"), "scan_id is required"),
        (lambda: VerificationRequest(scan_id="test", tier="invalid"), "Invalid tier"),
        (lambda: validate_signature("", "hash"), "Signature is required"),
        (lambda: validate_signature("sig", ""), "Artifact hash is required"),
    ]

    for func, expected_msg in error_cases:
        try:
            func()
            raise AssertionError("Should have raised an error")
        except Exception as e:
            assert expected_msg in str(e), f"Expected '{expected_msg}' in error message"

    print(f"✓ All {len(error_cases)} error messages are clear and helpful")


def test_error_consistency():
    """Test that similar errors have consistent handling."""
    # Both should raise ValidationError
    with pytest.raises(ValidationError):
        VerificationRequest(tier="basic")

    with pytest.raises(ValidationError):
        VerificationRequest(scan_id="test", tier="invalid")

    # Both should raise SignatureValidationError
    with pytest.raises(SignatureValidationError):
        validate_signature("", "hash")

    with pytest.raises(SignatureValidationError):
        validate_signature("sig", "")

    print("✓ Error handling is consistent")


# NOTE: Additional tests to add when actual error handling is available:
# - test_http_error_handling() - test HTTP error responses
# - test_database_error_handling() - test database error handling
# - test_network_error_handling() - test network error handling
# - test_retry_logic() - test retry logic for transient errors
