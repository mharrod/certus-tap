from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration for the customer-run data preparation service."""

    # Local S3/LocalStack configuration
    aws_access_key_id: str = Field(..., env="AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(..., env="AWS_SECRET_ACCESS_KEY")
    aws_region: str = Field(default="us-east-1", env="AWS_REGION")
    s3_endpoint_url: str = Field(default="http://localhost:4566", env="S3_ENDPOINT_URL")

    raw_bucket: str = Field(default="raw", env="DATALAKE_RAW_BUCKET")
    golden_bucket: str = Field(default="golden", env="DATALAKE_GOLDEN_BUCKET")
    active_prefix: str = Field(default="active/", env="RAW_ACTIVE_PREFIX")
    quarantine_prefix: str = Field(default="quarantine/", env="RAW_QUARANTINE_PREFIX")
    golden_destination_prefix: str = Field(default="scans/", env="GOLDEN_SCANS_PREFIX")

    # SaaS backend configuration
    saas_base_url: str = Field(default="http://ask-certus-backend:8000", env="SAAS_BACKEND_URL")
    saas_api_key: str | None = Field(default=None, env="SAAS_API_KEY")
    saas_verify_ssl: bool = Field(default=True, env="SAAS_VERIFY_SSL")

    # Certus-Trust backend configuration (for non-repudiation)
    trust_base_url: str = Field(default="http://certus-trust:8888", env="TRUST_BASE_URL")
    trust_api_key: str | None = Field(default=None, env="TRUST_API_KEY")
    trust_verify_ssl: bool = Field(default=True, env="TRUST_VERIFY_SSL")

    default_workspace_id: str = Field(default="security-streaming-demo", env="DEFAULT_WORKSPACE_ID")

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
