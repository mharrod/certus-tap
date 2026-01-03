"""OpenTelemetry initialization and configuration."""

import os

import structlog
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = structlog.get_logger(__name__)


def configure_opentelemetry(app_name: str = "certus-ask") -> None:
    """
    Configure OpenTelemetry tracing and metrics.

    This sets up:
    - TracerProvider with OTLP exporter
    - MeterProvider with OTLP exporter
    - Resource attributes for service identification
    - Batch span processing for efficient export

    Args:
        app_name: The service name to use in telemetry data
    """
    # Get OTLP endpoint from environment
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318")

    # Create resource with service name
    resource = Resource.create({
        "service.name": app_name,
        "service.version": "0.1.0",
    })

    # Configure tracing
    trace_provider = TracerProvider(resource=resource)
    otlp_span_exporter = OTLPSpanExporter(
        endpoint=f"{otlp_endpoint}/v1/traces",
    )
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))
    trace.set_tracer_provider(trace_provider)

    # Configure metrics
    otlp_metric_exporter = OTLPMetricExporter(
        endpoint=f"{otlp_endpoint}/v1/metrics",
    )
    metric_reader = PeriodicExportingMetricReader(
        otlp_metric_exporter,
        export_interval_millis=5000,  # Export every 5 seconds
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)

    logger.info(
        "observability_configured",
        service=app_name,
        endpoint=otlp_endpoint,
    )


def instrument_fastapi(app) -> None:
    """
    Instrument FastAPI application with OpenTelemetry.

    This adds automatic tracing for all HTTP requests.

    Args:
        app: The FastAPI application instance
    """
    FastAPIInstrumentor.instrument_app(app)
    logger.info("fastapi_instrumented")
