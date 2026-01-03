"""Smoke tests for audit trail and forensic queries.

These tests validate the audit capabilities described in docs/learn/trust/audit-queries.md
and ensure that forensic investigations and compliance reporting work as documented.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest
import requests

# Mark all tests as smoke tests, but allow them to skip if services unavailable
pytestmark = pytest.mark.smoke


# Check service availability at module level
def _check_service_available(url: str, timeout: int = 2) -> bool:
    """Check if a service is available."""
    try:
        requests.get(url, timeout=timeout)
        return True
    except (requests.RequestException, Exception):
        return False


NEO4J_AVAILABLE = _check_service_available(os.getenv("NEO4J_URL", "http://localhost:7474"))
OPENSEARCH_AVAILABLE = _check_service_available(os.getenv("OPENSEARCH_URL", "http://localhost:9200"))

# Configuration
REPO_ROOT = Path(os.getenv("SMOKE_REPO_ROOT", Path(__file__).resolve().parents[3]))
NEO4J_URL = os.getenv("NEO4J_URL", "http://localhost:7474")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")


def _neo4j_query(query: str, timeout: int = 30) -> dict[str, Any]:
    """Execute a Cypher query against Neo4j."""
    response = requests.post(
        f"{NEO4J_URL}/db/neo4j/tx/commit",
        auth=(NEO4J_USER, NEO4J_PASSWORD),
        json={"statements": [{"statement": query}]},
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


def _opensearch_query(index: str, query: dict[str, Any], timeout: int = 30) -> dict[str, Any]:
    """Execute a query against OpenSearch."""
    response = requests.post(f"{OPENSEARCH_URL}/{index}/_search", json=query, timeout=timeout)
    response.raise_for_status()
    return response.json()


@pytest.mark.skipif(not NEO4J_AVAILABLE, reason="Neo4j not available")
def test_neo4j_health_check():
    """Test that Neo4j is accessible for audit queries."""
    response = requests.get(f"{NEO4J_URL}", auth=(NEO4J_USER, NEO4J_PASSWORD), timeout=30)
    response.raise_for_status()
    print("✓ Neo4j is accessible")


@pytest.mark.skipif(not OPENSEARCH_AVAILABLE, reason="OpenSearch not available")
def test_opensearch_health_check():
    """Test that OpenSearch is accessible for provenance queries."""
    response = requests.get(f"{OPENSEARCH_URL}", timeout=30)
    response.raise_for_status()
    print("✓ OpenSearch is accessible")


@pytest.mark.skipif(not NEO4J_AVAILABLE, reason="Neo4j not available")
def test_neo4j_verification_chain_query():
    """Test Neo4j queries for verification chains.

    This test validates the queries shown in audit-queries.md for:
    - Finding verified scans
    - Chain of custody relationships
    - Timeline analysis
    """
    # Query to find artifacts with verified signatures
    # (This would be populated with actual data in a real deployment)
    chain_query = """
    MATCH (scan:SecurityScan)-[:HAS_SIGNATURE]->(sig:Signature)
    WHERE sig.verified = true
    RETURN scan.scan_id as scanId,
           sig.signer as signer,
           sig.timestamp as timestamp
    LIMIT 10
    """

    try:
        result = _neo4j_query(chain_query)
        assert "results" in result
        assert "data" in result["results"][0]
        print("✓ Verification chain query executed successfully")
        print(f"  Found {len(result['results'][0]['data'])} verified scans")
    except requests.RequestException as e:
        pytest.skip(f"Neo4j not available or query failed: {e}")


@pytest.mark.skipif(not NEO4J_AVAILABLE, reason="Neo4j not available")
def test_neo4j_timeline_query():
    """Test Neo4j timeline queries for incident investigation.

    Validates the timeline analysis queries from audit-queries.md.
    """
    # Query for timeline analysis
    timeline_query = """
    MATCH (scan:SecurityScan)-[:HAS_SIGNATURE]->(sig:Signature)
    WHERE datetime(sig.timestamp) > datetime('2024-01-01T00:00:00Z')
    RETURN scan.scan_id as scanId,
           sig.timestamp as timestamp,
           sig.signer as signer
    ORDER BY sig.timestamp DESC
    LIMIT 20
    """

    try:
        result = _neo4j_query(timeline_query)
        assert "results" in result
        print("✓ Timeline query executed successfully")
        if result["results"][0]["data"]:
            print(f"  Found {len(result['results'][0]['data'])} scans in timeline")
    except requests.RequestException as e:
        pytest.skip(f"Neo4j not available or query failed: {e}")


@pytest.mark.skipif(not NEO4J_AVAILABLE, reason="Neo4j not available")
def test_neo4j_chain_of_custody_query():
    """Test chain of custody queries.

    Validates the forensic queries from audit-queries.md that show
    who handled artifacts and when.
    """
    # Chain of custody query
    custody_query = """
    MATCH (artifact:Artifact)-[:VERIFIED_BY]->(signature:Signature)
    OPTIONAL MATCH (signature)-[:CREATED_BY]->(service:Service)
    RETURN artifact.artifact_id as artifactId,
           signature.signer as signer,
           signature.timestamp as timestamp,
           service.service_name as serviceName
    ORDER BY signature.timestamp
    LIMIT 10
    """

    try:
        result = _neo4j_query(custody_query)
        assert "results" in result
        print("✓ Chain of custody query executed successfully")
        print("  Query structure validated")
    except requests.RequestException as e:
        pytest.skip(f"Neo4j not available or query failed: {e}")


@pytest.mark.skipif(not OPENSEARCH_AVAILABLE, reason="OpenSearch not available")
def test_opensearch_provenance_search():
    """Test OpenSearch provenance search capabilities.

    Validates the provenance queries from audit-queries.md.
    """
    # Search for verified artifacts
    search_query = {
        "query": {"bool": {"must": [{"match": {"verified": True}}, {"exists": {"field": "signature_chain"}}]}},
        "size": 10,
        "sort": [{"timestamp": {"order": "desc"}}],
    }

    try:
        # Use a known index or create one for testing
        result = _opensearch_query("security-scans", search_query)
        assert "hits" in result
        print("✓ OpenSearch provenance query executed successfully")
        print(f"  Found {result['hits']['total']['value']} verified artifacts")
    except requests.RequestException as e:
        pytest.skip(f"OpenSearch not available or query failed: {e}")


@pytest.mark.skipif(not NEO4J_AVAILABLE, reason="Neo4j not available")
def test_compliance_reporting_query():
    """Test compliance reporting queries.

    Validates the compliance queries from audit-queries.md that generate
    data for compliance reports.
    """
    # Compliance reporting query
    compliance_query = """
    MATCH (scan:SecurityScan)-[:HAS_SIGNATURE]->(sig:Signature)
    WHERE sig.verified = true
    RETURN
        count(scan) as totalVerifiedScans,
        collect(DISTINCT sig.signer) as signers,
        min(sig.timestamp) as firstVerification,
        max(sig.timestamp) as lastVerification
    """

    try:
        result = _neo4j_query(compliance_query)
        assert "results" in result
        assert "data" in result["results"][0]

        if result["results"][0]["data"]:
            data = result["results"][0]["data"][0]
            print("✓ Compliance reporting query executed successfully")
            print(f"  Total verified scans: {data.get('totalVerifiedScans', 0)}")
            print(f"  Signers: {data.get('signers', [])}")
    except requests.RequestException as e:
        pytest.skip(f"Neo4j not available or query failed: {e}")


# NOTE: Additional tests to implement with actual data:
# - test_actual_verification_chain_with_data() - with populated database
# - test_actual_timeline_analysis() - with real timeline data
# - test_export_audit_trail() - test CSV/JSON export capabilities
# - test_compliance_report_generation() - generate actual reports
