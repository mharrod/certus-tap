"""Integration tests for semantic search functionality.

These tests validate the semantic search capabilities described in
 docs/learn/ask/semantic-search.md
"""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = [pytest.mark.integration, pytest.mark.slow]

ASK_URL = os.getenv("ASK_URL", "http://localhost:8000")
WORKSPACE_ID = "semantic-search-test"


def test_semantic_search_basic(http_session: requests.Session, request_timeout: int):
    """Test basic semantic search functionality.

    Validates the core semantic search capability described in the tutorial.
    """
    query = "What are the security vulnerabilities in this project?"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready - requires ingested artifacts")

    response.raise_for_status()
    results = response.json()

    # Validate basic response structure
    assert "answer" in results or "response" in results

    # Check that we got a meaningful answer
    if "answer" in results:
        assert len(results["answer"]) > 10  # Should have some content
        assert results["answer"] != "I don't know"

    print("✓ Basic semantic search validated")
    print(f"  - Query: {query}")
    print(f"  - Answer length: {len(results.get('answer', ''))} characters")


def test_semantic_search_with_context(http_session: requests.Session, request_timeout: int):
    """Test semantic search with context.

    Validates that semantic search provides relevant context.
    """
    query = "Explain the authentication vulnerabilities"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate context is provided
    if "context" in results:
        assert isinstance(results["context"], list)
        assert len(results["context"]) > 0

        # Check that context documents are meaningful
        for doc in results["context"]:
            assert "content" in doc or "text" in doc
            assert len(doc.get("content", doc.get("text", ""))) > 50  # Meaningful content

    print("✓ Semantic search with context validated")
    print(f"  - Query: {query}")
    print(f"  - Context documents: {len(results.get('context', []))}")


def test_semantic_search_relevance(http_session: requests.Session, request_timeout: int):
    """Test semantic search relevance.

    Validates that semantic search returns relevant results.
    """
    # Query about a specific topic
    query = "SQL injection vulnerabilities"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate relevance
    answer = results.get("answer", "").lower()

    # Check that answer contains relevant keywords
    relevant_keywords = ["sql", "injection", "vulnerability", "database"]
    found_keywords = [kw for kw in relevant_keywords if kw in answer]

    assert len(found_keywords) >= 2, f"Answer should contain relevant keywords, found: {found_keywords}"

    print("✓ Semantic search relevance validated")
    print(f"  - Query: {query}")
    print(f"  - Relevant keywords found: {len(found_keywords)}/{len(relevant_keywords)}")


def test_semantic_search_complex_query(http_session: requests.Session, request_timeout: int):
    """Test semantic search with complex queries.

    Validates handling of complex, multi-part queries.
    """
    query = "What are the high severity vulnerabilities in authentication that affect production systems?"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate that complex query is handled
    assert "answer" in results or "response" in results

    # Check that answer addresses multiple aspects of the query
    answer = results.get("answer", "").lower()
    aspects = ["vulnerability", "authentication", "production"]
    found_aspects = [a for a in aspects if a in answer]

    assert len(found_aspects) >= 2, f"Should address multiple query aspects, found: {found_aspects}"

    print("✓ Complex query handling validated")
    print(f"  - Query aspects: {aspects}")
    print(f"  - Addressed aspects: {found_aspects}")


def test_semantic_search_response_format(http_session: requests.Session, request_timeout: int):
    """Test semantic search response format.

    Validates the response format described in the tutorial.
    """
    query = "Security findings summary"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate response structure matches tutorial expectations
    assert isinstance(results, dict)

    # Check for expected fields
    if "answer" in results:
        assert isinstance(results["answer"], str)

    if "context" in results:
        assert isinstance(results["context"], list)

    if "sources" in results:
        assert isinstance(results["sources"], list)
        for source in results["sources"]:
            assert "document_id" in source or "id" in source

    print("✓ Semantic search response format validated")
    print(f"  - Response keys: {list(results.keys())}")


def test_semantic_search_with_parameters(http_session: requests.Session, request_timeout: int):
    """Test semantic search with additional parameters.

    Validates parameter handling in semantic search.
    """
    query = "Vulnerability analysis"
    parameters = {"top_k": 3, "temperature": 0.7, "max_tokens": 200}

    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query, "parameters": parameters}, timeout=request_timeout
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate that parameters are accepted
    assert "answer" in results or "response" in results

    print("✓ Semantic search with parameters validated")
    print(f"  - Query: {query}")
    print(f"  - Parameters: {parameters}")


# NOTE: Additional tests to implement:
# - test_semantic_search_performance() - measure response time
# - test_semantic_search_accuracy() - validate answer accuracy
# - test_semantic_search_embeddings() - test embedding generation
# - test_semantic_search_retrieval() - test document retrieval
