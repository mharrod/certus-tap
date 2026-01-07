# Certus-Evaluate Implementation Guide

> Practical implementation guide for building certus-evaluate as a hybrid Python module + optional FastAPI service, starting with RAGAS evaluation only. **Aligned with Certus architectural patterns.**

## Metadata

- **Type**: Implementation Guide
- **Status**: Ready for Implementation
- **Author**: Certus TAP (AI agent for @harma)
- **Created**: 2025-12-28
- **Last Updated**: 2025-12-28
- **Target Version**: v0.1.0 (MVP)
- **Implementation Timeline**: 8-10 weeks (3 phases)
- **Related**:
  - [certus-evaluate-service.md](./certus-evaluate-service.md) (original proposal)
  - [certus-evaluate-dataset-guide.md](./certus-evaluate-dataset-guide.md) (dataset creation guide)
- **ADRs**: ADR-EVAL-001 through ADR-EVAL-004 (to be created)

## Executive Summary

This guide provides a **simplified, phased approach** to implementing certus-evaluate:

1. **Start with evaluation only** (no guardrails initially)
2. **Use RAGAS framework only** (no DeepEval in Phase 1)
3. **Build as hybrid module/service** (flexible deployment)
4. **Shadow mode first** (prove architecture before enforcement)
5. **Follow Certus patterns** (structured logging, fail-fast config, semantic exceptions)

**Key Simplifications from Original Proposal**:

- ✅ RAGAS only (not RAGAS + DeepEval)
- ✅ Evaluation only (guardrails deferred to Phase 4+)
- ✅ Module-first, service-optional (simpler initial deployment)
- ✅ 4 core metrics only (not 10+)
- ✅ **Certus-aligned patterns** (structlog, CertusException, StandardResponse)
- ✅ 8-10 weeks instead of 6-8 weeks (proper time for Certus patterns)

## Goals & Non-Goals

### Phase 1-3 Goals

- [ ] Build Python module `certus_evaluate` with RAGAS integration
- [ ] Implement 4 core metrics: faithfulness, answer_relevancy, context_precision, context_recall
- [ ] Support both local (in-process) and remote (HTTP) execution strategies
- [ ] Integrate with MLflow for experiment tracking
- [ ] Add OpenTelemetry spans for observability
- [ ] **Follow Certus exception hierarchy** (inherit from CertusException)
- [ ] **Use structured logging** (structlog with JSON output)
- [ ] **Implement fail-fast configuration validation**
- [ ] **Add request context propagation** (trace_id in ContextVar)
- [ ] **Wrap responses in StandardResponse**
- [ ] Provide CLI for benchmarking/testing
- [ ] Shadow-mode integration with Certus-Ask (non-blocking, optional)
- [ ] Optional FastAPI service wrapper for remote execution

### Explicitly Deferred (Post-Phase 3)

- ❌ DeepEval integration (add in Phase 4 if needed)
- ❌ Guardrails (PII, prompt injection, etc.) - separate proposal
- ❌ Integrity/Trust signing (add in Phase 4)
- ❌ Manifest-driven thresholds (add in Phase 4)
- ❌ Enforcement mode (shadow only in Phase 1-3)

### Success Criteria

| Criterion              | Measurement                                                 |
| ---------------------- | ----------------------------------------------------------- |
| **Module installable** | `pip install certus-evaluate` works in Certus-Ask           |
| **Zero blocking**      | Certus-Ask latency unchanged when evaluation fails          |
| **Shadow coverage**    | 100% of Ask responses attempt evaluation (non-blocking)     |
| **Baseline metrics**   | MLflow dashboard shows evaluation scores for all workspaces |
| **Service optional**   | Can run locally OR as service, same code                    |
| **Certus patterns**    | Follows all Certus architectural patterns                   |

## Architecture

### Hybrid Deployment Model

```
┌─────────────────────────────────────────────────┐
│         DEPLOYMENT OPTIONS                       │
├─────────────────────────────────────────────────┤
│                                                  │
│  Option A: Local (In-Process)                   │
│  ┌──────────────────────────────┐               │
│  │     Certus-Ask               │               │
│  │  ┌────────────────────────┐  │               │
│  │  │ certus_evaluate (lib)  │  │               │
│  │  │  - RAGAS evaluator     │  │               │
│  │  │  - MLflow logger       │  │               │
│  │  └────────────────────────┘  │               │
│  └──────────────────────────────┘               │
│                                                  │
│  Option B: Remote (Service)                     │
│  ┌────────────┐      ┌───────────────────┐     │
│  │ Certus-Ask │─────▶│ certus-evaluate   │     │
│  │            │ HTTP │ (FastAPI service) │     │
│  └────────────┘      └───────────────────┘     │
│                                                  │
│  Option C: Hybrid                                │
│  ┌──────────────────────────────┐               │
│  │     Certus-Ask               │               │
│  │  ┌────────────────────────┐  │               │
│  │  │  Hybrid Strategy:      │  │──┐            │
│  │  │  1. Try local (1s)     │  │  │ If timeout │
│  │  │  2. Fallback to remote │◀─┘  │ or error   │
│  │  └────────────────────────┘  │               │
│  └──────────────────────────────┘               │
└─────────────────────────────────────────────────┘
```

### Package Structure

```
certus-evaluate/
├── pyproject.toml              # Project metadata, dependencies
├── README.md                   # Installation and usage docs
├── .env.example                # Example configuration
├── docker-compose.yml          # For service deployment
├── Dockerfile                  # FastAPI service image
├── docs/
│   └── architecture/
│       └── decisions/          # ADR documents
│           ├── ADR-EVAL-001-ragas-over-deepeval.md
│           ├── ADR-EVAL-002-hybrid-execution-strategy.md
│           ├── ADR-EVAL-003-shadow-mode-first.md
│           └── ADR-EVAL-004-reference-dataset-governance.md
│
├── src/certus_evaluate/
│   ├── __init__.py            # Package exports
│   ├── version.py             # Version info
│   │
│   ├── core/                  # Core evaluation logic
│   │   ├── __init__.py
│   │   ├── models.py          # Data models (EvaluationResult, etc.)
│   │   ├── evaluator.py       # Base Evaluator interface
│   │   ├── ragas.py           # RAGAS implementation
│   │   ├── exceptions.py      # Custom exceptions (Certus hierarchy)
│   │   ├── logging.py         # Structured logging setup
│   │   ├── config.py          # Configuration (Pydantic Settings)
│   │   ├── config_validation.py  # Fail-fast validation
│   │   ├── request_context.py # Request ID propagation
│   │   └── reference_loader.py # Reference dataset loader
│   │
│   ├── schemas/               # Request/Response models
│   │   ├── __init__.py
│   │   ├── requests.py        # EvaluationRequest
│   │   └── responses.py       # StandardResponse wrapper
│   │
│   ├── strategies/            # Execution strategies
│   │   ├── __init__.py
│   │   ├── local.py           # In-process execution
│   │   ├── remote.py          # HTTP client (with retry)
│   │   └── hybrid.py          # Local-first with remote fallback
│   │
│   ├── observability/         # Logging, metrics, tracing
│   │   ├── __init__.py
│   │   ├── mlflow_logger.py   # MLflow integration (with retry)
│   │   ├── tracing.py         # OpenTelemetry spans
│   │   └── cache.py           # Evaluation cache (Phase 2)
│   │
│   ├── middleware/            # FastAPI middleware
│   │   ├── __init__.py
│   │   ├── trace_id.py        # TraceIDMiddleware
│   │   └── logging.py         # RequestLoggingMiddleware
│   │
│   └── service/               # Optional FastAPI service
│       ├── __init__.py
│       ├── main.py            # FastAPI app
│       ├── api.py             # REST endpoints
│       └── health.py          # Health checks
│
├── cli/                       # CLI commands
│   ├── __init__.py
│   ├── main.py                # CLI entry point (typer)
│   ├── benchmark.py           # Benchmark command
│   └── test.py                # Test command
│
└── tests/
    ├── unit/
    │   ├── core/
    │   │   ├── test_models.py
    │   │   ├── test_exceptions.py
    │   │   ├── test_ragas_evaluator.py
    │   │   └── test_config_validation.py
    │   └── strategies/
    │       ├── test_local_strategy.py
    │       ├── test_remote_strategy.py
    │       └── test_hybrid_strategy.py
    ├── integration/
    │   ├── test_mlflow_integration.py
    │   ├── test_ragas_integration.py
    │   └── test_cache_integration.py
    ├── smoke/
    │   ├── test_health.py
    │   └── test_api_basic.py
    ├── contract/
    │   ├── test_evaluation_request_schema.py
    │   └── test_evaluation_result_schema.py
    └── fixtures/
        ├── sample_qa_pairs.jsonl
        └── reference_dataset.jsonl
```

