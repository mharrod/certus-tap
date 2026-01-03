"""Unit tests for Neo4jService.

Tests the service layer abstraction for Neo4j operations including:
- SARIF data loading
- SPDX data loading
- Markdown generation from SARIF
- Markdown generation from SPDX

All tests use mocked Neo4j loaders and markdown generators.
"""

from unittest.mock import Mock, patch

import pytest

from certus_ask.services.ingestion import Neo4jService


@pytest.fixture
def neo4j_service():
    """Create a Neo4jService instance with test credentials."""
    return Neo4jService(
        uri="bolt://localhost:7687",
        user="neo4j",
        password="testpassword",
    )


@pytest.fixture
def sample_sarif_data():
    """Sample SARIF JSON data for testing."""
    return {
        "version": "2.1.0",
        "runs": [
            {
                "tool": {"driver": {"name": "TestTool", "version": "1.0.0"}},
                "results": [{"ruleId": "TEST-001", "message": {"text": "Test finding"}, "level": "warning"}],
            }
        ],
    }


@pytest.fixture
def sample_spdx_data():
    """Sample SPDX JSON data for testing."""
    return {
        "spdxVersion": "SPDX-2.3",
        "name": "TestSBOM",
        "packages": [{"name": "test-package", "versionInfo": "1.0.0", "licenseDeclared": "MIT"}],
    }


class TestLoadSarif:
    """Tests for Neo4jService.load_sarif()."""

    @patch("certus_ask.pipelines.neo4j_loaders.sarif_loader.SarifToNeo4j")
    def test_load_sarif_basic(self, mock_sarif_loader_class, neo4j_service, sample_sarif_data):
        """Should instantiate SarifToNeo4j, call load(), and close."""
        # Arrange
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = {"nodes_created": 5, "relationships_created": 3}
        mock_sarif_loader_class.return_value = mock_loader_instance

        # Act
        result = neo4j_service.load_sarif(
            sarif_data=sample_sarif_data,
            scan_id="test-scan-123",
        )

        # Assert
        mock_sarif_loader_class.assert_called_once_with("bolt://localhost:7687", "neo4j", "testpassword")
        mock_loader_instance.load.assert_called_once_with(
            sample_sarif_data,
            "test-scan-123",
            verification_proof=None,
            assessment_id=None,
        )
        mock_loader_instance.close.assert_called_once()
        assert result["nodes_created"] == 5
        assert result["relationships_created"] == 3

    @patch("certus_ask.pipelines.neo4j_loaders.sarif_loader.SarifToNeo4j")
    def test_load_sarif_with_verification_proof(self, mock_sarif_loader_class, neo4j_service, sample_sarif_data):
        """Should pass verification_proof to loader for premium tier."""
        # Arrange
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = {"nodes_created": 5}
        mock_sarif_loader_class.return_value = mock_loader_instance

        verification_proof = {
            "chain_verified": True,
            "signer_outer": "test@example.com",
            "sigstore_timestamp": "2025-12-13T10:00:00Z",
        }

        # Act
        result = neo4j_service.load_sarif(
            sarif_data=sample_sarif_data,
            scan_id="premium-scan-456",
            verification_proof=verification_proof,
            assessment_id="assessment-789",
        )

        # Assert
        mock_loader_instance.load.assert_called_once_with(
            sample_sarif_data,
            "premium-scan-456",
            verification_proof=verification_proof,
            assessment_id="assessment-789",
        )

    @patch("certus_ask.pipelines.neo4j_loaders.sarif_loader.SarifToNeo4j")
    def test_load_sarif_closes_on_exception(self, mock_sarif_loader_class, neo4j_service, sample_sarif_data):
        """Should close loader even if load() raises exception."""
        # Arrange
        mock_loader_instance = Mock()
        mock_loader_instance.load.side_effect = Exception("Neo4j connection failed")
        mock_sarif_loader_class.return_value = mock_loader_instance

        # Act & Assert
        with pytest.raises(Exception, match="Neo4j connection failed"):
            neo4j_service.load_sarif(
                sarif_data=sample_sarif_data,
                scan_id="test-scan-123",
            )

        # Verify close() was still called
        mock_loader_instance.close.assert_called_once()


