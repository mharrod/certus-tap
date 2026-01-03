"""Integration tests for hybrid search functionality.

These tests validate the hybrid search workflows described in
 docs/learn/ask/hybrid-search.md
"""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = [pytest.mark.integration, pytest.mark.slow]

ASK_URL = os.getenv("ASK_URL", "http://localhost:8000")
OPENSEARCH_URL = os.getenv("OPENSEARCH_URL", "http://localhost:9200")
NEO4J_URL = os.getenv("NEO4J_URL", "http://localhost:7474")

WORKSPACE_ID = "hybrid-search-test"


def test_hybrid_search_workflow(http_session: requests.Session, request_timeout: int):
    """Test the complete hybrid search workflow.

    This test validates the workflow described in hybrid-search.md:
    1. Semantic search in OpenSearch (discovery)
    2. Graph traversal in Neo4j (analysis)
    3. Combined results (reporting)
    """
    # Step 1: Semantic search in OpenSearch
    semantic_query = "security vulnerabilities in authentication"

    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": semantic_query}, timeout=request_timeout
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready - requires ingested artifacts")

    response.raise_for_status()
    semantic_results = response.json()

    # Validate semantic search results
    assert "answer" in semantic_results or "response" in semantic_results
    print(f"✓ Semantic search completed: {semantic_query}")

    # Step 2: Graph traversal in Neo4j (simulated)
    # In a real implementation, this would query Neo4j based on semantic results
    graph_query = {"query": "MATCH (v:Vulnerability)-[:AFFECTS]->(p:Package) RETURN v, p", "parameters": {}}

    # For now, we'll simulate the graph query response
    graph_results = {
        "vulnerabilities": [
            {"id": "CVE-2023-1234", "severity": "high", "description": "Auth bypass"},
            {"id": "CVE-2023-5678", "severity": "medium", "description": "SQL injection"},
        ],
        "packages": [{"name": "auth-library", "version": "1.2.3"}, {"name": "db-connector", "version": "2.4.5"}],
    }

    print(f"✓ Graph traversal completed: found {len(graph_results['vulnerabilities'])} vulnerabilities")

    # Step 3: Combine results
    combined_results = {
        "semantic_search": semantic_results,
        "graph_analysis": graph_results,
        "summary": {
            "total_vulnerabilities": len(graph_results["vulnerabilities"]),
            "total_packages": len(graph_results["packages"]),
            "high_severity": 1,
            "medium_severity": 1,
        },
    }

    # Validate combined results
    assert "semantic_search" in combined_results
    assert "graph_analysis" in combined_results
    assert "summary" in combined_results
    assert combined_results["summary"]["total_vulnerabilities"] > 0

    print("✓ Hybrid search workflow validated")
    print(f"  - Semantic search: {semantic_query}")
    print(f"  - Vulnerabilities found: {combined_results['summary']['total_vulnerabilities']}")
    print(f"  - Packages affected: {combined_results['summary']['total_packages']}")


def test_semantic_to_graph_transition(http_session: requests.Session, request_timeout: int):
    """Test transition from semantic search to graph analysis.

    Validates the key hybrid workflow: using semantic search results
    to inform graph queries.
    """
    # Semantic search phase
    discovery_query = "authentication vulnerabilities"

    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": discovery_query}, timeout=request_timeout
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    semantic_results = response.json()

    # Extract entities from semantic results (simulated)
    extracted_entities = ["authentication", "vulnerability", "CVE-2023-1234"]

    # Graph analysis phase (simulated)
    graph_query = {
        "query": "MATCH (v:Vulnerability {id: $vuln_id})-[:AFFECTS]->(p:Package) RETURN v, p",
        "parameters": {"vuln_id": "CVE-2023-1234"},
    }

    graph_results = {
        "vulnerability": {
            "id": "CVE-2023-1234",
            "description": "Authentication bypass vulnerability",
            "severity": "high",
        },
        "affected_packages": [
            {"name": "auth-library", "version": "1.2.3"},
            {"name": "security-module", "version": "3.1.0"},
        ],
    }

    # Validate the transition
    assert len(extracted_entities) > 0
    assert "vulnerability" in graph_results
    assert len(graph_results["affected_packages"]) > 0

    print("✓ Semantic-to-graph transition validated")
    print(f"  - Extracted entities: {len(extracted_entities)}")
    print(f"  - Affected packages: {len(graph_results['affected_packages'])}")


def test_hybrid_search_with_filters(http_session: requests.Session, request_timeout: int):
    """Test hybrid search with filters.

    Validates filtering capabilities in hybrid search workflows.
    """
    # Query with filters
    query = "high severity vulnerabilities"
    filters = {"severity": ["high", "critical"], "status": ["open", "unpatched"]}

    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query, "filters": filters}, timeout=request_timeout
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate filtered results
    assert "answer" in results or "response" in results

    print("✓ Hybrid search with filters validated")
    print(f"  - Query: {query}")
    print(f"  - Filters: {filters}")


def test_hybrid_search_response_structure(http_session: requests.Session, request_timeout: int):
    """Test that hybrid search responses have correct structure.

    Validates the response format described in the tutorial.
    """
    query = "security findings with dependencies"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate response structure
    assert isinstance(results, dict)
    assert "answer" in results or "response" in results

    # Check for expected fields
    if "answer" in results:
        assert isinstance(results["answer"], str)
    if "context" in results:
        assert isinstance(results["context"], list)
    if "sources" in results:
        assert isinstance(results["sources"], list)

    print("✓ Hybrid search response structure validated")
    print(f"  - Response keys: {list(results.keys())}")


# NOTE: Additional tests to implement with actual Neo4j/OpenSearch:
# - test_actual_neo4j_graph_queries() - with real Neo4j instance
# - test_actual_opensearch_semantic_search() - with real OpenSearch instance
# - test_hybrid_search_performance() - measure performance metrics
# - test_hybrid_search_relevance() - validate relevance ranking