## Reference Dataset Requirements

Evaluation with RAGAS requires curated reference datasets with human-approved responses and vetted context. These datasets provide ground truth for metrics like context_precision and context_recall.

**For complete dataset creation workflow and tooling recommendations, see**:
→ **[Reference Dataset Creation Guide](./certus-evaluate-dataset-guide.md)**

The dataset guide covers:

- Understanding LLM-as-Judge evaluation mechanics
- Complete dataset lifecycle (sample → annotate → vet → approve)
- Tooling recommendations (Google Sheets → Label Studio → Custom webapp)
- Cost analysis and optimization strategies
- Governance and maintenance procedures
- Quality metrics and monitoring

**Implementation Timeline**:

- **Phase 1 Week 2**: Create initial datasets for 2 workspaces (100 entries total)
  - Engineering: 3-4 days (reference loader implementation)
  - Product/SME: 5-6 days (annotation, following dataset guide)
  - **Total: 8-10 days (parallelizable with engineering work)**

## Data Models

### Core Models (Phase 1)

```python
# src/certus_evaluate/core/models.py

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Literal
from datetime import datetime, timezone
from uuid import UUID, uuid4
import hashlib

class MetricScore(BaseModel):
    """Individual metric score with metadata"""
    name: Literal["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    value: float = Field(ge=0.0, le=1.0, description="Score normalized to 0-1")
    framework: Literal["ragas"] = "ragas"
    error: Optional[str] = Field(default=None, description="Error if metric failed to compute")

    model_config = ConfigDict(frozen=True)  # Immutable


class ReferenceEntry(BaseModel):
    """Ground-truth reference for evaluation"""

    query_signature: str = Field(description="Normalized/hashed query for lookup")
    ideal_response: str = Field(description="Human-approved ideal response")
    vetted_context: List[str] = Field(description="Verified context chunks")

    # Governance metadata
    workspace_id: str
    approved_by: str = Field(description="Email or ID of approver")
    approved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = Field(default=1, description="Version number for updates")

    # Optional metadata
    tags: List[str] = Field(default_factory=list, description="Tags for categorization")
    notes: Optional[str] = Field(default=None, description="Internal notes")

    model_config = ConfigDict(frozen=True)
```

### Request/Response Schemas

```python
# src/certus_evaluate/schemas/requests.py

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Literal

class EvaluationRequest(BaseModel):
    """Request to evaluate a RAG response"""

    # Required fields
    workspace_id: str = Field(min_length=1, max_length=255)
    query: str = Field(min_length=1, max_length=10000)
    response: str = Field(min_length=1, max_length=50000)
    context: List[str] = Field(description="Retrieved context chunks", max_length=50)

    # Optional fields
    timeout_ms: Optional[int] = Field(default=5000, ge=100, le=30000)
    trace_id: Optional[str] = Field(default=None, description="Tracing context from caller")

    # Which metrics to compute (default: all 4)
    metrics: List[Literal["faithfulness", "answer_relevancy", "context_precision", "context_recall"]] = Field(
        default=["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "workspace_id": "acme",
                "query": "What is Certus?",
                "response": "Certus is a trust automation platform...",
                "context": ["Certus TAP provides...", "The framework includes..."],
                "timeout_ms": 5000,
                "trace_id": "trace_abc123",
                "metrics": ["faithfulness", "answer_relevancy"]
            }
        }
    )


# src/certus_evaluate/schemas/responses.py

from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Optional, List
from datetime import datetime, timezone
from uuid import UUID

T = TypeVar('T')

class ErrorDetail(BaseModel):
    """Error details following Certus pattern"""
    code: str = Field(description="Error code (e.g., 'evaluation_timeout')")
    message: str = Field(description="Human-readable error message")
    context: Optional[dict] = Field(default=None, description="Additional error context")


class StandardResponse(BaseModel, Generic[T]):
    """
    Standard response wrapper for all API endpoints.

    Follows Certus pattern from certus_ask/schemas/responses.py
    """
    status: Literal["success", "error"]
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    trace_id: str

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "success",
                "data": {"evaluation_id": "550e8400-..."},
                "error": None,
                "timestamp": "2025-12-28T10:30:00Z",
                "trace_id": "trace_abc123"
            }
        }
    )


class EvaluationResult(BaseModel):
    """Result of an evaluation"""

    # Identifiers
    evaluation_id: UUID = Field(default_factory=uuid4)
    workspace_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Scores
    metrics: List[MetricScore] = Field(default_factory=list)
    overall_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Weighted average of metric scores"
    )

    # Metadata
    processing_time_ms: int = Field(ge=0)
    skipped: bool = Field(default=False, description="Was evaluation skipped?")
    skip_reason: Optional[str] = Field(default=None)

    # Observability
    mlflow_run_id: Optional[str] = Field(default=None)
    trace_id: Optional[str] = Field(default=None)

    # Content hashes (for future integrity integration)
    query_hash: str = Field(description="SHA-256 hash of query")
    response_hash: str = Field(description="SHA-256 hash of response")
    context_hashes: List[str] = Field(description="SHA-256 hashes of context chunks")

    @staticmethod
    def hash_content(content: str) -> str:
        """Generate SHA-256 hash with 'sha256:' prefix"""
        import hashlib
        return f"sha256:{hashlib.sha256(content.encode()).hexdigest()}"

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
                "workspace_id": "acme",
                "timestamp": "2025-12-28T10:30:00Z",
                "metrics": [
                    {"name": "faithfulness", "value": 0.85, "framework": "ragas", "error": None},
                    {"name": "answer_relevancy", "value": 0.78, "framework": "ragas", "error": None}
                ],
                "overall_score": 0.82,
                "processing_time_ms": 1847,
                "skipped": False,
                "mlflow_run_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "trace_id": "trace_abc123",
                "query_hash": "sha256:7d8e2a3f...",
                "response_hash": "sha256:3c7e1a4c...",
                "context_hashes": ["sha256:1a2b3c4d...", "sha256:2b3c4d5e..."]
            }
        }
    )
```

