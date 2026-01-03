"""Unit tests for Phase 1: Unified Security Scan Parser System.

Tests the core components:
- UnifiedSecurityScan data models
- SecurityScanParser framework
- Parser registry system
- Severity mapping
- SarifParser implementation
"""

import pytest

from certus_ask.pipelines.security_scan_parsers import (
    get_parser_registry,
    parse_security_scan,
)
from certus_ask.pipelines.security_scan_parsers.sarif_parser import SarifParser
from certus_ask.pipelines.security_scan_parsers.severity_mapping import (
    normalize_severity,
)
from certus_ask.schemas.unified_security_scan import (
    ScanMetadata,
    UnifiedDependency,
    UnifiedFinding,
    UnifiedLocation,
    UnifiedSecurityScan,
)

# ============================================================================
# UnifiedSecurityScan Model Tests
# ============================================================================


class TestUnifiedSecurityScanModel:
    """Tests for UnifiedSecurityScan data model."""

    def test_create_minimal_scan(self):
        """Test creating a minimal UnifiedSecurityScan."""
        metadata = ScanMetadata(tool_name="sarif")
        scan = UnifiedSecurityScan(metadata=metadata)

        assert scan.metadata.tool_name == "sarif"
        assert scan.findings == []
        assert scan.dependencies is None

    def test_create_scan_with_metadata(self):
        """Test creating scan with full metadata."""
        from datetime import datetime

        metadata = ScanMetadata(
            tool_name="bandit",
            tool_version="1.7.4",
            scan_timestamp=datetime.now(),
            scan_target="src/",
        )
        scan = UnifiedSecurityScan(metadata=metadata)

        assert scan.metadata.tool_name == "bandit"
        assert scan.metadata.tool_version == "1.7.4"
        assert scan.metadata.scan_target == "src/"

    def test_create_scan_with_findings(self):
        """Test creating scan with findings."""
        metadata = ScanMetadata(tool_name="sarif")
        finding = UnifiedFinding(
            id="TEST001",
            title="SQL Injection",
            severity="CRITICAL",
            type="vulnerability",
            description="User input in SQL query",
        )
        scan = UnifiedSecurityScan(metadata=metadata, findings=[finding])

        assert len(scan.findings) == 1
        assert scan.findings[0].id == "TEST001"
        assert scan.findings[0].severity == "CRITICAL"

    def test_create_finding_with_location(self):
        """Test finding with location information."""
        location = UnifiedLocation(
            file_path="src/auth.py",
            line_start=42,
            line_end=45,
            code_snippet='query = f"SELECT * FROM users WHERE id={user_id}"',
        )
        finding = UnifiedFinding(
            id="RULE001",
            title="SQL Injection",
            severity="CRITICAL",
            type="vulnerability",
            description="Unsafe SQL",
            location=location,
        )

        assert finding.location.file_path == "src/auth.py"
        assert finding.location.line_start == 42
        assert finding.location.code_snippet is not None

    def test_create_finding_with_remediation(self):
        """Test finding with remediation information."""
        finding = UnifiedFinding(
            id="TEST001",
            title="Vulnerability",
            severity="HIGH",
            type="vulnerability",
            description="Test issue",
            remediation="Use parameterized queries",
            references=["CWE-89", "https://owasp.org/A03_2021-Injection/"],
            tags=["injection", "database"],
        )

        assert finding.remediation == "Use parameterized queries"
        assert len(finding.references) == 2
        assert "injection" in finding.tags

    def test_create_finding_with_raw_data(self):
        """Test finding preserves raw tool data."""
        raw_data = {"tool_specific": "value", "extra_field": 123}
        finding = UnifiedFinding(
            id="TEST001",
            title="Test",
            severity="LOW",
            type="vulnerability",
            description="Test",
            raw_data=raw_data,
        )

        assert finding.raw_data == raw_data
        assert finding.raw_data["tool_specific"] == "value"

    def test_create_dependency(self):
        """Test creating dependency objects."""
        dep = UnifiedDependency(
            name="requests",
            version="2.28.1",
            license="Apache-2.0",
            vulnerabilities=["CVE-2021-33503"],
        )

        assert dep.name == "requests"
        assert dep.version == "2.28.1"
        assert "CVE-2021-33503" in dep.vulnerabilities


# ============================================================================
# Severity Mapping Tests
# ============================================================================