class TestLoadSpdx:
    """Tests for Neo4jService.load_spdx()."""

    @patch("certus_ask.pipelines.neo4j_loaders.spdx_loader.SpdxToNeo4j")
    def test_load_spdx_basic(self, mock_spdx_loader_class, neo4j_service, sample_spdx_data):
        """Should instantiate SpdxToNeo4j, call load(), and close."""
        # Arrange
        mock_loader_instance = Mock()
        mock_loader_instance.load.return_value = {"package_count": 10, "nodes_created": 15}
        mock_spdx_loader_class.return_value = mock_loader_instance

        # Act
        result = neo4j_service.load_spdx(
            spdx_data=sample_spdx_data,
            sbom_id="sbom-abc-123",
        )

        # Assert
        mock_spdx_loader_class.assert_called_once_with("bolt://localhost:7687", "neo4j", "testpassword")
        mock_loader_instance.load.assert_called_once_with(sample_spdx_data, "sbom-abc-123")
        mock_loader_instance.close.assert_called_once()
        assert result["package_count"] == 10

    @patch("certus_ask.pipelines.neo4j_loaders.spdx_loader.SpdxToNeo4j")
    def test_load_spdx_closes_on_exception(self, mock_spdx_loader_class, neo4j_service, sample_spdx_data):
        """Should close loader even if load() raises exception."""
        # Arrange
        mock_loader_instance = Mock()
        mock_loader_instance.load.side_effect = Exception("SBOM parsing failed")
        mock_spdx_loader_class.return_value = mock_loader_instance

        # Act & Assert
        with pytest.raises(Exception, match="SBOM parsing failed"):
            neo4j_service.load_spdx(
                spdx_data=sample_spdx_data,
                sbom_id="sbom-abc-123",
            )

        # Verify close() was still called
        mock_loader_instance.close.assert_called_once()


class TestGenerateSarifMarkdown:
    """Tests for Neo4jService.generate_sarif_markdown()."""

    @patch("certus_ask.pipelines.markdown_generators.sarif_markdown.SarifToMarkdown")
    def test_generate_sarif_markdown_basic(self, mock_markdown_class, neo4j_service):
        """Should instantiate SarifToMarkdown, call generate(), and close."""
        # Arrange
        mock_markdown_instance = Mock()
        mock_markdown_instance.generate.return_value = "# SARIF Report\n\n5 findings found."
        mock_markdown_class.return_value = mock_markdown_instance

        # Act
        result = neo4j_service.generate_sarif_markdown(scan_id="test-scan-123")

        # Assert
        mock_markdown_class.assert_called_once_with("bolt://localhost:7687", "neo4j", "testpassword")
        mock_markdown_instance.generate.assert_called_once_with("test-scan-123")
        mock_markdown_instance.close.assert_called_once()
        assert "# SARIF Report" in result
        assert "5 findings found" in result

    @patch("certus_ask.pipelines.markdown_generators.sarif_markdown.SarifToMarkdown")
    def test_generate_sarif_markdown_closes_on_exception(self, mock_markdown_class, neo4j_service):
        """Should close markdown generator even if generate() raises exception."""
        # Arrange
        mock_markdown_instance = Mock()
        mock_markdown_instance.generate.side_effect = Exception("Scan not found in Neo4j")
        mock_markdown_class.return_value = mock_markdown_instance

        # Act & Assert
        with pytest.raises(Exception, match="Scan not found in Neo4j"):
            neo4j_service.generate_sarif_markdown(scan_id="nonexistent-scan")

        # Verify close() was still called
        mock_markdown_instance.close.assert_called_once()