## Exception Hierarchy (Certus Pattern)

```python
# src/certus_evaluate/core/exceptions.py

from typing import Any, Optional

class CertusException(Exception):
    """
    Base exception for Certus services.

    Follows Certus pattern from certus_ask/core/exceptions.py
    All custom exceptions should inherit from this.
    """

    def __init__(
        self,
        message: str,
        error_code: str,
        details: Optional[dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)


# Evaluation Errors

class EvaluationError(CertusException):
    """Base exception for evaluation errors"""

    def __init__(
        self,
        message: str = "Evaluation failed",
        error_code: str = "evaluation_error",
        details: Optional[dict[str, Any]] = None
    ):
        super().__init__(message=message, error_code=error_code, details=details)


class EvaluationTimeoutError(EvaluationError):
    """Raised when evaluation times out"""

    def __init__(
        self,
        message: str = "Evaluation timed out",
        timeout_ms: Optional[int] = None,
        details: Optional[dict[str, Any]] = None
    ):
        _details = details or {}
        if timeout_ms:
            _details["timeout_ms"] = timeout_ms
        super().__init__(
            message=message,
            error_code="evaluation_timeout",
            details=_details
        )


class EvaluationServiceError(EvaluationError):
    """Raised when remote service is unavailable"""

    def __init__(
        self,
        message: str = "Evaluation service unavailable",
        service_url: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        _details = details or {}
        if service_url:
            _details["service_url"] = service_url
        super().__init__(
            message=message,
            error_code="evaluation_service_unavailable",
            details=_details
        )


class ReferenceDataMissingError(EvaluationError):
    """Raised when no reference data exists for workspace/query"""

    def __init__(
        self,
        message: str = "No reference data found",
        workspace_id: Optional[str] = None,
        query: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        _details = details or {}
        if workspace_id:
            _details["workspace_id"] = workspace_id
        if query:
            _details["query_preview"] = query[:100]
        super().__init__(
            message=message,
            error_code="reference_data_missing",
            details=_details
        )


class LLMProviderError(EvaluationError):
    """Raised when LLM provider API fails"""

    def __init__(
        self,
        message: str = "LLM provider API error",
        provider: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        _details = details or {}
        if provider:
            _details["provider"] = provider
        super().__init__(
            message=message,
            error_code="llm_provider_error",
            details=_details
        )


class MetricComputationError(EvaluationError):
    """Raised when individual metric computation fails"""

    def __init__(
        self,
        message: str = "Metric computation failed",
        metric_name: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        _details = details or {}
        if metric_name:
            _details["metric_name"] = metric_name
        super().__init__(
            message=message,
            error_code="metric_computation_error",
            details=_details
        )


# Configuration Errors

class ConfigurationError(CertusException):
    """Raised when configuration is invalid"""

    def __init__(
        self,
        message: str = "Invalid configuration",
        config_key: Optional[str] = None,
        details: Optional[dict[str, Any]] = None
    ):
        _details = details or {}
        if config_key:
            _details["config_key"] = config_key
        super().__init__(
            message=message,
            error_code="invalid_configuration",
            details=_details
        )
```

## Structured Logging (Certus Pattern)

```python
# src/certus_evaluate/core/logging.py

import structlog
import logging
import sys
from typing import Optional

def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    service_name: str = "certus-evaluate"
) -> None:
    """
    Configure structured logging with structlog.

    Follows Certus pattern from certus_ask/core/logging.py

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
        json_output: If True, output JSON; otherwise human-readable
        service_name: Service name to include in logs
    """

    # Configure stdlib logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper())
    )

    # Configure structlog processors
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    # Add service name to all logs
    processors.append(
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        )
    )

    # Renderer: JSON for production, console for development
    if json_output:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=True))

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Bind service name to all logs
    structlog.contextvars.bind_contextvars(service=service_name)

    logger = structlog.get_logger(__name__)
    logger.info(
        "logging.configured",
        log_level=level,
        json_output=json_output,
        service=service_name
    )


def get_logger(name: str) -> structlog.BoundLogger:
    """Get a structured logger instance"""
    return structlog.get_logger(name)
```

## Request Context (Certus Pattern)

```python
# src/certus_evaluate/core/request_context.py

from contextvars import ContextVar
from uuid import uuid4
from typing import Optional

_request_id_ctx_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)


def get_request_id() -> str:
    """
    Get or generate request ID for current request.

    Follows Certus pattern from certus_ask/core/request_context.py

    Returns:
        Request ID (UUID string)
    """
    request_id = _request_id_ctx_var.get()
    if request_id is None:
        request_id = str(uuid4())
        _request_id_ctx_var.set(request_id)
    return request_id


def set_request_id(request_id: str) -> None:
    """Set request ID for current context"""
    _request_id_ctx_var.set(request_id)


def clear_request_id() -> None:
    """Clear request ID from current context"""
    _request_id_ctx_var.set(None)
```

## Configuration with Fail-Fast Validation (Certus Pattern)