class TestSeverityMapping:
    """Tests for severity normalization."""

    def test_sarif_severity_mapping(self):
        """Test SARIF severity levels map correctly."""
        assert normalize_severity("error", "sarif") == "HIGH"
        assert normalize_severity("warning", "sarif") == "MEDIUM"
        assert normalize_severity("note", "sarif") == "LOW"

    def test_bandit_severity_mapping(self):
        """Test Bandit severity levels map correctly."""
        assert normalize_severity("HIGH", "bandit") == "HIGH"
        assert normalize_severity("MEDIUM", "bandit") == "MEDIUM"
        assert normalize_severity("LOW", "bandit") == "LOW"

    def test_trivy_severity_mapping(self):
        """Test Trivy severity levels map correctly."""
        assert normalize_severity("CRITICAL", "trivy") == "CRITICAL"
        assert normalize_severity("HIGH", "trivy") == "HIGH"
        assert normalize_severity("MEDIUM", "trivy") == "MEDIUM"
        assert normalize_severity("LOW", "trivy") == "LOW"
        assert normalize_severity("UNKNOWN", "trivy") == "INFO"

    def test_severity_normalization_none(self):
        """Test None severity defaults to INFO."""
        assert normalize_severity(None, "sarif") == "INFO"

    def test_severity_normalization_unknown(self):
        """Test unknown severity defaults to INFO."""
        assert normalize_severity("UNKNOWN_LEVEL", "sarif") == "INFO"

    def test_severity_case_insensitive(self):
        """Test severity mapping is case-insensitive."""
        assert normalize_severity("HIGH", "bandit") == "HIGH"
        assert normalize_severity("high", "bandit") == "HIGH"
        assert normalize_severity("High", "bandit") == "HIGH"

    def test_standard_severity_passthrough(self):
        """Test standard severities pass through unchanged."""
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]:
            assert normalize_severity(severity, "unknown_tool") == severity


# ============================================================================
# SecurityScanParser Framework Tests
# ============================================================================


class TestSecurityScanParser:
    """Tests for SecurityScanParser base class."""

    def test_parser_has_required_attributes(self):
        """Test parser has required attributes."""
        parser = SarifParser()
        assert hasattr(parser, "tool_name")
        assert hasattr(parser, "supported_versions")
        assert parser.tool_name == "sarif"

    def test_parser_must_implement_parse(self):
        """Test parser has parse method."""
        parser = SarifParser()
        assert callable(getattr(parser, "parse", None))

    def test_parser_must_implement_validate(self):
        """Test parser has validate method."""
        parser = SarifParser()
        assert callable(getattr(parser, "validate", None))


# ============================================================================
# SarifParser Tests
# ============================================================================


class TestSarifParser:
    """Tests for SARIF parser implementation."""

    @pytest.fixture
    def parser(self):
        """Create a SARIF parser instance."""
        return SarifParser()

    @pytest.fixture
    def minimal_sarif(self):
        """Minimal valid SARIF structure."""
        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [],
        }

    @pytest.fixture
    def sarif_with_finding(self):
        """SARIF with a single finding."""
        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "bandit", "version": "1.7.4"}},
                    "results": [
                        {
                            "ruleId": "B101",
                            "message": {"text": "Test assert detected"},
                            "level": "warning",
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "test.py"},
                                        "region": {"startLine": 10},
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }

    @pytest.fixture
    def sarif_with_multiple_findings(self):
        """SARIF with multiple findings at different severity levels."""
        return {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "bandit", "version": "1.7.4"}},
                    "results": [
                        {
                            "ruleId": "B101",
                            "message": {"text": "Assert detected"},
                            "level": "warning",
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "test.py"},
                                        "region": {"startLine": 10},
                                    }
                                }
                            ],
                        },
                        {
                            "ruleId": "B602",
                            "message": {"text": "Shell injection"},
                            "level": "error",
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "utils.py"},
                                        "region": {"startLine": 42},
                                    }
                                }
                            ],
                        },
                        {
                            "ruleId": "B703",
                            "message": {"text": "DAG vulnerability"},
                            "level": "note",
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "config.py"},
                                        "region": {"startLine": 5},
                                    }
                                }
                            ],
                        },
                    ],
                }
            ],
        }

    def test_validate_sarif_format(self, parser, minimal_sarif):
        """Test SARIF validation detects valid format."""
        assert parser.validate(minimal_sarif) is True

    def test_validate_rejects_non_sarif(self, parser):
        """Test validation rejects non-SARIF JSON."""
        non_sarif = {"some": "data", "with": "fields"}
        assert parser.validate(non_sarif) is False

    def test_validate_requires_runs_array(self, parser):
        """Test validation requires runs array."""
        invalid = {
            "$schema": "https://sarif.json",
            "version": "2.1.0",
            # Missing 'runs' array
        }
        assert parser.validate(invalid) is False

    def test_parse_minimal_sarif(self, parser, minimal_sarif):
        """Test parsing minimal SARIF."""
        result = parser.parse(minimal_sarif)

        assert isinstance(result, UnifiedSecurityScan)
        assert result.metadata.tool_name == "sarif"
        assert result.findings == []

    def test_parse_sarif_with_finding(self, parser, sarif_with_finding):
        """Test parsing SARIF with a finding."""
        result = parser.parse(sarif_with_finding)

        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.id == "B101"
        assert finding.title == "Test assert detected"
        assert finding.severity == "MEDIUM"  # warning maps to MEDIUM

    def test_parse_sarif_with_multiple_findings(self, parser, sarif_with_multiple_findings):
        """Test parsing SARIF with multiple findings."""
        result = parser.parse(sarif_with_multiple_findings)

        assert len(result.findings) == 3

        # Check severity mapping for each
        assert result.findings[0].severity == "MEDIUM"  # warning
        assert result.findings[1].severity == "HIGH"  # error
        assert result.findings[2].severity == "LOW"  # note

    def test_parse_preserves_raw_data(self, parser, sarif_with_finding):
        """Test parsing preserves original SARIF data."""
        result = parser.parse(sarif_with_finding)
        finding = result.findings[0]

        assert finding.raw_data is not None
        assert finding.raw_data["ruleId"] == "B101"

    def test_parse_extracts_location(self, parser, sarif_with_finding):
        """Test location extraction from SARIF."""
        result = parser.parse(sarif_with_finding)
        location = result.findings[0].location

        assert location is not None
        assert location.file_path == "test.py"
        assert location.line_start == 10

    def test_parse_sarif_with_remediation(self, parser):
        """Test parsing SARIF with fix information."""
        sarif = {
            "$schema": "https://sarif.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "test", "version": "1.0"}},
                    "results": [
                        {
                            "ruleId": "TEST001",
                            "message": {"text": "Test issue"},
                            "level": "warning",
                            "fixes": [{"description": {"text": "Use this pattern instead"}}],
                        }
                    ],
                }
            ],
        }

        result = parser.parse(sarif)
        assert result.findings[0].remediation == "Use this pattern instead"


