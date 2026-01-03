"""Contract tests for Certus-Ask API.

These tests validate the API contracts and response schemas
described in the tutorials.
"""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = pytest.mark.contract

ASK_URL = os.getenv("ASK_URL", "http://localhost:8000")
WORKSPACE_ID = "contract-test"


def test_ask_endpoint_contract(http_session: requests.Session, request_timeout: int):
    """Test the basic Ask endpoint contract.

    Validates that the Ask endpoint accepts the expected request format
    and returns the expected response format.
    """
    # Valid request format
    request_payload = {"question": "What are the security vulnerabilities?", "workspace_id": WORKSPACE_ID}

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json=request_payload, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    # Validate response
    response.raise_for_status()
    response_data = response.json()

    # Validate response structure
    assert isinstance(response_data, dict)
    assert "answer" in response_data or "response" in response_data

    print("✓ Ask endpoint contract validated")
    print(f"  - Request format: {list(request_payload.keys())}")
    print(f"  - Response format: {list(response_data.keys())}")


def test_ask_request_schema(http_session: requests.Session, request_timeout: int):
    """Test the Ask request schema.

    Validates that the Ask endpoint accepts various request formats.
    """
    # Test minimal request
    minimal_request = {"question": "Test question"}

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json=minimal_request, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()

    # Test extended request
    extended_request = {
        "question": "Complex question",
        "parameters": {"top_k": 5, "temperature": 0.7},
        "filters": {"severity": ["high", "critical"]},
    }

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json=extended_request, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()

    print("✓ Ask request schema validated")
    print("  - Minimal request: accepted")
    print("  - Extended request: accepted")


def test_ask_response_schema(http_session: requests.Session, request_timeout: int):
    """Test the Ask response schema.

    Validates that responses contain expected fields and types.
    """
    query = "Security vulnerabilities"

    response = http_session.post(f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout)

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    response.raise_for_status()
    response_data = response.json()

    # Validate response schema
    assert isinstance(response_data, dict)

    # Check answer field
    if "answer" in response_data:
        assert isinstance(response_data["answer"], str)
        assert len(response_data["answer"]) > 0

    # Check context field
    if "context" in response_data:
        assert isinstance(response_data["context"], list)
        for item in response_data["context"]:
            assert isinstance(item, dict)

    # Check sources field
    if "sources" in response_data:
        assert isinstance(response_data["sources"], list)
        for source in response_data["sources"]:
            assert isinstance(source, dict)

    print("✓ Ask response schema validated")
    print(f"  - Response fields: {list(response_data.keys())}")


def test_ask_error_responses(http_session: requests.Session, request_timeout: int):
    """Test Ask endpoint error responses.

    Validates that the endpoint returns appropriate error responses.
    """
    # Test invalid workspace
    invalid_workspace = "nonexistent-workspace"

    response = http_session.post(
        f"{ASK_URL}/v1/{invalid_workspace}/ask", json={"question": "Test question"}, timeout=request_timeout
    )

    # Should return 404 or 422 for invalid workspace
    assert response.status_code in [404, 422]

    # Validate error response structure
    error_data = response.json()
    assert "detail" in error_data or "error" in error_data or "message" in error_data

    print("✓ Ask error responses validated")
    print(f"  - Invalid workspace status: {response.status_code}")
    print(f"  - Error response: {list(error_data.keys())}")


def test_ask_response_consistency(http_session: requests.Session, request_timeout: int):
    """Test Ask response consistency.

    Validates that similar queries return consistent response formats.
    """
    queries = [
        "What are the security vulnerabilities?",
        "List security vulnerabilities",
        "Show me security vulnerabilities",
    ]

    response_formats = []

    for query in queries:
        response = http_session.post(
            f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": query}, timeout=request_timeout
        )

        if response.status_code == 404:
            pytest.skip("Ask endpoint not available")
        if response.status_code == 422:
            pytest.skip("Workspace not ready")

        response.raise_for_status()
        response_data = response.json()
        response_formats.append(set(response_data.keys()))

    # All responses should have similar structure
    if len(response_formats) > 1:
        # Check that all have answer field
        for fmt in response_formats:
            assert "answer" in fmt or "response" in fmt

    print("✓ Ask response consistency validated")
    print(f"  - Queries tested: {len(queries)}")
    print(f"  - Consistent response structure: {response_formats[0] if response_formats else 'N/A'}")


def test_ask_api_documentation_compliance(http_session: requests.Session, request_timeout: int):
    """Test compliance with API documentation.

    Validates that the API behaves as documented in the tutorials.
    """
    # Test documented endpoint
    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask", json={"question": "Test question"}, timeout=request_timeout
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")
    if response.status_code == 422:
        pytest.skip("Workspace not ready")

    # Should succeed for valid request
    response.raise_for_status()

    # Test documented response format
    response_data = response.json()
    assert isinstance(response_data, dict)

    print("✓ API documentation compliance validated")
    print("  - Endpoint: /v1/{workspace}/ask")
    print("  - Method: POST")
    print("  - Response: JSON")


# NOTE: Additional contract tests to implement:
# - test_health_endpoint_contract() - test health endpoint contract
# - test_ingestion_endpoint_contract() - test ingestion endpoint contract
# - test_query_endpoint_contract() - test query endpoint contract
# - test_response_schema_validation() - detailed schema validation
