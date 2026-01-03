"""Main FastAPI application for Certus-Trust service."""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.models import ErrorResponse
from .api.router import router as trust_router
from .config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager."""
    logger.info("Certus-Trust service starting...")

    # Initialize settings
    settings = get_settings()
    app.state.settings = settings

    # Initialize Sigstore clients if in production mode
    if not settings.mock_sigstore:
        from .clients import RekorClient, SigningClient

        logger.info("Initializing production Sigstore clients...")
        app.state.rekor_client = RekorClient(settings)
        app.state.signing_client = SigningClient(settings)
        logger.info("✓ Production Sigstore clients initialized")
    else:
        logger.info("Running in MOCK mode (set CERTUS_TRUST_MOCK_SIGSTORE=false for production)")
        app.state.rekor_client = None
        app.state.signing_client = None

    yield

    logger.info("Certus-Trust service shutting down...")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Certus-Trust",
        description="Supply chain integrity service using Sigstore stack",
        version="0.1.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ========================================================================
    # Middleware Configuration
    # ========================================================================

    # CORS middleware - allow all origins for development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        """Add request ID to all requests for tracing."""
        import uuid

        request.state.request_id = str(uuid.uuid4())
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    # ========================================================================
    # Exception Handlers
    # ========================================================================

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions."""
        request_id = getattr(request.state, "request_id", "unknown")

        logger.error(
            f"Unhandled exception: {exc!s}",
            extra={
                "request_id": request_id,
                "path": request.url.path,
                "method": request.method,
            },
        )

        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error="internal_server_error",
                message="An unexpected error occurred",
                timestamp=datetime.now(timezone.utc),
                request_id=request_id,
            ).model_dump(),
        )

    # ========================================================================
    # Routes
    # ========================================================================

    # Include API router
    app.include_router(trust_router, prefix="", tags=["trust"])

    # Root endpoint
    @app.get("/", tags=["info"])
    async def root():
        """Service root endpoint."""
        return {
            "service": "Certus-Trust",
            "version": "0.1.0",
            "description": "Supply chain integrity service using Sigstore",
            "docs_url": "/docs",
            "health_url": "/v1/health",
            "ready_url": "/v1/ready",
        }

    # ========================================================================
    # Startup/Shutdown Events
    # ========================================================================

    @app.on_event("startup")
    async def startup_event():
        """Initialize on startup."""
        logger.info(f"Environment: {settings.environment}")
        logger.info(f"Log level: {settings.log_level}")
        logger.info(f"Host: {settings.host}:{settings.port}")

        if settings.enable_keyless:
            logger.info("Keyless signing enabled")
        if settings.enable_transparency:
            logger.info("Transparency log enabled")

        logger.info("Certus-Trust service ready")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Cleanup on shutdown."""
        logger.info("Certus-Trust service stopped")

    return app


# Create app instance
app = create_app()

if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "certus_trust.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
