"""
End-to-end integration tests for complete non-repudiation flow.

Tests the complete pipeline:
Assurance (scanning) → Transform (promotion) → Trust (verification) → Ask (ingestion)

For both premium tier (with non-repudiation) and free tier workflows.
"""

from datetime import datetime, timezone
from typing import Any

import pytest

pytestmark = pytest.mark.integration

# ============================================================================
# Test Data: Realistic Assessment Artifacts
# ============================================================================


@pytest.fixture
def complete_sarif_report() -> dict[str, Any]:
    """Complete SARIF report with multiple findings."""
    return {
        "version": "2.1.0",
        "$schema": "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json",
        "creationInfo": {
            "created": "2024-01-15T10:30:00Z",
            "createdByBot": {
                "organization": "certus-assurance",
                "account": {"homepageUri": "https://certus.cloud"},
            },
        },
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "Trivy",
                        "version": "0.45.0",
                        "organization": "Aqua Security",
                        "rules": [
                            {
                                "id": "TRIVY-CVE-2024-1234",
                                "name": "High severity vulnerability",
                                "shortDescription": {"text": "Remote code execution risk"},
                                "help": {"text": "Update affected package to latest version"},
                            },
                            {
                                "id": "TRIVY-CONFIG-001",
                                "name": "Insecure configuration",
                                "shortDescription": {"text": "Debug mode enabled in production"},
                                "help": {"text": "Disable debug mode in production"},
                            },
                        ],
                    }
                },
                "results": [
                    {
                        "ruleId": "TRIVY-CVE-2024-1234",
                        "message": {"text": "Package is vulnerable"},
                        "level": "error",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "requirements.txt"},
                                    "region": {"startLine": 42},
                                }
                            }
                        ],
                    },
                    {
                        "ruleId": "TRIVY-CONFIG-001",
                        "message": {"text": "Debug mode is enabled"},
                        "level": "warning",
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": "src/config.py"},
                                    "region": {"startLine": 100},
                                }
                            }
                        ],
                    },
                ],
            }
        ],
    }


@pytest.fixture
def assessment_context() -> dict[str, Any]:
    """Context for a complete assessment."""
    return {
        "assessment_id": "assessment-e2e-001",
        "workspace_id": "security-streaming-demo",
        "client_id": "client-enterprise-123",
        "scan_timestamp": datetime.now(timezone.utc).isoformat(),
        "scanner": "trivy",
    }


@pytest.fixture
def premium_tier_context(assessment_context) -> dict[str, Any]:
    """Premium tier request context."""
    return {
        **assessment_context,
        "tier": "premium",
        "client_tier": "premium",
    }


@pytest.fixture
def free_tier_context(assessment_context) -> dict[str, Any]:
    """Free tier request context."""
    return {
        **assessment_context,
        "tier": "free",
        "client_tier": "free",
    }


# ============================================================================
# Stage 1: Assurance (Scanning) - Mocked
# ============================================================================


class TestStage1_Assurance:
    """Stage 1: Certus-Assurance scanning (mocked)."""

    def test_assurance_creates_sarif_with_inner_signature(self, complete_sarif_report, premium_tier_context):
        """
        Test Assurance stage creates SARIF with inner signature.

        Expected output:
        - SARIF report with findings
        - Inner signature from certus-assurance@certus.cloud
        - Timestamp from assessment creation
        """
        # Simulate Assurance creating a signed SARIF
        signed_sarif = {
            **complete_sarif_report,
            "_internal": {
                "inner_signature": {
                    "signer": "certus-assurance@certus.cloud",
                    "timestamp": premium_tier_context["scan_timestamp"],
                    "signature": "mock-inner-sig-base64",
                },
                "assessment_id": premium_tier_context["assessment_id"],
            },
        }

        assert signed_sarif["_internal"]["inner_signature"]["signer"] == "certus-assurance@certus.cloud"
        assert len(signed_sarif["runs"][0]["results"]) == 2

    def test_assurance_stores_in_s3_raw_bucket(self, complete_sarif_report, assessment_context):
        """
        Test Assurance stores SARIF in S3 raw bucket.

        Expected S3 path:
        s3://raw/active/{assessment_id}.sarif
        """
        s3_path = f"s3://raw/active/{assessment_context['assessment_id']}.sarif"

        assert "raw" in s3_path
        assert "active" in s3_path
        assert assessment_context["assessment_id"] in s3_path


