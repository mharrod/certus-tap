"""
Configuration Tests for certus_integrity.

Tests environment variable parsing, validation, and default values for:
- IntegrityMiddleware configuration (rate limits, shadow mode, whitelist)
- Telemetry configuration (service name, endpoints)
- EvidenceGenerator configuration (trust service URL)
"""

import os
from unittest.mock import patch

import pytest
from fastapi import FastAPI

from certus_integrity.evidence import EvidenceGenerator
from certus_integrity.middleware import IntegrityMiddleware
from certus_integrity.telemetry import configure_observability


class TestMiddlewareConfiguration:
    """Test IntegrityMiddleware environment variable parsing."""

    def test_middleware_default_values(self):
        """Test middleware uses correct defaults when env vars not set."""
        app = FastAPI()

        with patch.dict(os.environ, {}, clear=True):
            middleware = IntegrityMiddleware(app)

        assert middleware.rate_limit == 100
        assert middleware.burst_limit == 20
        assert middleware.shadow_mode is True
        assert "127.0.0.1" in middleware.whitelist

    def test_middleware_custom_rate_limit(self):
        """Test custom rate limit from environment."""
        app = FastAPI()

        with patch.dict(os.environ, {"INTEGRITY_RATE_LIMIT_PER_MIN": "200"}, clear=True):
            middleware = IntegrityMiddleware(app)

        assert middleware.rate_limit == 200

    def test_middleware_custom_burst_limit(self):
        """Test custom burst limit from environment."""
        app = FastAPI()

        with patch.dict(os.environ, {"INTEGRITY_BURST_LIMIT": "50"}, clear=True):
            middleware = IntegrityMiddleware(app)

        assert middleware.burst_limit == 50

    def test_middleware_shadow_mode_disabled(self):
        """Test shadow mode can be disabled."""
        app = FastAPI()

        with patch.dict(os.environ, {"INTEGRITY_SHADOW_MODE": "false"}, clear=True):
            middleware = IntegrityMiddleware(app)

        assert middleware.shadow_mode is False

    def test_middleware_shadow_mode_case_insensitive(self):
        """Test shadow mode parsing is case insensitive."""
        app = FastAPI()

        # Test various cases
        for value in ["FALSE", "False", "FaLsE"]:
            with patch.dict(os.environ, {"INTEGRITY_SHADOW_MODE": value}, clear=True):
                middleware = IntegrityMiddleware(app)
                assert middleware.shadow_mode is False

    def test_middleware_invalid_rate_limit_falls_back(self):
        """Test invalid rate limit value handling."""
        app = FastAPI()

        # Non-numeric value should cause ValueError, need to handle
        with patch.dict(os.environ, {"INTEGRITY_RATE_LIMIT_PER_MIN": "invalid"}, clear=True):
            with pytest.raises(ValueError):
                middleware = IntegrityMiddleware(app)

    def test_middleware_whitelist_parsing(self):
        """Test whitelist IP parsing from environment."""
        app = FastAPI()

        with patch.dict(os.environ, {"INTEGRITY_WHITELIST_IPS": "10.0.0.1,192.168.1.0/24,172.16.0.0/16"}, clear=True):
            middleware = IntegrityMiddleware(app)

        assert "10.0.0.1" in middleware.whitelist
        assert "192.168.1.0/24" in middleware.whitelist
        assert "172.16.0.0/16" in middleware.whitelist

    def test_middleware_empty_whitelist(self):
        """Test empty whitelist configuration."""
        app = FastAPI()

        with patch.dict(os.environ, {"INTEGRITY_WHITELIST_IPS": ""}, clear=True):
            middleware = IntegrityMiddleware(app)

        assert len(middleware.whitelist) == 0


class TestEvidenceGeneratorConfiguration:
    """Test EvidenceGenerator configuration."""

    def test_evidence_generator_service_name(self):
        """Test service name configuration."""
        generator = EvidenceGenerator(service_name="test-service")
        assert generator.service_name == "test-service"

    def test_evidence_generator_custom_trust_url(self):
        """Test custom trust service URL."""
        with patch.dict(os.environ, {"TRUST_BASE_URL": "http://custom-trust:8080"}, clear=True):
            generator = EvidenceGenerator(service_name="test")
            assert generator.trust_url == "http://custom-trust:8080"

    def test_evidence_generator_default_trust_url(self):
        """Test default trust service URL."""
        with patch.dict(os.environ, {}, clear=True):
            generator = EvidenceGenerator(service_name="test")
            assert generator.trust_url == "http://certus-trust:8000"


class TestTelemetryConfiguration:
    """Test telemetry configuration."""

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_telemetry_default_configuration(self, mock_logging, mock_otel, mock_instrumentor):
        """Test telemetry with default configuration."""
        app = FastAPI()

        configure_observability(app, service_name="test-service")

        mock_otel.assert_called_once_with("test-service", "http://otel-collector:4318")
        mock_instrumentor.instrument_app.assert_called_once_with(app)
        mock_logging.assert_called_once_with("INFO", True)

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_telemetry_custom_endpoint(self, mock_logging, mock_otel, mock_instrumentor):
        """Test custom OpenTelemetry endpoint."""
        app = FastAPI()

        configure_observability(app, service_name="test-service", otel_endpoint="http://custom-otel:4318")

        mock_otel.assert_called_once_with("test-service", "http://custom-otel:4318")

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_telemetry_custom_log_level(self, mock_logging, mock_otel, mock_instrumentor):
        """Test custom log level."""
        app = FastAPI()

        configure_observability(app, service_name="test-service", log_level="DEBUG")

        mock_logging.assert_called_once_with("DEBUG", True)

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_telemetry_json_logs_disabled(self, mock_logging, mock_otel, mock_instrumentor):
        """Test disabling JSON logs."""
        app = FastAPI()

        configure_observability(app, service_name="test-service", enable_json_logs=False)

        mock_logging.assert_called_once_with("INFO", False)
