"""
Certus Integrity Telemetry Chassis.

This module acts as the "One Stop Shop" for configuring observability and integrity
for any Certus service. It handles:
1. OpenTelemetry Setup (Traces, Metrics)
2. FastAPI Instrumentation
3. Logging Configuration (Structlog)
4. Integrity Middleware Injection
"""

import logging

import structlog
from fastapi import FastAPI
from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from certus_integrity.middleware import IntegrityMiddleware


def configure_observability(
    app: FastAPI,
    service_name: str,
    log_level: str = "INFO",
    enable_json_logs: bool = True,
    otel_endpoint: str = "http://otel-collector:4318",
) -> None:
    """
    Configure the full observability stack for a FastAPI application.
    """
    # 1. Configure OpenTelemetry
    _configure_opentelemetry(service_name, otel_endpoint)

    # 2. Instrument FastAPI
    FastAPIInstrumentor.instrument_app(app)

    # 3. Configure Logging
    _configure_logging(log_level, enable_json_logs)

    # 4. Add Integrity Middleware
    app.add_middleware(IntegrityMiddleware)

    logger = structlog.get_logger(__name__)
    logger.info("observability_configured", service=service_name, endpoint=otel_endpoint)


def _configure_opentelemetry(service_name: str, endpoint: str):
    """Sets up the OTel TracerProvider and MeterProvider."""
    resource = Resource(
        attributes={
            SERVICE_NAME: service_name,
        }
    )

    # 1. Tracing
    trace_provider = TracerProvider(resource=resource)
    otlp_trace_exporter = OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces")
    trace_provider.add_span_processor(BatchSpanProcessor(otlp_trace_exporter))
    trace.set_tracer_provider(trace_provider)

    # 2. Metrics
    # Note: OTLP endpoint for metrics usually ends in /v1/metrics
    otlp_metric_exporter = OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics")
    metric_reader = PeriodicExportingMetricReader(otlp_metric_exporter)
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)


def _configure_logging(level: str, json_output: bool):
    """Configures structlog."""
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level)),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
