"""Shared test fixtures for certus_transform tests.

Provides:
- HTTP client for testing FastAPI endpoints
- Mock S3 resources
- Configuration fixtures
- Sample data for testing
"""

import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

import pytest
import requests
from httpx import AsyncClient

# Test configuration
TRANSFORM_URL = os.getenv("TRANSFORM_URL", "http://localhost:8100")


@pytest.fixture(scope="session")
def transform_base_url() -> str:
    """Get the Transform service base URL.

    Returns:
        Base URL for Transform service (default: http://localhost:8100)
    """
    return TRANSFORM_URL


@pytest.fixture(scope="session")
def http_session() -> Generator[requests.Session, None, None]:
    """Create HTTP session for synchronous requests.

    Yields:
        Configured requests.Session
    """
    session = requests.Session()
    # Don't set Content-Type header - let requests handle it automatically
    # for multipart/form-data (file uploads) and application/json (JSON requests)
    yield session
    session.close()


@pytest.fixture
async def async_client(transform_base_url: str) -> AsyncGenerator[AsyncClient, None]:
    """Create async HTTP client for testing endpoints.

    Args:
        transform_base_url: Base URL for Transform service

    Yields:
        Configured AsyncClient for httpx
    """
    async with AsyncClient(base_url=transform_base_url, timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def request_timeout() -> int:
    """Default request timeout for tests.

    Returns:
        Timeout in seconds (default: 30)
    """
    return int(os.getenv("TEST_REQUEST_TIMEOUT", "30"))


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """Path to test data directory.

    Returns:
        Path to test-artifacts directory
    """
    # Go up from certus_transform/tests/ to project root, then to samples
    # This matches how certus_trust tests work
    repo_root = Path(__file__).resolve().parents[2]
    samples_dir = repo_root / "samples"

    if not samples_dir.exists():
        pytest.skip(f"Samples directory not found: {samples_dir}")

    return samples_dir


@pytest.fixture
def scan_artifacts_dir(test_data_dir: Path) -> Path:
    """Path to scan artifacts directory.

    Args:
        test_data_dir: Test data directory (samples/)

    Returns:
        Path to non-repudiation/scan-artifacts
    """
    scan_artifacts = test_data_dir / "non-repudiation" / "scan-artifacts"

    if not scan_artifacts.exists():
        pytest.skip(f"Scan artifacts directory not found: {scan_artifacts}")

    return scan_artifacts


@pytest.fixture
def sample_document(scan_artifacts_dir: Path) -> Path:
    """Path to a sample document for upload testing.

    Args:
        scan_artifacts_dir: Scan artifacts directory

    Returns:
        Path to sample document
    """
    # Look for markdown files first (documentation)
    sample_files = list(scan_artifacts_dir.glob("*.md"))

    if not sample_files:
        # Fall back to any SARIF or JSON file
        sample_files = list(scan_artifacts_dir.glob("*.sarif.json")) + list(scan_artifacts_dir.glob("*.json"))

    if not sample_files:
        pytest.skip("No sample documents found in scan artifacts")

    return sample_files[0]


@pytest.fixture
def s3_test_config() -> dict[str, str]:
    """S3 configuration for testing.

    Returns:
        Dict with S3 bucket names and prefixes
    """
    return {
        "raw_bucket": os.getenv("DATALAKE_RAW_BUCKET", "raw"),
        "golden_bucket": os.getenv("DATALAKE_GOLDEN_BUCKET", "golden"),
        "raw_prefix": "active/",
        "quarantine_prefix": "quarantine/",
        "golden_prefix": "",
    }


@pytest.fixture
def sample_upload_request() -> dict:
    """Sample upload request payload for verification workflow.

    Returns:
        Dict representing ExecuteUploadRequestModel
    """
    return {
        "upload_permission_id": "perm_test_12345",
        "scan_id": "scan_test_abc123",
        "tier": "basic",
        "artifacts": [
            {
                "name": "trivy.json",
                "hash": "sha256:abc123def456",
                "size": 1024,
            }
        ],
        "metadata": {
            "git_url": "https://github.com/example/repo",
            "branch": "main",
            "commit": "a1b2c3d4e5f6",
            "requested_by": "test-user",
        },
        "verification_proof": {
            "chain_verified": True,
            "inner_signature_valid": True,
            "outer_signature_valid": False,
            "signer_inner": "certus-assurance@certus.cloud",
            "signer_outer": None,
            "verification_timestamp": "2025-12-18T19:30:00Z",
            "rekor_entry_uuid": "uuid-test-12345",
        },
        "storage_config": {
            "raw_s3_bucket": "raw",
            "raw_s3_prefix": "active/test/",
            "oci_registry": None,
            "oci_repository": None,
            "upload_to_s3": True,
            "upload_to_oci": False,
        },
    }


@pytest.fixture
def sample_privacy_scan_request(s3_test_config: dict[str, str]) -> dict:
    """Sample privacy scan request payload.

    Args:
        s3_test_config: S3 configuration

    Returns:
        Dict representing PrivacyScanRequest
    """
    return {
        "bucket": s3_test_config["raw_bucket"],
        "prefix": s3_test_config["raw_prefix"],
        "quarantine_prefix": s3_test_config["quarantine_prefix"],
        "dry_run": False,
        "report_object": None,
    }


@pytest.fixture
def sample_promotion_request(s3_test_config: dict[str, str]) -> dict:
    """Sample promotion request payload.

    Args:
        s3_test_config: S3 configuration

    Returns:
        Dict representing PromotionRequest
    """
    return {
        "source_bucket": s3_test_config["raw_bucket"],
        "source_prefix": s3_test_config["raw_prefix"],
        "destination_bucket": s3_test_config["golden_bucket"],
        "destination_prefix": s3_test_config["golden_prefix"],
        "keys": [],  # Specific keys to promote
    }