```python
# src/certus_evaluate/core/config.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Literal
from pydantic import Field, field_validator


class Settings(BaseSettings):
    """
    Configuration for certus-evaluate.

    Follows Certus pattern from certus_ask/core/config.py
    Load from environment variables or .env file.
    """

    # Execution strategy
    EVALUATE_STRATEGY: Literal["local", "remote", "hybrid"] = "local"
    EVALUATE_LOCAL_TIMEOUT_MS: int = Field(default=5000, ge=100, le=30000)
    EVALUATE_REQUEST_TIMEOUT_MS: int = Field(default=10000, ge=1000, le=60000)
    EVALUATE_SERVICE_URL: Optional[str] = None
    EVALUATE_API_KEY: Optional[str] = None

    # RAGAS configuration
    RAGAS_LLM_PROVIDER: Literal["openai", "anthropic", "azure"] = "openai"
    RAGAS_LLM_MODEL: str = "gpt-4"
    RAGAS_EMBEDDINGS_MODEL: str = "text-embedding-3-small"

    # API keys for LLM providers
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None

    # MLflow configuration
    MLFLOW_TRACKING_URI: str = "http://localhost:5000"
    MLFLOW_EXPERIMENT_PREFIX: str = "certus-evaluate"
    MLFLOW_LOG_FULL_CONTENT: bool = False

    # Caching configuration (Phase 2)
    CACHE_ENABLED: bool = False
    CACHE_BACKEND: Literal["redis", "memory"] = "redis"
    CACHE_REDIS_URL: Optional[str] = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = Field(default=86400, ge=60, le=604800)

    # OpenTelemetry configuration
    OTEL_ENABLED: bool = True
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_SERVICE_NAME: str = "certus-evaluate"

    # Logging
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    # Service configuration (for FastAPI service)
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = Field(default=8080, ge=1024, le=65535)
    SERVICE_WORKERS: int = Field(default=4, ge=1, le=32)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @field_validator("EVALUATE_SERVICE_URL")
    @classmethod
    def validate_service_url(cls, v: Optional[str], info) -> Optional[str]:
        """Validate service URL is provided for remote/hybrid strategies"""
        strategy = info.data.get("EVALUATE_STRATEGY")
        if strategy in ["remote", "hybrid"] and not v:
            raise ValueError(
                f"EVALUATE_SERVICE_URL required when EVALUATE_STRATEGY={strategy}"
            )
        return v


# Singleton settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get settings singleton (with caching)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# src/certus_evaluate/core/config_validation.py

import sys
from typing import List
from .config import get_settings, Settings
from .exceptions import ConfigurationError


class ConfigurationValidator:
    """
    Fail-fast configuration validator.

    Follows Certus pattern from certus_ask/core/config_validation.py
    """

    @staticmethod
    def fail_fast(env_path: str = ".env") -> None:
        """
        Validate configuration and exit immediately if invalid.

        Args:
            env_path: Path to .env file

        Raises:
            SystemExit: If configuration is invalid
        """
        errors: List[str] = []

        try:
            settings = get_settings()
        except Exception as e:
            print(f"❌ Configuration error: {e}", file=sys.stderr)
            sys.exit(1)

        # Validate LLM provider API keys
        if settings.RAGAS_LLM_PROVIDER == "openai" and not settings.OPENAI_API_KEY:
            errors.append("OPENAI_API_KEY required when RAGAS_LLM_PROVIDER=openai")

        if settings.RAGAS_LLM_PROVIDER == "anthropic" and not settings.ANTHROPIC_API_KEY:
            errors.append("ANTHROPIC_API_KEY required when RAGAS_LLM_PROVIDER=anthropic")

        if settings.RAGAS_LLM_PROVIDER == "azure":
            if not settings.AZURE_OPENAI_API_KEY:
                errors.append("AZURE_OPENAI_API_KEY required when RAGAS_LLM_PROVIDER=azure")
            if not settings.AZURE_OPENAI_ENDPOINT:
                errors.append("AZURE_OPENAI_ENDPOINT required when RAGAS_LLM_PROVIDER=azure")

        # Validate remote/hybrid strategy requirements
        if settings.EVALUATE_STRATEGY in ["remote", "hybrid"]:
            if not settings.EVALUATE_SERVICE_URL:
                errors.append(
                    f"EVALUATE_SERVICE_URL required when EVALUATE_STRATEGY={settings.EVALUATE_STRATEGY}"
                )

        # Validate cache configuration
        if settings.CACHE_ENABLED and settings.CACHE_BACKEND == "redis":
            if not settings.CACHE_REDIS_URL:
                errors.append("CACHE_REDIS_URL required when CACHE_ENABLED=true and CACHE_BACKEND=redis")

        # Report all errors at once
        if errors:
            print("❌ Configuration validation failed:", file=sys.stderr)
            print(f"   Found {len(errors)} error(s) in {env_path}:\n", file=sys.stderr)
            for i, error in enumerate(errors, 1):
                print(f"   {i}. {error}", file=sys.stderr)
            print("\nFix these errors and try again.", file=sys.stderr)
            sys.exit(1)

        # Success
        print("✅ Configuration validated successfully")
```

## Core Implementation

### 1. RAGAS Evaluator (with Structured Logging)

```python
# src/certus_evaluate/core/ragas.py

from typing import List, Optional
import asyncio
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall
)
from datasets import Dataset

from .logging import get_logger
from .models import MetricScore
from .request_context import get_request_id
from ..schemas.requests import EvaluationRequest
from ..schemas.responses import EvaluationResult
from .exceptions import (
    EvaluationTimeoutError,
    LLMProviderError,
    MetricComputationError
)
from .evaluator import BaseEvaluator

logger = get_logger(__name__)


class RAGASEvaluator(BaseEvaluator):
    """
    RAGAS-based evaluator for RAG responses.

    Computes 4 core metrics:
    - faithfulness: Is response grounded in context?
    - answer_relevancy: Does response answer the query?
    - context_precision: Were the right docs retrieved?
    - context_recall: Did we get all relevant docs?
    """

    METRIC_MAP = {
        "faithfulness": faithfulness,
        "answer_relevancy": answer_relevancy,
        "context_precision": context_precision,
        "context_recall": context_recall
    }

    def __init__(
        self,
        llm_provider: str = "openai",
        llm_model: str = "gpt-4",
        embeddings_model: str = "text-embedding-3-small",
        api_key: Optional[str] = None
    ):
        """
        Initialize RAGAS evaluator.

        Args:
            llm_provider: LLM provider (openai, anthropic, azure)
            llm_model: Model name for LLM-based metrics
            embeddings_model: Model name for embeddings
            api_key: API key (if None, read from environment)
        """
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.embeddings_model = embeddings_model
        self.api_key = api_key

        logger.info(
            "ragas.evaluator.initialized",
            llm_provider=llm_provider,
            llm_model=llm_model,
            embeddings_model=embeddings_model
        )

    async def evaluate(
        self,
        request: EvaluationRequest
    ) -> EvaluationResult:
        """
        Evaluate a RAG response.

        Args:
            request: EvaluationRequest with query, response, context

        Returns:
            EvaluationResult with scores

        Raises:
            EvaluationTimeoutError: If evaluation exceeds timeout
            LLMProviderError: If LLM API fails
            MetricComputationError: If metric computation fails
        """
        start_time = asyncio.get_event_loop().time()

        logger.info(
            "ragas.evaluate.start",
            workspace_id=request.workspace_id,
            metrics=request.metrics,
            timeout_ms=request.timeout_ms,
            trace_id=request.trace_id or get_request_id()
        )

        try:
            # Run evaluation with timeout
            result = await asyncio.wait_for(
                self._evaluate_internal(request),
                timeout=request.timeout_ms / 1000.0
            )

            processing_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            result.processing_time_ms = processing_time_ms

            logger.info(
                "ragas.evaluate.complete",
                workspace_id=request.workspace_id,
                overall_score=result.overall_score,
                processing_time_ms=processing_time_ms,
                trace_id=request.trace_id or get_request_id()
            )

            return result

        except asyncio.TimeoutError:
            processing_time_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)
            logger.warning(
                "ragas.evaluate.timeout",
                workspace_id=request.workspace_id,
                timeout_ms=request.timeout_ms,
                actual_time_ms=processing_time_ms,
                trace_id=request.trace_id or get_request_id()
            )
            raise EvaluationTimeoutError(
                message=f"Evaluation timed out after {request.timeout_ms}ms",
                timeout_ms=request.timeout_ms,
                details={
                    "workspace_id": request.workspace_id,
                    "actual_time_ms": processing_time_ms
                }
            )

    async def _evaluate_internal(
        self,
        request: EvaluationRequest
    ) -> EvaluationResult:
        """Internal evaluation logic (without timeout handling)"""

        # Prepare dataset for RAGAS
        dataset_dict = {
            "question": [request.query],
            "answer": [request.response],
            "contexts": [request.context],
            "ground_truth": [request.response]
        }
        dataset = Dataset.from_dict(dataset_dict)

        # Select metrics to compute
        metrics_to_compute = [
            self.METRIC_MAP[metric_name]
            for metric_name in request.metrics
            if metric_name in self.METRIC_MAP
        ]

        if not metrics_to_compute:
            logger.warning(
                "ragas.metrics.invalid",
                requested=request.metrics,
                using_all=True
            )
            metrics_to_compute = list(self.METRIC_MAP.values())

        # Run RAGAS evaluation (blocking, so run in thread pool)
        loop = asyncio.get_event_loop()

        try:
            ragas_result = await loop.run_in_executor(
                None,
                lambda: evaluate(dataset, metrics=metrics_to_compute)
            )
        except Exception as e:
            logger.error(
                "ragas.evaluation.failed",
                error=str(e),
                provider=self.llm_provider,
                trace_id=request.trace_id or get_request_id()
            )
            raise LLMProviderError(
                message=f"RAGAS evaluation failed: {str(e)}",
                provider=self.llm_provider,
                details={"original_error": str(e)}
            )

        # Extract scores
        metric_scores = []
        for metric_name in request.metrics:
            if metric_name in ragas_result:
                score = float(ragas_result[metric_name])
                metric_scores.append(
                    MetricScore(
                        name=metric_name,
                        value=score,
                        framework="ragas",
                        error=None
                    )
                )
                logger.debug(
                    "ragas.metric.computed",
                    metric=metric_name,
                    score=score
                )
            else:
                logger.warning(
                    "ragas.metric.missing",
                    metric=metric_name
                )
                metric_scores.append(
                    MetricScore(
                        name=metric_name,
                        value=0.0,
                        framework="ragas",
                        error=f"Metric not computed by RAGAS"
                    )
                )

        # Calculate overall score (simple average for now)
        valid_scores = [m.value for m in metric_scores if m.error is None]
        overall_score = sum(valid_scores) / len(valid_scores) if valid_scores else None

        # Generate content hashes
        query_hash = EvaluationResult.hash_content(request.query)
        response_hash = EvaluationResult.hash_content(request.response)
        context_hashes = [
            EvaluationResult.hash_content(chunk)
            for chunk in request.context
        ]

        return EvaluationResult(
            workspace_id=request.workspace_id,
            metrics=metric_scores,
            overall_score=overall_score,
            processing_time_ms=0,  # Will be set by caller
            skipped=False,
            trace_id=request.trace_id or get_request_id(),
            query_hash=query_hash,
            response_hash=response_hash,
            context_hashes=context_hashes
        )


# src/certus_evaluate/core/evaluator.py

from abc import ABC, abstractmethod
from ..schemas.requests import EvaluationRequest
from ..schemas.responses import EvaluationResult


class BaseEvaluator(ABC):
    """Base interface for evaluators"""

    @abstractmethod
    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """
        Evaluate a RAG response.

        Args:
            request: EvaluationRequest with query, response, context

        Returns:
            EvaluationResult with scores
        """
        pass
```

