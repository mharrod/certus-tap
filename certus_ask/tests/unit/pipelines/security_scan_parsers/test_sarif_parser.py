"""Unit tests for SARIF parser.

Tests the SARIF parser's ability to:
- Validate SARIF format
- Parse SARIF findings into UnifiedSecurityScan
- Extract locations, remediation, references, and tags
- Handle edge cases and malformed data
"""

from typing import Any

import pytest

from certus_ask.pipelines.security_scan_parsers.sarif_parser import SarifParser
from certus_ask.schemas.unified_security_scan import UnifiedSecurityScan


class TestSarifParserValidation:
    """Test SARIF format validation."""

    @pytest.fixture
    def parser(self) -> SarifParser:
        """Create parser instance."""
        return SarifParser()

    def test_validate_valid_sarif(self, parser: SarifParser) -> None:
        """Test validation of valid SARIF document."""
        sarif = {
            "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
            "version": "2.1.0",
            "runs": [],
        }

        assert parser.validate(sarif) is True

    def test_validate_sarif_with_runs(self, parser: SarifParser) -> None:
        """Test validation of SARIF with runs."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "test"}}, "results": []}],
        }

        assert parser.validate(sarif) is True

    def test_validate_sarif_case_insensitive_schema(self, parser: SarifParser) -> None:
        """Test validation with case-insensitive schema check."""
        sarif = {
            "$schema": "https://example.com/SARIF-schema.json",
            "version": "2.1.0",
            "runs": [],
        }

        assert parser.validate(sarif) is True

    def test_validate_missing_schema(self, parser: SarifParser) -> None:
        """Test validation fails without schema."""
        sarif = {
            "version": "2.1.0",
            "runs": [],
        }

        # Should still pass if "runs" is present (flexible validation)
        # But since schema doesn't contain "sarif", should fail
        assert parser.validate(sarif) is False

    def test_validate_missing_runs(self, parser: SarifParser) -> None:
        """Test validation fails without runs."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
        }

        assert parser.validate(sarif) is False

    def test_validate_empty_object(self, parser: SarifParser) -> None:
        """Test validation fails on empty object."""
        assert parser.validate({}) is False

    def test_validate_non_dict(self, parser: SarifParser) -> None:
        """Test validation handles non-dict input."""
        assert parser.validate([]) is False  # type: ignore
        assert parser.validate("not a dict") is False  # type: ignore
        assert parser.validate(None) is False  # type: ignore

    def test_validate_version_2_0(self, parser: SarifParser) -> None:
        """Test validation accepts SARIF 2.0.0."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.0.0",
            "version": "2.0.0",
            "runs": [],
        }

        assert parser.validate(sarif) is True


class TestSarifParserParsing:
    """Test SARIF parsing functionality."""

    @pytest.fixture
    def parser(self) -> SarifParser:
        """Create parser instance."""
        return SarifParser()

    def test_parse_minimal_sarif(self, parser: SarifParser) -> None:
        """Test parsing minimal valid SARIF."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "test-tool",
                            "version": "1.0.0",
                        }
                    },
                    "results": [],
                }
            ],
        }

        result = parser.parse(sarif)

        assert isinstance(result, UnifiedSecurityScan)
        assert result.metadata.tool_name == "sarif"
        assert result.metadata.tool_version == "test-tool:1.0.0"
        assert result.findings == []

    def test_parse_sarif_with_findings(self, parser: SarifParser) -> None:
        """Test parsing SARIF with findings."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "bandit",
                            "version": "1.7.0",
                        }
                    },
                    "results": [
                        {
                            "ruleId": "B101",
                            "level": "error",
                            "message": {"text": "Use of assert detected"},
                            "locations": [
                                {
                                    "physicalLocation": {
                                        "artifactLocation": {"uri": "src/app.py"},
                                        "region": {
                                            "startLine": 42,
                                            "endLine": 42,
                                            "startColumn": 5,
                                            "endColumn": 20,
                                            "snippet": {"text": "assert x > 0"},
                                        },
                                    }
                                }
                            ],
                        }
                    ],
                }
            ],
        }

        result = parser.parse(sarif)

        assert len(result.findings) == 1
        finding = result.findings[0]
        assert finding.id == "B101"
        assert finding.title == "Use of assert detected"
        assert finding.severity == "HIGH"  # error -> HIGH
        assert finding.location is not None
        assert finding.location.file_path == "src/app.py"
        assert finding.location.line_start == 42
        assert finding.location.line_end == 42
        assert finding.location.column_start == 5
        assert finding.location.column_end == 20
        assert finding.location.code_snippet == "assert x > 0"

    def test_parse_sarif_no_runs(self, parser: SarifParser) -> None:
        """Test parsing SARIF with no runs returns empty scan."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "runs": [],
        }

        result = parser.parse(sarif)

        assert result.metadata.tool_name == "sarif"
        assert result.findings == []

    def test_parse_sarif_missing_runs(self, parser: SarifParser) -> None:
        """Test parsing SARIF without runs field."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
        }

        result = parser.parse(sarif)

        assert result.findings == []

    def test_parse_sarif_multiple_findings(self, parser: SarifParser) -> None:
        """Test parsing SARIF with multiple findings."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "test-tool"}},
                    "results": [
                        {
                            "ruleId": "RULE1",
                            "level": "warning",
                            "message": {"text": "First issue"},
                        },
                        {
                            "ruleId": "RULE2",
                            "level": "error",
                            "message": {"text": "Second issue"},
                        },
                        {
                            "ruleId": "RULE3",
                            "level": "note",
                            "message": {"text": "Third issue"},
                        },
                    ],
                }
            ],
        }

        result = parser.parse(sarif)

        assert len(result.findings) == 3
        assert result.findings[0].id == "RULE1"
        assert result.findings[0].severity == "MEDIUM"
        assert result.findings[1].id == "RULE2"
        assert result.findings[1].severity == "HIGH"
        assert result.findings[2].id == "RULE3"
        assert result.findings[2].severity == "LOW"


