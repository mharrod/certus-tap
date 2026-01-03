from types import SimpleNamespace

import pytest

from certus_ask.core.exceptions import ValidationError
from certus_ask.services.ingestion import (
    compute_sha256_digest,
    enforce_verified_digest,
    match_expected_digest,
)


def test_index_document_runs_pipeline(test_client, fake_preprocessing_pipeline, monkeypatch, tmp_path):
    """Uploading a document should invoke the preprocessing pipeline and return metadata preview."""
    monkeypatch.chdir(tmp_path)

    response = test_client.post(
        "/v1/demo/index/",
        files={"uploaded_file": ("doc.txt", b"hello tap", "text/plain")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"].startswith("Indexed document")
    assert payload["metadata_preview"][0]["chunk_id"] == "fake-1"
    assert fake_preprocessing_pipeline.calls, "Pipeline was not invoked"
    pipeline_payload = fake_preprocessing_pipeline.calls[0]
    assert pipeline_payload["file_type_router"]["sources"][0].name == "doc.txt"


def test_index_document_rejects_large_files(test_client, fake_preprocessing_pipeline, monkeypatch):
    """Files larger than MAX_UPLOAD_SIZE_BYTES should be rejected with HTTP 400."""
    monkeypatch.setattr("certus_ask.routers.ingestion.MAX_UPLOAD_SIZE_BYTES", 1)

    response = test_client.post(
        "/v1/demo/index/",
        files={"uploaded_file": ("large.txt", b"too big", "text/plain")},
    )

    assert response.status_code == 400
    assert fake_preprocessing_pipeline.calls == []


def test_index_security_file_delegates_to_ingest(test_client, monkeypatch):
    """Uploaded SARIF/SPDX payloads should delegate to _ingest_security_payload."""

    async def fake_ingest(workspace_id, **kwargs):
        return {
            "ingestion_id": "sec-123",
            "request_id": "req-1",
            "message": f"{workspace_id}-ok",
            "document_count": 5,
            "metadata_preview": [],
            "findings_indexed": 2,
        }

    monkeypatch.setattr("certus_ask.routers.ingestion._ingest_security_payload", fake_ingest)

    response = test_client.post(
        "/v1/demo/index/security",
        data={"format": "auto"},
        files={"uploaded_file": ("scan.sarif", b'{"runs": []}', "application/json")},
    )

    assert response.status_code == 200
    assert response.json()["ingestion_id"] == "sec-123"


def test_index_security_file_rejects_empty_payload(test_client):
    """Empty uploads should raise HTTP 400 before calling the ingest helper."""
    response = test_client.post(
        "/v1/demo/index/security",
        data={"format": "sarif"},
        files={"uploaded_file": ("scan.sarif", b"", "application/json")},
    )

    assert response.status_code == 400
    assert "empty" in response.json()["detail"]


def test_index_security_file_from_s3_streams_object(test_client, monkeypatch):
    """S3 ingestion should stream the object and forward contents to the ingestion helper."""

    class FakeBody:
        def __init__(self, payload: bytes):
            self.payload = payload

        def read(self) -> bytes:
            return self.payload

    class FakeS3Client:
        exceptions = SimpleNamespace(NoSuchKey=type("NoSuchKey", (Exception,), {}))

        def __init__(self):
            self.requests = []

        def get_object(self, Bucket, Key):
            self.requests.append((Bucket, Key))
            return {"Body": FakeBody(b'{"runs": []}')}

    fake_client = FakeS3Client()

    class FakeBoto3:
        @staticmethod
        def client(*args, **kwargs):
            return fake_client

    class FakeSettings:
        aws_access_key_id = "key"
        aws_secret_access_key = "secret"
        s3_endpoint_url = "http://localhost:4566"
        aws_region = "us-east-1"

    async def fake_ingest(workspace_id, **kwargs):
        fake_ingest.called_with = kwargs
        return {
            "ingestion_id": "sec-456",
            "request_id": "req-2",
            "message": "ok",
            "document_count": 10,
            "metadata_preview": [],
            "findings_indexed": 1,
        }

    monkeypatch.setattr("boto3.client", FakeBoto3.client)
    monkeypatch.setattr("certus_ask.core.config.Settings", lambda: FakeSettings())
    monkeypatch.setattr("certus_ask.routers.ingestion._ingest_security_payload", fake_ingest)

    response = test_client.post(
        "/v1/demo/index/security/s3",
        json={
            "bucket_name": "raw-bucket",
            "key": "scan.sarif",
            "format": "sarif",
            "tier": "free",
        },
    )

    assert response.status_code == 200
    assert fake_client.requests == [("raw-bucket", "scan.sarif")]
    assert fake_ingest.called_with["source_name"] == "s3://raw-bucket/scan.sarif"
    assert response.json()["ingestion_id"] == "sec-456"


def test_match_expected_digest_supports_uri():
    """match_expected_digest should handle entries provided as dictionaries or URIs."""
    artifact_locations = {
        "s3": [
            {"bucket": "raw-bucket", "key": "reports/scan.sarif", "digest": "sha256:dead"},
            {"uri": "s3://raw-bucket/reports/subdir/", "digest": "sha256:feed"},
        ]
    }

    assert match_expected_digest(artifact_locations, "raw-bucket", "reports/scan.sarif") == "sha256:dead"
    assert match_expected_digest(artifact_locations, "raw-bucket", "reports/subdir/file.sarif") == "sha256:feed"


def test_enforce_verified_digest_returns_actual_digest():
    """enforce_verified_digest should return the matching digest when verification succeeds."""
    payload = b"verified payload"
    digest = compute_sha256_digest(payload)
    artifact_locations = {"s3": [{"bucket": "raw-bucket", "key": "reports", "digest": digest}]}

    assert enforce_verified_digest(payload, artifact_locations, "raw-bucket", "reports/file.sarif") == digest


def test_enforce_verified_digest_raises_on_mismatch():
    """Digest mismatches must raise ValidationError to stop ingestion."""
    artifact_locations = {"s3": [{"bucket": "raw-bucket", "key": "reports", "digest": "sha256:expected"}]}

    with pytest.raises(ValidationError):
        enforce_verified_digest(b"not matching", artifact_locations, "raw-bucket", "reports/file")