class TestGenerateSpdxMarkdown:
    """Tests for Neo4jService.generate_spdx_markdown()."""

    @patch("certus_ask.pipelines.markdown_generators.spdx_markdown.SpdxToMarkdown")
    def test_generate_spdx_markdown_basic(self, mock_markdown_class, neo4j_service):
        """Should instantiate SpdxToMarkdown, call generate(), and close."""
        # Arrange
        mock_markdown_instance = Mock()
        mock_markdown_instance.generate.return_value = "# SBOM Report\n\n10 packages found."
        mock_markdown_class.return_value = mock_markdown_instance

        # Act
        result = neo4j_service.generate_spdx_markdown(sbom_id="sbom-abc-123")

        # Assert
        mock_markdown_class.assert_called_once_with("bolt://localhost:7687", "neo4j", "testpassword")
        mock_markdown_instance.generate.assert_called_once_with("sbom-abc-123")
        mock_markdown_instance.close.assert_called_once()
        assert "# SBOM Report" in result
        assert "10 packages found" in result

    @patch("certus_ask.pipelines.markdown_generators.spdx_markdown.SpdxToMarkdown")
    def test_generate_spdx_markdown_closes_on_exception(self, mock_markdown_class, neo4j_service):
        """Should close markdown generator even if generate() raises exception."""
        # Arrange
        mock_markdown_instance = Mock()
        mock_markdown_instance.generate.side_effect = Exception("SBOM not found in Neo4j")
        mock_markdown_class.return_value = mock_markdown_instance

        # Act & Assert
        with pytest.raises(Exception, match="SBOM not found in Neo4j"):
            neo4j_service.generate_spdx_markdown(sbom_id="nonexistent-sbom")

        # Verify close() was still called
        mock_markdown_instance.close.assert_called_once()


class TestNeo4jServiceIntegration:
    """Integration-style tests that verify multiple methods work together."""

    @patch("certus_ask.pipelines.neo4j_loaders.sarif_loader.SarifToNeo4j")
    @patch("certus_ask.pipelines.markdown_generators.sarif_markdown.SarifToMarkdown")
    def test_sarif_load_and_markdown_generation(
        self, mock_markdown_class, mock_loader_class, neo4j_service, sample_sarif_data
    ):
        """Should load SARIF data and then generate markdown from it."""
        # Arrange
        mock_loader = Mock()
        mock_loader.load.return_value = {"nodes_created": 5}
        mock_loader_class.return_value = mock_loader

        mock_markdown = Mock()
        mock_markdown.generate.return_value = "# Report\n5 findings"
        mock_markdown_class.return_value = mock_markdown

        scan_id = "integration-scan-001"

        # Act
        load_result = neo4j_service.load_sarif(sample_sarif_data, scan_id)
        markdown_result = neo4j_service.generate_sarif_markdown(scan_id)

        # Assert
        assert load_result["nodes_created"] == 5
        assert "5 findings" in markdown_result
        mock_loader.load.assert_called_once()
        mock_markdown.generate.assert_called_once_with(scan_id)

    @patch("certus_ask.pipelines.neo4j_loaders.spdx_loader.SpdxToNeo4j")
    @patch("certus_ask.pipelines.markdown_generators.spdx_markdown.SpdxToMarkdown")
    def test_spdx_load_and_markdown_generation(
        self, mock_markdown_class, mock_loader_class, neo4j_service, sample_spdx_data
    ):
        """Should load SPDX data and then generate markdown from it."""
        # Arrange
        mock_loader = Mock()
        mock_loader.load.return_value = {"package_count": 10}
        mock_loader_class.return_value = mock_loader

        mock_markdown = Mock()
        mock_markdown.generate.return_value = "# SBOM\n10 packages"
        mock_markdown_class.return_value = mock_markdown

        sbom_id = "integration-sbom-001"

        # Act
        load_result = neo4j_service.load_spdx(sample_spdx_data, sbom_id)
        markdown_result = neo4j_service.generate_spdx_markdown(sbom_id)

        # Assert
        assert load_result["package_count"] == 10
        assert "10 packages" in markdown_result
        mock_loader.load.assert_called_once()
        mock_markdown.generate.assert_called_once_with(sbom_id)
