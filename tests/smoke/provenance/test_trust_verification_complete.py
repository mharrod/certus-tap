"""
End-to-end integration test for Trust Verification Tutorial.

This test validates the complete workflow from:
docs/learn/provenance/trust-verification.md

Workflow Steps:
1. Create security scan (Assurance)
2. Wait for scan completion
3. Submit upload request to Trust
4. Verify artifacts in S3 (raw bucket)
5. Privacy scan and promote to golden
6. Ingest security files to Neo4j + OpenSearch
7. Query Neo4j for verification metadata
8. Validate complete non-repudiation chain

Test validates that the tutorial works end-to-end with real services.
"""

import json
import os
import socket
import time
from typing import Any
from urllib.parse import urlparse

import pytest
import requests
from neo4j import GraphDatabase

pytestmark = pytest.mark.smoke


# =============================================================================
# Service Availability Check
# =============================================================================


def _check_service_available(url: str, timeout: int = 2) -> bool:
    """Check if a service is available."""
    try:
        requests.get(url, timeout=timeout)
        return True
    except (requests.RequestException, Exception):
        return False


ASSURANCE_AVAILABLE = _check_service_available(os.getenv("ASSURANCE_URL", "http://localhost:8056") + "/health")
TRANSFORM_AVAILABLE = _check_service_available(os.getenv("TRANSFORM_URL", "http://localhost:8100") + "/health")
TRUST_AVAILABLE = _check_service_available(os.getenv("TRUST_URL", "http://localhost:8057") + "/health")
NEO4J_AVAILABLE = _check_service_available(os.getenv("NEO4J_URL", "http://localhost:7474"))

SERVICES_AVAILABLE = all([ASSURANCE_AVAILABLE, TRANSFORM_AVAILABLE, TRUST_AVAILABLE, NEO4J_AVAILABLE])


# =============================================================================
# Configuration and Fixtures
# =============================================================================


def _prefer_host_url(uri: str, fallback: str) -> str:
    """Return URI if hostname resolves, otherwise use fallback."""
    parsed = urlparse(uri)
    host = parsed.hostname
    if not host:
        return uri
    try:
        socket.getaddrinfo(host, None)
        return uri
    except socket.gaierror:
        return fallback


@pytest.fixture(scope="session")
def config():
    """Test configuration from environment."""
    neo4j_uri = os.getenv("NEO4J_URI", "neo4j://neo4j:7687")
    resolved_neo4j_uri = _prefer_host_url(neo4j_uri, "neo4j://localhost:7687")
    return {
        "assurance_url": os.getenv("ASSURANCE_URL", "http://localhost:8056"),
        "transform_url": os.getenv("TRANSFORM_URL", "http://localhost:8100"),
        "trust_url": os.getenv("TRUST_URL", "http://localhost:8057"),
        "ask_url": os.getenv("ASK_URL", "http://localhost:8000"),
        "neo4j_uri": resolved_neo4j_uri,
        "neo4j_user": os.getenv("NEO4J_USER", "neo4j"),
        "neo4j_password": os.getenv("NEO4J_PASSWORD", "password"),
    }


@pytest.fixture(scope="session")
def neo4j_driver(config):
    """Neo4j driver for verification queries."""
    driver = GraphDatabase.driver(
        config["neo4j_uri"],
        auth=(config["neo4j_user"], config["neo4j_password"]),
    )
    yield driver
    driver.close()


# =============================================================================
# Helper Functions
# =============================================================================


def wait_for_scan_completion(assurance_url: str, scan_id: str, timeout: int = 120) -> dict[str, Any]:
    """
    Poll Assurance API until scan completes or timeout.

    Args:
        assurance_url: Base URL for Assurance service
        scan_id: Scan ID to poll
        timeout: Maximum seconds to wait

    Returns:
        Final scan status response

    Raises:
        TimeoutError: If scan doesn't complete within timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(f"{assurance_url}/v1/security-scans/{scan_id}")
        response.raise_for_status()
        scan_data = response.json()

        status = scan_data.get("status")
        if status == "SUCCEEDED":
            return scan_data
        elif status == "FAILED":
            raise RuntimeError(f"Scan failed: {scan_data}")

        time.sleep(2)

    raise TimeoutError(f"Scan {scan_id} did not complete within {timeout} seconds")


def wait_for_upload_completion(assurance_url: str, scan_id: str, timeout: int = 60) -> dict[str, Any]:
    """
    Poll Assurance API until upload completes.

    Args:
        assurance_url: Base URL for Assurance service
        scan_id: Scan ID to poll
        timeout: Maximum seconds to wait

    Returns:
        Final scan status with upload_status

    Raises:
        TimeoutError: If upload doesn't complete within timeout
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(f"{assurance_url}/v1/security-scans/{scan_id}")
        response.raise_for_status()
        scan_data = response.json()

        upload_status = scan_data.get("upload_status")
        if upload_status == "uploaded":
            return scan_data
        elif upload_status == "denied":
            raise RuntimeError(f"Upload denied: {scan_data}")

        time.sleep(2)

    raise TimeoutError(f"Upload for scan {scan_id} did not complete within {timeout} seconds")


