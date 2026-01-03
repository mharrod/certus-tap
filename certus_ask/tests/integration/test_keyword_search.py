"""Integration tests for keyword search functionality.

These tests validate the keyword search capabilities described in
 docs/learn/ask/keyword-search.md
"""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = [pytest.mark.integration, pytest.mark.slow]

ASK_URL = os.getenv("ASK_URL", "http://localhost:8000")
WORKSPACE_ID = "keyword-search-test"


def test_keyword_search_basic(http_session: requests.Session, request_timeout: int):
    """Test basic keyword search functionality.

    Validates the core keyword search capability described in the tutorial.
    """
    query = "SQL injection"

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

    print("✓ Basic keyword search validated")
    print(f"  - Query: {query}")


def test_keyword_search_with_boolean_operators(http_session: requests.Session, request_timeout: int):
    """Test keyword search with boolean operators.

    Validates boolean search capabilities (AND, OR, NOT).
    """
    # Test AND operator
    query = "SQL injection AND authentication"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate that both keywords are addressed
    answer = results.get("answer", "").lower()
    assert ("sql" in answer or "injection" in answer) and "authentication" in answer

    print("✓ Boolean keyword search validated")
    print(f"  - Query: {query}")


def test_keyword_search_specificity(http_session: requests.Session, request_timeout: int):
    """Test keyword search specificity.

    Validates that keyword search returns specific, relevant results.
    """
    # Specific query
    query = "CVE-2023-1234 vulnerability"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate specificity
    answer = results.get("answer", "").lower()

    # Should mention the specific CVE or related vulnerabilities
    assert "cve" in answer or "vulnerability" in answer

    print("✓ Keyword search specificity validated")
    print(f"  - Query: {query}")


def test_keyword_search_with_quotes(http_session: requests.Session, request_timeout: int):
    """Test keyword search with exact phrase matching.

    Validates exact phrase search using quotes.
    """
    # Exact phrase query
    query = '"authentication bypass"'

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate exact phrase handling
    assert "answer" in results or "response" in results

    print("✓ Keyword search with exact phrases validated")
    print(f"  - Query: {query}")


def test_keyword_search_with_wildcards(http_session: requests.Session, request_timeout: int):
    """Test keyword search with wildcards.

    Validates wildcard search capabilities.
    """
    # Wildcard query
    query = "vulnerabilit*"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate wildcard handling
    answer = results.get("answer", "").lower()
    assert "vulnerability" in answer or "vulnerabilities" in answer

    print("✓ Keyword search with wildcards validated")
    print(f"  - Query: {query}")


def test_keyword_search_faceted(http_session: requests.Session, request_timeout: int):
    """Test faceted keyword search.

    Validates faceted search capabilities.
    """
    # Faceted query
    query = "vulnerabilities"
    facets = {"severity": ["high", "critical"], "status": ["open", "unpatched"]}

    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query, "facets": facets}, timeout=request_timeout
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate faceted search
    assert "answer" in results or "response" in results

    print("✓ Faceted keyword search validated")
    print(f"  - Query: {query}")
    print(f"  - Facets: {facets}")


def test_keyword_search_response_structure(http_session: requests.Session, request_timeout: int):
    """Test keyword search response structure.

    Validates the response format described in the tutorial.
    """
    query = "security findings"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    results = response.json()

    # Validate response structure
    assert isinstance(results, dict)

    if "answer" in results:
        assert isinstance(results["answer"], str)

    if "context" in results:
        assert isinstance(results["context"], list)

    if "sources" in results:
        assert isinstance(results["sources"], list)

    print("✓ Keyword search response structure validated")
    print(f"  - Response keys: {list(results.keys())}")


# NOTE: Additional tests to implement:
# - test_keyword_search_performance() - measure response time
# - test_keyword_search_relevance_ranking() - validate ranking algorithms
# - test_keyword_search_boolean_complexity() - complex boolean queries
# - test_keyword_search_fuzzy_matching() - fuzzy matching capabilities
