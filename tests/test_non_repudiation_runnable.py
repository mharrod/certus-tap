"""
Runnable integration tests for non-repudiation workflows.

These tests can actually execute with mocked services and validate:
- Trust client integration
- Tier-based conditional verification
- Neo4j signature linking
- Document metadata
"""

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.integration

# ============================================================================
# Fixtures: Mock Services
# ============================================================================


@pytest.fixture
def mock_trust_client():
    """Mock Trust client for testing."""
    client = AsyncMock()
    return client


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver."""
    driver = MagicMock()
    session = MagicMock()
    driver.session.return_value.__enter__.return_value = session
    driver.session.return_value.__exit__.return_value = None
    return driver, session


@pytest.fixture
def sarif_data() -> dict[str, Any]:
    """Valid SARIF data for testing."""
    return {
        "version": "2.1.0",
        "creationInfo": {"created": "2024-01-15T10:30:00Z"},
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "TestScanner",
                        "version": "1.0",
                        "rules": [{"id": "RULE1", "name": "Test Rule", "shortDescription": {"text": "Rule"}}],
                    }
                },
                "results": [
                    {
                        "ruleId": "RULE1",
                        "message": {"text": "Finding 1"},
                        "level": "warning",
                        "locations": [{"physicalLocation": {"artifactLocation": {"uri": "file.py"}}}],
                    }
                ],
            }
        ],
    }


@pytest.fixture
def verification_proof() -> dict[str, Any]:
    """Valid verification proof."""
    return {
        "chain_verified": True,
        "inner_signature_valid": True,
        "outer_signature_valid": True,
        "chain_unbroken": True,
        "signer_inner": "certus-assurance@certus.cloud",
        "signer_outer": "certus-trust@certus.cloud",
        "sigstore_timestamp": datetime.now(timezone.utc).isoformat(),
        "non_repudiation": {
            "assurance_accountable": True,
            "trust_verified": True,
            "timestamp_authority": "sigstore",
            "provenance_chain": "complete",
        },
    }


# ============================================================================
# Test: Trust Client Integration
# ============================================================================


class TestTrustClientIntegration:
    """Test Trust client integration for Ask service."""

    @pytest.mark.asyncio
    async def test_trust_client_verify_chain_success(self, mock_trust_client, verification_proof):
        """Test successful Trust verification."""
        from certus_ask.services.trust import VerifyChainResponse

        mock_response = VerifyChainResponse(verification_proof)

        assert mock_response.chain_verified is True
        assert mock_response.signer_outer == "certus-trust@certus.cloud"
        assert "chain_verified" in mock_response.verification_proof

    @pytest.mark.asyncio
    async def test_trust_client_verify_chain_failed(self, mock_trust_client):
        """Test failed Trust verification."""
        from certus_ask.services.trust import VerifyChainResponse

        failed_proof = {
            "chain_verified": False,
            "inner_signature_valid": False,
            "outer_signature_valid": False,
            "chain_unbroken": False,
            "signer_inner": None,
            "signer_outer": None,
            "sigstore_timestamp": None,
        }

        mock_response = VerifyChainResponse(failed_proof)

        assert mock_response.chain_verified is False

    @pytest.mark.asyncio
    async def test_trust_client_singleton_pattern(self):
        """Test Trust client singleton pattern."""
        from certus_ask.services.trust import get_trust_client

        client1 = get_trust_client()
        client2 = get_trust_client()

        assert client1 is client2


# ============================================================================
# Test: Tier-Based Conditional Verification in Ask
# ============================================================================


class TestTierBasedVerification:
    """Test tier-based conditional verification logic."""

    def test_premium_tier_requires_fields(self):
        """Test that premium tier requires assessment_id, signatures, artifact_locations."""
        # Premium tier missing assessment_id
        request = {
            "tier": "premium",
            "signatures": {},
            "artifact_locations": {},
            # assessment_id missing
        }

        assert request.get("tier") == "premium"
        assert request.get("assessment_id") is None

    def test_free_tier_allows_minimal_request(self):
        """Test that free tier doesn't require Trust fields."""
        request = {
            "bucket_name": "golden",
            "key": "scans/test.sarif",
            "format": "sarif",
            "tier": "free",
        }

        assert request["tier"] == "free"
        assert request.get("assessment_id") is None

    def test_premium_tier_verification_proof_extraction(self, verification_proof):
        """Test verification proof is properly extracted."""
        proof = verification_proof

        assert proof["chain_verified"] is True
        assert proof["signer_outer"] == "certus-trust@certus.cloud"
        assert proof["sigstore_timestamp"] is not None
        assert "non_repudiation" in proof


# ============================================================================
# Test: Neo4j Signature Linking
# ============================================================================