### 2. Remote Strategy with Retry (Certus Pattern)

```python
# src/certus_evaluate/strategies/remote.py

from typing import Optional
import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    RetryError
)

from ..core.logging import get_logger
from ..core.request_context import get_request_id
from ..schemas.requests import EvaluationRequest
from ..schemas.responses import EvaluationResult, StandardResponse
from ..core.exceptions import (
    EvaluationServiceError,
    EvaluationTimeoutError
)

logger = get_logger(__name__)


class RemoteStrategy:
    """
    Execute evaluation via HTTP call to remote service.

    Follows Certus pattern with retry logic (tenacity).
    """

    def __init__(
        self,
        base_url: str,
        api_key: Optional[str] = None,
        timeout_ms: int = 10000,
        max_retries: int = 3
    ):
        """
        Initialize remote strategy.

        Args:
            base_url: Base URL of certus-evaluate service
            api_key: API key for authentication
            timeout_ms: HTTP request timeout
            max_retries: Maximum retry attempts
        """
        self.base_url = base_url.rstrip('/')
        self.timeout_ms = timeout_ms
        self.max_retries = max_retries

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers,
            timeout=httpx.Timeout(timeout_ms / 1000.0)
        )

        logger.info(
            "remote.strategy.initialized",
            base_url=base_url,
            timeout_ms=timeout_ms,
            max_retries=max_retries
        )

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    async def evaluate(self, request: EvaluationRequest) -> EvaluationResult:
        """
        Call remote evaluation service with retry.

        Args:
            request: EvaluationRequest

        Returns:
            EvaluationResult

        Raises:
            EvaluationServiceError: If service is unavailable
            EvaluationTimeoutError: If request times out
        """
        logger.debug(
            "remote.evaluate.start",
            base_url=self.base_url,
            workspace_id=request.workspace_id,
            trace_id=request.trace_id or get_request_id()
        )

        try:
            response = await self.client.post(
                "/v1/evaluate",
                json=request.model_dump(mode='json')
            )
            response.raise_for_status()

            # Parse StandardResponse wrapper
            standard_response = StandardResponse[EvaluationResult](**response.json())

            if standard_response.status == "error":
                logger.error(
                    "remote.evaluate.error",
                    error_code=standard_response.error.code if standard_response.error else "unknown",
                    error_message=standard_response.error.message if standard_response.error else "Unknown error"
                )
                raise EvaluationServiceError(
                    message=standard_response.error.message if standard_response.error else "Remote service error",
                    service_url=self.base_url
                )

            logger.info(
                "remote.evaluate.success",
                workspace_id=request.workspace_id,
                trace_id=request.trace_id or get_request_id()
            )

            return standard_response.data

        except httpx.TimeoutException as e:
            logger.warning(
                "remote.evaluate.timeout",
                error=str(e),
                timeout_ms=self.timeout_ms
            )
            raise EvaluationTimeoutError(
                message=f"Remote service timeout: {e}",
                timeout_ms=self.timeout_ms,
                details={"service_url": self.base_url}
            )

        except httpx.HTTPStatusError as e:
            logger.error(
                "remote.evaluate.http_error",
                status_code=e.response.status_code,
                error=str(e)
            )
            raise EvaluationServiceError(
                message=f"Remote service error: HTTP {e.response.status_code}",
                service_url=self.base_url,
                details={"status_code": e.response.status_code}
            )

        except httpx.RequestError as e:
            logger.error(
                "remote.evaluate.request_error",
                error=str(e)
            )
            raise EvaluationServiceError(
                message=f"Remote service unavailable: {e}",
                service_url=self.base_url
            )

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()
        logger.debug("remote.client.closed")
```

### 3. MLflow Logger with Retry (Certus Pattern)

