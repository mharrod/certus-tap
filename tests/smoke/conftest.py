from __future__ import annotations

import os
import re
import socket
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import boto3
import pytest
import requests
from botocore.exceptions import ClientError

from tests.smoke.utils import upload_directory_to_s3

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(os.getenv("SMOKE_REPO_ROOT", Path(__file__).resolve().parents[2]))
SAMPLES_ROOT = Path(os.getenv("SMOKE_SAMPLES_ROOT", REPO_ROOT / "samples"))
DEFAULT_SAMPLE_FILE = Path(
    os.getenv("SMOKE_TUTORIAL_FILE_DEFAULT", SAMPLES_ROOT / "ingestion-examples/quick-start-guide.txt")
)
DEFAULT_SAMPLE_DIR = Path(os.getenv("SMOKE_TUTORIAL_DIR_DEFAULT", SAMPLES_ROOT / "ingestion-examples"))
DEFAULT_DATALAKE_DIR = Path(os.getenv("SMOKE_DATALAKE_DIR_DEFAULT", SAMPLES_ROOT / "datalake-demo"))
DEFAULT_PRIVACY_RAW_DIR = Path(os.getenv("SMOKE_PRIVACY_RAW_DIR_DEFAULT", SAMPLES_ROOT / "privacy-pack/raw"))
DEFAULT_RAW_BUCKET = "raw"
DEFAULT_GOLDEN_BUCKET = "golden"
DEFAULT_LOCALSTACK_ENDPOINT = "http://localstack:4566"

_HOST_FALLBACKS = {
    "NEO4J_BOLT_URI": "neo4j://localhost:7687",
    "NEO4J_HTTP_URL": "http://localhost:7474/db/neo4j/tx/commit",
    "ASSURANCE_INTERNAL_URL": "http://localhost:8056",
    "ASSURANCE_EXTERNAL_URL": "http://localhost:8056",
    "TRUST_INTERNAL_URL": "http://localhost:8057",
    "TRUST_EXTERNAL_URL": "http://localhost:8057",
}

for env_key, default_value in _HOST_FALLBACKS.items():
    os.environ.setdefault(env_key, default_value)


def _prefer_host_url(env_var: str, container_url: str, host_url: str) -> str:
    override = os.getenv(env_var)
    if override:
        return override.rstrip("/")
    parsed = urlparse(container_url)
    host = parsed.hostname or ""
    try:
        if host:
            socket.getaddrinfo(host, None)
            return container_url.rstrip("/")
    except socket.gaierror:
        pass
    return host_url.rstrip("/")


@pytest.fixture(scope="session")
def api_base() -> str:
    """Base URL for the Ask Certus API."""
    return _prefer_host_url("API_BASE", "http://ask-certus-backend:8000", "http://localhost:8000")


@pytest.fixture(scope="session")
def os_endpoint() -> str:
    """Base URL for the OpenSearch cluster."""
    return _prefer_host_url("OS_ENDPOINT", "http://opensearch:9200", "http://localhost:9200")


@pytest.fixture(scope="session")
def workspace_id() -> str:
    """
    Workspace used for smoke tests.

    Default is a unique session-specific workspace so repeated runs do not
    collide with one another, but the value can be overridden through
    SMOKE_WORKSPACE when debugging locally.
    """
    env_override = os.getenv("SMOKE_WORKSPACE")
    if env_override:
        return env_override
    timestamp = int(time.time())
    return f"smoke-ingestion-{timestamp}"


@pytest.fixture(scope="session")
def workspace_index(workspace_id: str) -> str:
    """Mirror the application logic for mapping workspace→index."""
    sanitized = re.sub(r"[^a-z0-9_-]+", "-", workspace_id.lower()).strip("-")
    if not sanitized:
        sanitized = "default"
    return f"ask_certus_{sanitized}"


@pytest.fixture(scope="session")
def tutorial_sample_file() -> Path:
    """Path to the single-document example from the tutorial."""
    path = Path(os.getenv("SMOKE_TUTORIAL_FILE", DEFAULT_SAMPLE_FILE))
    if not path.exists():
        pytest.fail(f"Sample tutorial file not found: {path}")
    return path


@pytest.fixture(scope="session")
def tutorial_samples_dir() -> Path:
    """Directory that contains the ingestion tutorial's batch corpus."""
    path = Path(os.getenv("SMOKE_TUTORIAL_DIR", DEFAULT_SAMPLE_DIR))
    if not path.exists():
        pytest.fail(f"Sample tutorial directory not found: {path}")
    return path


@pytest.fixture(scope="session")
def tutorial_samples_dir_container() -> str:
    """Container path for the ingestion tutorial samples (for index_folder API)."""
    return os.getenv("SMOKE_TUTORIAL_DIR_CONTAINER", "/app/samples/ingestion-examples")