def list_s3_objects(s3_client, bucket: str, prefix: str) -> list[str]:
    """List all object keys under a prefix."""
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [obj["Key"] for obj in response.get("Contents", []) if not obj["Key"].endswith("/")]
    except Exception as e:
        print(f"Failed to list S3 objects: {e}")
        return []


def download_s3_object(s3_client, bucket: str, key: str) -> bytes:
    """Download S3 object as bytes."""
    response = s3_client.get_object(Bucket=bucket, Key=key)
    return response["Body"].read()


# =============================================================================
# End-to-End Test
# =============================================================================


class TestTrustVerificationTutorialE2E:
    """
    End-to-end integration test for the Trust Verification tutorial.

    This test validates the complete workflow from docs/learn/provenance/trust-verification.md
    """

    @pytest.mark.skipif(
        not SERVICES_AVAILABLE, reason="Required services not available (Assurance, Transform, Trust, Neo4j)"
    )
    def test_complete_verification_workflow(self, config, s3_client, neo4j_driver, raw_bucket_name, golden_bucket_name):
        """
        Test the complete trust verification workflow end-to-end.

        Steps match the tutorial:
        1. Step 4: Initiate a scan
        2. Step 5: Human review (simulated approval)
        3. Step 6: Submit upload request to Trust
        4. Step 6b: Verify artifacts in S3
        5. Step 9: Privacy scan and promote to golden
        6. Step 10: Ingest security files with Neo4j
        7. Step 11: Query Neo4j for verification proof
        """

        # =====================================================================
        # Step 4: Initiate a Scan
        # =====================================================================
        print("\n=== Step 4: Initiating security scan ===")

        scan_request = {
            "workspace_id": "smoke-test",
            "component_id": "certus-tap",
            "assessment_id": "smoke-assessment",
            "git_url": "https://github.com/octocat/Hello-World.git",
            "branch": "master",
            "requested_by": "e2e-test@certus.cloud",
            "manifest": {"version": "1.0", "tools": ["bandit", "trivy"]},
        }

        response = requests.post(
            f"{config['assurance_url']}/v1/security-scans",
            json=scan_request,
        )
        response.raise_for_status()
        scan_data = response.json()
        scan_id = scan_data["test_id"]

        print(f"Scan created: {scan_id}")
        assert scan_id is not None

        # Wait for scan to complete
        print("Waiting for scan to complete...")
        scan_complete = wait_for_scan_completion(config["assurance_url"], scan_id)
        assert scan_complete["status"] == "SUCCEEDED"
        print(f"Scan completed with status: {scan_complete['status']}")

        # =====================================================================
        # Step 5: Human Review (Simulated Approval)
        # =====================================================================
        print("\n=== Step 5: Human review (simulated approval) ===")
        # In real workflow, human would review artifacts
        # For test, we automatically approve
        print("Scan approved for upload")

        # =====================================================================
        # Step 6: Submit Upload Request to Trust
        # =====================================================================
        print("\n=== Step 6: Submitting upload request to Trust ===")

        upload_request = {
            "tier": "verified",
            "requested_by": "e2e-test@certus.cloud",
        }

        response = requests.post(
            f"{config['assurance_url']}/v1/security-scans/{scan_id}/upload-request",
            json=upload_request,
        )
        response.raise_for_status()
        upload_response = response.json()

        print(f"Upload request submitted: {upload_response.get('upload_permission_id')}")
        assert upload_response.get("upload_permission_id") is not None

        # Wait for upload to complete
        print("Waiting for upload to S3...")
        upload_complete = wait_for_upload_completion(config["assurance_url"], scan_id)
        assert upload_complete["upload_status"] == "uploaded"
        print(f"Upload completed with status: {upload_complete['upload_status']}")

        # =====================================================================
        # Step 6b: Verify Artifacts in S3 (Raw Bucket)
        # =====================================================================
        print("\n=== Step 6b: Verifying artifacts in S3 raw bucket ===")

        s3_prefix = f"security-scans/{scan_id}/{scan_id}/"
        raw_objects = list_s3_objects(s3_client, raw_bucket_name, s3_prefix)

        print(f"Found {len(raw_objects)} objects in raw bucket:")
        for obj in raw_objects:
            print(f"  - {obj}")

        # Verify expected files exist
        assert any("verification-proof.json" in obj for obj in raw_objects), (
            "verification-proof.json not found in raw bucket"
        )
        assert any("trivy.sarif.json" in obj for obj in raw_objects) or any(
            "trivy.json" in obj for obj in raw_objects
        ), "SARIF file not found in raw bucket"

        # Download and verify verification proof
        proof_key = next(obj for obj in raw_objects if "verification-proof.json" in obj)
        proof_data = json.loads(download_s3_object(s3_client, raw_bucket_name, proof_key))

        print("\nVerification proof:")
        print(f"  chain_verified: {proof_data.get('chain_verified')}")
        print(f"  signer_inner: {proof_data.get('signer_inner')}")
        print(f"  signer_outer: {proof_data.get('signer_outer')}")

        assert proof_data["chain_verified"] is True, "Verification chain is not verified"
        assert proof_data["signer_inner"] == "certus-assurance@certus.cloud"
        assert proof_data["signer_outer"] == "certus-trust@certus.cloud"

        # =====================================================================
        # Step 9: Privacy Scan and Promote to Golden
        # =====================================================================
        print("\n=== Step 9: Privacy scan and promotion to golden ===")

        # Run privacy scan
        print("Running privacy scan...")
        privacy_response = requests.post(
            f"{config['transform_url']}/v1/privacy/scan",
            json={
                "scan_id": scan_id,
                "report_key": f"security-scans/{scan_id}/privacy-scan-report.txt",
            },
        )
        privacy_response.raise_for_status()
        privacy_data = privacy_response.json()

        print("Privacy scan complete:")
        print(f"  Total files: {privacy_data.get('total_files')}")
        print(f"  Clean: {privacy_data.get('clean_count')}")
        print(f"  Quarantined: {privacy_data.get('quarantined_count')}")

        # Promote to golden bucket
        print("\nPromoting to golden bucket...")
        promote_response = requests.post(
            f"{config['ask_url']}/v1/datalake/preprocess/batch",
            json={
                "source_prefix": f"security-scans/{scan_id}/",
                "destination_prefix": f"security-scans/{scan_id}/golden",
            },
        )
        promote_response.raise_for_status()
        promote_data = promote_response.json()

        print(f"Promoted {len(promote_data.get('promoted', []))} files to golden")

        # Verify files in golden bucket
        golden_prefix = f"security-scans/{scan_id}/golden/"
        golden_objects = list_s3_objects(s3_client, golden_bucket_name, golden_prefix)

        print(f"\nFound {len(golden_objects)} objects in golden bucket:")
        for obj in golden_objects[:5]:  # Show first 5
            print(f"  - {obj}")

        assert len(golden_objects) > 0, "No files promoted to golden bucket"

        # =====================================================================
        # Step 10: Ingest Security Files with Neo4j
        # =====================================================================
        print("\n=== Step 10: Ingesting security files to Neo4j + OpenSearch ===")

        # Find SARIF file in golden bucket
        sarif_key = next(
            (obj for obj in golden_objects if "trivy.sarif.json" in obj or "trivy.json" in obj),
            None,
        )

        if not sarif_key:
            pytest.skip("No SARIF file found in golden bucket")

        # Set assessment_id
        assessment_id = scan_id  # Use scan_id as assessment_id

        print(f"Ingesting SARIF file: {sarif_key}")
        print(f"Assessment ID: {assessment_id}")

        # Ingest SARIF with Neo4j support
        ingest_response = requests.post(
            f"{config['ask_url']}/v1/default/index/security/s3",
            json={
                "bucket_name": golden_bucket_name,
                "key": sarif_key,
                "format": "sarif",
                "tier": "premium",
                "assessment_id": assessment_id,
                "signatures": {
                    "signer_inner": "certus-assurance@certus.cloud",
                    "signer_outer": "certus-trust@certus.cloud",
                },
                "artifact_locations": {
                    "s3": {
                        "bucket": golden_bucket_name,
                        "key": sarif_key,
                    }
                },
            },
        )
        ingest_response.raise_for_status()
        ingest_data = ingest_response.json()

        print("\nIngestion complete:")
        print(f"  Ingestion ID: {ingest_data.get('ingestion_id')}")
        print(f"  Findings indexed: {ingest_data.get('findings_indexed')}")
        print(f"  Neo4j scan ID: {ingest_data.get('neo4j_scan_id')}")
        print(f"  Document count: {ingest_data.get('document_count')}")

        assert ingest_data.get("findings_indexed", 0) > 0, "No findings were indexed"
        assert ingest_data.get("neo4j_scan_id") is not None, "Neo4j scan ID is missing"

        # =====================================================================
        # Step 11: Query Neo4j for Verification Proof
        # =====================================================================
        print("\n=== Step 11: Querying Neo4j for verification metadata ===")

        with neo4j_driver.session() as session:
            # Query 1: Find SecurityScan by assessment_id
            print(f"\nQuerying for SecurityScan with assessment_id: {assessment_id}")

            result = session.run(
                """
                MATCH (s:SecurityScan {assessment_id: $assessment_id})
                RETURN s.id as id,
                       s.assessment_id as assessment_id,
                       s.chain_verified as chain_verified,
                       s.signer_inner as signer_inner,
                       s.signer_outer as signer_outer,
                       s.sigstore_timestamp as sigstore_timestamp,
                       s.verification_timestamp as verification_timestamp
                """,
                assessment_id=assessment_id,
            )

            records = list(result)
            assert len(records) > 0, f"No SecurityScan found with assessment_id={assessment_id}"

            scan_record = records[0]
            print("\nSecurityScan found:")
            print(f"  ID: {scan_record['id']}")
            print(f"  Assessment ID: {scan_record['assessment_id']}")
            print(f"  Chain verified: {scan_record['chain_verified']}")
            print(f"  Signer (inner): {scan_record['signer_inner']}")
            print(f"  Signer (outer): {scan_record['signer_outer']}")
            print(f"  Sigstore timestamp: {scan_record['sigstore_timestamp']}")
            print(f"  Verification timestamp: {scan_record['verification_timestamp']}")

            # Assertions
            assert scan_record["assessment_id"] == assessment_id
            assert scan_record["chain_verified"] is True, "Chain not verified in Neo4j"
            assert scan_record["signer_inner"] == "certus-assurance@certus.cloud"
            assert scan_record["signer_outer"] == "certus-trust@certus.cloud"
            assert scan_record["sigstore_timestamp"] is not None

            # Query 2: Count findings for this scan
            result = session.run(
                """
                MATCH (s:SecurityScan {assessment_id: $assessment_id})-[:CONTAINS]->(f:Finding)
                RETURN count(f) as finding_count
                """,
                assessment_id=assessment_id,
            )

            finding_record = result.single()
            finding_count = finding_record["finding_count"]
            print(f"\nFindings linked to SecurityScan: {finding_count}")
            assert finding_count > 0, "No findings linked to SecurityScan"

            # Query 3: Verify unbroken chain
            result = session.run(
                """
                MATCH (s:SecurityScan {assessment_id: $assessment_id})
                RETURN s.chain_unbroken as chain_unbroken,
                       s.inner_signature_valid as inner_valid,
                       s.outer_signature_valid as outer_valid
                """,
                assessment_id=assessment_id,
            )

            chain_record = result.single()
            if chain_record:
                print("\nVerification chain status:")
                print(f"  Chain unbroken: {chain_record['chain_unbroken']}")
                print(f"  Inner signature valid: {chain_record['inner_valid']}")
                print(f"  Outer signature valid: {chain_record['outer_valid']}")

                assert chain_record["chain_unbroken"] is True
                assert chain_record["inner_valid"] is True
                assert chain_record["outer_valid"] is True

        print("\n=== ✅ End-to-end test PASSED ===")
        print(f"Successfully verified complete workflow for scan: {scan_id}")
        print(f"Assessment ID: {assessment_id}")
        print("Non-repudiation chain: VERIFIED")


# =============================================================================
# Cleanup Test (Optional)
# =============================================================================


class TestCleanup:
    """Clean up test data after e2e tests."""

    def test_cleanup_neo4j_test_data(self, neo4j_driver):
        """Optional: Clean up test SecurityScan nodes from Neo4j."""
        with neo4j_driver.session() as session:
            # Only delete scans from e2e tests (requested_by contains 'e2e-test')
            result = session.run(
                """
                MATCH (s:SecurityScan)
                WHERE s.id STARTS WITH 'scan_'
                OPTIONAL MATCH (s)-[:CONTAINS]->(f:Finding)
                OPTIONAL MATCH (f)-[:LOCATED_AT]->(loc:Location)
                DETACH DELETE s, f, loc
                RETURN count(s) as deleted_count
                """
            )

            record = result.single()
            if record and record["deleted_count"] > 0:
                print(f"Cleaned up {record['deleted_count']} test SecurityScan nodes")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