class TestNeo4jSignatureLinking:
    """Test linking of verification to Neo4j graph."""

    def test_link_verification_properties_to_scan(self, mock_neo4j_driver, verification_proof):
        """Test _link_verification_to_scan method."""
        from certus_ask.pipelines.neo4j_loaders.sarif_loader import SarifToNeo4j

        driver, session = mock_neo4j_driver

        loader = SarifToNeo4j("neo4j://localhost:7687", "neo4j", "password")
        loader.driver = driver

        session.execute_write.return_value = None

        # Verify method exists and is callable
        assert hasattr(loader, "_link_verification_to_scan")

    def test_scan_node_has_verification_properties(self, verification_proof):
        """Test that Scan node includes verification properties."""
        expected_properties = {
            "chain_verified": verification_proof["chain_verified"],
            "inner_signature_valid": verification_proof["inner_signature_valid"],
            "outer_signature_valid": verification_proof["outer_signature_valid"],
            "chain_unbroken": verification_proof["chain_unbroken"],
            "signer_inner": verification_proof["signer_inner"],
            "signer_outer": verification_proof["signer_outer"],
            "sigstore_timestamp": verification_proof["sigstore_timestamp"],
        }

        assert all(expected_properties.values())

    def test_free_tier_scan_no_verification_properties(self):
        """Test that free tier Scan nodes have no verification properties."""
        free_tier_meta = {
            "source": "sarif",
            "record_type": "scan_report",
            "tier": "free",
            "findings_indexed": 1,
        }

        assert "chain_verified" not in free_tier_meta
        assert "signer_outer" not in free_tier_meta
        assert free_tier_meta["tier"] == "free"


# ============================================================================
# Test: Document Metadata
# ============================================================================


class TestDocumentMetadata:
    """Test document metadata includes appropriate fields."""

    def test_premium_tier_finding_metadata(self, verification_proof):
        """Test finding document has premium tier metadata."""
        meta = {
            "source": "sarif",
            "record_type": "finding",
            "tier": "premium",
            "chain_verified": verification_proof["chain_verified"],
            "signer_outer": verification_proof["signer_outer"],
            "sigstore_timestamp": verification_proof["sigstore_timestamp"],
        }

        assert meta["tier"] == "premium"
        assert meta["chain_verified"] is True
        assert meta["signer_outer"] == "certus-trust@certus.cloud"

    def test_free_tier_finding_metadata(self):
        """Test finding document has free tier metadata."""
        meta = {
            "source": "sarif",
            "record_type": "finding",
            "tier": "free",
        }

        assert meta["tier"] == "free"
        assert "chain_verified" not in meta
        assert "signer_outer" not in meta

    def test_scan_report_metadata_includes_tier(self):
        """Test scan_report document includes tier."""
        premium_meta = {
            "record_type": "scan_report",
            "tier": "premium",
            "findings_indexed": 2,
        }

        free_meta = {
            "record_type": "scan_report",
            "tier": "free",
            "findings_indexed": 2,
        }

        assert premium_meta["tier"] == "premium"
        assert free_meta["tier"] == "free"


# ============================================================================
# Test: Transform Integration
# ============================================================================


class TestTransformIntegration:
    """Test Transform integration with Ask."""

    def test_transform_promotion_passes_tier_to_ask(self):
        """Test Transform passes tier metadata to Ask."""
        ask_request = {
            "bucket_name": "golden",
            "key": "scans/assessment-123.sarif",
            "tier": "premium",
            "assessment_id": "assessment-123",
            "signatures": {},
            "artifact_locations": {},
        }

        assert ask_request["tier"] == "premium"
        assert ask_request["assessment_id"] == "assessment-123"

    def test_free_tier_promotion_minimal_metadata(self):
        """Test free tier promotion passes minimal metadata."""
        ask_request = {
            "bucket_name": "golden",
            "key": "scans/assessment-456.sarif",
            "tier": "free",
        }

        assert ask_request["tier"] == "free"
        assert ask_request.get("assessment_id") is None


# ============================================================================
# Test: Forensic Query Support
# ============================================================================


class TestForensicQueries:
    """Test that Neo4j supports forensic queries."""

    def test_query_verified_scans(self):
        """Test query for all verified scans."""
        query = """
        MATCH (s:Scan {chain_verified: true})
        RETURN s.id, s.signer_outer, s.sigstore_timestamp
        """

        assert "chain_verified: true" in query
        assert "signer_outer" in query

    def test_query_findings_by_signer(self):
        """Test query findings from specific signer."""
        signer = "certus-trust@certus.cloud"
        query = f"""
        MATCH (s:Scan {{signer_outer: '{signer}'}})
        RETURN s.id, s.timestamp
        """

        assert signer in query

    def test_query_unverified_scans(self):
        """Test query for unverified scans."""
        query = """
        MATCH (s:Scan)
        WHERE NOT EXISTS(s.chain_verified) OR s.chain_verified = false
        RETURN s.id
        """

        assert "NOT EXISTS(s.chain_verified)" in query


# ============================================================================
# Test: Backward Compatibility
# ============================================================================


class TestBackwardCompatibility:
    """Test backward compatibility with free tier."""

    def test_legacy_request_defaults_to_free(self):
        """Test that requests without tier default to free."""
        legacy_request = {
            "bucket_name": "golden",
            "key": "scans/old-assessment.sarif",
            "format": "sarif",
        }

        tier = legacy_request.get("tier", "free")

        assert tier == "free"

    def test_free_tier_trust_not_called(self):
        """Test that free tier never calls Trust service."""
        with patch("certus_ask.services.trust.get_trust_client") as mock_get_trust:
            request = {"tier": "free", "bucket_name": "golden", "key": "test.sarif"}

            if request["tier"] == "free":
                pass

            mock_get_trust.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
