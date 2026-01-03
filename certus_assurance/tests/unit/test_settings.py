"""Unit tests for Certus Assurance settings."""

import os
from pathlib import Path

import pytest

from certus_assurance.settings import CertusAssuranceSettings


def test_settings_defaults():
    """Test that settings have expected defaults."""
    settings = CertusAssuranceSettings()

    assert settings.artifact_root == Path("certus-assurance-artifacts")
    assert settings.trust_base_url == "http://certus-trust:8000"
    assert settings.datalake_raw_bucket == "raw"
    assert settings.datalake_golden_bucket == "golden"
    assert settings.s3_region == "us-east-1"
    assert settings.enable_s3_upload is False
    assert settings.enable_registry_push is False
    assert settings.use_sample_mode is False
    assert settings.max_workers == 2


def test_settings_use_sample_mode_default():
    """Test that use_sample_mode defaults to False."""
    settings = CertusAssuranceSettings()

    assert settings.use_sample_mode is False


def test_settings_can_override_via_env(monkeypatch):
    """Test that settings can be overridden via environment variables."""
    monkeypatch.setenv("CERTUS_ASSURANCE_ARTIFACT_ROOT", "/tmp/test-artifacts")
    monkeypatch.setenv("CERTUS_ASSURANCE_USE_SAMPLE_MODE", "true")
    monkeypatch.setenv("CERTUS_ASSURANCE_MAX_WORKERS", "4")

    settings = CertusAssuranceSettings()

    assert settings.artifact_root == Path("/tmp/test-artifacts")
    assert settings.use_sample_mode is True
    assert settings.max_workers == 4


def test_settings_trust_base_url_customizable(monkeypatch):
    """Test that trust_base_url can be customized."""
    monkeypatch.setenv("CERTUS_ASSURANCE_TRUST_BASE_URL", "http://custom-trust:9000")

    settings = CertusAssuranceSettings()

    assert settings.trust_base_url == "http://custom-trust:9000"


def test_settings_s3_configuration():
    """Test S3 configuration fields exist."""
    settings = CertusAssuranceSettings()

    # Should have S3-related fields
    assert hasattr(settings, "s3_endpoint_url")
    assert hasattr(settings, "s3_region")
    assert hasattr(settings, "s3_access_key_id")
    assert hasattr(settings, "s3_secret_access_key")
    assert hasattr(settings, "enable_s3_upload")


def test_settings_registry_configuration():
    """Test registry configuration fields exist."""
    settings = CertusAssuranceSettings()

    # Should have registry-related fields
    assert hasattr(settings, "registry")
    assert hasattr(settings, "registry_repository")
    assert hasattr(settings, "registry_username")
    assert hasattr(settings, "registry_password")
    assert hasattr(settings, "enable_registry_push")
    assert hasattr(settings, "registry_push_strategy")


def test_settings_cosign_configuration():
    """Test Cosign signing configuration fields exist."""
    settings = CertusAssuranceSettings()

    # Should have Cosign-related fields
    assert hasattr(settings, "cosign_enabled")
    assert hasattr(settings, "cosign_path")
    assert hasattr(settings, "cosign_key_ref")
    assert hasattr(settings, "cosign_password")


def test_settings_manifest_verification_configuration():
    """Test manifest verification configuration fields exist."""
    settings = CertusAssuranceSettings()

    # Should have manifest verification fields
    assert hasattr(settings, "manifest_verification_key_ref")
    assert hasattr(settings, "manifest_verification_required")
    assert settings.manifest_verification_required is False


def test_settings_case_study_source_default():
    """Test that case_study_source points to sample artifacts."""
    settings = CertusAssuranceSettings()

    assert settings.case_study_source == Path("samples/non-repudiation/scan-artifacts")


def test_settings_registry_push_strategy_default():
    """Test that registry_push_strategy defaults to 'mirror'."""
    settings = CertusAssuranceSettings()

    assert settings.registry_push_strategy == "mirror"


def test_settings_registry_push_strategy_accepts_docker(monkeypatch):
    """Test that registry_push_strategy can be set to 'docker'."""
    monkeypatch.setenv("CERTUS_ASSURANCE_REGISTRY_PUSH_STRATEGY", "docker")

    settings = CertusAssuranceSettings()

    assert settings.registry_push_strategy == "docker"
