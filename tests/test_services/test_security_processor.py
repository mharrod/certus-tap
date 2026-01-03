"""Unit tests for SecurityProcessor parsing methods.

Tests the service layer abstraction for security file parsing including:
- Format detection
- Filename extraction
- SARIF parsing
- SPDX parsing
- JSONPath parsing
- Pre-registered tool parsing
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from certus_ask.core.exceptions import DocumentParseError
from certus_ask.services.ingestion import SecurityProcessor


@pytest.fixture
def security_processor():
    """Create a SecurityProcessor instance for testing."""
    return SecurityProcessor()


@pytest.fixture
def sample_sarif_json():
    """Sample SARIF JSON for testing."""
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "TestTool", "version": "1.0.0"}},
                "results": [
                    {
                        "ruleId": "TEST-001",
                        "message": {"text": "Test finding"},
                        "level": "warning",
                        "locations": [
                            {"physicalLocation": {"artifactLocation": {"uri": "test.py"}, "region": {"startLine": 10}}}
                        ],
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_spdx_json():
    """Sample SPDX JSON for testing."""
    return {
        "spdxVersion": "SPDX-2.3",
        "name": "TestSBOM",
        "packages": [
            {"name": "test-package", "versionInfo": "1.0.0", "licenseDeclared": "MIT"},
            {"name": "another-package", "versionInfo": "2.0.0", "licenseDeclared": "Apache-2.0"},
        ],
    }


class TestExtractFilename:
    """Tests for SecurityProcessor.extract_filename()."""

    def test_extract_filename_simple(self, security_processor):
        """Should return filename as-is when no path."""
        result = security_processor.extract_filename("scan.sarif")
        assert result == "scan.sarif"

    def test_extract_filename_from_path(self, security_processor):
        """Should extract filename from path."""
        result = security_processor.extract_filename("/path/to/scan.sarif")
        assert result == "scan.sarif"

    def test_extract_filename_from_s3_uri(self, security_processor):
        """Should extract filename from S3 URI."""
        result = security_processor.extract_filename("s3://bucket/scans/scan.sarif")
        assert result == "scan.sarif"

    def test_extract_filename_trailing_slash(self, security_processor):
        """Should handle trailing slash gracefully."""
        result = security_processor.extract_filename("s3://bucket/scans/")
        assert result == "s3://bucket/scans/"  # Returns original if no filename


class TestDetectFormat:
    """Tests for SecurityProcessor.detect_format()."""

    def test_detect_format_explicit_sarif(self, security_processor):
        """Should return explicit format when provided."""
        result = security_processor.detect_format("test.json", "sarif", None)
        assert result == "sarif"

    def test_detect_format_explicit_spdx(self, security_processor):
        """Should return explicit format when provided."""
        result = security_processor.detect_format("test.json", "spdx", None)
        assert result == "spdx"

    def test_detect_format_sarif_by_extension(self, security_processor):
        """Should detect SARIF by .sarif extension."""
        result = security_processor.detect_format("scan.sarif", "auto", None)
        assert result == "sarif"

    def test_detect_format_sarif_with_suffix(self, security_processor):
        """Should detect SARIF from .sarif. pattern."""
        result = security_processor.detect_format("scan.sarif.json", "auto", None)
        assert result == "sarif"

    def test_detect_format_spdx_json(self, security_processor):
        """Should detect SPDX by .spdx.json extension."""
        result = security_processor.detect_format("sbom.spdx.json", "auto", None)
        assert result == "spdx"

    def test_detect_format_spdx_yaml(self, security_processor):
        """Should detect SPDX by .spdx.yaml extension."""
        result = security_processor.detect_format("sbom.spdx.yaml", "auto", None)
        assert result == "spdx"

    def test_detect_format_with_tool_hint(self, security_processor):
        """Should use tool_hint when format is auto."""
        result = security_processor.detect_format("scan.json", "auto", "trivy")
        assert result == "trivy"

    def test_detect_format_unknown_raises_error(self, security_processor):
        """Should raise DocumentParseError when format cannot be detected."""
        with pytest.raises(DocumentParseError) as exc_info:
            security_processor.detect_format("unknown.txt", "auto", None)

        assert exc_info.value.error_code == "unknown_format"
        assert "unknown.txt" in str(exc_info.value.details)

    def test_detect_format_case_insensitive(self, security_processor):
        """Should handle case-insensitive detection."""
        result = security_processor.detect_format("SCAN.SARIF", "auto", None)
        assert result == "sarif"


class TestParseSarif:
    """Tests for SecurityProcessor.parse_sarif()."""

    @patch("certus_ask.pipelines.security_scan_parsers.parse_security_scan")
    def test_parse_sarif_basic(self, mock_parse, security_processor, sample_sarif_json):
        """Should parse SARIF file and return scan data."""
        # Arrange
        mock_unified_scan = Mock()
        mock_unified_scan.findings = [Mock(), Mock(), Mock()]  # 3 findings
        mock_unified_scan.metadata.tool_version = "TestTool 1.0"
        mock_parse.return_value = mock_unified_scan

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sample_sarif_json, f)
            temp_path = Path(f.name)

        try:
            # Act
            unified_scan, documents, findings_count = security_processor.parse_sarif(
                temp_path, "test-ingestion-123", "workspace-1"
            )

            # Assert
            assert unified_scan == mock_unified_scan
            assert documents == []  # Documents created later with Neo4j data
            assert findings_count == 3
            mock_parse.assert_called_once_with(sample_sarif_json, tool_hint="sarif")
        finally:
            temp_path.unlink()

    @patch("certus_ask.pipelines.security_scan_parsers.parse_security_scan")
    def test_parse_sarif_no_findings(self, mock_parse, security_processor, sample_sarif_json):
        """Should handle SARIF with no findings."""
        # Arrange
        mock_unified_scan = Mock()
        mock_unified_scan.findings = []
        mock_unified_scan.metadata.tool_version = "TestTool 1.0"
        mock_parse.return_value = mock_unified_scan

        with tempfile.NamedTemporaryFile(mode="w", suffix=".sarif", delete=False) as f:
            json.dump(sample_sarif_json, f)
            temp_path = Path(f.name)

        try:
            # Act
            _, _, findings_count = security_processor.parse_sarif(temp_path, "test-ingestion-123", "workspace-1")

            # Assert
            assert findings_count == 0
        finally:
            temp_path.unlink()


class TestParseSpdx:
    """Tests for SecurityProcessor.parse_spdx()."""

    @patch("certus_ask.pipelines.spdx.SpdxFileToDocuments")
    def test_parse_spdx_basic(self, mock_parser_class, security_processor, sample_spdx_json):
        """Should parse SPDX file and return data."""
        # Arrange
        mock_parser = Mock()
        mock_parser.run.return_value = {"spdx_data": sample_spdx_json}
        mock_parser_class.return_value = mock_parser

        with tempfile.NamedTemporaryFile(mode="w", suffix=".spdx.json", delete=False) as f:
            json.dump(sample_spdx_json, f)
            temp_path = Path(f.name)

        try:
            # Act
            spdx_data, documents, package_count = security_processor.parse_spdx(
                temp_path, "test-ingestion-456", "workspace-1"
            )

            # Assert
            assert spdx_data == sample_spdx_json
            assert documents == []  # Documents created later with Neo4j data
            assert package_count == 2  # sample_spdx_json has 2 packages
            mock_parser.run.assert_called_once_with(temp_path)
        finally:
            temp_path.unlink()

    @patch("certus_ask.pipelines.spdx.SpdxFileToDocuments")
    def test_parse_spdx_no_packages(self, mock_parser_class, security_processor):
        """Should handle SPDX with no packages."""
        # Arrange
        spdx_no_packages = {"spdxVersion": "SPDX-2.3", "name": "Empty", "packages": []}
        mock_parser = Mock()
        mock_parser.run.return_value = {"spdx_data": spdx_no_packages}
        mock_parser_class.return_value = mock_parser

        with tempfile.NamedTemporaryFile(mode="w", suffix=".spdx.json", delete=False) as f:
            json.dump(spdx_no_packages, f)
            temp_path = Path(f.name)

        try:
            # Act
            _, _, package_count = security_processor.parse_spdx(temp_path, "test-ingestion-456", "workspace-1")

            # Assert
            assert package_count == 0
        finally:
            temp_path.unlink()


class TestParseJsonpath:
    """Tests for SecurityProcessor.parse_jsonpath()."""

    @patch("certus_ask.pipelines.security_scan_parsers.get_parser_registry")
    @patch("certus_ask.pipelines.security_scan_parsers.JSONPathParser")
    @patch("certus_ask.pipelines.security_scan_parsers.SchemaLoader")
    def test_parse_jsonpath_basic(
        self, mock_schema_loader_class, mock_parser_class, mock_registry_func, security_processor
    ):
        """Should parse file using JSONPath schema."""
        # Arrange
        schema = {"tool_name": "CustomTool", "findings_path": "$.results"}

        mock_schema_loader = Mock()
        mock_schema_loader_class.return_value = mock_schema_loader

        mock_finding = Mock()
        mock_finding.title = "Test Finding"
        mock_finding.id = "CUSTOM-001"
        mock_finding.severity = "high"
        mock_finding.description = "Test description"
        mock_finding.location = None

        mock_scan = Mock()
        mock_scan.findings = [mock_finding]
        mock_scan.metadata.tool_name = "CustomTool"
        mock_scan.metadata.tool_version = "1.0.0"

        mock_parser = Mock()
        mock_parser.parse.return_value = mock_scan
        mock_parser_class.return_value = mock_parser

        mock_registry = Mock()
        mock_registry_func.return_value = mock_registry

        test_json = {"results": [{"id": "CUSTOM-001"}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_json, f)
            temp_path = Path(f.name)

        try:
            # Act
            unified_scan, documents, findings_count = security_processor.parse_jsonpath(
                temp_path, schema, "test-ingestion-789", "workspace-1"
            )

            # Assert
            assert unified_scan == mock_scan
            assert len(documents) == 1
            assert findings_count == 1
            assert "CustomTool" in documents[0].content
            assert documents[0].meta["source"] == "jsonpath"
            assert documents[0].meta["tool"] == "CustomTool"

            mock_schema_loader.validate_schema.assert_called_once_with(schema)
            mock_registry.register.assert_called_once()
        finally:
            temp_path.unlink()


class TestParsePreregisteredTool:
    """Tests for SecurityProcessor.parse_preregistered_tool()."""

    @patch("certus_ask.pipelines.security_scan_parsers.JSONPathParser")
    @patch("certus_ask.pipelines.security_scan_parsers.SchemaLoader")
    def test_parse_preregistered_tool_basic(self, mock_schema_loader_class, mock_parser_class, security_processor):
        """Should parse file using pre-registered tool schema."""
        # Arrange
        mock_schema_loader = Mock()
        mock_schema = {"tool_name": "Bandit"}
        mock_schema_loader.load_schema_by_name.return_value = mock_schema
        mock_schema_loader_class.return_value = mock_schema_loader

        mock_finding = Mock()
        mock_finding.title = "Hardcoded Password"
        mock_finding.id = "B105"
        mock_finding.severity = "medium"
        mock_finding.description = "Possible hardcoded password"
        mock_finding.location = None

        mock_scan = Mock()
        mock_scan.findings = [mock_finding, mock_finding]  # 2 findings
        mock_scan.metadata.tool_name = "Bandit"
        mock_scan.metadata.tool_version = "1.7.5"

        mock_parser = Mock()
        mock_parser.parse.return_value = mock_scan
        mock_parser_class.return_value = mock_parser

        test_json = {"results": [{"test_id": "B105"}]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(test_json, f)
            temp_path = Path(f.name)

        try:
            # Act
            unified_scan, documents, findings_count = security_processor.parse_preregistered_tool(
                temp_path, "bandit", "test-ingestion-999", "workspace-1"
            )

            # Assert
            assert unified_scan == mock_scan
            assert len(documents) == 1
            assert findings_count == 2
            assert "Bandit" in documents[0].content
            assert documents[0].meta["source"] == "bandit"
            assert documents[0].meta["tool"] == "Bandit"

            mock_schema_loader.load_schema_by_name.assert_called_once_with("bandit")
        finally:
            temp_path.unlink()

    @patch("certus_ask.pipelines.security_scan_parsers.SchemaLoader")
    def test_parse_preregistered_tool_error_handling(self, mock_schema_loader_class, security_processor):
        """Should raise FileUploadError when parsing fails."""
        from certus_ask.core.exceptions import FileUploadError

        # Arrange
        mock_schema_loader = Mock()
        mock_schema_loader.load_schema_by_name.side_effect = Exception("Schema not found")
        mock_schema_loader_class.return_value = mock_schema_loader

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{}")
            temp_path = Path(f.name)

        try:
            # Act & Assert
            with pytest.raises(FileUploadError) as exc_info:
                security_processor.parse_preregistered_tool(
                    temp_path, "nonexistent", "test-ingestion-error", "workspace-1"
                )

            assert "NONEXISTENT" in exc_info.value.message
            assert exc_info.value.error_code == "nonexistent_processing_failed"
        finally:
            temp_path.unlink()