```python
# src/certus_evaluate/observability/mlflow_logger.py

from typing import Optional
import mlflow
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential
)

from ..core.logging import get_logger
from ..schemas.responses import EvaluationResult

logger = get_logger(__name__)


class MLflowLogger:
    """
    Logger for evaluation results to MLflow.

    Follows Certus pattern with retry logic.
    """

    def __init__(
        self,
        tracking_uri: str,
        experiment_prefix: str = "certus-evaluate"
    ):
        """
        Initialize MLflow logger.

        Args:
            tracking_uri: MLflow tracking server URI
            experiment_prefix: Prefix for experiment names
        """
        self.tracking_uri = tracking_uri
        self.experiment_prefix = experiment_prefix

        mlflow.set_tracking_uri(tracking_uri)
        logger.info(
            "mlflow.logger.initialized",
            tracking_uri=tracking_uri,
            experiment_prefix=experiment_prefix
        )

    @retry(
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True
    )
    def log_evaluation(
        self,
        result: EvaluationResult,
        query: Optional[str] = None,
        response: Optional[str] = None,
        context: Optional[list[str]] = None,
        log_full_content: bool = False
    ) -> str:
        """
        Log evaluation result to MLflow with retry.

        Args:
            result: EvaluationResult to log
            query: Original query (optional)
            response: Original response (optional)
            context: Original context (optional)
            log_full_content: If True, log full query/response (PII risk!)

        Returns:
            MLflow run ID
        """
        experiment_name = f"{self.experiment_prefix}-{result.workspace_id}"
        mlflow.set_experiment(experiment_name)

        timestamp = result.timestamp.strftime("%Y%m%d-%H%M%S")
        run_name = f"eval-{timestamp}-{str(result.evaluation_id)[:8]}"

        logger.debug(
            "mlflow.log.start",
            experiment=experiment_name,
            run_name=run_name,
            workspace_id=result.workspace_id
        )

        with mlflow.start_run(run_name=run_name) as run:

            # Log parameters
            mlflow.log_params({
                "workspace_id": result.workspace_id,
                "evaluation_id": str(result.evaluation_id),
                "skipped": result.skipped,
                "trace_id": result.trace_id or "none"
            })

            # Log metrics
            metrics_dict = {
                "processing_time_ms": float(result.processing_time_ms)
            }

            if result.overall_score is not None:
                metrics_dict["overall_score"] = result.overall_score

            for metric in result.metrics:
                if metric.error is None:
                    metrics_dict[metric.name] = metric.value

            mlflow.log_metrics(metrics_dict)

            # Log tags
            mlflow.set_tags({
                "certus_service": "certus-evaluate",
                "skipped": str(result.skipped).lower(),
                "timestamp": result.timestamp.isoformat()
            })

            if result.skip_reason:
                mlflow.set_tag("skip_reason", result.skip_reason)

            # Log artifacts (always log hashes)
            mlflow.log_text(result.query_hash, "query_hash.txt")
            mlflow.log_text(result.response_hash, "response_hash.txt")

            # Optionally log full content (PII risk!)
            if log_full_content and query and response:
                logger.warning(
                    "mlflow.log.full_content",
                    workspace_id=result.workspace_id,
                    message="Logging full content (contains PII)"
                )
                mlflow.log_text(query, "query.txt")
                mlflow.log_text(response, "response.txt")
                if context:
                    mlflow.log_text("\n\n---\n\n".join(context), "context.txt")

            logger.info(
                "mlflow.log.complete",
                run_id=run.info.run_id,
                experiment=experiment_name,
                workspace_id=result.workspace_id
            )

            return run.info.run_id
```

## Middleware (Certus Pattern)

```python
# src/certus_evaluate/middleware/trace_id.py

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from uuid import uuid4

from ..core.request_context import set_request_id, clear_request_id
from ..core.logging import get_logger

logger = get_logger(__name__)


class TraceIDMiddleware(BaseHTTPMiddleware):
    """
    Middleware to generate/propagate trace IDs.

    Follows Certus pattern from certus_ask/middleware/
    """

    async def dispatch(self, request: Request, call_next):
        # Get trace ID from header or generate new one
        trace_id = request.headers.get("X-Trace-ID") or str(uuid4())

        # Set in context for this request
        set_request_id(trace_id)

        # Add to response headers
        response = await call_next(request)
        response.headers["X-Trace-ID"] = trace_id

        # Clear context
        clear_request_id()

        return response


# src/certus_evaluate/middleware/logging.py

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
import time

from ..core.logging import get_logger
from ..core.request_context import get_request_id

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log all requests/responses.

    Follows Certus pattern from certus_ask/middleware/logging.py
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request
        logger.info(
            "request.start",
            method=request.method,
            path=request.url.path,
            trace_id=get_request_id()
        )

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_ms = int((time.time() - start_time) * 1000)

        # Log response
        logger.info(
            "request.complete",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            trace_id=get_request_id()
        )

        return response
```

## FastAPI Service (with Certus Patterns)

