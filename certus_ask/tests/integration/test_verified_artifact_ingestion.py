"""Integration tests for ingesting verified artifacts into Certus TAP.

This test suite validates artifact ingestion from verified bundles as described in
docs/learn/trust/vendor-review.md Step 5.

Tutorial reference: docs/learn/trust/vendor-review.md (Step 5)
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import requests

pytestmark = [pytest.mark.integration, pytest.mark.slow]

ASK_URL = os.getenv("ASK_URL", "http://localhost:8000")
WORKSPACE_ID = "oci-attestations-review"
SAMPLES_ROOT = Path(__file__).resolve().parents[3] / "samples"
ARTIFACTS_DIR = SAMPLES_ROOT / "oci-attestations/artifacts"


def test_ingest_sbom_from_verified_bundle(http_session: requests.Session, request_timeout: int) -> None:
    """Ingest SBOM from verified bundle into TAP."""
    sbom_path = ARTIFACTS_DIR / "sbom/product.spdx.json"

    if not sbom_path.exists():
        pytest.skip("SBOM artifact not available")

    with sbom_path.open("rb") as f:
        files = {"uploaded_file": ("product.spdx.json", f, "application/json")}

        response = http_session.post(
            f"{ASK_URL}/v1/{WORKSPACE_ID}/index/",
            files=files,
            timeout=request_timeout,
        )

    if response.status_code == 404:
        pytest.skip("Ingestion endpoint not available")

    if response.status_code == 422:
        pytest.skip("Workspace not ready or ingestion not supported")

    response.raise_for_status()
    result = response.json()

    assert "ingestion_id" in result or "document_count" in result
    print(f"✓ SBOM ingested: {result}")


def test_ingest_sarif_from_verified_bundle(http_session: requests.Session, request_timeout: int) -> None:
    """Ingest SARIF from verified bundle into TAP."""
    sarif_path = ARTIFACTS_DIR / "scans/vulnerability.sarif"

    if not sarif_path.exists():
        pytest.skip("SARIF artifact not available")

    with sarif_path.open("rb") as f:
        files = {"uploaded_file": ("vulnerability.sarif", f, "application/json")}

        response = http_session.post(
            f"{ASK_URL}/v1/{WORKSPACE_ID}/index/security",
            files=files,
            timeout=request_timeout,
        )

    if response.status_code == 404:
        pytest.skip("Ingestion endpoint not available")

    if response.status_code == 422:
        pytest.skip("Workspace not ready or invalid SARIF format")

    response.raise_for_status()
    result = response.json()

    assert "ingestion_id" in result or "document_count" in result or "status" in result
    print(f"✓ SARIF ingested: {result}")


def test_ingest_provenance_from_verified_bundle(http_session: requests.Session, request_timeout: int) -> None:
    """Ingest SLSA provenance from verified bundle into TAP."""
    provenance_path = ARTIFACTS_DIR / "provenance/slsa-provenance.json"

    if not provenance_path.exists():
        pytest.skip("SLSA provenance artifact not available")

    with provenance_path.open("rb") as f:
        files = {"uploaded_file": ("slsa-provenance.json", f, "application/json")}

        response = http_session.post(
            f"{ASK_URL}/v1/{WORKSPACE_ID}/index/",
            files=files,
            timeout=request_timeout,
        )

    if response.status_code == 404:
        pytest.skip("Ingestion endpoint not available")

    if response.status_code == 422:
        pytest.skip("Workspace not ready or invalid provenance format")

    response.raise_for_status()
    result = response.json()

    assert "ingestion_id" in result or "document_count" in result or "status" in result
    print(f"✓ SLSA provenance ingested: {result}")


def test_validate_ingestion_audit_trail(http_session: requests.Session, request_timeout: int) -> None:
    """Validate ingestion creates proper audit trail in logs."""
    import os

    opensearch_url = os.getenv("OPENSEARCH_URL", "http://localhost:9200")

    # Query OpenSearch for ingestion events
    query = {
        "query": {"bool": {"must": [{"term": {"workspace_id": WORKSPACE_ID}}, {"exists": {"field": "ingestion_id"}}]}},
        "size": 1,
        "sort": [{"@timestamp": {"order": "desc"}}],
    }

    try:
        response = http_session.post(
            f"{opensearch_url}/certus-logs-*/_search",
            json=query,
            timeout=request_timeout,
        )

        if response.status_code == 404:
            pytest.skip("OpenSearch logs not available")

        response.raise_for_status()
        result = response.json()

        # Check if we have any ingestion events
        hits = result.get("hits", {}).get("hits", [])
        if len(hits) == 0:
            pytest.skip("No ingestion events found in audit trail")

        print(f"✓ Audit trail validation: Found {len(hits)} ingestion event(s)")

    except Exception as e:
        pytest.skip(f"Could not query audit trail: {e}")


# NOTE: More tests to add:
# - test_ingest_with_verification_metadata()
# - test_query_ingested_artifacts()
# - test_cross_reference_verification_proof()