# ============================================================================
# Parser Registry Tests
# ============================================================================


class TestParserRegistry:
    """Tests for parser registry."""

    def test_get_registry(self):
        """Test getting the global parser registry."""
        registry = get_parser_registry()
        assert registry is not None

    def test_registry_has_sarif_parser(self):
        """Test SARIF parser is registered."""
        registry = get_parser_registry()
        sarif_parser = registry.get("sarif")
        assert sarif_parser is not None
        assert sarif_parser.tool_name == "sarif"

    def test_list_parsers(self):
        """Test listing registered parsers."""
        registry = get_parser_registry()
        parsers = registry.list_parsers()

        assert isinstance(parsers, dict)
        assert "sarif" in parsers

    def test_auto_detect_sarif(self):
        """Test auto-detecting SARIF format."""
        registry = get_parser_registry()
        sarif = {
            "$schema": "https://sarif.json",
            "version": "2.1.0",
            "runs": [],
        }

        detected = registry.auto_detect(sarif)
        assert detected == "sarif"

    def test_auto_detect_non_sarif(self):
        """Test auto-detection fails for unknown format."""
        registry = get_parser_registry()
        unknown = {"some": "data"}

        detected = registry.auto_detect(unknown)
        assert detected is None

    def test_parse_with_tool_hint(self):
        """Test parsing with tool hint."""
        registry = get_parser_registry()
        sarif = {
            "$schema": "https://sarif.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "test"}},
                    "results": [],
                }
            ],
        }

        result = registry.parse(sarif, tool_hint="sarif")
        assert result.metadata.tool_name == "sarif"

    def test_parse_auto_detect(self):
        """Test parsing with auto-detection."""
        registry = get_parser_registry()
        sarif = {
            "$schema": "https://sarif.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "test"}},
                    "results": [],
                }
            ],
        }

        result = registry.parse(sarif)  # No tool_hint
        assert result.metadata.tool_name == "sarif"


# ============================================================================
# Integration Tests
# ============================================================================


class TestParseSecurityScan:
    """Integration tests for parse_security_scan function."""

    def test_parse_with_tool_hint(self):
        """Test top-level parse function with tool hint."""
        sarif = {
            "$schema": "https://sarif.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "bandit", "version": "1.7.4"}},
                    "results": [
                        {
                            "ruleId": "B101",
                            "message": {"text": "Assert"},
                            "level": "warning",
                        }
                    ],
                }
            ],
        }

        result = parse_security_scan(sarif, tool_hint="sarif")
        assert len(result.findings) == 1

    def test_parse_with_auto_detection(self):
        """Test top-level parse function with auto-detection."""
        sarif = {
            "$schema": "https://sarif.json",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "bandit"}},
                    "results": [],
                }
            ],
        }

        result = parse_security_scan(sarif)
        assert result.metadata.tool_name == "sarif"

    def test_parse_unknown_format_raises_error(self):
        """Test parsing unknown format raises ValidationError."""
        from certus_ask.core.exceptions import ValidationError

        unknown = {"some": "data"}

        with pytest.raises(ValidationError):
            parse_security_scan(unknown)