```python
# src/certus_evaluate/service/main.py

from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager

from ..core.config import get_settings
from ..core.config_validation import ConfigurationValidator
from ..core.logging import configure_logging, get_logger
from ..core.ragas import RAGASEvaluator
from ..schemas.requests import EvaluationRequest
from ..schemas.responses import EvaluationResult, StandardResponse, ErrorDetail
from ..core.request_context import get_request_id
from ..core.exceptions import (
    EvaluationError,
    EvaluationTimeoutError
)
from ..observability.mlflow_logger import MLflowLogger
from ..middleware.trace_id import TraceIDMiddleware
from ..middleware.logging import RequestLoggingMiddleware

# Validate configuration at startup (fail-fast)
ConfigurationValidator.fail_fast()

settings = get_settings()

# Configure logging
configure_logging(
    level=settings.LOG_LEVEL,
    json_output=(settings.LOG_FORMAT == "json"),
    service_name=settings.OTEL_SERVICE_NAME
)

logger = get_logger(__name__)

# Lifespan context manager for startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info(
        "service.startup",
        version="0.1.0",
        strategy=settings.EVALUATE_STRATEGY,
        llm_provider=settings.RAGAS_LLM_PROVIDER
    )
    yield
    # Shutdown
    logger.info("service.shutdown")

# Initialize FastAPI app
app = FastAPI(
    title="Certus-Evaluate",
    description="RAG response evaluation service",
    version="0.1.0",
    lifespan=lifespan
)

# Add middleware (order matters - reverse execution order)
app.add_middleware(TraceIDMiddleware)
app.add_middleware(RequestLoggingMiddleware)

# Initialize evaluator and logger (singleton)
evaluator = RAGASEvaluator(
    llm_provider=settings.RAGAS_LLM_PROVIDER,
    llm_model=settings.RAGAS_LLM_MODEL,
    embeddings_model=settings.RAGAS_EMBEDDINGS_MODEL,
    api_key=settings.OPENAI_API_KEY or settings.ANTHROPIC_API_KEY
)

mlflow_logger = MLflowLogger(
    tracking_uri=settings.MLFLOW_TRACKING_URI,
    experiment_prefix=settings.MLFLOW_EXPERIMENT_PREFIX
)


@app.post("/v1/evaluate", response_model=StandardResponse[EvaluationResult])
async def evaluate_endpoint(request: EvaluationRequest):
    """
    Evaluate a RAG response.

    Args:
        request: EvaluationRequest with query, response, context

    Returns:
        StandardResponse wrapping EvaluationResult
    """
    trace_id = get_request_id()

    logger.info(
        "evaluate.request.received",
        workspace_id=request.workspace_id,
        trace_id=trace_id,
        metrics=request.metrics
    )

    try:
        # Run evaluation
        result = await evaluator.evaluate(request)

        # Log to MLflow (don't fail if this fails)
        try:
            mlflow_run_id = mlflow_logger.log_evaluation(
                result,
                query=request.query if settings.MLFLOW_LOG_FULL_CONTENT else None,
                response=request.response if settings.MLFLOW_LOG_FULL_CONTENT else None,
                context=request.context if settings.MLFLOW_LOG_FULL_CONTENT else None,
                log_full_content=settings.MLFLOW_LOG_FULL_CONTENT
            )
            result.mlflow_run_id = mlflow_run_id
        except Exception as mlflow_error:
            logger.warning(
                "mlflow.log.failed",
                error=str(mlflow_error),
                trace_id=trace_id
            )

        logger.info(
            "evaluate.request.success",
            workspace_id=request.workspace_id,
            overall_score=result.overall_score,
            processing_time_ms=result.processing_time_ms,
            trace_id=trace_id
        )

        # Return wrapped in StandardResponse
        from datetime import datetime, timezone
        return StandardResponse(
            status="success",
            data=result,
            error=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=trace_id
        )

    except EvaluationTimeoutError as e:
        logger.warning(
            "evaluate.request.timeout",
            error_code=e.error_code,
            message=e.message,
            trace_id=trace_id
        )

        # Return skipped result (200 OK, not error)
        skipped_result = EvaluationResult(
            workspace_id=request.workspace_id,
            metrics=[],
            overall_score=None,
            processing_time_ms=request.timeout_ms,
            skipped=True,
            skip_reason="timeout",
            trace_id=trace_id,
            query_hash=EvaluationResult.hash_content(request.query),
            response_hash=EvaluationResult.hash_content(request.response),
            context_hashes=[
                EvaluationResult.hash_content(chunk)
                for chunk in request.context
            ]
        )

        from datetime import datetime, timezone
        return StandardResponse(
            status="success",  # Still success, just skipped
            data=skipped_result,
            error=None,
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=trace_id
        )

    except EvaluationError as e:
        logger.error(
            "evaluate.request.error",
            error_code=e.error_code,
            message=e.message,
            details=e.details,
            trace_id=trace_id
        )

        from datetime import datetime, timezone
        return StandardResponse(
            status="error",
            data=None,
            error=ErrorDetail(
                code=e.error_code,
                message=e.message,
                context=e.details
            ),
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=trace_id
        )

    except Exception as e:
        logger.exception(
            "evaluate.request.unexpected_error",
            error=str(e),
            trace_id=trace_id
        )

        from datetime import datetime, timezone
        return StandardResponse(
            status="error",
            data=None,
            error=ErrorDetail(
                code="internal_server_error",
                message="Unexpected error occurred",
                context={"error": str(e)}
            ),
            timestamp=datetime.now(timezone.utc).isoformat(),
            trace_id=trace_id
        )


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "certus-evaluate"
    }


@app.get("/")
async def root():
    """Root endpoint with service info"""
    return {
        "service": "certus-evaluate",
        "version": "0.1.0",
        "endpoints": {
            "evaluate": "POST /v1/evaluate",
            "health": "GET /health"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "certus_evaluate.service.main:app",
        host=settings.SERVICE_HOST,
        port=settings.SERVICE_PORT,
        workers=settings.SERVICE_WORKERS,
        log_level=settings.LOG_LEVEL.lower()
    )
```

## Dependencies (pyproject.toml)

