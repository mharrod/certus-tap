"""
Telemetry Integration Tests for certus_integrity.

Tests the full observability configuration including:
- OpenTelemetry setup (traces and metrics)
- FastAPI instrumentation
- Structlog configuration
- Middleware integration
- End-to-end telemetry flow
- Error handling in telemetry setup
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI

from certus_integrity.telemetry import (
    _configure_logging,
    _configure_opentelemetry,
    configure_observability,
)


class TestOpenTelemetryConfiguration:
    """Test OpenTelemetry setup."""

    @patch("certus_integrity.telemetry.trace.set_tracer_provider")
    @patch("certus_integrity.telemetry.metrics.set_meter_provider")
    @patch("certus_integrity.telemetry.OTLPSpanExporter")
    @patch("certus_integrity.telemetry.OTLPMetricExporter")
    def test_otel_configuration_creates_providers(
        self, mock_metric_exporter, mock_span_exporter, mock_set_meter, mock_set_tracer
    ):
        """Test OpenTelemetry providers are created and configured."""
        _configure_opentelemetry("test-service", "http://otel:4318")

        # Verify trace exporter configured
        mock_span_exporter.assert_called_once_with(endpoint="http://otel:4318/v1/traces")
        mock_set_tracer.assert_called_once()

        # Verify metric exporter configured
        mock_metric_exporter.assert_called_once_with(endpoint="http://otel:4318/v1/metrics")
        mock_set_meter.assert_called_once()

    @patch("certus_integrity.telemetry.trace.set_tracer_provider")
    @patch("certus_integrity.telemetry.metrics.set_meter_provider")
    @patch("certus_integrity.telemetry.OTLPSpanExporter")
    @patch("certus_integrity.telemetry.OTLPMetricExporter")
    @patch("certus_integrity.telemetry.Resource")
    def test_otel_configuration_sets_service_name(
        self, mock_resource, mock_metric_exporter, mock_span_exporter, mock_set_meter, mock_set_tracer
    ):
        """Test service name is set in resource attributes."""
        _configure_opentelemetry("my-service", "http://otel:4318")

        # Verify Resource called with service name
        mock_resource.assert_called_once()
        call_kwargs = mock_resource.call_args[1]
        assert "attributes" in call_kwargs
        assert call_kwargs["attributes"]["service.name"] == "my-service"


class TestLoggingConfiguration:
    """Test structlog configuration."""

    @patch("certus_integrity.telemetry.structlog.configure")
    def test_logging_json_output_enabled(self, mock_configure):
        """Test JSON logging configuration."""
        _configure_logging("INFO", json_output=True)

        # Verify structlog configured
        mock_configure.assert_called_once()

        # Check that processors include JSONRenderer
        call_kwargs = mock_configure.call_args[1]
        processors = call_kwargs["processors"]

        # Should have JSONRenderer
        processor_names = [type(p).__name__ for p in processors]
        assert "JSONRenderer" in processor_names

    @patch("certus_integrity.telemetry.structlog.configure")
    def test_logging_console_output(self, mock_configure):
        """Test console logging configuration."""
        _configure_logging("DEBUG", json_output=False)

        mock_configure.assert_called_once()

        # Check that processors include ConsoleRenderer
        call_kwargs = mock_configure.call_args[1]
        processors = call_kwargs["processors"]

        # Should have ConsoleRenderer
        processor_names = [type(p).__name__ for p in processors]
        assert "ConsoleRenderer" in processor_names

    @patch("certus_integrity.telemetry.structlog.configure")
    def test_logging_level_configuration(self, mock_configure):
        """Test log level is configured correctly."""
        for level in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            mock_configure.reset_mock()
            _configure_logging(level, json_output=True)
            assert mock_configure.called


class TestFullObservabilityConfiguration:
    """Test end-to-end observability configuration."""

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_configure_observability_full_chain(self, mock_logging, mock_otel, mock_instrumentor):
        """Test full observability configuration chain."""
        app = FastAPI()

        configure_observability(
            app, service_name="test-service", log_level="INFO", enable_json_logs=True, otel_endpoint="http://otel:4318"
        )

        # Verify all components configured
        mock_otel.assert_called_once_with("test-service", "http://otel:4318")
        mock_instrumentor.instrument_app.assert_called_once_with(app)
        mock_logging.assert_called_once_with("INFO", True)

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_configure_observability_adds_middleware(self, mock_logging, mock_otel, mock_instrumentor):
        """Test IntegrityMiddleware is added to app."""
        app = FastAPI()

        configure_observability(app, service_name="test-service")

        # Verify middleware was added
        # Check app.user_middleware for IntegrityMiddleware
        middleware_names = [m.cls.__name__ for m in app.user_middleware]
        assert "IntegrityMiddleware" in middleware_names

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    @patch("certus_integrity.telemetry.structlog.get_logger")
    def test_configure_observability_logs_success(self, mock_get_logger, mock_logging, mock_otel, mock_instrumentor):
        """Test success message is logged."""
        app = FastAPI()
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger

        configure_observability(app, service_name="test-service")

        # Verify success logged
        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args
        assert call_args[0][0] == "observability_configured"


class TestTelemetryErrorHandling:
    """Test error handling in telemetry setup."""

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_otel_initialization_failure_handled(self, mock_logging, mock_otel, mock_instrumentor):
        """Test OpenTelemetry initialization failure is handled gracefully."""
        app = FastAPI()

        # Make OTel initialization fail
        mock_otel.side_effect = Exception("OTel connection failed")

        # Should raise exception (fail fast for telemetry issues)
        with pytest.raises(Exception, match="OTel connection failed"):
            configure_observability(app, service_name="test-service")

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_logging_initialization_failure_handled(self, mock_logging, mock_otel, mock_instrumentor):
        """Test logging initialization failure is handled."""
        app = FastAPI()

        # Make logging initialization fail
        mock_logging.side_effect = Exception("Logging config failed")

        # Should raise exception
        with pytest.raises(Exception, match="Logging config failed"):
            configure_observability(app, service_name="test-service")


class TestFastAPIInstrumentation:
    """Test FastAPI instrumentation."""

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_fastapi_instrumentation_called(self, mock_logging, mock_otel, mock_instrumentor):
        """Test FastAPI is instrumented."""
        app = FastAPI()

        configure_observability(app, service_name="test-service")

        # Verify instrumentation
        mock_instrumentor.instrument_app.assert_called_once_with(app)

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_fastapi_instrumentation_failure(self, mock_logging, mock_otel, mock_instrumentor):
        """Test FastAPI instrumentation failure handling."""
        app = FastAPI()

        # Make instrumentation fail
        mock_instrumentor.instrument_app.side_effect = Exception("Instrumentation failed")

        # Should raise exception
        with pytest.raises(Exception, match="Instrumentation failed"):
            configure_observability(app, service_name="test-service")