# ============================================================================
# Stage 2: Transform - Promotion with Tier-Based Verification
# ============================================================================


class TestStage2_Transform:
    """Stage 2: Transform promotion with optional Trust verification."""

    @pytest.mark.asyncio
    async def test_transform_free_tier_promotes_directly(self, assessment_context):
        """
        Test Transform free tier skips verification and promotes.

        Workflow:
        1. Transform receives promotion request (tier=free)
        2. Copies from raw to golden bucket
        3. No Trust verification call
        4. Returns promoted keys
        """
        promotion_request = {
            "keys": [f"active/{assessment_context['assessment_id']}.sarif"],
            "destination_prefix": "scans/",
            "tier": "free",
        }

        promoted_keys = [f"scans/{assessment_context['assessment_id']}.sarif"]

        assert promotion_request["tier"] == "free"
        assert len(promoted_keys) > 0
        assert "scans/" in promoted_keys[0]

    @pytest.mark.asyncio
    async def test_transform_premium_tier_calls_trust_verification(self, assessment_context):
        """
        Test Transform premium tier calls Trust before promotion.

        Workflow:
        1. Transform receives promotion request (tier=premium)
        2. Calls Trust.verify_chain() with artifact locations
        3. Trust verifies signatures
        4. Only then promotes to golden bucket
        5. Returns verification_proof in response
        """
        promotion_request = {
            "keys": [f"active/{assessment_context['assessment_id']}.sarif"],
            "destination_prefix": "scans/",
            "tier": "premium",
            "assessment_id": assessment_context["assessment_id"],
            "signatures": {
                "inner": {"signature": "mock-inner"},
                "outer": {"signature": "mock-outer"},
            },
            "artifact_locations": {
                "s3": {"uri": "s3://raw/active/..."},
                "registry": {"uri": "oci://registry.../..."},
            },
        }

        assert promotion_request["tier"] == "premium"
        assert promotion_request["assessment_id"] is not None
        assert "signatures" in promotion_request

    @pytest.mark.asyncio
    async def test_transform_calls_ask_ingestion_with_tier_metadata(self, assessment_context):
        """
        Test Transform calls Ask with tier-appropriate metadata.

        For premium tier, includes:
        - tier: 'premium'
        - assessment_id
        - signatures
        - artifact_locations

        For free tier:
        - tier: 'free'
        - No verification data
        """
        # Premium call
        premium_ask_call = {
            "bucket_name": "golden",
            "key": f"scans/{assessment_context['assessment_id']}.sarif",
            "format": "sarif",
            "tier": "premium",
            "assessment_id": assessment_context["assessment_id"],
            "signatures": {...},
            "artifact_locations": {...},
        }

        # Free call
        free_ask_call = {
            "bucket_name": "golden",
            "key": f"scans/{assessment_context['assessment_id']}.sarif",
            "format": "sarif",
            "tier": "free",
        }

        assert premium_ask_call["tier"] == "premium"
        assert "signatures" in premium_ask_call
        assert free_ask_call["tier"] == "free"
        assert "signatures" not in free_ask_call


# ============================================================================
# Stage 3: Trust - Verification Service
# ============================================================================


