"""High-level API tests that exercise FastAPI routers end-to-end."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock


def test_health_endpoint_ok(test_client):
    """Smoke test for the base health endpoint."""
    response = test_client.get("/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_ingestion_unavailable_returns_503(test_client, monkeypatch):
    """If OpenSearch is unavailable the ingestion health check should fail."""

    class FailingStore:
        def count_documents(self) -> None:
            raise RuntimeError("OpenSearch down")

    monkeypatch.setattr(
        "certus_ask.routers.health.get_document_store",
        lambda: FailingStore(),
    )

    response = test_client.get("/v1/health/ingestion")

    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


def _stub_s3_client(tmp_contents: bytes = b"stub data") -> Any:
    """Create a minimal fake S3 client for datalake router tests."""

    class _StubS3:
        def download_file(self, bucket: str, key: str, filename: str) -> None:
            Path(filename).write_bytes(tmp_contents)

        def list_objects_v2(self, *args, **kwargs):
            return {"Contents": []}

    return _StubS3()


def test_datalake_preprocess_promotes_file(test_client, monkeypatch):
    """Happy-path API call to preprocess a single object."""
    upload_mock = MagicMock()

    monkeypatch.setattr("certus_ask.routers.datalake.get_s3_client", _stub_s3_client)
    monkeypatch.setattr(
        "certus_ask.routers.datalake.datalake_service.initialize_datalake_structure",
        lambda client: None,
    )
    monkeypatch.setattr(
        "certus_ask.routers.datalake.datalake_service.upload_file",
        upload_mock,
    )
    monkeypatch.setattr(
        "certus_ask.routers.datalake._extract_scan_id",
        lambda path: None,
    )
    monkeypatch.setattr(
        "certus_ask.routers.datalake._ensure_verified_scan",
        lambda client, scan_id, verified_scans: None,
    )

    payload = {
        "source_key": "privacy-pack/incoming/privacy-quickstart.md",
        "destination_prefix": "privacy-pack/golden",
    }

    response = test_client.post("/v1/datalake/preprocess", json=payload)

    assert response.status_code == 200
    assert "privacy-pack/golden" in response.json()["message"]
    upload_mock.assert_called_once()


def test_datalake_preprocess_failure_returns_500(test_client, monkeypatch):
    """If upload fails the API should respond with a 500."""
    monkeypatch.setattr("certus_ask.routers.datalake.get_s3_client", _stub_s3_client)
    monkeypatch.setattr(
        "certus_ask.routers.datalake.datalake_service.initialize_datalake_structure",
        lambda client: None,
    )
    monkeypatch.setattr(
        "certus_ask.routers.datalake.datalake_service.upload_file",
        MagicMock(side_effect=RuntimeError("upload failed")),
    )
    monkeypatch.setattr(
        "certus_ask.routers.datalake._extract_scan_id",
        lambda path: None,
    )
    monkeypatch.setattr(
        "certus_ask.routers.datalake._ensure_verified_scan",
        lambda client, scan_id, verified_scans: None,
    )

    payload = {
        "source_key": "privacy-pack/incoming/privacy-quickstart.md",
        "destination_prefix": "privacy-pack/golden",
    }

    response = test_client.post("/v1/datalake/preprocess", json=payload)

    assert response.status_code == 500


def test_query_router_returns_answer(test_client, monkeypatch):
    """Happy-path API call to the query endpoint."""

    class DummyPipeline:
        def run(self, payload):
            assert payload["retriever"]["top_k"] == 3
            return {"llm": {"replies": ["Here is your answer."]}}

    class DummyMetrics:
        def record_query(self, **kwargs):
            pass

    monkeypatch.setattr(
        "certus_ask.routers.query.get_document_store_for_workspace",
        lambda workspace_id: object(),
    )
    monkeypatch.setattr(
        "certus_ask.routers.query.create_rag_pipeline",
        lambda store: DummyPipeline(),
    )
    monkeypatch.setattr(
        "certus_ask.routers.query.get_query_metrics",
        lambda: DummyMetrics(),
    )

    response = test_client.post("/v1/demo/ask", json={"question": "Hello?"})

    assert response.status_code == 200
    assert response.json()["answer"] == "Here is your answer."


def test_query_router_timeout_returns_504(test_client, monkeypatch):
    """Pipeline timeouts should surface as HTTP 504."""

    class TimeoutPipeline:
        def run(self, payload):
            raise TimeoutError("LLM took too long")

    class DummyMetrics:
        def record_query(self, **kwargs):
            pass

    monkeypatch.setattr(
        "certus_ask.routers.query.get_document_store_for_workspace",
        lambda workspace_id: object(),
    )
    monkeypatch.setattr(
        "certus_ask.routers.query.create_rag_pipeline",
        lambda store: TimeoutPipeline(),
    )
    monkeypatch.setattr(
        "certus_ask.routers.query.get_query_metrics",
        lambda: DummyMetrics(),
    )

    response = test_client.post("/v1/demo/ask", json={"question": "Will this time out?"})

    assert response.status_code == 504
