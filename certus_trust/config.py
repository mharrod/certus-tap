"""Configuration for Certus-Trust service."""

from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class CertusTrustSettings(BaseSettings):
    """Certus-Trust configuration from environment variables."""

    # Service configuration
    host: str = "0.0.0.0"
    port: int = 8888
    log_level: str = "INFO"
    environment: str = "development"

    # Sigstore endpoints (local development defaults)
    fulcio_addr: str = "http://fulcio:5555"
    rekor_addr: str = "http://rekor:3000"
    tuf_addr: str = "http://tuf:8001"
    keycloak_addr: str = "http://keycloak:8080"

    # OIDC Configuration
    oidc_issuer: str = "http://keycloak:8080/realms/master"
    oidc_client_id: str = "certus"

    # Key management (optional for local key-based signing)
    cosign_key_path: Optional[str] = None
    cosign_password: Optional[str] = None

    # Feature flags
    enable_keyless: bool = True
    enable_transparency: bool = True

    # Mock/Production toggle (KEY SETTING)
    mock_sigstore: bool = Field(
        default=True, description="If True, use mock implementations. If False, use real Sigstore."
    )

    # Limits
    max_artifact_size: int = 1_000_000_000  # 1GB

    # S3 configuration (for passing to Transform)
    s3_raw_bucket: str = Field(default="raw", env="DATALAKE_RAW_BUCKET")
    s3_golden_bucket: str = Field(default="golden", env="DATALAKE_GOLDEN_BUCKET")
    s3_endpoint_url: str = Field(default="http://localstack:4566", env="S3_ENDPOINT_URL")

    class Config:
        env_prefix = "CERTUS_TRUST_"
        env_file = ".env"
        case_sensitive = False


def get_settings() -> CertusTrustSettings:
    """Get Certus-Trust settings."""
    return CertusTrustSettings()
