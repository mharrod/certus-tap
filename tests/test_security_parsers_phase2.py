"""Phase 2 tests: JSONPath-based security scan parsing.

Tests for:
- JSONPathParser class
- SchemaLoader functionality
- Registry schema registration
- End-to-end parsing with custom schemas
"""

import json
from pathlib import Path

import pytest

from certus_ask.pipelines.security_scan_parsers import (
    JSONPathParser,
    SchemaLoader,
    get_parser_registry,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def bandit_schema() -> dict:
    """Bandit JSONPath schema."""
    return {
        "tool_name": "bandit",
        "version": "1.7.0",
        "description": "Bandit is a tool for finding common security issues in Python code",
        "format": {
            "findings_path": "$.results[*]",
            "mapping": {
                "id": "$.test_id",
                "title": "$.test",
                "severity": "$.severity",
                "description": "$.issue_text",
                "type": "vulnerability",
                "file_path": "$.filename",
                "line_start": "$.line_number",
                "code_snippet": "$.code",
            },
        },
    }


@pytest.fixture
def custom_schema() -> dict:
    """Custom tool JSONPath schema."""
    return {
        "tool_name": "custom-scanner",
        "version": "1.0.0",
        "format": {
            "findings_path": "$.vulnerabilities[*]",
            "mapping": {
                "id": "$.vuln_id",
                "title": "$.name",
                "severity": "$.level",
                "file_path": "$.path",
                "line_start": "$.line",
            },
        },
    }


@pytest.fixture
def bandit_data() -> dict:
    """Sample Bandit output data."""
    return {
        "results": [
            {
                "test_id": "B101",
                "test": "assert_used",
                "severity": "MEDIUM",
                "issue_text": "Use of assert detected.",
                "filename": "src/utils.py",
                "line_number": 42,
                "code": "assert condition",
            },
            {
                "test_id": "B601",
                "test": "paramiko_calls",
                "severity": "HIGH",
                "issue_text": "Paramiko call with policy detected.",
                "filename": "src/ssh.py",
                "line_number": 15,
                "code": "ssh.set_missing_host_key_policy(AutoAddPolicy())",
            },
        ]
    }


@pytest.fixture
def custom_data() -> dict:
    """Sample custom scanner output data."""
    return {
        "vulnerabilities": [
            {
                "vuln_id": "VULN-001",
                "name": "SQL Injection",
                "level": "CRITICAL",
                "path": "src/models.py",
                "line": 34,
            },
            {
                "vuln_id": "VULN-002",
                "name": "XSS Vulnerability",
                "level": "HIGH",
                "path": "src/templates.py",
                "line": 56,
            },
        ]
    }


# ============================================================================
# SchemaLoader Tests
# ============================================================================


class TestSchemaLoader:
    """Tests for SchemaLoader class."""

    def test_validate_schema_valid(self, bandit_schema):
        """Test validation of valid schema."""
        assert SchemaLoader.validate_schema(bandit_schema) is True

    def test_validate_schema_missing_tool_name(self):
        """Test validation fails without tool_name."""
        schema = {"format": {"findings_path": "$.results", "mapping": {}}}
        with pytest.raises(ValueError, match="tool_name"):
            SchemaLoader.validate_schema(schema)

    def test_validate_schema_missing_format(self):
        """Test validation fails without format."""
        schema = {"tool_name": "test"}
        with pytest.raises(ValueError, match="format"):
            SchemaLoader.validate_schema(schema)

    def test_validate_schema_missing_findings_path(self):
        """Test validation fails without findings_path."""
        schema = {"tool_name": "test", "format": {"mapping": {}}}
        with pytest.raises(ValueError, match="findings_path"):
            SchemaLoader.validate_schema(schema)

    def test_validate_schema_missing_mapping(self):
        """Test validation fails without mapping."""
        schema = {
            "tool_name": "test",
            "format": {"findings_path": "$.results"},
        }
        with pytest.raises(ValueError, match="mapping"):
            SchemaLoader.validate_schema(schema)

    def test_validate_schema_invalid_findings_path_type(self):
        """Test validation fails if findings_path is not string."""
        schema = {
            "tool_name": "test",
            "format": {"findings_path": 123, "mapping": {}},
        }
        with pytest.raises(ValueError, match="findings_path must be a string"):
            SchemaLoader.validate_schema(schema)

    def test_validate_schema_invalid_mapping_type(self):
        """Test validation fails if mapping is not dict."""
        schema = {
            "tool_name": "test",
            "format": {"findings_path": "$.results", "mapping": "not_dict"},
        }
        with pytest.raises(ValueError, match="mapping must be a dict"):
            SchemaLoader.validate_schema(schema)

    def test_validate_schema_invalid_mapping_field_type(self):
        """Test validation fails if mapping field is not string."""
        schema = {
            "tool_name": "test",
            "format": {"findings_path": "$.results", "mapping": {"id": 123}},
        }
        with pytest.raises(ValueError):
            SchemaLoader.validate_schema(schema)

    def test_list_available_schemas(self):
        """Test listing available built-in schemas."""
        schemas = SchemaLoader.list_available_schemas()
        assert "bandit" in schemas
        assert "opengrep" in schemas
        assert "trivy" in schemas

    def test_load_schema_by_name(self):
        """Test loading a built-in schema."""
        schema = SchemaLoader.load_schema_by_name("bandit")
        assert schema["tool_name"] == "bandit"
        assert "format" in schema
        assert "mapping" in schema["format"]

    def test_load_schema_not_found(self):
        """Test loading non-existent schema."""
        with pytest.raises(FileNotFoundError):
            SchemaLoader.load_schema_by_name("nonexistent")

    def test_get_schema_info(self):
        """Test getting schema metadata."""
        info = SchemaLoader.get_schema_info("bandit")
        assert info["tool_name"] == "bandit"
        assert "version" in info
        assert "description" in info
        assert "fields" in info
        assert len(info["fields"]) > 0


# ============================================================================
# JSONPathParser Tests
# ============================================================================


class TestJSONPathParser:
    """Tests for JSONPathParser class."""

    def test_parser_initialization(self, bandit_schema):
        """Test parser initialization with schema."""
        parser = JSONPathParser(bandit_schema)
        assert parser.tool_name == "bandit"
        assert parser.version == "1.7.0"
        assert parser.findings_path == "$.results[*]"

    def test_parser_invalid_jsonpath(self):
        """Test parser initialization with invalid JSONPath."""
        schema = {
            "tool_name": "test",
            "format": {
                "findings_path": "$[invalid jsonpath",
                "mapping": {},
            },
        }
        with pytest.raises(ValueError, match="Invalid JSONPath"):
            JSONPathParser(schema)

    def test_validate_with_findings(self, bandit_schema, bandit_data):
        """Test validation succeeds with findings."""
        parser = JSONPathParser(bandit_schema)
        assert parser.validate(bandit_data) is True

    def test_validate_without_findings(self, bandit_schema):
        """Test validation fails without findings."""
        parser = JSONPathParser(bandit_schema)
        assert parser.validate({}) is False
        assert parser.validate({"results": []}) is False

    def test_parse_bandit_format(self, bandit_schema, bandit_data):
        """Test parsing Bandit format data."""
        parser = JSONPathParser(bandit_schema)
        result = parser.parse(bandit_data)

        assert result.metadata.tool_name == "bandit"
        assert len(result.findings) == 2

        # Check first finding
        finding = result.findings[0]
        assert finding.id == "B101"
        assert finding.title == "assert_used"
        assert finding.severity == "MEDIUM"
        assert finding.location.file_path == "src/utils.py"
        assert finding.location.line_start == 42

    def test_parse_custom_format(self, custom_schema, custom_data):
        """Test parsing custom format data."""
        parser = JSONPathParser(custom_schema)
        result = parser.parse(custom_data)

        assert result.metadata.tool_name == "custom-scanner"
        assert len(result.findings) == 2

        # Check first finding
        finding = result.findings[0]
        assert finding.id == "VULN-001"
        assert finding.title == "SQL Injection"
        assert finding.severity == "CRITICAL"
        assert finding.location.file_path == "src/models.py"

    def test_parse_empty_findings(self, bandit_schema):
        """Test parsing with no findings."""
        parser = JSONPathParser(bandit_schema)
        result = parser.parse({"results": []})

        assert result.metadata.tool_name == "bandit"
        assert len(result.findings) == 0

    def test_parse_preserves_raw_data(self, bandit_schema, bandit_data):
        """Test that raw finding data is preserved."""
        parser = JSONPathParser(bandit_schema)
        result = parser.parse(bandit_data)

        finding = result.findings[0]
        assert finding.raw_data == bandit_data["results"][0]

    def test_parse_missing_optional_fields(self, custom_schema):
        """Test parsing with missing optional fields."""
        data = {
            "vulnerabilities": [
                {
                    "vuln_id": "VULN-001",
                    "name": "SQL Injection",
                    "level": "CRITICAL",
                    # missing path and line
                }
            ]
        }
        parser = JSONPathParser(custom_schema)
        result = parser.parse(data)

        finding = result.findings[0]
        assert finding.id == "VULN-001"
        assert finding.title == "SQL Injection"
        assert finding.location is None  # Missing file path

    def test_parse_severity_normalization(self, bandit_schema, bandit_data):
        """Test that severity is normalized."""
        parser = JSONPathParser(bandit_schema)
        result = parser.parse(bandit_data)

        # Bandit uses uppercase severity
        assert result.findings[0].severity == "MEDIUM"
        assert result.findings[1].severity == "HIGH"

    def test_parse_with_references(self):
        """Test parsing with reference fields."""
        schema = {
            "tool_name": "test",
            "format": {
                "findings_path": "$.issues[*]",
                "mapping": {
                    "id": "$.issue_id",
                    "title": "$.name",
                    "references": "$.cves[*]",
                },
            },
        }
        data = {
            "issues": [
                {
                    "issue_id": "1",
                    "name": "Issue 1",
                    "cves": ["CVE-2021-1234", "CVE-2021-5678"],
                }
            ]
        }

        parser = JSONPathParser(schema)
        result = parser.parse(data)

        finding = result.findings[0]
        assert finding.references == ["CVE-2021-1234", "CVE-2021-5678"]


# ============================================================================
# Registry Schema Registration Tests
# ============================================================================


class TestRegistrySchemaRegistration:
    """Tests for registering schemas in the registry."""

    def test_register_schema(self, custom_schema):
        """Test registering a schema."""
        registry = get_parser_registry()
        registry.register_schema(custom_schema)

        # Should be able to retrieve the parser
        parser = registry.get("custom-scanner")
        assert parser is not None
        assert parser.tool_name == "custom-scanner"

    def test_register_invalid_schema(self):
        """Test registering invalid schema fails."""
        registry = get_parser_registry()
        invalid_schema = {"tool_name": "test"}  # Missing format

        with pytest.raises(ValueError):
            registry.register_schema(invalid_schema)

    def test_parse_with_registered_schema(self, custom_schema, custom_data):
        """Test parsing with a registered schema."""
        registry = get_parser_registry()
        registry.register_schema(custom_schema)

        result = registry.parse(custom_data, tool_hint="custom-scanner")
        assert len(result.findings) == 2
        assert result.findings[0].id == "VULN-001"


# ============================================================================
# End-to-End Integration Tests
# ============================================================================


class TestPhase2Integration:
    """End-to-end integration tests for Phase 2."""

    def test_parse_bandit_dummy_data(self):
        """Test parsing actual Bandit dummy data file."""
        # Load dummy data
        dummy_path = Path(__file__).parent.parent / "samples" / "bandit_dummy.json"
        with open(dummy_path) as f:
            bandit_data = json.load(f)

        # Load schema
        schema = SchemaLoader.load_schema_by_name("bandit")

        # Parse
        parser = JSONPathParser(schema)
        result = parser.parse(bandit_data)

        assert result.metadata.tool_name == "bandit"
        assert len(result.findings) > 0

        # Validate findings structure
        for finding in result.findings:
            assert finding.id
            assert finding.title
            assert finding.severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]

    def test_parse_opengrep_dummy_data(self):
        """Test parsing actual OpenGrep dummy data file."""
        dummy_path = Path(__file__).parent.parent / "samples" / "opengrep_dummy.json"
        with open(dummy_path) as f:
            opengrep_data = json.load(f)

        schema = SchemaLoader.load_schema_by_name("opengrep")
        parser = JSONPathParser(schema)
        result = parser.parse(opengrep_data)

        assert result.metadata.tool_name == "opengrep"
        assert len(result.findings) > 0

    def test_parse_trivy_dummy_data(self):
        """Test parsing actual Trivy dummy data file."""
        dummy_path = Path(__file__).parent.parent / "samples" / "trivy_dummy.json"
        with open(dummy_path) as f:
            trivy_data = json.load(f)

        schema = SchemaLoader.load_schema_by_name("trivy")
        parser = JSONPathParser(schema)
        result = parser.parse(trivy_data)

        assert result.metadata.tool_name == "trivy"
        # Trivy has nested findings structure
        assert len(result.findings) > 0