class TestSarifParserLocationExtraction:
    """Test location extraction from SARIF results."""

    @pytest.fixture
    def parser(self) -> SarifParser:
        """Create parser instance."""
        return SarifParser()

    def test_extract_location_full_details(self, parser: SarifParser) -> None:
        """Test extracting location with all details."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "message": {"text": "Test issue"},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": "src/test.py"},
                        "region": {
                            "startLine": 10,
                            "endLine": 12,
                            "startColumn": 1,
                            "endColumn": 20,
                            "snippet": {"text": "vulnerable_code()"},
                        },
                    }
                }
            ],
        }

        location = parser._extract_location(result_data)

        assert location is not None
        assert location.file_path == "src/test.py"
        assert location.line_start == 10
        assert location.line_end == 12
        assert location.column_start == 1
        assert location.column_end == 20
        assert location.code_snippet == "vulnerable_code()"

    def test_extract_location_minimal(self, parser: SarifParser) -> None:
        """Test extracting minimal location (just file path)."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "message": {"text": "Test issue"},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {"uri": "src/test.py"},
                        "region": {},
                    }
                }
            ],
        }

        location = parser._extract_location(result_data)

        assert location is not None
        assert location.file_path == "src/test.py"
        assert location.line_start == 1  # Default
        assert location.line_end is None
        assert location.code_snippet is None

    def test_extract_location_no_locations(self, parser: SarifParser) -> None:
        """Test extracting location when none provided."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "message": {"text": "Test issue"},
            "locations": [],
        }

        location = parser._extract_location(result_data)

        assert location is None

    def test_extract_location_missing_locations_field(self, parser: SarifParser) -> None:
        """Test extracting location when field missing."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "message": {"text": "Test issue"},
        }

        location = parser._extract_location(result_data)

        assert location is None

    def test_extract_location_no_artifact_uri(self, parser: SarifParser) -> None:
        """Test extracting location without file path."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "message": {"text": "Test issue"},
            "locations": [
                {
                    "physicalLocation": {
                        "artifactLocation": {},
                        "region": {"startLine": 10},
                    }
                }
            ],
        }

        location = parser._extract_location(result_data)

        assert location is None


class TestSarifParserRemediation:
    """Test remediation extraction."""

    @pytest.fixture
    def parser(self) -> SarifParser:
        """Create parser instance."""
        return SarifParser()

    def test_extract_remediation(self, parser: SarifParser) -> None:
        """Test extracting remediation from fixes."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "fixes": [{"description": {"text": "Replace with secure function"}}],
        }

        remediation = parser._extract_remediation(result_data)

        assert remediation == "Replace with secure function"

    def test_extract_remediation_no_fixes(self, parser: SarifParser) -> None:
        """Test extracting remediation when none provided."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "fixes": [],
        }

        remediation = parser._extract_remediation(result_data)

        assert remediation is None

    def test_extract_remediation_missing_field(self, parser: SarifParser) -> None:
        """Test extracting remediation when field missing."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
        }

        remediation = parser._extract_remediation(result_data)

        assert remediation is None


