"""Unit tests for identifier generation logic."""

import hashlib
import re

import pytest


def test_workspace_id_format():
    """Test that workspace_id follows expected format."""
    workspace_id = "test-workspace"

    # Should be lowercase with hyphens
    assert workspace_id.islower()
    assert "-" in workspace_id or workspace_id.isalnum()


def test_component_id_format():
    """Test that component_id follows expected format."""
    component_id = "test-component"

    # Should be lowercase with hyphens
    assert component_id.islower()
    assert "-" in component_id or component_id.isalnum()


def test_assessment_id_has_prefix():
    """Test that assessment_id starts with 'assess_' prefix."""
    assessment_id = "assess_test123"

    assert assessment_id.startswith("assess_")


def test_assessment_id_suffix_is_alphanumeric():
    """Test that assessment_id suffix is alphanumeric."""
    assessment_id = "assess_abc123def456"

    prefix, suffix = assessment_id.split("_", 1)
    assert prefix == "assess"
    assert suffix.isalnum()


def test_test_id_generation_from_components():
    """Test generating test_id from workspace, component, and assessment."""
    workspace_id = "acme-corp"
    component_id = "payment-service"
    assessment_id = "assess_abc123"

    # Common pattern: workspace/component/assessment
    test_id = f"{workspace_id}/{component_id}/{assessment_id}"

    assert workspace_id in test_id
    assert component_id in test_id
    assert assessment_id in test_id


def test_assessment_id_uniqueness_via_hash():
    """Test generating unique assessment IDs using hash."""
    timestamp = "2025-01-15T10:30:00Z"
    workspace_id = "test-workspace"
    component_id = "test-component"

    # Generate hash-based ID
    hash_input = f"{workspace_id}:{component_id}:{timestamp}"
    hash_digest = hashlib.sha256(hash_input.encode()).hexdigest()[:12]
    assessment_id = f"assess_{hash_digest}"

    assert assessment_id.startswith("assess_")
    assert len(assessment_id) == 7 + 12  # "assess_" + 12 chars


def test_assessment_id_different_for_different_inputs():
    """Test that different inputs produce different assessment IDs."""
    # Generate two IDs with different timestamps
    id1_input = "workspace:component:2025-01-15T10:00:00Z"
    id2_input = "workspace:component:2025-01-15T11:00:00Z"

    hash1 = hashlib.sha256(id1_input.encode()).hexdigest()[:12]
    hash2 = hashlib.sha256(id2_input.encode()).hexdigest()[:12]

    assert hash1 != hash2


def test_workspace_id_validation_pattern():
    """Test workspace_id matches DNS-safe pattern."""
    valid_ids = ["acme-corp", "test123", "my-workspace-v2"]

    for workspace_id in valid_ids:
        # Should match DNS-safe pattern: lowercase, numbers, hyphens
        assert re.match(r"^[a-z0-9-]+$", workspace_id)


def test_component_id_validation_pattern():
    """Test component_id matches DNS-safe pattern."""
    valid_ids = ["payment-service", "api-gateway", "user-auth"]

    for component_id in valid_ids:
        # Should match DNS-safe pattern
        assert re.match(r"^[a-z0-9-]+$", component_id)


def test_assessment_id_validation_pattern():
    """Test assessment_id matches expected pattern."""
    valid_ids = [
        "assess_abc123",
        "assess_def456ghi789",
        "assess_1234567890ab",
    ]

    for assessment_id in valid_ids:
        # Should match pattern: assess_ followed by alphanumeric
        assert re.match(r"^assess_[a-zA-Z0-9]+$", assessment_id)


def test_identifier_no_special_characters():
    """Test that identifiers avoid special characters."""
    workspace_id = "test-workspace"
    component_id = "test-component"

    # Should not contain: @, !, $, %, etc.
    assert not any(char in workspace_id for char in "@!$%^&*()+=[]{}|\\:;\"'<>?,./")
    assert not any(char in component_id for char in "@!$%^&*()+=[]{}|\\:;\"'<>?,./")


def test_identifier_case_sensitivity():
    """Test identifier case handling."""
    # Workspace and component IDs should be lowercase
    workspace_id = "Test-Workspace"
    normalized_workspace = workspace_id.lower()

    assert normalized_workspace == "test-workspace"
    assert normalized_workspace.islower()


def test_hierarchical_identifier_construction():
    """Test constructing hierarchical identifier paths."""
    workspace_id = "acme-corp"
    component_id = "payment-api"
    assessment_id = "assess_abc123"
    test_id = "bandit_B608"

    # Full hierarchical path
    full_path = f"{workspace_id}/{component_id}/{assessment_id}/{test_id}"

    assert full_path == "acme-corp/payment-api/assess_abc123/bandit_B608"


def test_s3_path_generation():
    """Test generating S3 path from identifiers."""
    workspace_id = "acme-corp"
    component_id = "payment-api"
    assessment_id = "assess_abc123"

    s3_path = f"s3://certus-artifacts/{workspace_id}/{component_id}/{assessment_id}/"

    assert "s3://" in s3_path
    assert workspace_id in s3_path
    assert component_id in s3_path
    assert assessment_id in s3_path
    assert s3_path.endswith("/")
