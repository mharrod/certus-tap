"""Main FastAPI application factory for Ask Certus Backend."""

import sys

import structlog
from fastapi import FastAPI

from certus_ask.core.config import get_settings
from certus_ask.core.config_validation import ConfigurationValidator
from certus_ask.core.logging import configure_logging


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Sets up:
    - Configuration validation at startup (fail-fast)
    - Structured logging to console and OpenSearch
    - Request/response logging middleware
    - All API routers

    Returns:
        Configured FastAPI application instance

    Raises:
        SystemExit: If critical configuration is missing or invalid.
    """
    # Validate configuration before doing anything else
    ConfigurationValidator.fail_fast(env_path=".env")

    settings = get_settings()

    # Configure Logging and Telemetry via Chassis
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    from certus_ask.core.async_opensearch_handler import AsyncOpenSearchHandler
    from certus_integrity.middleware import IntegrityMiddleware

    # Create OpenSearch handler if enabled
    opensearch_handler = None
    if settings.send_logs_to_opensearch and not settings.disable_opensearch_logging:
        print(
            f"[STARTUP] Creating OpenSearch logging handler: host={settings.opensearch_log_host}:{settings.opensearch_log_port}",
            file=sys.stderr,
            flush=True,
        )
        opensearch_handler = AsyncOpenSearchHandler(
            hosts=[{"host": settings.opensearch_log_host, "port": settings.opensearch_log_port}],
            index_name="logs-certus-tap",
            username=settings.opensearch_log_username,
            password=settings.opensearch_log_password,
        )
        print(
            f"[STARTUP] OpenSearch handler created: available={opensearch_handler.is_available if opensearch_handler else False}",
            file=sys.stderr,
            flush=True,
        )
    else:
        print(
            f"[STARTUP] OpenSearch logging disabled: send_logs={settings.send_logs_to_opensearch}, disable={settings.disable_opensearch_logging}",
            file=sys.stderr,
            flush=True,
        )

    # Configure logging using the application's native logging module
    configure_logging(
        level=settings.log_level,
        json_output=settings.log_json_output,
        opensearch_handler=opensearch_handler,
    )

    # Create FastAPI application with comprehensive metadata
    app = FastAPI(
        title="Certus-TAP Backend API",
        version="0.1.0",
        description="A production-grade document processing and RAG (Retrieval-Augmented Generation) system with privacy-first design, structured logging, and comprehensive error handling.",
        contact={
            "name": "Certus-TAP Team",
            "url": "https://github.com/mharrod/certus-TAP",
            "email": "martin.harrod@gmail.com",
        },
        license_info={
            "name": "License information",
            "url": "https://github.com/mharrod/certus-TAP/blob/main/LICENSE",
        },
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        openapi_tags=[
            {
                "name": "ingestion",
                "description": "Document ingestion endpoints for uploading and indexing documents from various sources (files, folders, GitHub, SARIF, web)",
            },
            {
                "name": "query",
                "description": "RAG query endpoints for searching indexed documents and retrieving answers using the LLM",
            },
            {
                "name": "datalake",
                "description": "S3 datalake management endpoints for uploading, listing, preprocessing, and ingesting documents",
            },
            {
                "name": "evaluation",
                "description": "LLM evaluation endpoints for generating test cases and evaluating model performance",
            },
            {
                "name": "health",
                "description": "Health check endpoints for monitoring service status and dependencies",
            },
        ],
    )

    # Configure Telemetry (Traces and Metrics)
    from certus_integrity.telemetry import _configure_opentelemetry

    _configure_opentelemetry(
        service_name="certus-ask",
        endpoint=settings.otel_exporter_otlp_endpoint
        if hasattr(settings, "otel_exporter_otlp_endpoint")
        else "http://otel-collector:4318",
    )

    # Instrument FastAPI for OpenTelemetry
    FastAPIInstrumentor.instrument_app(app)

    # Add Integrity Middleware for security context
    app.add_middleware(IntegrityMiddleware)

    # Logging can now be used
    logger = structlog.get_logger(__name__)
    logger.info(
        "app.startup",
        log_level=settings.log_level,
        json_output=settings.log_json_output,
    )

    # Log available features at startup
    from certus_ask.core.features import Features

    Features.log_feature_summary()

    from certus_ask.core.middleware import TraceIDMiddleware
    from certus_ask.middleware.logging import RequestLoggingMiddleware

    # Add middleware (order matters - added in reverse execution order)
    # Trace ID middleware must be added first (executes last) to wrap all other middleware
    # Note: IntegrityMiddleware is already added by configure_observability
    app.add_middleware(TraceIDMiddleware)
    # Request logging middleware executes before route handlers
    app.add_middleware(RequestLoggingMiddleware)

    # Include routers (core routers always available)
    from certus_ask.routers import health, ingestion, query

    app.include_router(health.router)
    app.include_router(ingestion.router)
    app.include_router(query.router)

    # Conditionally include optional feature routers
    if Features.DATALAKE():
        from certus_ask.routers import datalake

        app.include_router(datalake.router)
    else:
        logger.warning(
            "datalake_router_disabled",
            reason="Missing document processing dependencies",
            install_command=Features.install_command("documents"),
        )

    if Features.EVALUATION():
        from certus_ask.routers import evaluation

        app.include_router(evaluation.router)
    else:
        logger.warning(
            "evaluation_router_disabled",
            reason="Missing evaluation dependencies",
            install_command=Features.install_command("eval"),
        )

    return app


# Only create app at module level if not in test environment
# This allows tests and utility scripts to import without triggering app initialization
import os

if "pytest" not in sys.modules and not os.getenv("SKIP_APP_CREATION"):
    app = create_app()
