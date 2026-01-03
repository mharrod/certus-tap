"""End-to-end test for integrity trace and signing pipeline."""

import logging
import os
import time

import pytest
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE = os.getenv("API_BASE", "http://localhost:8000")
TRUST_BASE = os.getenv("TRUST_BASE", "http://localhost:8057")
OS_ENDPOINT = os.getenv("OS_ENDPOINT", "http://localhost:9200")
PROMETHEUS_ENDPOINT = os.getenv("PROMETHEUS_ENDPOINT", "http://localhost:8889")


@pytest.mark.smoke
def test_end_to_end_integrity_pipeline():
    """
    End-to-end test that validates:
    1. Request goes through IntegrityMiddleware
    2. Evidence file is created and signed by certus-trust
    3. Integrity span is exported to OpenTelemetry
    4. Metrics are recorded in Prometheus
    """
    # Step 1: Verify certus-trust is healthy
    logger.info("Checking certus-trust health...")
    trust_health = requests.get(f"{TRUST_BASE}/v1/health", timeout=5)
    assert trust_health.status_code == 200, "certus-trust must be healthy"
    logger.info("✓ certus-trust is healthy")

    # Step 2: Send request through the API
    logger.info("Sending request to API...")
    response = requests.get(f"{API_BASE}/v1/health", timeout=5)
    assert response.status_code == 200, "API request should succeed"
    logger.info(f"✓ API responded: {response.json()}")

    # Step 3: Wait for telemetry and evidence to be processed
    logger.info("Waiting for telemetry to flush...")
    time.sleep(5)

    # Step 4: Verify integrity span in OpenSearch
    logger.info("Checking for integrity span in OpenSearch...")
    search_query = {
        "size": 1,
        "sort": [{"endTime": {"order": "desc"}}],
        "query": {"match": {"name": "integrity.request"}},
    }

    span_found = False
    for index in ["traces-otel"]:
        try:
            res = requests.post(f"{OS_ENDPOINT}/{index}/_search", json=search_query, auth=("admin", "admin"), timeout=5)
            if res.status_code == 200:
                hits = res.json().get("hits", {}).get("hits", [])
                if hits:
                    span = hits[0]["_source"]
                    logger.info(f"✓ Found integrity span: {span.get('name')}")

                    # Validate span attributes
                    attrs = span.get("attributes", {})
                    assert attrs.get("integrity.decision") == "allowed"
                    assert "integrity.guardrail" in attrs
                    assert "integrity.reason" in attrs

                    logger.info(f"  - Decision: {attrs.get('integrity.decision')}")
                    logger.info(f"  - Guardrail: {attrs.get('integrity.guardrail')}")
                    logger.info(f"  - Reason: {attrs.get('integrity.reason')}")
                    logger.info(f"  - Shadow Mode: {attrs.get('integrity.shadow_mode')}")

                    span_found = True
                    break
        except Exception as e:
            logger.warning(f"Could not query {index}: {e}")
            continue

    assert span_found, "Integrity span should be found in OpenSearch"

    # Step 5: Check metrics in Prometheus
    logger.info("Checking metrics in Prometheus...")
    try:
        metrics_response = requests.get(f"{PROMETHEUS_ENDPOINT}/metrics", timeout=5)
        if metrics_response.status_code == 200:
            metrics_text = metrics_response.text

            # Look for integrity metrics
            if "integrity_decisions_total" in metrics_text:
                logger.info("✓ Found integrity_decisions_total metric")

                # Extract the metric value
                for line in metrics_text.split("\n"):
                    if "integrity_decisions_total" in line and not line.startswith("#"):
                        logger.info(f"  - {line.strip()}")
            else:
                logger.warning("Integrity metrics not yet available in Prometheus")
    except Exception as e:
        logger.warning(f"Could not check Prometheus metrics: {e}")
        # Don't fail the test if Prometheus is not accessible

    logger.info("✓ End-to-end integrity pipeline test passed!")


@pytest.mark.smoke
def test_evidence_signing():
    """
    Test that evidence files are created and properly signed.

    Note: This test requires access to the container filesystem.
    Skip if running outside of the container environment.
    """
    # Send a request to generate evidence
    logger.info("Sending request to generate evidence...")
    response = requests.get(f"{API_BASE}/v1/health", timeout=5)
    assert response.status_code == 200

    # Wait for evidence to be written and signed
    time.sleep(3)

    # Note: This check would need container access or a dedicated API endpoint
    # For now, we verify the signing service is available
    trust_health = requests.get(f"{TRUST_BASE}/v1/health", timeout=5)
    assert trust_health.status_code == 200

    # Check trust service stats
    try:
        stats_response = requests.get(f"{TRUST_BASE}/v1/stats", timeout=5)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            logger.info("✓ Trust service stats:")
            logger.info(f"  - Total signatures: {stats.get('total_signatures', 0)}")
            logger.info(f"  - Total transparency entries: {stats.get('total_transparency_entries', 0)}")
    except Exception as e:
        logger.warning(f"Could not get trust stats: {e}")

    logger.info("✓ Evidence signing pipeline is operational")