# ============================================================================
# Edge Cases and Error Handling
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_parse_with_null_fields(self):
        """Test parsing with null values in data."""
        schema = {
            "tool_name": "test",
            "format": {
                "findings_path": "$.issues[*]",
                "mapping": {
                    "id": "$.id",
                    "title": "$.title",
                    "description": "$.desc",
                },
            },
        }
        data = {
            "issues": [
                {
                    "id": "1",
                    "title": None,
                    "desc": "Description",
                }
            ]
        }

        parser = JSONPathParser(schema)
        result = parser.parse(data)

        # Should use title as fallback for missing title
        finding = result.findings[0]
        assert finding.title == "Unknown Issue"

    def test_parse_with_nested_references(self):
        """Test parsing with nested reference arrays."""
        schema = {
            "tool_name": "test",
            "format": {
                "findings_path": "$.findings[*]",
                "mapping": {
                    "id": "$.id",
                    "title": "$.title",
                    "references": "$.metadata.cves[*]",
                },
            },
        }
        data = {
            "findings": [
                {
                    "id": "1",
                    "title": "Issue",
                    "metadata": {"cves": ["CVE-2021-1234"]},
                }
            ]
        }

        parser = JSONPathParser(schema)
        result = parser.parse(data)
        finding = result.findings[0]
        assert finding.references == ["CVE-2021-1234"]

    def test_parser_reregistration_allowed(self, custom_schema):
        """Test that JSONPath parsers can be re-registered with new schema."""
        registry = get_parser_registry()

        # Register once
        registry.register_schema(custom_schema)
        parser1 = registry.get("custom-scanner")

        # Register again with same schema
        registry.register_schema(custom_schema)
        parser2 = registry.get("custom-scanner")

        # Should be allowed and updated
        assert parser1 is not None
        assert parser2 is not None
        assert parser1.tool_name == parser2.tool_name