```toml
[tool.poetry]
name = "certus-evaluate"
version = "0.1.0"
description = "RAG response evaluation for Certus TAP"
authors = ["Certus Team"]
readme = "README.md"
packages = [{include = "certus_evaluate", from = "src"}]

[tool.poetry.dependencies]
python = "^3.11"
pydantic = "^2.5"
pydantic-settings = "^2.1"
ragas = "^0.1"
mlflow = "^2.9"

# Structured logging (Certus pattern)
structlog = "^24.1"

# OpenTelemetry
opentelemetry-api = "^1.21"
opentelemetry-sdk = "^1.21"
opentelemetry-exporter-otlp = "^1.21"

# HTTP client with retry
httpx = "^0.25"
tenacity = "^8.2"

# FastAPI service
fastapi = "^0.104"
uvicorn = {extras = ["standard"], version = "^0.24"}

# CLI
typer = "^0.9"
python-dotenv = "^1.0"

# Caching (Phase 2)
redis = {extras = ["hiredis"], version = "^5.0", optional = true}

[tool.poetry.group.dev.dependencies]
pytest = "^7.4"
pytest-asyncio = "^0.21"
pytest-cov = "^4.1"
black = "^23.11"
ruff = "^0.1"
mypy = "^1.7"

[tool.poetry.scripts]
certus-evaluate = "certus_evaluate.cli.main:app"

[tool.poetry.extras]
cache = ["redis"]

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

## Implementation Plan (Updated)

**Timeline**: 8-10 weeks (with Certus pattern implementation)

### Phase 1: Core Module with Certus Patterns (4 weeks)

**Week 1: Foundation & Certus Infrastructure**

- [ ] Setup project structure (poetry, pyproject.toml)
- [ ] **Implement Certus exception hierarchy** (exceptions.py)
- [ ] **Implement structured logging** (logging.py with structlog)
- [ ] **Implement request context** (request_context.py)
- [ ] **Implement fail-fast configuration validation** (config_validation.py)
- [ ] Implement core data models (models.py, requests.py, responses.py)
- [ ] Unit tests for all Certus patterns

**Week 2: RAGAS Evaluator & Reference Loader**

- [ ] Implement RAGAS evaluator with structured logging
- [ ] Implement reference dataset loader (reference_loader.py)
- [ ] Bootstrap reference dataset contract
- [ ] **Create initial reference datasets** (see [Dataset Creation Guide](./certus-evaluate-dataset-guide.md))
  - [ ] Product/SME: Annotate 100 query-response pairs (2 workspaces × 50 entries)
  - [ ] Product/SME: Vet context chunks for each entry
  - [ ] Product/SME: Review and approve dataset entries
  - [ ] Engineering: Validate dataset format and upload to MLflow
  - [ ] **Timeline**: 5-6 days for annotation, 3-4 days for engineering (parallelizable)
- [ ] Unit tests for evaluator and loader (mocked)

**Week 3: Execution Strategies with Retry**

- [ ] Implement LocalStrategy
- [ ] **Implement RemoteStrategy with tenacity retry**
- [ ] Implement HybridStrategy
- [ ] Unit tests for all strategies
- [ ] Integration test for RAGAS with real API

**Week 4: Observability & CLI**

- [ ] **Add MLflow logger with retry logic**
- [ ] Add OpenTelemetry tracing
- [ ] Add CLI (benchmark, test commands)
- [ ] Integration tests (MLflow, OTEL)
- [ ] Documentation (README, usage examples)
- [ ] **Create ADR documents** (ADR-EVAL-001 through ADR-EVAL-004)

**Deliverables**:

- ✅ Working Python package following all Certus patterns
- ✅ Structured logging with JSON output
- ✅ Fail-fast configuration validation
- ✅ Semantic exception hierarchy
- ✅ Retry logic on external calls
- ✅ 80%+ unit test coverage

### Phase 2: Service, Middleware & Deployment (3 weeks)

**Week 5: FastAPI Service with Middleware**

- [ ] **Implement TraceIDMiddleware**
- [ ] **Implement RequestLoggingMiddleware**
- [ ] Implement FastAPI app with middleware stack
- [ ] **Wrap responses in StandardResponse**
- [ ] Add health check and info endpoints
- [ ] Add API authentication (Bearer token)
- [ ] Service smoke tests
- [ ] Contract tests for API schemas

**Week 6: Caching & Performance**

- [ ] Implement evaluation cache (cache.py)
- [ ] Add cache integration to evaluator
- [ ] Cache integration tests
- [ ] Load testing (p50/p99 latency benchmarks)
- [ ] Cost optimization validation

**Week 7: Deployment & Documentation**

- [ ] Create Dockerfile
- [ ] Create docker-compose.yml (with MLflow + Redis)
- [ ] Create K8s manifests
- [ ] Deploy service to dev environment
- [ ] Performance tuning
- [ ] Deployment guide documentation
- [ ] Runbook for operations

**Deliverables**:

- ✅ FastAPI service with full middleware stack
- ✅ Structured logging flowing to console/OpenSearch
- ✅ Redis caching operational
- ✅ Docker images published
- ✅ Dev environment deployed
- ✅ p99 latency < 10 seconds

### Phase 3: Certus-Ask Integration (3 weeks)

**Week 8: Integration Development**

- [ ] Add EvaluationClient to Certus-Ask
- [ ] **Ensure graceful degradation** (never raises)
- [ ] Shadow-mode integration in Ask pipeline
- [ ] Configuration flags (enable/disable per workspace)

**Week 9: Testing & Validation**

- [ ] Cross-service workflow tests
- [ ] End-to-end testing in dev environment
- [ ] **Verify zero impact on Ask latency**
- [ ] **Verify 99.9% Ask success when evaluate service down**
- [ ] MLflow dashboard validation

**Week 10: Production Rollout**

- [ ] Production deployment (K8s)
- [ ] Monitoring/alerting setup
- [ ] Gradual rollout plan (1% → 10% → 100%)
- [ ] Go-live checklist and approval
- [ ] Post-deployment validation

**Deliverables**:

- ✅ Certus-Ask evaluating 100% of responses (shadow mode)
- ✅ Ask p99 latency unchanged
- ✅ 99.9% Ask success rate when evaluate down
- ✅ All Certus patterns followed
- ✅ Production-ready service

## Testing Strategy

Same as original proposal, with additional tests for Certus patterns:

### Additional Unit Tests

- `test_exceptions.py` - Exception hierarchy and error codes
- `test_config_validation.py` - Fail-fast validation logic
- `test_request_context.py` - ContextVar propagation
- `test_logging.py` - Structured logging output

### Additional Integration Tests

- `test_mlflow_retry.py` - MLflow retry logic
- `test_remote_retry.py` - Remote HTTP retry logic
- `test_middleware.py` - Trace ID and logging middleware

## Success Metrics

Same as original proposal, plus:

### Certus Pattern Compliance

- [ ] All exceptions inherit from CertusException
- [ ] All logs use structlog with JSON output
- [ ] All API responses wrapped in StandardResponse
- [ ] Fail-fast configuration validation implemented
- [ ] Request context propagated across all logs
- [ ] Retry logic on all external calls
- [ ] Middleware stack follows Certus order

## Architecture Decision Records

### ADR-EVAL-001: RAGAS Over DeepEval for Initial Implementation

**Status**: Accepted

**Context**: Need to choose evaluation framework for Phase 1.

**Decision**: Use RAGAS only, defer DeepEval to Phase 4.

**Rationale**:

- RAGAS has mature LLM-based metrics
- Better documented than DeepEval
- Sufficient for MVP validation
- Can add DeepEval later for comparison

**Consequences**: Single framework risk, but reduces initial complexity.

### ADR-EVAL-002: Hybrid Execution Strategy

**Status**: Accepted

**Context**: Need to support multiple deployment topologies.

**Decision**: Implement local, remote, and hybrid strategies.

**Rationale**:

- Matches Certus flexible deployment philosophy
- Local for low-latency development
- Remote for production scale
- Hybrid for reliability

**Consequences**: More code complexity, but better flexibility.

### ADR-EVAL-003: Shadow Mode First, Enforcement Later

**Status**: Accepted

**Context**: How to integrate evaluation with Certus-Ask.

**Decision**: Shadow mode in Phase 1-3, enforcement deferred to Phase 4+.

**Rationale**:

- Proves architecture without risk
- Establishes baseline metrics
- Allows tuning before enforcement
- Follows Certus fail-safe philosophy

**Consequences**: Delayed enforcement, but safer rollout.

### ADR-EVAL-004: Reference Dataset Governance Model

**Status**: Accepted

**Context**: How to manage ground-truth reference data.

**Decision**: Workspace-owned datasets in MLflow, fail-fast when missing.

**Decision**:

- Each workspace owns reference data quality
- Store in MLflow for versioning
- Evaluator skips when reference missing
- Quarterly audit loop

**Consequences**: Manual curation overhead, but ensures quality.

## Open Questions

Same as original proposal.

## Future Enhancements

Same as original proposal.

## References

- [RAGAS Documentation](https://docs.ragas.io/)
- [MLflow Documentation](https://mlflow.org/docs/latest/index.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [structlog Documentation](https://www.structlog.org/)
- [tenacity Documentation](https://tenacity.readthedocs.io/)
- [Original Proposal](./certus-evaluate-service.md)
- [Certus Test Organization Guide](../../testing/TEST-ORGANIZATION.md)

## Summary of Certus Pattern Alignment

This revised proposal now fully aligns with Certus architectural patterns:

✅ **Exception Hierarchy** - All exceptions inherit from CertusException with error_code and details
✅ **Structured Logging** - Uses structlog with JSON output and dot-separated event names
✅ **Configuration Validation** - Fail-fast validation at startup with clear error messages
✅ **Request Context** - ContextVar-based trace ID propagation across all operations
✅ **Standard Responses** - All API responses wrapped in StandardResponse[T]
✅ **Middleware Stack** - TraceID and RequestLogging middleware in Certus order
✅ **Retry Logic** - tenacity retry on all external calls (MLflow, remote service)
✅ **Graceful Degradation** - Shadow mode, non-blocking evaluation, skip on failure
✅ **Privacy-First** - Hash-only logging by default, explicit opt-in for full content
✅ **Observable** - Structured logs, OTEL spans, MLflow tracking

The implementation is now production-ready and consistent with the Certus platform philosophy.
