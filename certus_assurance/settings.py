from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class CertusAssuranceSettings(BaseSettings):
    """Configuration for the incubating Certus Assurance service.

    All values can be overridden via environment variables. Prefix: ``CERTUS_ASSURANCE_``.
    """

    artifact_root: Path = Field(default=Path("certus-assurance-artifacts"))
    trust_base_url: str = Field(default="http://certus-trust:8000")
    s3_bucket: str | None = None  # Backwards compatibility (unused when raw/golden configured)
    datalake_raw_bucket: str = Field(default="raw")
    datalake_golden_bucket: str = Field(default="golden")
    datalake_raw_prefix: str = "security-scans"
    datalake_golden_prefix: str = "security-scans"
    s3_endpoint_url: str | None = None
    s3_region: str = "us-east-1"
    s3_access_key_id: str | None = None
    s3_secret_access_key: str | None = None
    enable_s3_upload: bool = False
    registry: str = "registry.example.com"
    registry_repository: str = "certus-assurance"
    registry_username: str | None = None
    registry_password: str | None = None
    enable_registry_push: bool = False
    registry_push_strategy: Literal["mirror", "docker"] = "mirror"
    registry_mirror_dir: Path = Field(default=Path("certus-assurance-registry"))
    case_study_source: Path = Field(default=Path("samples/non-repudiation/scan-artifacts"))
    cosign_enabled: bool = False
    cosign_path: str = "cosign"
    cosign_key_ref: str | None = None
    cosign_password: str | None = None
    manifest_verification_key_ref: str | None = None
    manifest_verification_required: bool = False
    max_workers: int = 2
    webhook_url: str | None = None
    use_sample_mode: bool = Field(
        default=False,
        description="Use sample scanner (demo mode) instead of real security tools. "
        "Set to true for tutorials/demos that don't require security_module.",
    )

    model_config = SettingsConfigDict(env_prefix="CERTUS_ASSURANCE_", extra="ignore")


settings = CertusAssuranceSettings()
