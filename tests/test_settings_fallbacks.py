"""Tests for Settings host fallback logic."""

import socket

import pytest

from certus_ask.core.config import Settings


@pytest.mark.parametrize(
    "host,expected",
    [
        ("http://opensearch:9200", "http://localhost:9200"),
        ("http://localstack:4566", "http://localhost:4566"),
        ("http://mlflow:5001", "http://localhost:5001"),
        ("neo4j://neo4j:7687", "neo4j://localhost:7687"),
    ],
)
def test_settings_apply_host_fallback(monkeypatch, host: str, expected: str) -> None:
    """Ensure container hostnames fall back to localhost when DNS lookup fails."""

    def fake_getaddrinfo(target_host: str, *_args, **_kwargs):
        if target_host in {"opensearch", "localstack", "mlflow", "neo4j"}:
            raise socket.gaierror
        return [(None, None, None, None, None)]

    monkeypatch.setattr("certus_ask.core.config.socket.getaddrinfo", fake_getaddrinfo)

    settings = Settings(
        opensearch_host=host if "opensearch" in host else "http://opensearch:9200",
        opensearch_index="ask_certus",
        aws_access_key_id="test",
        aws_secret_access_key="test",
        s3_endpoint_url=host if "localstack" in host else "http://localstack:4566",
        aws_region="us-east-1",
        llm_model="llama",
        llm_url="http://localhost:11434",
        mlflow_tracking_uri=host if "mlflow" in host else "http://mlflow:5001",
        neo4j_uri=host if host.startswith("neo4j://") else "neo4j://neo4j:7687",
    )

    if "opensearch" in host:
        assert settings.opensearch_host == expected
    elif "localstack" in host:
        assert settings.s3_endpoint_url == expected
    elif "mlflow" in host:
        assert settings.mlflow_tracking_uri == expected
    elif host.startswith("neo4j://"):
        assert settings.neo4j_uri == expected