@pytest.fixture(scope="session")
def datalake_samples_dir() -> Path:
    """Directory containing the sample datalake bundle."""
    path = Path(os.getenv("SMOKE_DATALAKE_DIR", DEFAULT_DATALAKE_DIR))
    if not path.exists():
        pytest.fail(f"Datalake sample directory not found: {path}")
    return path


@pytest.fixture(scope="session")
def privacy_raw_samples_dir() -> Path:
    """Directory containing the privacy pack raw documents."""
    path = Path(os.getenv("SMOKE_PRIVACY_RAW_DIR", DEFAULT_PRIVACY_RAW_DIR))
    if not path.exists():
        pytest.fail(f"Privacy sample directory not found: {path}")
    return path


@pytest.fixture(scope="session")
def s3_endpoint() -> str:
    """Endpoint for LocalStack S3 interactions."""
    return _prefer_host_url("LOCALSTACK_ENDPOINT", DEFAULT_LOCALSTACK_ENDPOINT, "http://localhost:4566")


@pytest.fixture(scope="session")
def s3_client(s3_endpoint: str):
    """Session-scoped boto3 client pointed at LocalStack."""
    return boto3.client(
        "s3",
        endpoint_url=s3_endpoint,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
        region_name=os.getenv("AWS_REGION", "us-east-1"),
    )


@pytest.fixture(scope="session")
def raw_bucket_name(s3_client) -> str:
    """Ensure the raw bucket exists and return its name."""
    bucket = os.getenv("SMOKE_RAW_BUCKET", os.getenv("DATALAKE_RAW_BUCKET", DEFAULT_RAW_BUCKET))
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        s3_client.create_bucket(Bucket=bucket)
    return bucket


@pytest.fixture(scope="session")
def golden_bucket_name(s3_client) -> str:
    """Ensure the golden bucket exists and return its name."""
    bucket = os.getenv("SMOKE_GOLDEN_BUCKET", os.getenv("DATALAKE_GOLDEN_BUCKET", DEFAULT_GOLDEN_BUCKET))
    try:
        s3_client.head_bucket(Bucket=bucket)
    except ClientError:
        s3_client.create_bucket(Bucket=bucket)
    return bucket


@pytest.fixture(scope="session", autouse=True)
def seed_localstack_samples(
    s3_client,
    raw_bucket_name: str,
    datalake_samples_dir: Path,
    privacy_raw_samples_dir: Path,
) -> None:
    """
    Ensure required sample prefixes exist in LocalStack before running tests.
    """
    sample_prefix = os.getenv("SMOKE_SAMPLE_PREFIX", "samples")
    upload_directory_to_s3(s3_client, raw_bucket_name, f"{sample_prefix}/datalake-demo", datalake_samples_dir)
    upload_directory_to_s3(s3_client, raw_bucket_name, f"{sample_prefix}/privacy-pack/raw", privacy_raw_samples_dir)


@pytest.fixture(scope="session")
def http_session() -> Iterator[requests.Session]:
    """Reusable HTTP session for all smoke tests."""
    with requests.Session() as session:
        yield session


@pytest.fixture(scope="session")
def request_timeout() -> int:
    """Default request timeout (seconds) for the smoke test HTTP calls."""
    return int(os.getenv("SMOKE_REQUEST_TIMEOUT", "60"))


@pytest.fixture(scope="session")
def wait_for_phrase(
    http_session: requests.Session, os_endpoint: str
) -> Callable[[str, str, int, float], dict[str, Any]]:
    """Poll OpenSearch until a phrase appears in the target index."""

    def _wait(
        index_name: str,
        phrase: str,
        timeout: int = 120,
        poll_interval: float = 2.0,
    ) -> dict[str, Any]:
        search_url = f"{os_endpoint}/{index_name}/_search"
        deadline = time.time() + timeout
        last_error: str | None = None

        while time.time() < deadline:
            try:
                response = http_session.post(
                    search_url,
                    json={"query": {"match_phrase": {"content": phrase}}},
                    timeout=10,
                )
            except requests.RequestException as exc:
                last_error = str(exc)
                time.sleep(poll_interval)
                continue

            if response.status_code == 404:
                time.sleep(poll_interval)
                continue

            try:
                response.raise_for_status()
            except requests.HTTPError as exc:
                last_error = str(exc)
                time.sleep(poll_interval)
                continue

            data: dict[str, Any] = response.json()
            hits = data.get("hits", {}).get("total", {})
            hit_count = hits.get("value", hits if isinstance(hits, int) else 0)
            if hit_count and hit_count > 0:
                return data

            time.sleep(poll_interval)

        detail = f" OpenSearch last error: {last_error}" if last_error else ""
        pytest.fail(f"Timed out waiting for phrase '{phrase}' in index {index_name}.{detail}")

    return _wait


@pytest.fixture(scope="session")
def base_index_name() -> str:
    """Primary OpenSearch index used for shared preprocessing flows."""
    return os.getenv("SMOKE_BASE_INDEX") or os.getenv("OPENSEARCH_INDEX", "ask_certus")
