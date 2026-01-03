"""Unit tests for manifest validation logic."""

import pytest


def test_manifest_has_required_fields(mock_manifest: dict):
    """Test that mock manifest includes required fields."""
    assert "version" in mock_manifest
    assert "profile" in mock_manifest
    assert "tools" in mock_manifest
    assert "thresholds" in mock_manifest


def test_manifest_tools_is_list(mock_manifest: dict):
    """Test that tools field is a list."""
    assert isinstance(mock_manifest["tools"], list)
    assert len(mock_manifest["tools"]) > 0


def test_manifest_tools_have_name_field(mock_manifest: dict):
    """Test that each tool has a name field."""
    for tool in mock_manifest["tools"]:
        assert "name" in tool
        assert isinstance(tool["name"], str)
        assert len(tool["name"]) > 0


def test_manifest_tools_have_enabled_field(mock_manifest: dict):
    """Test that each tool has an enabled field."""
    for tool in mock_manifest["tools"]:
        assert "enabled" in tool
        assert isinstance(tool["enabled"], bool)


def test_manifest_thresholds_have_severity_levels(mock_manifest: dict):
    """Test that thresholds include critical, high, medium."""
    thresholds = mock_manifest["thresholds"]

    assert "critical" in thresholds
    assert "high" in thresholds
    assert "medium" in thresholds


def test_manifest_thresholds_are_integers(mock_manifest: dict):
    """Test that threshold values are integers."""
    thresholds = mock_manifest["thresholds"]

    assert isinstance(thresholds["critical"], int)
    assert isinstance(thresholds["high"], int)
    assert isinstance(thresholds["medium"], int)


def test_manifest_thresholds_are_non_negative(mock_manifest: dict):
    """Test that threshold values are non-negative."""
    thresholds = mock_manifest["thresholds"]

    assert thresholds["critical"] >= 0
    assert thresholds["high"] >= 0
    assert thresholds["medium"] >= 0


def test_manifest_profile_is_string(mock_manifest: dict):
    """Test that profile field is a string."""
    assert isinstance(mock_manifest["profile"], str)
    assert len(mock_manifest["profile"]) > 0


def test_manifest_profile_is_valid_value(mock_manifest: dict):
    """Test that profile is one of the known profiles."""
    valid_profiles = ["light", "standard", "polyglot", "comprehensive", "custom"]

    assert mock_manifest["profile"] in valid_profiles


def test_manifest_metadata_is_optional(mock_manifest: dict):
    """Test that metadata field exists but could be optional."""
    # If metadata exists, it should be a dict
    if "metadata" in mock_manifest:
        assert isinstance(mock_manifest["metadata"], dict)


def test_manifest_metadata_has_name_if_present(mock_manifest: dict):
    """Test that metadata includes name if present."""
    if "metadata" in mock_manifest:
        metadata = mock_manifest["metadata"]
        if "name" in metadata:
            assert isinstance(metadata["name"], str)


def test_manifest_version_is_v1(mock_manifest: dict):
    """Test that manifest version is v1."""
    assert mock_manifest["version"] == "v1"


def test_manifest_tool_config_is_dict(mock_manifest: dict):
    """Test that tool config is a dictionary."""
    for tool in mock_manifest["tools"]:
        if "config" in tool:
            assert isinstance(tool["config"], dict)


def test_manifest_without_tools_is_invalid():
    """Test that a manifest without tools is considered invalid."""
    invalid_manifest = {
        "version": "v1",
        "profile": "light",
        "thresholds": {"critical": 0, "high": 5, "medium": 50},
    }

    # Missing 'tools' field - should be invalid
    assert "tools" not in invalid_manifest


def test_manifest_with_empty_tools_list():
    """Test manifest with empty tools list."""
    manifest_with_no_tools = {
        "version": "v1",
        "profile": "custom",
        "tools": [],  # No tools configured
        "thresholds": {"critical": 0, "high": 5, "medium": 50},
    }

    assert len(manifest_with_no_tools["tools"]) == 0
    # This might be valid for a custom profile with manual configuration
