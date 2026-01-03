import socket
from functools import lru_cache
from urllib.parse import urlparse

import structlog
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = structlog.get_logger(__name__)


def _prefer_resolvable_url(url: str, fallback: str, field_name: str) -> str:
    """
    Return the original URL if its hostname resolves, otherwise fall back to localhost.

    This enables developers to run the stack outside of Docker without having to
    override every `*_HOST` environment variable when the default container
    hostname (e.g., `opensearch`, `neo4j`) cannot be resolved from the host OS.
    """
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        return url.rstrip("/")

    try:
        socket.getaddrinfo(host, None)
        return url.rstrip("/")
    except socket.gaierror:
        logger.warning(
            "config.host_fallback_applied",
            field=field_name,
            configured=url,
            fallback=fallback,
        )
        return fallback.rstrip("/")


class Settings(BaseSettings):
    # OpenSearch - Documents
    opensearch_host: str = Field(..., env="OPENSEARCH_HOST")
    opensearch_index: str = Field(..., env="OPENSEARCH_INDEX")
    opensearch_http_auth_user: str | None = Field(None, env="OPENSEARCH_HTTP_AUTH_USER")
    opensearch_http_auth_password: str | None = Field(None, env="OPENSEARCH_HTTP_AUTH_PASSWORD")

    # OpenSearch - Logging (optional, same cluster or separate)
    opensearch_log_host: str = Field(default="localhost", env="OPENSEARCH_LOG_HOST")
    opensearch_log_port: int = Field(default=9200, env="OPENSEARCH_LOG_PORT")
    opensearch_log_username: str | None = Field(None, env="OPENSEARCH_LOG_USERNAME")
    opensearch_log_password: str | None = Field(None, env="OPENSEARCH_LOG_PASSWORD")

    # Neo4j - Knowledge Graph
    neo4j_uri: str = Field(default="neo4j://localhost:7687", env="NEO4J_URI")
    neo4j_user: str = Field(default="neo4j", env="NEO4J_USER")
    neo4j_password: str = Field(default="password", env="NEO4J_PASSWORD")
    neo4j_enabled: bool = Field(default=True, env="NEO4J_ENABLED")

    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_json_output: bool = Field(default=True, env="LOG_JSON_OUTPUT")
    send_logs_to_opensearch: bool = Field(default=True, env="SEND_LOGS_TO_OPENSEARCH")
    disable_opensearch_logging: bool = Field(
        default=False,
        env="DISABLE_OPENSEARCH_LOGGING",
        description="When true, never attempt to initialize the async OpenSearch log handler.",
    )

    aws_access_key_id: str = Field(..., env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., env="AWS_SECRET_ACCESS_KEY")
    s3_endpoint_url: str = Field(..., env="S3_ENDPOINT_URL")
    aws_region: str = Field(..., env="AWS_REGION")

    llm_model: str = Field(..., env="LLM_MODEL")
    llm_url: str = Field(..., env="LLM_URL")

    mlflow_tracking_uri: str = Field(..., env="MLFLOW_TRACKING_URI")

    anonymizer_enabled: bool = Field(default=True, env="ANONYMIZER_ENABLED")

    github_token: str | None = Field(None, env="GITHUB_TOKEN")

    datalake_raw_bucket: str = Field(default="raw", env="DATALAKE_RAW_BUCKET")
    datalake_golden_bucket: str = Field(default="golden", env="DATALAKE_GOLDEN_BUCKET")
    datalake_default_folders: str | list[str] = Field(
        default="broker,support,marketing,video,other",
        env="DATALAKE_DEFAULT_FOLDERS",
    )

    evaluation_bucket: str = Field(default="evaluation-results", env="EVALUATION_BUCKET")

    # Certus-Trust backend configuration (for non-repudiation verification)
    trust_base_url: str = Field(default="http://certus-trust:8000", env="TRUST_BASE_URL")
    trust_api_key: str | None = Field(default=None, env="TRUST_API_KEY")
    trust_verify_ssl: bool = Field(default=True, env="TRUST_VERIFY_SSL")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _normalize_datalake_folders(self) -> "Settings":
        if isinstance(self.datalake_default_folders, str):
            self.datalake_default_folders = [
                item.strip() for item in self.datalake_default_folders.split(",") if item.strip()
            ]
        return self

    @model_validator(mode="after")
    def _apply_host_fallbacks(self) -> "Settings":
        # Prefer localhost when Docker hostnames are unreachable outside the compose network.
        self.opensearch_host = _prefer_resolvable_url(self.opensearch_host, "http://localhost:9200", "opensearch_host")
        self.s3_endpoint_url = _prefer_resolvable_url(self.s3_endpoint_url, "http://localhost:4566", "s3_endpoint_url")
        self.mlflow_tracking_uri = _prefer_resolvable_url(
            self.mlflow_tracking_uri, "http://localhost:5001", "mlflow_tracking_uri"
        )
        self.neo4j_uri = _prefer_resolvable_url(self.neo4j_uri, "neo4j://localhost:7687", "neo4j_uri")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