class TestSarifParserReferences:
    """Test reference extraction."""

    @pytest.fixture
    def parser(self) -> SarifParser:
        """Create parser instance."""
        return SarifParser()

    def test_extract_references_from_related_locations(self, parser: SarifParser) -> None:
        """Test extracting references from related locations."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "relatedLocations": [
                {"message": {"text": "https://example.com/docs"}},
                {"message": {"text": "See also: CWE-79"}},
            ],
        }

        references = parser._extract_references(result_data)

        assert references is not None
        assert len(references) == 2
        assert "https://example.com/docs" in references
        assert "See also: CWE-79" in references

    def test_extract_references_from_cve_property(self, parser: SarifParser) -> None:
        """Test extracting CVE from properties."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "properties": {"cve": "CVE-2024-1234"},
        }

        references = parser._extract_references(result_data)

        assert references is not None
        assert "CVE-2024-1234" in references

    def test_extract_references_combined(self, parser: SarifParser) -> None:
        """Test extracting references from multiple sources."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "relatedLocations": [
                {"message": {"text": "https://example.com/docs"}},
            ],
            "properties": {"cve": "CVE-2024-1234"},
        }

        references = parser._extract_references(result_data)

        assert references is not None
        assert len(references) == 2

    def test_extract_references_none_found(self, parser: SarifParser) -> None:
        """Test extracting references when none present."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
        }

        references = parser._extract_references(result_data)

        assert references is None


class TestSarifParserTags:
    """Test tag extraction."""

    @pytest.fixture
    def parser(self) -> SarifParser:
        """Create parser instance."""
        return SarifParser()

    def test_extract_tags_from_rule_properties(self, parser: SarifParser) -> None:
        """Test extracting tags from rule properties."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "rule": {"properties": {"tags": ["security", "injection"]}},
        }

        tags = parser._extract_tags(result_data)

        assert tags is not None
        assert set(tags) == {"security", "injection"}

    def test_extract_tags_from_result_properties(self, parser: SarifParser) -> None:
        """Test extracting tags from result properties."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "properties": {"tags": ["cwe-79", "xss"]},
        }

        tags = parser._extract_tags(result_data)

        assert tags is not None
        assert set(tags) == {"cwe-79", "xss"}

    def test_extract_tags_combined_and_deduplicated(self, parser: SarifParser) -> None:
        """Test extracting tags from both sources with deduplication."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "rule": {"properties": {"tags": ["security", "injection"]}},
            "properties": {"tags": ["injection", "xss"]},
        }

        tags = parser._extract_tags(result_data)

        assert tags is not None
        assert set(tags) == {"security", "injection", "xss"}

    def test_extract_tags_none_found(self, parser: SarifParser) -> None:
        """Test extracting tags when none present."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
        }

        tags = parser._extract_tags(result_data)

        assert tags is None

    def test_extract_tags_non_list(self, parser: SarifParser) -> None:
        """Test extracting tags handles non-list values."""
        result_data: dict[str, Any] = {
            "ruleId": "TEST",
            "properties": {"tags": "not-a-list"},
        }

        tags = parser._extract_tags(result_data)

        # Should handle gracefully and return None
        assert tags is None


class TestSarifParserEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def parser(self) -> SarifParser:
        """Create parser instance."""
        return SarifParser()

    def test_parse_finding_with_guid_no_rule_id(self, parser: SarifParser) -> None:
        """Test parsing finding with GUID instead of ruleId."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "test"}},
                    "results": [
                        {
                            "guid": "12345-abcde",
                            "level": "warning",
                            "message": {"text": "Issue found"},
                        }
                    ],
                }
            ],
        }

        result = parser.parse(sarif)

        assert len(result.findings) == 1
        assert result.findings[0].id == "12345-abcde"

    def test_parse_finding_no_id_uses_unknown(self, parser: SarifParser) -> None:
        """Test parsing finding without ruleId or guid."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "test"}},
                    "results": [
                        {
                            "level": "warning",
                            "message": {"text": "Issue found"},
                        }
                    ],
                }
            ],
        }

        result = parser.parse(sarif)

        assert len(result.findings) == 1
        assert result.findings[0].id == "unknown"

    def test_parse_with_scan_target_property(self, parser: SarifParser) -> None:
        """Test parsing SARIF with scan target in properties."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "properties": {"scanTarget": "my-app:v1.0.0"},
            "runs": [
                {
                    "tool": {"driver": {"name": "test"}},
                    "results": [],
                }
            ],
        }

        result = parser.parse(sarif)

        assert result.metadata.scan_target == "my-app:v1.0.0"

    def test_parse_finding_includes_raw_data(self, parser: SarifParser) -> None:
        """Test that raw SARIF result is preserved."""
        sarif = {
            "$schema": "https://sarif-schema.org/2.1.0",
            "version": "2.1.0",
            "runs": [
                {
                    "tool": {"driver": {"name": "test"}},
                    "results": [
                        {
                            "ruleId": "TEST",
                            "level": "error",
                            "message": {"text": "Test"},
                            "customField": "customValue",
                        }
                    ],
                }
            ],
        }

        result = parser.parse(sarif)

        assert len(result.findings) == 1
        assert result.findings[0].raw_data is not None
        assert result.findings[0].raw_data["customField"] == "customValue"

    def test_tool_name_and_version_attributes(self, parser: SarifParser) -> None:
        """Test that parser has correct tool name and supported versions."""
        assert parser.tool_name == "sarif"
        assert "2.1.0" in parser.supported_versions
        assert "2.0.0" in parser.supported_versions