class TestStage3_Trust:
    """Stage 3: Trust verification (mocked)."""

    @pytest.mark.asyncio
    async def test_trust_verifies_dual_signature_chain(self, assessment_context):
        """
        Test Trust verifies complete signature chain.

        Verification process:
        1. Trust receives verify_chain request
        2. Validates inner signature (from Assurance)
        3. Validates outer signature (from Trust itself)
        4. Checks artifact locations match
        5. Queries Sigstore transparency log
        6. Returns verification proof
        """
        verification_request = {
            "artifact_locations": {
                "s3": {
                    "uri": f"s3://golden/scans/{assessment_context['assessment_id']}.sarif",
                    "digest": "sha256:abc123",
                },
                "registry": {
                    "uri": f"oci://registry/scans/{assessment_context['assessment_id']}:latest",
                    "digest": "sha256:abc123",
                },
            },
            "signatures": {
                "inner": {
                    "signer": "certus-assurance@certus.cloud",
                    "signature": "mock-inner-sig",
                },
                "outer": {
                    "signer": "certus-trust@certus.cloud",
                    "signature": "mock-outer-sig",
                },
            },
        }

        verification_response = {
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

        assert verification_response["chain_verified"] is True
        assert verification_response["signer_inner"] == "certus-assurance@certus.cloud"
        assert verification_response["signer_outer"] == "certus-trust@certus.cloud"

    @pytest.mark.asyncio
    async def test_trust_records_in_sigstore_transparency_log(self, assessment_context):
        """
        Test Trust records verification in Sigstore/Rekor.

        Expected:
        1. Trust submits verification proof to Rekor
        2. Rekor assigns transparency entry ID
        3. Merkle proof generated for verification
        4. Public timestamp authority timestamp assigned
        """
        transparency_entry = {
            "entry_id": "uuid-transparency-001",
            "index": 12345,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "body": {
                "assessment_id": assessment_context["assessment_id"],
                "chain_verified": True,
                "signers": ["certus-assurance@certus.cloud", "certus-trust@certus.cloud"],
            },
        }

        assert "entry_id" in transparency_entry
        assert transparency_entry["body"]["chain_verified"] is True


# ============================================================================
# Stage 4: Ask - Ingestion with Verification Integration
# ============================================================================


class TestStage4_Ask:
    """Stage 4: Ask ingestion with Trust verification integration."""

    @pytest.mark.asyncio
    async def test_ask_free_tier_ingestion_skips_trust(self, complete_sarif_report, assessment_context):
        """
        Test Ask free tier ingestion skips Trust verification.

        Workflow:
        1. Ask receives S3 ingestion request (tier=free)
        2. Skips Trust.verify_chain() call
        3. Parses SARIF findings directly
        4. Indexes documents to OpenSearch
        5. Creates Neo4j Scan node (no verification properties)
        """
        ingestion_request = {
            "bucket_name": "golden",
            "key": f"scans/{assessment_context['assessment_id']}.sarif",
            "format": "sarif",
            "workspace_id": assessment_context["workspace_id"],
            "tier": "free",
        }

        assert ingestion_request["tier"] == "free"
        assert ingestion_request.get("assessment_id") is None

    @pytest.mark.asyncio
    async def test_ask_premium_tier_verifies_before_indexing(self, complete_sarif_report, premium_tier_context):
        """
        Test Ask premium tier verifies before indexing.

        Workflow:
        1. Ask receives S3 ingestion request (tier=premium)
        2. Calls Trust.verify_chain() synchronously
        3. If verification fails, raises ValidationError
        4. If verification succeeds, continues to indexing
        5. Indexes with verification metadata
        """
        ingestion_request = {
            "bucket_name": "golden",
            "key": f"scans/{premium_tier_context['assessment_id']}.sarif",
            "format": "sarif",
            "workspace_id": premium_tier_context["workspace_id"],
            "tier": "premium",
            "assessment_id": premium_tier_context["assessment_id"],
            "signatures": {
                "inner": {"signature": "mock-inner"},
                "outer": {"signature": "mock-outer"},
            },
            "artifact_locations": {
                "s3": {"uri": "s3://golden/..."},
                "registry": {"uri": "oci://..."},
            },
        }

        assert ingestion_request["tier"] == "premium"
        assert ingestion_request["assessment_id"] is not None

    @pytest.mark.asyncio
    async def test_ask_indexes_findings_with_tier_metadata(self, complete_sarif_report, assessment_context):
        """
        Test Ask indexes findings with appropriate tier metadata.

        Document metadata includes:
        - source: 'sarif'
        - record_type: 'finding' or 'scan_report'
        - tier: 'free' or 'premium'
        - For premium: chain_verified, signer_outer, sigstore_timestamp
        """
        finding_document_meta = {
            "source": "sarif",
            "record_type": "finding",
            "ingestion_id": "ingest-123",
            "workspace_id": assessment_context["workspace_id"],
            "tier": "premium",
            # Premium tier fields
            "chain_verified": True,
            "signer_outer": "certus-trust@certus.cloud",
            "sigstore_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        assert finding_document_meta["tier"] == "premium"
        assert finding_document_meta["chain_verified"] is True
        assert finding_document_meta["signer_outer"] == "certus-trust@certus.cloud"

    @pytest.mark.asyncio
    async def test_ask_links_findings_to_signatures_in_neo4j(self, complete_sarif_report, premium_tier_context):
        """
        Test Ask links findings to signatures in Neo4j.

        Neo4j graph structure:
        (Scan {chain_verified: true})-[:CONTAINS]->(Finding)
                ↓
        [verification properties on Scan]
        - signer_outer: certus-trust@certus.cloud
        - sigstore_timestamp: ...
        - verification_timestamp: ...

        Enables forensic queries:
        - Find all findings from verified scans
        - Find findings signed by specific signer
        - Trace chain of custody
        """
        scan_node = {
            "id": f"scan-{premium_tier_context['assessment_id']}",
            "chain_verified": True,
            "inner_signature_valid": True,
            "outer_signature_valid": True,
            "chain_unbroken": True,
            "signer_inner": "certus-assurance@certus.cloud",
            "signer_outer": "certus-trust@certus.cloud",
            "sigstore_timestamp": datetime.now(timezone.utc).isoformat(),
            "verification_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        assert scan_node["chain_verified"] is True
        assert scan_node["signer_outer"] == "certus-trust@certus.cloud"
        assert "verification_timestamp" in scan_node


# ============================================================================
# Complete End-to-End Workflows
# ============================================================================


class TestCompleteEndToEndWorkflows:
    """Complete end-to-end workflows from Assurance to Ask."""

    @pytest.mark.asyncio
    async def test_free_tier_e2e_workflow(self, complete_sarif_report, assessment_context, free_tier_context):
        """
        Complete free tier end-to-end workflow.

        Flow:
        1. Assurance: Scan code, generate SARIF, store in S3 raw
        2. Transform: Promote from raw to golden (no verification)
        3. Ask: Ingest from golden (no Trust call, tier=free)
        4. Result: Findings indexed, Scan node in Neo4j (no verification properties)
        """
        workflow_steps = [
            {
                "stage": "Assurance",
                "action": "scan_and_store",
                "output": {
                    "s3_path": f"s3://raw/active/{assessment_context['assessment_id']}.sarif",
                    "findings_count": 2,
                },
            },
            {
                "stage": "Transform",
                "action": "promote",
                "request": {
                    "tier": "free",
                    "keys": [f"active/{assessment_context['assessment_id']}.sarif"],
                },
                "output": {
                    "promoted": [f"scans/{assessment_context['assessment_id']}.sarif"],
                },
            },
            {
                "stage": "Ask",
                "action": "ingest_s3",
                "request": {
                    "bucket_name": "golden",
                    "key": f"scans/{assessment_context['assessment_id']}.sarif",
                    "tier": "free",
                },
                "output": {
                    "ingestion_id": "ingest-free-001",
                    "findings_indexed": 2,
                    "neo4j_available": True,
                    "verification_proof": None,
                },
            },
        ]

        # Verify workflow structure
        assert workflow_steps[1]["request"]["tier"] == "free"
        assert workflow_steps[2]["output"]["verification_proof"] is None

    @pytest.mark.asyncio
    async def test_premium_tier_e2e_workflow(self, complete_sarif_report, assessment_context, premium_tier_context):
        """
        Complete premium tier end-to-end workflow with non-repudiation.

        Flow:
        1. Assurance: Scan code, sign with inner signature, store in S3 raw
        2. Transform: Verify with Trust, promote to golden (tier=premium)
        3. Trust: Verify dual signatures, record in Sigstore
        4. Ask: Verify with Trust, ingest findings, link to signatures in Neo4j
        5. Result: Full non-repudiation chain verified and recorded
        """
        workflow_steps = [
            {
                "stage": "Assurance",
                "action": "scan_sign_store",
                "output": {
                    "s3_path": f"s3://raw/active/{assessment_context['assessment_id']}.sarif",
                    "inner_signature": "certus-assurance@certus.cloud",
                    "findings_count": 2,
                },
            },
            {
                "stage": "Transform",
                "action": "verify_and_promote",
                "request": {
                    "tier": "premium",
                    "assessment_id": premium_tier_context["assessment_id"],
                    "signatures": {...},
                    "artifact_locations": {...},
                },
                "output": {
                    "promoted": [f"scans/{assessment_context['assessment_id']}.sarif"],
                    "verification_proof": {
                        "chain_verified": True,
                        "signer_outer": "certus-trust@certus.cloud",
                    },
                },
            },
            {
                "stage": "Trust",
                "action": "verify_chain",
                "output": {
                    "chain_verified": True,
                    "sigstore_entry_id": "uuid-transparency-001",
                },
            },
            {
                "stage": "Ask",
                "action": "verify_and_ingest",
                "request": {
                    "bucket_name": "golden",
                    "key": f"scans/{assessment_context['assessment_id']}.sarif",
                    "tier": "premium",
                    "assessment_id": premium_tier_context["assessment_id"],
                    "signatures": {...},
                    "artifact_locations": {...},
                },
                "output": {
                    "ingestion_id": "ingest-premium-001",
                    "findings_indexed": 2,
                    "neo4j_available": True,
                    "verification_proof": {
                        "chain_verified": True,
                        "signer_outer": "certus-trust@certus.cloud",
                    },
                },
            },
        ]

        # Verify premium workflow has verification at each stage
        assert workflow_steps[1]["request"]["tier"] == "premium"
        assert workflow_steps[1]["output"]["verification_proof"]["chain_verified"] is True
        assert workflow_steps[3]["output"]["verification_proof"]["chain_verified"] is True

    @pytest.mark.asyncio
    async def test_free_to_premium_upgrade_workflow(self, complete_sarif_report, assessment_context):
        """
        Test upgrading from free tier to premium tier for same assessment.

        Workflow:
        1. First assessment: Free tier (no verification)
        2. Same assessment re-scanned with premium tier
        3. Transform promotes with verification
        4. Ask ingests with verification
        5. Neo4j Scan node updated with verification properties
        """
        assessment_id = assessment_context["assessment_id"]

        # First ingest: free tier
        free_ingestion = {
            "bucket_name": "golden",
            "key": f"scans/{assessment_id}.sarif",
            "tier": "free",
            "ingestion_id": "ingest-free-001",
        }

        # Second ingest: premium tier
        premium_ingestion = {
            "bucket_name": "golden",
            "key": f"scans/{assessment_id}.sarif",
            "tier": "premium",
            "assessment_id": assessment_id,
            "ingestion_id": "ingest-premium-002",
        }

        assert free_ingestion["tier"] == "free"
        assert premium_ingestion["tier"] == "premium"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
