"""Unit tests for severity mapping logic.

Tests the normalization of tool-specific severity levels to standard levels.
"""

from certus_ask.pipelines.security_scan_parsers.severity_mapping import (
    SEVERITY_MAPPINGS,
    STANDARD_SEVERITIES,
    get_severity_mappings,
    normalize_severity,
)


class TestNormalizeSeverity:
    """Tests for normalize_severity function."""

    def test_normalize_severity_standard_levels(self):
        """Test that standard severity levels pass through unchanged."""
        for severity in STANDARD_SEVERITIES:
            result = normalize_severity(severity, "any_tool")
            assert result == severity

    def test_normalize_severity_sarif_mappings(self):
        """Test SARIF-specific severity mappings."""
        assert normalize_severity("ERROR", "sarif") == "HIGH"
        assert normalize_severity("WARNING", "sarif") == "MEDIUM"
        assert normalize_severity("NOTE", "sarif") == "LOW"
        assert normalize_severity("CRITICAL", "sarif") == "CRITICAL"

    def test_normalize_severity_bandit_mappings(self):
        """Test Bandit-specific severity mappings."""
        assert normalize_severity("HIGH", "bandit") == "HIGH"
        assert normalize_severity("MEDIUM", "bandit") == "MEDIUM"
        assert normalize_severity("LOW", "bandit") == "LOW"

    def test_normalize_severity_trivy_mappings(self):
        """Test Trivy-specific severity mappings."""
        assert normalize_severity("CRITICAL", "trivy") == "CRITICAL"
        assert normalize_severity("HIGH", "trivy") == "HIGH"
        assert normalize_severity("MEDIUM", "trivy") == "MEDIUM"
        assert normalize_severity("LOW", "trivy") == "LOW"
        assert normalize_severity("UNKNOWN", "trivy") == "INFO"

    def test_normalize_severity_opengrep_mappings(self):
        """Test OpenGrep-specific severity mappings."""
        assert normalize_severity("ERROR", "opengrep") == "HIGH"
        assert normalize_severity("WARNING", "opengrep") == "MEDIUM"

    def test_normalize_severity_case_insensitive(self):
        """Test that severity normalization is case-insensitive."""
        assert normalize_severity("error", "sarif") == "HIGH"
        assert normalize_severity("Error", "sarif") == "HIGH"
        assert normalize_severity("ERROR", "sarif") == "HIGH"
        assert normalize_severity("warning", "sarif") == "MEDIUM"
        assert normalize_severity("Warning", "sarif") == "MEDIUM"

    def test_normalize_severity_none_input(self):
        """Test handling of None severity input."""
        result = normalize_severity(None, "any_tool")
        assert result == "INFO"  # Default value

    def test_normalize_severity_none_with_custom_default(self):
        """Test None severity with custom default."""
        result = normalize_severity(None, "any_tool", default="MEDIUM")
        assert result == "MEDIUM"

    def test_normalize_severity_unknown_tool(self):
        """Test unknown tool falls back to default."""
        result = normalize_severity("SOME_LEVEL", "unknown_tool")
        assert result == "INFO"  # Default for unknown

    def test_normalize_severity_unknown_tool_with_custom_default(self):
        """Test unknown tool with custom default."""
        result = normalize_severity("SOME_LEVEL", "unknown_tool", default="LOW")
        assert result == "LOW"

    def test_normalize_severity_unknown_level_for_known_tool(self):
        """Test unknown severity level for a known tool."""
        result = normalize_severity("BOGUS", "sarif")
        assert result == "INFO"  # Falls back to default

    def test_normalize_severity_empty_string(self):
        """Test handling of empty string severity."""
        result = normalize_severity("", "sarif")
        assert result == "INFO"  # Falls back to default


class TestGetSeverityMappings:
    """Tests for get_severity_mappings function."""

    def test_get_severity_mappings_sarif(self):
        """Test retrieving SARIF severity mappings."""
        mappings = get_severity_mappings("sarif")
        assert isinstance(mappings, dict)
        assert mappings["ERROR"] == "HIGH"
        assert mappings["WARNING"] == "MEDIUM"
        assert mappings["NOTE"] == "LOW"

    def test_get_severity_mappings_bandit(self):
        """Test retrieving Bandit severity mappings."""
        mappings = get_severity_mappings("bandit")
        assert isinstance(mappings, dict)
        assert mappings["HIGH"] == "HIGH"
        assert mappings["MEDIUM"] == "MEDIUM"
        assert mappings["LOW"] == "LOW"

    def test_get_severity_mappings_trivy(self):
        """Test retrieving Trivy severity mappings."""
        mappings = get_severity_mappings("trivy")
        assert isinstance(mappings, dict)
        assert mappings["CRITICAL"] == "CRITICAL"
        assert mappings["UNKNOWN"] == "INFO"

    def test_get_severity_mappings_unknown_tool(self):
        """Test retrieving mappings for unknown tool returns empty dict."""
        mappings = get_severity_mappings("unknown_tool")
        assert isinstance(mappings, dict)
        assert len(mappings) == 0

    def test_get_severity_mappings_immutability(self):
        """Test that returned mappings don't affect the original."""
        mappings = get_severity_mappings("sarif")
        original_error_value = mappings["ERROR"]

        # Modify the returned mapping
        mappings["ERROR"] = "CRITICAL"

        # Original should be unchanged
        assert SEVERITY_MAPPINGS["sarif"]["ERROR"] == original_error_value


class TestSeverityConstants:
    """Tests for severity mapping constants."""

    def test_standard_severities_contains_expected_levels(self):
        """Test that STANDARD_SEVERITIES contains all expected levels."""
        assert "CRITICAL" in STANDARD_SEVERITIES
        assert "HIGH" in STANDARD_SEVERITIES
        assert "MEDIUM" in STANDARD_SEVERITIES
        assert "LOW" in STANDARD_SEVERITIES
        assert "INFO" in STANDARD_SEVERITIES

    def test_severity_mappings_structure(self):
        """Test that SEVERITY_MAPPINGS has expected structure."""
        assert isinstance(SEVERITY_MAPPINGS, dict)
        assert "sarif" in SEVERITY_MAPPINGS
        assert "bandit" in SEVERITY_MAPPINGS
        assert "trivy" in SEVERITY_MAPPINGS
        assert "opengrep" in SEVERITY_MAPPINGS

    def test_all_mapped_severities_are_standard(self):
        """Test that all mapped values are standard severities."""
        for tool_name, mappings in SEVERITY_MAPPINGS.items():
            for input_sev, output_sev in mappings.items():
                assert output_sev in STANDARD_SEVERITIES, (
                    f"Tool '{tool_name}' maps '{input_sev}' to non-standard severity '{output_sev}'"
                )
