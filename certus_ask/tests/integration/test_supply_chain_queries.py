"""Integration tests for supply chain RAG queries.

This test suite validates TAP queries on ingested supply chain artifacts as
described in docs/learn/trust/vendor-review.md Step 6.

Tutorial reference: docs/learn/trust/vendor-review.md (Step 6)
"""

from __future__ import annotations

import os

import pytest
import requests

pytestmark = [pytest.mark.integration, pytest.mark.slow]

ASK_URL = os.getenv("ASK_URL", "http://localhost:8000")
WORKSPACE_ID = "oci-attestations-review"


def test_query_sbom_packages_and_licenses(http_session: requests.Session, request_timeout: int) -> None:
    """Query: What packages and licenses are in the SBOM?"""
    question = "What packages and licenses are listed in the SBOM?"

    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask",
        json={"question": question},
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")

    # TODO: Requires ingested SBOM
    if response.status_code == 422:
        pytest.skip("Workspace not ready - requires ingested artifacts")

    response.raise_for_status()
    result = response.json()

    # Validate response structure (handle different response field names)
    assert "answer" in result or "response" in result or "reply" in result
    print(f"✓ SBOM query response: {result}")


def test_query_slsa_provenance(http_session: requests.Session, request_timeout: int) -> None:
    """Query: What does SLSA provenance say about build pipeline?"""
    question = "What does the SLSA provenance say about the build pipeline?"

    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask",
        json={"question": question},
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")

    if response.status_code == 422:
        pytest.skip("Workspace not ready - requires ingested SLSA provenance")

    response.raise_for_status()
    result = response.json()

    # Validate response structure
    assert "answer" in result or "response" in result or "reply" in result
    print(f"✓ SLSA provenance query response: {result}")


def test_query_high_severity_vulnerabilities(http_session: requests.Session, request_timeout: int) -> None:
    """Query: Summarize high-severity vulnerabilities."""
    question = "What are the high severity vulnerabilities?"

    response = http_session.post(
        f"{ASK_URL}/v1/{WORKSPACE_ID}/ask",
        json={"question": question},
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Ask endpoint not available")

    if response.status_code == 422:
        pytest.skip("Workspace not ready - requires ingested SARIF")

    response.raise_for_status()
    result = response.json()

    # Validate response structure
    assert "answer" in result or "response" in result or "reply" in result
    print(f"✓ High severity vulnerabilities query response: {result}")


# NOTE: Additional query tests:
# - test_query_build_reproducibility()
# - test_query_dependency_tree()
# - test_query_license_compliance()
# - test_query_verification_status()
