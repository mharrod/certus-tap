# Certus-Evaluate Technical Specification

> Detailed schemas, APIs, and implementation guide for certus-evaluate service (Phase 1)

## Metadata

- **Related Proposal**: [certus-evaluate-service.md](./certus-evaluate-service.md)
- **Status**: Draft
- **Phase**: Phase 1 Implementation Guide
- **Author**: Certus TAP (AI agent for @harma)
- **Created**: 2024-12-21
- **Last Updated**: 2024-12-21
- **Target Readers**: Developers, Implementation Team

## Overview

This document provides implementation-level details for certus-evaluate Phase 1.
See the [main proposal](./certus-evaluate-service.md) for business justification,
architectural decisions, and overall roadmap.

**Phase 1 Scope**: REST API service with RAGAS/DeepEval integration, shadow mode,
graceful degradation, and integrity bridge.

## Table of Contents

1. [Data Models](#1-data-models)
2. [API Contracts](#2-api-contracts)
3. [Integration Contracts](#3-integration-contracts)
4. [Configuration](#4-configuration)
5. [Observability](#5-observability)
6. [Security](#6-security)
7. [Error Handling](#7-error-handling)
8. [Example Flows](#8-example-flows)

---

## 1. Data Models

All models use Pydantic v2 for validation and serialization.

### 1.1 IntegrityDecision

**Purpose**: Core decision payload sent to certus-integrity for signing. Represents
the evaluation verdict for a single RAG response.

**File**: `src/certus_evaluate/models/integrity.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Literal
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

class DecisionType(str, Enum):
    """Type of decision being made"""
    EVALUATION = "evaluation"  # Quality metrics only
    GUARDRAIL = "guardrail"    # Security checks only
    COMBINED = "combined"      # Both evaluation + guardrails

class DecisionOutcome(str, Enum):
    """Overall verdict of the decision"""
    PASS = "pass"        # All checks passed
    FAIL = "fail"        # Critical failures
    WARNING = "warning"  # Non-critical issues
    SKIPPED = "skipped"  # Evaluation not performed

class MetricScore(BaseModel):
    """Individual metric score with metadata"""
    name: str = Field(description="Metric name (e.g., 'faithfulness')")
    value: float = Field(ge=0.0, le=1.0, description="Score normalized to 0-1")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    passed: bool = Field(description="Did this metric pass its threshold?")
    framework: Literal["ragas", "deepeval", "custom"]
    error: Optional[str] = Field(default=None, description="Error if metric failed to compute")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "faithfulness",
                "value": 0.85,
                "threshold": 0.7,
                "passed": True,
                "framework": "ragas",
                "error": None
            }
        }

class GuardrailViolation(BaseModel):
    """Guardrail violation details (PII-safe)"""
    guardrail_type: Literal[
        "pii",
        "prompt_injection",
        "code_safety",
        "data_exfiltration",
        "jailbreak",
        "vuln_hallucination"
    ]
    severity: Literal["low", "medium", "high", "critical"]
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence")

    # PII-safe fields only
    content_hash: str = Field(description="SHA-256 hash of violating content")
    location: Optional[str] = Field(
        default=None,
        description="Location in response (e.g., 'char 45-67')"
    )
    remediation: Optional[str] = Field(
        default=None,
        description="Suggested remediation action"
    )

    # Do NOT store actual content, even redacted

    class Config:
        json_schema_extra = {
            "example": {
                "guardrail_type": "pii",
                "severity": "high",
                "confidence": 0.92,
                "content_hash": "sha256:a3f5e8...",
                "location": "char 120-135",
                "remediation": "Redact detected email address"
            }
        }

class IntegrityDecision(BaseModel):
    """
    Decision payload sent to certus-integrity for signing.

    IMPORTANT: This gets cryptographically signed and stored in transparency log.
    - Do NOT include PII (use hashes)
    - Do NOT include sensitive content
    - All fields become immutable evidence
    """

    # Identifiers
    decision_id: UUID = Field(
        default_factory=uuid4,
        description="Unique decision ID"
    )
    workspace_id: str = Field(
        min_length=1,
        max_length=255,
        description="Workspace this evaluation belongs to"
    )
    decision_type: DecisionType

    # Request context (hashed for PII safety)
    query_hash: str = Field(description="SHA-256 hash of user query")
    response_hash: str = Field(description="SHA-256 hash of generated response")
    context_hashes: List[str] = Field(
        description="SHA-256 hashes of retrieved context chunks",
        max_length=50  # Reasonable limit
    )

    # Evaluation results
    metrics: List[MetricScore] = Field(default_factory=list)
    guardrail_violations: List[GuardrailViolation] = Field(default_factory=list)

    # Overall verdict
    outcome: DecisionOutcome
    overall_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Weighted average of metric scores"
    )

    # Manifest reference
    manifest_uri: str = Field(
        pattern=r"^certus://manifests/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$",
        description="Manifest that defined thresholds"
    )

    # Metadata
    mode: Literal["shadow", "enforce"]
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of evaluation"
    )
    processing_time_ms: int = Field(ge=0, description="Time taken to evaluate")

    # Evidence chain (populated by downstream services)
    evidence_id: Optional[str] = Field(
        default=None,
        description="Populated by certus-integrity after signing"
    )
    mlflow_run_id: Optional[str] = Field(
        default=None,
        description="MLflow run ID for full details"
    )

    @field_validator('context_hashes')
    @classmethod
    def validate_hash_format(cls, v: List[str]) -> List[str]:
        """Ensure all hashes are valid SHA-256 format"""
        for hash_val in v:
            if not hash_val.startswith('sha256:') or len(hash_val) != 71:
                raise ValueError(f'Invalid SHA-256 hash format: {hash_val}')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "decision_id": "550e8400-e29b-41d4-a716-446655440000",
                "workspace_id": "acme",
                "decision_type": "combined",
                "query_hash": "sha256:7d8e2a3f9c1b5e4d6a8f2e9c3b7a5d4e6f8a2c9b5e7d3f1a4c6e8b2d9f5a3c7e1",
                "response_hash": "sha256:3c7e1a4c6e8b2d9f5a3c7e19c1b5e4d6a8f2e9c3b7a5d4e6f8a2c9b5e7d3f1a4",
                "context_hashes": [
                    "sha256:1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b",
                    "sha256:2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d3e4f5a6b7c8d9e0f1a2b3c"
                ],
                "metrics": [
                    {
                        "name": "faithfulness",
                        "value": 0.85,
                        "threshold": 0.7,
                        "passed": True,
                        "framework": "ragas"
                    },
                    {
                        "name": "answer_relevancy",
                        "value": 0.78,
                        "threshold": 0.6,
                        "passed": True,
                        "framework": "ragas"
                    }
                ],
                "guardrail_violations": [],
                "outcome": "pass",
                "overall_score": 0.82,
                "manifest_uri": "certus://manifests/acme/2025-01",
                "mode": "shadow",
                "timestamp": "2024-12-21T10:30:00Z",
                "processing_time_ms": 1847,
                "evidence_id": None,
                "mlflow_run_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"
            }
        }
```

### 1.2 EvaluationManifest

**Purpose**: Defines thresholds, guardrail policies, and evaluation configuration per workspace.

**File**: `src/certus_evaluate/models/manifest.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import Dict, Optional, Literal
from datetime import datetime, timezone

class ThresholdConfig(BaseModel):
    """Threshold configuration for a single metric"""
    min_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    max_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    weight: float = Field(default=1.0, ge=0.0, description="Weight for overall score")
    required: bool = Field(default=True, description="Must this metric pass?")

    @field_validator('max_score')
    @classmethod
    def validate_max_greater_than_min(cls, v, info):
        """Ensure max_score >= min_score if both are set"""
        if v is not None and info.data.get('min_score') is not None:
            if v < info.data['min_score']:
                raise ValueError('max_score must be >= min_score')
        return v

    @field_validator('min_score', 'max_score')
    @classmethod
    def at_least_one_threshold(cls, v, info):
        """At least one of min_score or max_score must be set"""
        # This runs after both fields are validated
        if info.field_name == 'max_score':
            if v is None and info.data.get('min_score') is None:
                raise ValueError('At least one of min_score or max_score must be set')
        return v

class GuardrailConfig(BaseModel):
    """Guardrail configuration"""
    enabled: bool = True
    block_on_violation: bool = Field(
        default=False,
        description="In enforce mode, block response if violated"
    )
    severity_threshold: Literal["low", "medium", "high", "critical"] = "medium"
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence to trigger violation"
    )

class EvaluationManifest(BaseModel):
    """
    Manifest defining evaluation configuration for a workspace.
    Stored as signed artifact in certus-trust.
    """

    # Manifest metadata
    manifest_id: str = Field(pattern=r"^manifest_[a-zA-Z0-9_-]+$")
    manifest_uri: str = Field(
        pattern=r"^certus://manifests/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$"
    )
    workspace_id: str = Field(min_length=1, max_length=255)
    version: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}$", description="Format: YYYY-MM")

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    signed_by: str = Field(description="Email or identity of signer")

    # Evaluation mode
    default_mode: Literal["shadow", "enforce", "disabled"] = "shadow"

    # Metric thresholds
    thresholds: Dict[str, ThresholdConfig] = Field(
        default_factory=dict,
        description="Metric name -> threshold configuration"
    )

    # Guardrail configuration
    guardrails: Dict[str, GuardrailConfig] = Field(
        default_factory=lambda: {
            "pii": GuardrailConfig(
                enabled=True,
                block_on_violation=True,
                severity_threshold="high"
            ),
            "prompt_injection": GuardrailConfig(
                enabled=True,
                block_on_violation=True,
                severity_threshold="high"
            ),
            "code_safety": GuardrailConfig(
                enabled=True,
                block_on_violation=False,
                severity_threshold="medium"
            ),
            "data_exfiltration": GuardrailConfig(
                enabled=True,
                block_on_violation=True,
                severity_threshold="high"
            ),
            "jailbreak": GuardrailConfig(
                enabled=True,
                block_on_violation=True,
                severity_threshold="high"
            ),
            "vuln_hallucination": GuardrailConfig(
                enabled=False,
                severity_threshold="medium"
            )
        }
    )

    # Overall evaluation policy
    require_all_metrics_pass: bool = Field(
        default=False,
        description="If true, all required metrics must pass"
    )
    min_overall_score: Optional[float] = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum weighted average score to pass"
    )

    # Timeout configuration
    timeout_ms: int = Field(
        default=2000,
        ge=100,
        le=30000,
        description="Max evaluation time in milliseconds"
    )

    # Observability
    mlflow_experiment_name: Optional[str] = Field(
        default=None,
        description="Custom MLflow experiment name (default: certus-evaluate-{workspace_id})"
    )
    log_full_content: bool = Field(
        default=False,
        description="Log full query/response to MLflow (PII risk!)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "manifest_id": "manifest_acme_2025_01",
                "manifest_uri": "certus://manifests/acme/2025-01",
                "workspace_id": "acme",
                "version": "2025-01",
                "signed_by": "security-team@acme.com",
                "default_mode": "shadow",
                "thresholds": {
                    "faithfulness": {
                        "min_score": 0.7,
                        "weight": 2.0,
                        "required": True
                    },
                    "answer_relevancy": {
                        "min_score": 0.6,
                        "weight": 1.5,
                        "required": True
                    },
                    "context_precision": {
                        "min_score": 0.5,
                        "weight": 1.0,
                        "required": False
                    }
                },
                "require_all_metrics_pass": False,
                "min_overall_score": 0.7,
                "timeout_ms": 2000,
                "log_full_content": False
            }
        }
```

### 1.3 API Request/Response Models

**File**: `src/certus_evaluate/models/api.py`

```python
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Optional, Literal
from uuid import UUID

class EvaluateRequest(BaseModel):
    """Request to POST /v1/evaluate endpoint"""

    workspace_id: str = Field(
        min_length=1,
        max_length=255,
        pattern=r"^[a-zA-Z0-9_-]+$"
    )
    query: str = Field(min_length=1, max_length=10000)
    response: str = Field(min_length=1, max_length=50000)
    context: List[str] = Field(
        description="Retrieved context chunks",
        max_length=50  # Max 50 chunks
    )

    # Manifest reference
    manifest_uri: str = Field(
        pattern=r"^certus://manifests/[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$"
    )

    # Optional overrides (requires workspace:admin scope)
    mode: Optional[Literal["shadow", "enforce", "async"]] = None
    timeout_ms: Optional[int] = Field(default=None, ge=100, le=30000)

    # Tracing context (propagated from Certus-Ask)
    trace_id: Optional[str] = None
    parent_span_id: Optional[str] = None

    @field_validator('context')
    @classmethod
    def validate_context_chunks(cls, v: List[str]) -> List[str]:
        """Validate individual context chunk sizes"""
        for i, chunk in enumerate(v):
            if len(chunk) > 10000:  # 10KB max per chunk
                raise ValueError(f'Context chunk {i} exceeds 10KB limit')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "workspace_id": "acme",
                "query": "What is Certus?",
                "response": "Certus is a trust automation platform...",
                "context": [
                    "Certus TAP provides cryptographic evidence...",
                    "The framework includes four core services..."
                ],
                "manifest_uri": "certus://manifests/acme/2025-01",
                "mode": "shadow",
                "timeout_ms": 2000,
                "trace_id": "trace_abc123xyz"
            }
        }

class EvaluateResponse(BaseModel):
    """Success response from POST /v1/evaluate (200 OK)"""

    evaluation_id: UUID
    passed: bool = Field(description="Did evaluation pass thresholds?")
    evidence_id: Optional[str] = Field(
        default=None,
        description="Evidence ID from certus-integrity (if signed)"
    )

    # Metrics
    metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Metric name -> score"
    )
    overall_score: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    # Guardrails
    guardrail_violations: List[Dict] = Field(
        default_factory=list,
        description="List of guardrail violations (sanitized)"
    )

    # Metadata
    processing_time_ms: int = Field(ge=0)
    mode: Literal["shadow", "enforce"]
    skipped: bool = Field(
        default=False,
        description="Was evaluation skipped due to timeout/error?"
    )
    skip_reason: Optional[str] = None

    # Observability
    mlflow_run_id: Optional[str] = None
    trace_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
                "passed": True,
                "evidence_id": "evi_a1b2c3d4e5f6",
                "metrics": {
                    "faithfulness": 0.85,
                    "answer_relevancy": 0.78,
                    "context_precision": 0.72
                },
                "overall_score": 0.80,
                "guardrail_violations": [],
                "processing_time_ms": 1847,
                "mode": "shadow",
                "skipped": False,
                "mlflow_run_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
                "trace_id": "trace_abc123xyz"
            }
        }

class SkippedEvaluateResponse(BaseModel):
    """Response when evaluation was skipped (200 OK)"""

    evaluation_id: Optional[UUID] = None
    skipped: bool = True
    skip_reason: str = Field(
        description="Why evaluation was skipped",
        examples=["evaluator_timeout", "circuit_breaker_open", "service_unavailable"]
    )
    evidence_id: Optional[str] = None
    metrics: Dict[str, float] = Field(default_factory=dict)
    guardrail_violations: List = Field(default_factory=list)
    processing_time_ms: int = Field(ge=0)
    trace_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "evaluation_id": None,
                "skipped": True,
                "skip_reason": "evaluator_timeout",
                "evidence_id": None,
                "metrics": {},
                "guardrail_violations": [],
                "processing_time_ms": 2500,
                "trace_id": "trace_abc123xyz"
            }
        }

class EvaluateErrorResponse(BaseModel):
    """Error response from POST /v1/evaluate"""

    error: str = Field(description="Error code")
    message: str = Field(description="Human-readable error message")
    details: Optional[Dict] = Field(default=None)
    fallback: str = Field(
        description="Guidance for caller on how to proceed"
    )
    retry_after_ms: Optional[int] = Field(
        default=None,
        description="Suggested retry delay (for 503 responses)"
    )
    trace_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "error": "evaluation_service_unavailable",
                "message": "Evaluation service is temporarily unavailable",
                "details": {"upstream_error": "Connection to MLflow timed out"},
                "fallback": "Response generated without quality evaluation",
                "retry_after_ms": 30000,
                "trace_id": "trace_abc123xyz"
            }
        }

class AsyncEvaluateResponse(BaseModel):
    """Response for async evaluation mode (202 Accepted)"""

    evaluation_id: UUID
    status: Literal["pending", "processing"]
    status_uri: str = Field(
        description="URI to poll for status",
        pattern=r"^/v1/evaluate/[a-f0-9-]+/status$"
    )
    estimated_completion_ms: int = Field(
        ge=0,
        description="Estimated time until completion"
    )
    trace_id: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "pending",
                "status_uri": "/v1/evaluate/550e8400-e29b-41d4-a716-446655440000/status",
                "estimated_completion_ms": 5000,
                "trace_id": "trace_abc123xyz"
            }
        }
```

---

## 2. API Contracts

### 2.1 certus-evaluate REST API

#### 2.1.1 POST /v1/evaluate

**Purpose**: Evaluate a RAG response with metrics and guardrails.

**Authentication**: Required. JWT bearer token with `workspace:read` scope.

**Request**:

```http
POST /v1/evaluate HTTP/1.1
Host: certus-evaluate.example.com
Authorization: Bearer <jwt_token>
Content-Type: application/json

{
  "workspace_id": "acme",
  "query": "What is Certus?",
  "response": "Certus is a trust automation platform...",
  "context": ["Certus TAP provides...", "The framework..."],
  "manifest_uri": "certus://manifests/acme/2025-01",
  "mode": "shadow",
  "timeout_ms": 2000,
  "trace_id": "trace_abc123"
}
```

**Responses**:

| Status                  | Description              | Response Model                                  |
| ----------------------- | ------------------------ | ----------------------------------------------- |
| 200 OK                  | Evaluation completed     | `EvaluateResponse` or `SkippedEvaluateResponse` |
| 202 Accepted            | Async evaluation queued  | `AsyncEvaluateResponse`                         |
| 400 Bad Request         | Invalid request          | `EvaluateErrorResponse`                         |
| 401 Unauthorized        | Missing/invalid auth     | `EvaluateErrorResponse`                         |
| 403 Forbidden           | Insufficient permissions | `EvaluateErrorResponse`                         |
| 503 Service Unavailable | Service degraded         | `EvaluateErrorResponse`                         |

**Example Success Response (200 OK)**:

```json
{
  "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
  "passed": true,
  "evidence_id": "evi_a1b2c3d4e5f6",
  "metrics": {
    "faithfulness": 0.85,
    "answer_relevancy": 0.78
  },
  "overall_score": 0.82,
  "guardrail_violations": [],
  "processing_time_ms": 1847,
  "mode": "shadow",
  "skipped": false,
  "mlflow_run_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "trace_id": "trace_abc123"
}
```

**Example Skipped Response (200 OK)**:

```json
{
  "evaluation_id": null,
  "skipped": true,
  "skip_reason": "evaluator_timeout",
  "evidence_id": null,
  "metrics": {},
  "guardrail_violations": [],
  "processing_time_ms": 2500,
  "trace_id": "trace_abc123"
}
```

**Example Error Response (503 Service Unavailable)**:

```json
{
  "error": "evaluation_service_unavailable",
  "message": "RAGAS evaluator timed out",
  "details": { "timeout_ms": 2000, "actual_ms": 2500 },
  "fallback": "Response generated without quality evaluation",
  "retry_after_ms": 30000,
  "trace_id": "trace_abc123"
}
```

#### 2.1.2 GET /v1/evaluate/{evaluation_id}/status

**Purpose**: Poll async evaluation status (for async mode).

**Authentication**: Required. Same workspace access as original request.

**Request**:

```http
GET /v1/evaluate/550e8400-e29b-41d4-a716-446655440000/status HTTP/1.1
Host: certus-evaluate.example.com
Authorization: Bearer <jwt_token>
```

**Response (200 OK - Still Processing)**:

```json
{
  "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress_percent": 65,
  "estimated_completion_ms": 2000
}
```

**Response (200 OK - Completed)**:

```json
{
  "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "passed": true,
    "evidence_id": "evi_a1b2c3d4e5f6",
    "metrics": {...},
    ...
  }
}
```

#### 2.1.3 GET /v1/health

**Purpose**: Health check endpoint.

**Authentication**: Not required.

**Response (200 OK)**:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "dependencies": {
    "certus_integrity": "healthy",
    "mlflow": "healthy",
    "ragas": "healthy",
    "deepeval": "healthy"
  }
}
```

**Response (503 Service Unavailable)**:

```json
{
  "status": "degraded",
  "version": "0.1.0",
  "dependencies": {
    "certus_integrity": "unhealthy",
    "mlflow": "healthy",
    "ragas": "healthy",
    "deepeval": "healthy"
  },
  "error": "certus-integrity unreachable"
}
```

### 2.2 certus-integrity Client API

**Purpose**: Submit evaluation decisions for signing.

**File**: `src/certus_evaluate/clients/integrity_client.py`

```python
from typing import Optional
import httpx
from .models.integrity import IntegrityDecision

class IntegrityClient:
    """Client for certus-integrity service"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 5000):
        self.base_url = base_url
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout / 1000.0)
        )

    async def submit_decision(
        self,
        decision: IntegrityDecision
    ) -> Dict[str, str]:
        """
        Submit evaluation decision for signing.

        Args:
            decision: IntegrityDecision to sign

        Returns:
            Dict with 'evidence_id' and 'proof_uri'

        Raises:
            IntegrityClientError: If submission fails
        """
        try:
            response = await self.client.post(
                "/v1/decisions",
                json=decision.model_dump(mode='json')
            )
            response.raise_for_status()
            data = response.json()

            return {
                "evidence_id": data["evidence_id"],
                "proof_uri": data["proof_uri"]
            }
        except httpx.HTTPError as e:
            raise IntegrityClientError(f"Failed to submit decision: {e}")

    async def close(self):
        await self.client.aclose()
```

**Expected certus-integrity API**:

```http
POST /v1/decisions HTTP/1.1
Host: certus-integrity.example.com
Authorization: Bearer <service_api_key>
Content-Type: application/json

{
  "decision_id": "550e8400-e29b-41d4-a716-446655440000",
  "workspace_id": "acme",
  "decision_type": "combined",
  "query_hash": "sha256:...",
  "response_hash": "sha256:...",
  "context_hashes": ["sha256:...", "sha256:..."],
  "metrics": [...],
  "guardrail_violations": [],
  "outcome": "pass",
  "overall_score": 0.82,
  "manifest_uri": "certus://manifests/acme/2025-01",
  "mode": "shadow",
  "timestamp": "2024-12-21T10:30:00Z",
  "processing_time_ms": 1847
}
```

**Response (201 Created)**:

```json
{
  "evidence_id": "evi_a1b2c3d4e5f6",
  "proof_uri": "certus://trust/proofs/evi_a1b2c3d4e5f6",
  "signed_at": "2024-12-21T10:30:01Z",
  "signature": "base64_encoded_signature..."
}
```

---

## 3. Integration Contracts

### 3.1 Certus-Ask Integration

**File**: `certus-ask/src/clients/evaluation_client.py` (in Certus-Ask repo)

#### 3.1.1 Circuit Breaker Implementation

```python
from circuitbreaker import circuit
import httpx
import asyncio
from typing import Optional

class EvaluationClient:
    """
    Client for certus-evaluate service with circuit breaker.

    Implements graceful degradation - Certus-Ask works fully
    even when evaluation service is unavailable.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout_ms: int = 2000,
        circuit_failure_threshold: int = 3,
        circuit_timeout_s: int = 30
    ):
        self.base_url = base_url
        self.timeout_ms = timeout_ms
        self.client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout_ms / 1000.0)
        )

    @circuit(failure_threshold=3, recovery_timeout=30, expected_exception=EvaluationError)
    async def evaluate(
        self,
        workspace_id: str,
        query: str,
        response: str,
        context: List[str],
        manifest_uri: str,
        trace_id: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Evaluate RAG response with circuit breaker protection.

        Returns:
            Evaluation result dict, or None if skipped/failed

        Never raises - always degrades gracefully.
        """
        try:
            result = await self.client.post(
                "/v1/evaluate",
                json={
                    "workspace_id": workspace_id,
                    "query": query,
                    "response": response,
                    "context": context,
                    "manifest_uri": manifest_uri,
                    "mode": "shadow",
                    "timeout_ms": self.timeout_ms,
                    "trace_id": trace_id
                }
            )
            result.raise_for_status()
            return result.json()

        except httpx.TimeoutException:
            logger.warning(
                "Evaluation timeout",
                extra={"timeout_ms": self.timeout_ms, "trace_id": trace_id}
            )
            return {"skipped": True, "skip_reason": "timeout"}

        except httpx.HTTPError as e:
            logger.error(
                "Evaluation HTTP error",
                extra={"error": str(e), "trace_id": trace_id}
            )
            raise EvaluationError(f"Evaluation failed: {e}")

        except Exception as e:
            logger.exception(
                "Unexpected evaluation error",
                extra={"error": str(e), "trace_id": trace_id}
            )
            return {"skipped": True, "skip_reason": "unexpected_error"}
```

#### 3.1.2 Integration Pattern

```python
# In Certus-Ask RAG pipeline
async def generate_response_with_evaluation(
    query: str,
    workspace_id: str,
    trace_id: str
) -> Dict:
    """
    Generate response with optional evaluation.
    Response ALWAYS succeeds, evaluation is optional.
    """

    # 1. Generate response (primary function)
    response = await rag_pipeline.run(query)

    # 2. Attempt evaluation (non-blocking, optional)
    evaluation_result = None
    try:
        evaluation_task = asyncio.create_task(
            evaluation_client.evaluate(
                workspace_id=workspace_id,
                query=query,
                response=response["answer"],
                context=response["context"],
                manifest_uri=f"certus://manifests/{workspace_id}/latest",
                trace_id=trace_id
            )
        )

        # Wait with timeout
        evaluation_result = await asyncio.wait_for(
            evaluation_task,
            timeout=2.5  # Slightly longer than service timeout
        )

    except asyncio.TimeoutError:
        logger.warning("Evaluation timeout at client level", extra={"trace_id": trace_id})
        evaluation_result = {"skipped": True, "skip_reason": "client_timeout"}

    except Exception as e:
        logger.error("Evaluation error", extra={"error": str(e), "trace_id": trace_id})
        evaluation_result = {"skipped": True, "skip_reason": "error"}

    # 3. Return response with evaluation metadata
    return {
        "answer": response["answer"],
        "context": response["context"],
        "evaluation": evaluation_result,  # May be None or skipped
        "trace_id": trace_id
    }
```

### 3.2 MLflow Integration

**File**: `src/certus_evaluate/observability/mlflow_logger.py`

```python
import mlflow
from typing import Dict, Any
from ..models.integrity import IntegrityDecision
import hashlib
import json

class MLflowLogger:
    """Logger for evaluation runs to MLflow"""

    def __init__(self, tracking_uri: str, experiment_prefix: str = "certus-evaluate"):
        self.tracking_uri = tracking_uri
        self.experiment_prefix = experiment_prefix
        mlflow.set_tracking_uri(tracking_uri)

    def log_evaluation_run(
        self,
        decision: IntegrityDecision,
        query: str,
        response: str,
        context: List[str],
        log_full_content: bool = False
    ) -> str:
        """
        Log evaluation run to MLflow.

        Args:
            decision: IntegrityDecision with results
            query: Original query (for logging, not signing)
            response: Original response (for logging, not signing)
            context: Original context (for logging, not signing)
            log_full_content: If True, log full query/response (PII risk!)

        Returns:
            MLflow run ID
        """

        # Experiment name: certus-evaluate-{workspace_id}
        experiment_name = f"{self.experiment_prefix}-{decision.workspace_id}"
        mlflow.set_experiment(experiment_name)

        # Run name: eval-{decision_id}
        run_name = f"eval-{str(decision.decision_id)[:8]}"

        with mlflow.start_run(run_name=run_name) as run:

            # Log parameters (immutable)
            mlflow.log_params({
                "workspace_id": decision.workspace_id,
                "manifest_uri": decision.manifest_uri,
                "mode": decision.mode,
                "decision_type": decision.decision_type.value,
                "ragas_version": self._get_ragas_version(),
                "deepeval_version": self._get_deepeval_version()
            })

            # Log metrics (numeric)
            metrics_dict = {
                "processing_time_ms": float(decision.processing_time_ms),
                "guardrail_violations_count": float(len(decision.guardrail_violations))
            }

            if decision.overall_score is not None:
                metrics_dict["overall_score"] = decision.overall_score

            for metric in decision.metrics:
                metrics_dict[metric.name] = metric.value

            mlflow.log_metrics(metrics_dict)

            # Log tags
            mlflow.set_tags({
                "evidence_id": decision.evidence_id or "pending",
                "decision_outcome": decision.outcome.value,
                "certus_service": "certus-evaluate"
            })

            # Log artifacts
            # Always log decision JSON
            decision_json = decision.model_dump_json(indent=2)
            mlflow.log_text(decision_json, "decision.json")

            # Optionally log full content (PII risk!)
            if log_full_content:
                mlflow.log_text(query, "query.txt")
                mlflow.log_text(response, "response.txt")
                mlflow.log_text(json.dumps(context, indent=2), "context.json")
            else:
                # Log only hashes
                mlflow.log_text(decision.query_hash, "query_hash.txt")
                mlflow.log_text(decision.response_hash, "response_hash.txt")

            return run.info.run_id

    def _get_ragas_version(self) -> str:
        import ragas
        return ragas.__version__

    def _get_deepeval_version(self) -> str:
        import deepeval
        return deepeval.__version__
```

**MLflow Experiment Structure**:

```
certus-evaluate-acme/
├── eval-550e8400/
│   ├── params/
│   │   ├── workspace_id: acme
│   │   ├── manifest_uri: certus://manifests/acme/2025-01
│   │   ├── mode: shadow
│   │   └── decision_type: combined
│   ├── metrics/
│   │   ├── faithfulness: 0.85
│   │   ├── answer_relevancy: 0.78
│   │   ├── overall_score: 0.82
│   │   └── processing_time_ms: 1847
│   ├── tags/
│   │   ├── evidence_id: evi_a1b2c3d4e5f6
│   │   └── decision_outcome: pass
│   └── artifacts/
│       ├── decision.json
│       ├── query_hash.txt
│       └── response_hash.txt
```

### 3.3 OpenTelemetry Integration

**File**: `src/certus_evaluate/observability/tracing.py`

```python
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode, SpanKind
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from contextlib import contextmanager
from typing import Optional

# Span names
SPAN_EVALUATE = "certus.evaluate.run"
SPAN_RAGAS = "certus.evaluate.ragas"
SPAN_DEEPEVAL = "certus.evaluate.deepeval"
SPAN_GUARDRAILS = "certus.evaluate.guardrails"
SPAN_INTEGRITY_BRIDGE = "certus.evaluate.integrity_bridge"

# Attribute names
ATTR_WORKSPACE_ID = "certus.workspace_id"
ATTR_DECISION_ID = "certus.decision_id"
ATTR_EVIDENCE_ID = "certus.evidence_id"
ATTR_MANIFEST_URI = "certus.manifest_uri"
ATTR_EVALUATION_MODE = "certus.evaluation.mode"
ATTR_EVALUATION_OUTCOME = "certus.evaluation.outcome"
ATTR_EVALUATION_SKIPPED = "certus.evaluation.skipped"
ATTR_METRIC_NAME = "certus.metric.name"
ATTR_METRIC_VALUE = "certus.metric.value"
ATTR_METRIC_PASSED = "certus.metric.passed"

class EvaluationTracer:
    """OpenTelemetry tracer for evaluation service"""

    def __init__(self, service_name: str = "certus-evaluate", otlp_endpoint: Optional[str] = None):
        self.tracer = trace.get_tracer(__name__)

        if otlp_endpoint:
            provider = TracerProvider()
            processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
            provider.add_span_processor(processor)
            trace.set_tracer_provider(provider)

    @contextmanager
    def trace_evaluation(
        self,
        workspace_id: str,
        decision_id: str,
        manifest_uri: str,
        mode: str,
        trace_id: Optional[str] = None
    ):
        """
        Main evaluation span.

        Usage:
            with tracer.trace_evaluation(...) as span:
                # ... evaluation logic
                span.set_outcome("pass", 0.85)
        """
        with self.tracer.start_as_current_span(
            SPAN_EVALUATE,
            kind=SpanKind.SERVER,
            attributes={
                ATTR_WORKSPACE_ID: workspace_id,
                ATTR_DECISION_ID: decision_id,
                ATTR_MANIFEST_URI: manifest_uri,
                ATTR_EVALUATION_MODE: mode
            }
        ) as span:
            if trace_id:
                span.set_attribute("trace_id", trace_id)

            # Add helper method to span
            def set_outcome(outcome: str, score: Optional[float] = None):
                span.set_attribute(ATTR_EVALUATION_OUTCOME, outcome)
                if score is not None:
                    span.set_attribute("certus.evaluation.overall_score", score)
                span.set_status(Status(StatusCode.OK))

            span.set_outcome = set_outcome

            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise

    @contextmanager
    def trace_metric(self, metric_name: str, framework: str):
        """
        Span for individual metric evaluation.

        Usage:
            with tracer.trace_metric("faithfulness", "ragas") as span:
                score = await ragas.evaluate(...)
                span.set_score(score, passed=True)
        """
        span_name = f"{SPAN_RAGAS if framework == 'ragas' else SPAN_DEEPEVAL}.{metric_name}"

        with self.tracer.start_as_current_span(
            span_name,
            kind=SpanKind.INTERNAL,
            attributes={
                ATTR_METRIC_NAME: metric_name,
                "certus.metric.framework": framework
            }
        ) as span:

            def set_score(value: float, passed: bool):
                span.set_attribute(ATTR_METRIC_VALUE, value)
                span.set_attribute(ATTR_METRIC_PASSED, passed)
                span.set_status(Status(StatusCode.OK))

            span.set_score = set_score

            try:
                yield span
            except Exception as e:
                span.set_status(Status(StatusCode.ERROR, str(e)))
                span.record_exception(e)
                raise
```

**Example Usage**:

```python
# In evaluation engine
async def evaluate(self, request: EvaluateRequest) -> EvaluateResponse:

    with self.tracer.trace_evaluation(
        workspace_id=request.workspace_id,
        decision_id=str(decision_id),
        manifest_uri=request.manifest_uri,
        mode=request.mode or "shadow",
        trace_id=request.trace_id
    ) as eval_span:

        # Run RAGAS metrics
        with self.tracer.trace_metric("faithfulness", "ragas") as metric_span:
            score = await self.ragas_evaluator.faithfulness(...)
            metric_span.set_score(score, passed=score >= 0.7)

        # ... more metrics

        # Set overall outcome
        eval_span.set_outcome("pass", overall_score=0.85)

        return response
```

---

## 4. Configuration

### 4.1 Environment Variables

**File**: `src/certus_evaluate/config.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, Literal

class Settings(BaseSettings):
    """Environment-based configuration"""

    # Service configuration
    SERVICE_HOST: str = "0.0.0.0"
    SERVICE_PORT: int = 8080
    SERVICE_WORKERS: int = 4
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    LOG_FORMAT: Literal["json", "text"] = "json"

    # Integration endpoints
    CERTUS_INTEGRITY_URL: str = "http://certus-integrity:8081"
    CERTUS_TRUST_URL: str = "http://certus-trust:8082"
    MANIFEST_STORE_URL: str = "http://manifest-store:8083"

    # MLflow configuration
    MLFLOW_TRACKING_URI: str = "http://mlflow:5000"
    MLFLOW_EXPERIMENT_PREFIX: str = "certus-evaluate"

    # OpenTelemetry configuration
    OTEL_EXPORTER_OTLP_ENDPOINT: Optional[str] = None
    OTEL_SERVICE_NAME: str = "certus-evaluate"
    OTEL_SERVICE_VERSION: str = "0.1.0"

    # Evaluation framework configuration
    RAGAS_LLM_PROVIDER: Literal["openai", "anthropic", "azure"] = "openai"
    RAGAS_LLM_MODEL: str = "gpt-4"
    RAGAS_EMBEDDINGS_MODEL: str = "text-embedding-3-small"

    DEEPEVAL_LLM_PROVIDER: Literal["openai", "anthropic", "azure"] = "openai"
    DEEPEVAL_LLM_MODEL: str = "gpt-4"

    # API keys (secrets - never log these!)
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    AZURE_OPENAI_API_KEY: Optional[str] = None
    AZURE_OPENAI_ENDPOINT: Optional[str] = None

    # Service API key (for service-to-service auth)
    CERTUS_API_KEY: str  # Required, no default

    # Guardrail configuration
    PRESIDIO_ANALYZER_URL: Optional[str] = None  # None = use local Presidio
    LLMGUARD_ENABLED: bool = True

    # Circuit breaker configuration
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: int = 3
    CIRCUIT_BREAKER_TIMEOUT_SECONDS: int = 30

    # Defaults
    DEFAULT_EVALUATION_TIMEOUT_MS: int = 2000
    DEFAULT_MODE: Literal["shadow", "enforce", "disabled"] = "shadow"

    # Feature flags
    ENABLE_ASYNC_MODE: bool = False  # Phase 1: disabled
    ENABLE_GPU_EVALUATORS: bool = False  # Phase 1: disabled

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

# Global settings instance
settings = Settings()
```

### 4.2 Example Configuration Files

**`.env.development`**:

```bash
# Service
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8080
SERVICE_WORKERS=1
LOG_LEVEL=DEBUG
LOG_FORMAT=text

# Integration (local services)
CERTUS_INTEGRITY_URL=http://localhost:8081
CERTUS_TRUST_URL=http://localhost:8082
MANIFEST_STORE_URL=http://localhost:8083

# MLflow
MLFLOW_TRACKING_URI=http://localhost:5000

# OpenTelemetry (optional in dev)
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Evaluation frameworks
RAGAS_LLM_PROVIDER=openai
RAGAS_LLM_MODEL=gpt-4
DEEPEVAL_LLM_PROVIDER=openai
DEEPEVAL_LLM_MODEL=gpt-4

# API keys (from environment or secrets manager)
OPENAI_API_KEY=${OPENAI_API_KEY}
CERTUS_API_KEY=dev-test-key-123

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=3
CIRCUIT_BREAKER_TIMEOUT_SECONDS=30

# Defaults
DEFAULT_EVALUATION_TIMEOUT_MS=2000
DEFAULT_MODE=shadow
```

**`.env.production`**:

```bash
# Service
SERVICE_HOST=0.0.0.0
SERVICE_PORT=8080
SERVICE_WORKERS=4
LOG_LEVEL=INFO
LOG_FORMAT=json

# Integration (k8s service names)
CERTUS_INTEGRITY_URL=http://certus-integrity.certus.svc.cluster.local:8081
CERTUS_TRUST_URL=http://certus-trust.certus.svc.cluster.local:8082
MANIFEST_STORE_URL=http://manifest-store.certus.svc.cluster.local:8083

# MLflow
MLFLOW_TRACKING_URI=http://mlflow.observability.svc.cluster.local:5000

# OpenTelemetry
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.observability.svc.cluster.local:4317

# Evaluation frameworks
RAGAS_LLM_PROVIDER=openai
RAGAS_LLM_MODEL=gpt-4
DEEPEVAL_LLM_PROVIDER=openai
DEEPEVAL_LLM_MODEL=gpt-4

# API keys (from Kubernetes secrets)
OPENAI_API_KEY=${OPENAI_API_KEY}
CERTUS_API_KEY=${CERTUS_API_KEY}

# Guardrails
PRESIDIO_ANALYZER_URL=http://presidio.security.svc.cluster.local:3000
LLMGUARD_ENABLED=true

# Circuit breaker
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_TIMEOUT_SECONDS=60

# Defaults
DEFAULT_EVALUATION_TIMEOUT_MS=2000
DEFAULT_MODE=shadow
```

### 4.3 Secrets Management

**Kubernetes Secrets** (production):

```yaml
# k8s/secrets.yaml
apiVersion: v1
kind: Secret
metadata:
  name: certus-evaluate-secrets
  namespace: certus
type: Opaque
stringData:
  OPENAI_API_KEY: 'sk-...'
  CERTUS_API_KEY: 'certus_...'
```

**Mount in Deployment**:

```yaml
# k8s/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: certus-evaluate
spec:
  template:
    spec:
      containers:
        - name: certus-evaluate
          image: certus-evaluate:0.1.0
          envFrom:
            - secretRef:
                name: certus-evaluate-secrets
            - configMapRef:
                name: certus-evaluate-config
```

---

## 5. Observability

### 5.1 Structured Logging

**File**: `src/certus_evaluate/observability/logging.py`

```python
import logging
import json
from datetime import datetime
from typing import Any, Dict

class JSONFormatter(logging.Formatter):
    """Format logs as JSON for structured logging"""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": "certus-evaluate"
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "workspace_id"):
            log_data["workspace_id"] = record.workspace_id
        if hasattr(record, "decision_id"):
            log_data["decision_id"] = record.decision_id
        if hasattr(record, "trace_id"):
            log_data["trace_id"] = record.trace_id

        return json.dumps(log_data)

def setup_logging(level: str = "INFO", format_type: str = "json"):
    """Configure logging for the service"""

    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

    # Suppress noisy third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
```

### 5.2 Metrics (Prometheus)

**File**: `src/certus_evaluate/observability/metrics.py`

```python
from prometheus_client import Counter, Histogram, Gauge, Info

# Request metrics
requests_total = Counter(
    'certus_evaluate_requests_total',
    'Total evaluation requests',
    ['workspace_id', 'mode', 'outcome']
)

request_duration_seconds = Histogram(
    'certus_evaluate_request_duration_seconds',
    'Evaluation request duration',
    ['workspace_id', 'mode'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
)

# Metric scores
metric_scores = Histogram(
    'certus_evaluate_metric_score',
    'Individual metric scores',
    ['workspace_id', 'metric_name', 'framework'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

# Guardrail violations
guardrail_violations_total = Counter(
    'certus_evaluate_guardrail_violations_total',
    'Total guardrail violations detected',
    ['workspace_id', 'guardrail_type', 'severity']
)

# Circuit breaker state
circuit_breaker_state = Gauge(
    'certus_evaluate_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open)',
    ['workspace_id']
)

# Service info
service_info = Info(
    'certus_evaluate_service',
    'Service information'
)
service_info.info({
    'version': '0.1.0',
    'python_version': '3.11'
})
```

### 5.3 Health Checks

**File**: `src/certus_evaluate/health.py`

```python
from typing import Dict, Literal
import httpx
from .config import settings

HealthStatus = Literal["healthy", "degraded", "unhealthy"]

class HealthChecker:
    """Health check for service and dependencies"""

    async def check_health(self) -> Dict[str, Any]:
        """
        Check health of service and dependencies.

        Returns:
            Dict with status and dependency health
        """
        dependency_health = {
            "certus_integrity": await self._check_certus_integrity(),
            "mlflow": await self._check_mlflow(),
            "ragas": self._check_ragas(),
            "deepeval": self._check_deepeval()
        }

        # Overall status
        if all(status == "healthy" for status in dependency_health.values()):
            overall_status = "healthy"
        elif any(status == "unhealthy" for status in dependency_health.values()):
            overall_status = "degraded"
        else:
            overall_status = "healthy"

        return {
            "status": overall_status,
            "version": "0.1.0",
            "dependencies": dependency_health
        }

    async def _check_certus_integrity(self) -> HealthStatus:
        """Check if certus-integrity is reachable"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.CERTUS_INTEGRITY_URL}/health",
                    timeout=2.0
                )
                return "healthy" if response.status_code == 200 else "unhealthy"
        except:
            return "unhealthy"

    async def _check_mlflow(self) -> HealthStatus:
        """Check if MLflow is reachable"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.MLFLOW_TRACKING_URI}/health",
                    timeout=2.0
                )
                return "healthy" if response.status_code == 200 else "unhealthy"
        except:
            return "degraded"  # MLflow is optional

    def _check_ragas(self) -> HealthStatus:
        """Check if RAGAS is importable"""
        try:
            import ragas
            return "healthy"
        except ImportError:
            return "unhealthy"

    def _check_deepeval(self) -> HealthStatus:
        """Check if DeepEval is importable"""
        try:
            import deepeval
            return "healthy"
        except ImportError:
            return "unhealthy"
```

---

## 6. Security

### 6.1 Authentication

**JWT Bearer Token Authentication**:

```python
# File: src/certus_evaluate/auth.py
from fastapi import HTTPException, Security, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Optional

security = HTTPBearer()

def verify_token(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> Dict[str, Any]:
    """
    Verify JWT token and extract claims.

    Raises:
        HTTPException: If token is invalid
    """
    try:
        token = credentials.credentials
        payload = jwt.decode(
            token,
            settings.JWT_PUBLIC_KEY,
            algorithms=["RS256"]
        )
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )

def verify_workspace_access(
    token_payload: Dict[str, Any],
    workspace_id: str,
    required_scope: str = "workspace:read"
) -> bool:
    """
    Verify token has access to workspace.

    Args:
        token_payload: Decoded JWT payload
        workspace_id: Workspace being accessed
        required_scope: Required scope (workspace:read or workspace:admin)

    Returns:
        True if access granted

    Raises:
        HTTPException: If access denied
    """
    # Check workspace scope
    scopes = token_payload.get("scopes", [])
    workspaces = token_payload.get("workspaces", [])

    if workspace_id not in workspaces:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"No access to workspace: {workspace_id}"
        )

    if required_scope not in scopes:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required scope: {required_scope}"
        )

    return True
```

**Usage in FastAPI endpoints**:

```python
from fastapi import Depends

@app.post("/v1/evaluate")
async def evaluate(
    request: EvaluateRequest,
    token: Dict = Depends(verify_token)
):
    # Verify workspace access
    verify_workspace_access(
        token,
        request.workspace_id,
        required_scope="workspace:read"
    )

    # ... evaluation logic
```

### 6.2 PII Handling

**Content Hashing**:

```python
# File: src/certus_evaluate/security/hashing.py
import hashlib
from typing import List

def hash_content(content: str) -> str:
    """
    Create SHA-256 hash of content.

    Returns:
        Hash in format: sha256:{hex_digest}
    """
    hash_obj = hashlib.sha256(content.encode('utf-8'))
    return f"sha256:{hash_obj.hexdigest()}"

def hash_context_chunks(chunks: List[str]) -> List[str]:
    """Hash all context chunks"""
    return [hash_content(chunk) for chunk in chunks]
```

**Usage**:

```python
# Before creating IntegrityDecision
decision = IntegrityDecision(
    query_hash=hash_content(request.query),
    response_hash=hash_content(request.response),
    context_hashes=hash_context_chunks(request.context),
    ...
)

# Original content only logged to MLflow with access controls
mlflow_logger.log_evaluation_run(
    decision=decision,
    query=request.query,  # Not in decision, only in MLflow
    response=request.response,
    context=request.context,
    log_full_content=manifest.log_full_content
)
```

### 6.3 Rate Limiting

**File**: `src/certus_evaluate/middleware/rate_limit.py`

```python
from fastapi import Request, HTTPException, status
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# Apply to FastAPI app
app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rate limit endpoint
@app.post("/v1/evaluate")
@limiter.limit("100/minute")  # 100 requests per minute per IP
async def evaluate(request: Request, eval_request: EvaluateRequest):
    ...
```

---

## 7. Error Handling

### 7.1 Error Taxonomy

```python
# File: src/certus_evaluate/exceptions.py
from fastapi import HTTPException, status
from typing import Optional, Dict, Any

class EvaluateException(Exception):
    """Base exception for certus-evaluate"""
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Dict[str, Any]] = None,
        fallback: str = "Continue without evaluation"
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.fallback = fallback
        super().__init__(message)

# Client errors (4xx)
class InvalidRequestError(EvaluateException):
    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            error_code="invalid_request",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
            fallback="Fix request and retry"
        )

class UnauthorizedError(EvaluateException):
    def __init__(self, message: str = "Invalid or missing authentication"):
        super().__init__(
            error_code="unauthorized",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            fallback="Provide valid authentication token"
        )

class ForbiddenError(EvaluateException):
    def __init__(self, message: str, workspace_id: str):
        super().__init__(
            error_code="forbidden",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details={"workspace_id": workspace_id},
            fallback="Request access to this workspace"
        )

class ManifestNotFoundError(EvaluateException):
    def __init__(self, manifest_uri: str):
        super().__init__(
            error_code="manifest_not_found",
            message=f"Manifest not found: {manifest_uri}",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"manifest_uri": manifest_uri},
            fallback="Check manifest URI or create manifest"
        )

# Server errors (5xx)
class EvaluatorTimeoutError(EvaluateException):
    def __init__(self, evaluator: str, timeout_ms: int):
        super().__init__(
            error_code="evaluator_timeout",
            message=f"{evaluator} evaluator timed out",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details={"evaluator": evaluator, "timeout_ms": timeout_ms},
            fallback="Response generated without quality evaluation"
        )

class IntegrityServiceError(EvaluateException):
    def __init__(self, message: str):
        super().__init__(
            error_code="integrity_service_error",
            message=f"certus-integrity error: {message}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            fallback="Evaluation completed but not signed"
        )

class EvaluationServiceError(EvaluateException):
    def __init__(self, message: str):
        super().__init__(
            error_code="evaluation_service_unavailable",
            message=message,
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            fallback="Response generated without quality evaluation"
        )
```

### 7.2 Error Handler

```python
# File: src/certus_evaluate/api/error_handlers.py
from fastapi import Request
from fastapi.responses import JSONResponse
from .exceptions import EvaluateException

async def evaluate_exception_handler(
    request: Request,
    exc: EvaluateException
) -> JSONResponse:
    """Handle custom evaluation exceptions"""

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details,
            "fallback": exc.fallback,
            "retry_after_ms": 30000 if exc.status_code == 503 else None,
            "trace_id": request.headers.get("X-Trace-ID")
        }
    )

# Register in FastAPI app
app.add_exception_handler(EvaluateException, evaluate_exception_handler)
```

---

## 8. Example Flows

### 8.1 Happy Path: Successful Evaluation

**Step-by-step flow**:

1. **Certus-Ask receives user query**:

```python
query = "What is Certus?"
workspace_id = "acme"
```

2. **Certus-Ask generates response**:

```python
response = await rag_pipeline.run(query)
# response = {
#     "answer": "Certus is a trust automation platform...",
#     "context": ["Certus TAP provides...", "The framework..."]
# }
```

3. **Certus-Ask calls evaluation API**:

```http
POST /v1/evaluate HTTP/1.1
Authorization: Bearer <token>

{
  "workspace_id": "acme",
  "query": "What is Certus?",
  "response": "Certus is a trust automation platform...",
  "context": ["Certus TAP provides...", "The framework..."],
  "manifest_uri": "certus://manifests/acme/2025-01",
  "mode": "shadow",
  "timeout_ms": 2000,
  "trace_id": "trace_abc123"
}
```

4. **certus-evaluate processes**:

```python
# Fetch manifest
manifest = await manifest_store.get("certus://manifests/acme/2025-01")

# Run RAGAS metrics
faithfulness = await ragas.evaluate(query, response, context)  # 0.85
relevancy = await ragas.evaluate_relevancy(query, response)    # 0.78

# Run guardrails
pii_violations = await presidio.analyze(response)  # []
injection = await llm_guard.check_injection(query)  # None

# Create decision
decision = IntegrityDecision(
    workspace_id="acme",
    query_hash=hash_content(query),
    response_hash=hash_content(response),
    context_hashes=[hash_content(c) for c in context],
    metrics=[
        MetricScore(name="faithfulness", value=0.85, threshold=0.7, passed=True, framework="ragas"),
        MetricScore(name="answer_relevancy", value=0.78, threshold=0.6, passed=True, framework="ragas")
    ],
    guardrail_violations=[],
    outcome="pass",
    overall_score=0.82,
    manifest_uri="certus://manifests/acme/2025-01",
    mode="shadow",
    processing_time_ms=1847
)

# Submit to integrity
evidence = await integrity_client.submit_decision(decision)
decision.evidence_id = evidence["evidence_id"]

# Log to MLflow
mlflow_run_id = mlflow_logger.log_evaluation_run(decision, query, response, context)
```

5. **certus-evaluate returns**:

```json
{
  "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
  "passed": true,
  "evidence_id": "evi_a1b2c3d4e5f6",
  "metrics": {
    "faithfulness": 0.85,
    "answer_relevancy": 0.78
  },
  "overall_score": 0.82,
  "guardrail_violations": [],
  "processing_time_ms": 1847,
  "mode": "shadow",
  "skipped": false,
  "mlflow_run_id": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
  "trace_id": "trace_abc123"
}
```

6. **Certus-Ask returns to user**:

```json
{
  "answer": "Certus is a trust automation platform...",
  "context": [...],
  "evaluation": {
    "passed": true,
    "score": 0.82,
    "evidence_id": "evi_a1b2c3d4e5f6"
  }
}
```

### 8.2 Error Path: Evaluation Timeout

**Step-by-step flow**:

1. **Certus-Ask calls evaluation API** (same as happy path)

2. **RAGAS evaluator times out**:

```python
try:
    faithfulness = await asyncio.wait_for(
        ragas.evaluate(...),
        timeout=2.0
    )
except asyncio.TimeoutError:
    logger.warning("RAGAS timeout", extra={"metric": "faithfulness"})
    raise EvaluatorTimeoutError("ragas", 2000)
```

3. **certus-evaluate catches timeout**:

```python
try:
    result = await evaluate_with_timeout(request)
except EvaluatorTimeoutError as e:
    # Return skipped response instead of error
    return SkippedEvaluateResponse(
        skipped=True,
        skip_reason="evaluator_timeout",
        processing_time_ms=2500,
        trace_id=request.trace_id
    )
```

4. **certus-evaluate returns 200 OK (skipped)**:

```json
{
  "evaluation_id": null,
  "skipped": true,
  "skip_reason": "evaluator_timeout",
  "evidence_id": null,
  "metrics": {},
  "guardrail_violations": [],
  "processing_time_ms": 2500,
  "trace_id": "trace_abc123"
}
```

5. **Certus-Ask logs warning and continues**:

```python
if evaluation_result.get("skipped"):
    logger.warning(
        "Evaluation skipped",
        extra={
            "reason": evaluation_result["skip_reason"],
            "trace_id": trace_id
        }
    )

# Still return response to user
return {
    "answer": response["answer"],
    "context": response["context"],
    "evaluation": {"skipped": True, "reason": "timeout"}
}
```

### 8.3 Circuit Breaker Activation

**Scenario**: certus-integrity service is down, circuit breaker opens.

1. **First 3 requests fail**:

```python
for i in range(3):
    try:
        await integrity_client.submit_decision(decision)
    except IntegrityServiceError:
        circuit_breaker.record_failure()
        # Still return evaluation results, just not signed
```

2. **Circuit breaker opens on 3rd failure**:

```python
if circuit_breaker.failure_count >= 3:
    circuit_breaker.open()
    logger.error("Circuit breaker opened for certus-integrity")
    metrics.circuit_breaker_state.labels(workspace_id="acme").set(1)
```

3. **Next requests skip integrity submission**:

```python
if circuit_breaker.is_open():
    logger.warning("Circuit breaker open, skipping integrity submission")
    # Return evaluation results without evidence_id
    return EvaluateResponse(
        evaluation_id=decision.decision_id,
        passed=True,
        evidence_id=None,  # Not signed
        metrics={...},
        mode="shadow",
        ...
    )
```

4. **After 30 seconds, circuit breaker half-opens**:

```python
# Test with single request
try:
    await integrity_client.submit_decision(decision)
    circuit_breaker.close()
    logger.info("Circuit breaker closed, certus-integrity recovered")
    metrics.circuit_breaker_state.labels(workspace_id="acme").set(0)
except:
    circuit_breaker.open()
    logger.warning("Circuit breaker test failed, remaining open")
```

### 8.4 Guardrail Violation (PII Detected)

**Scenario**: Response contains PII (email address).

1. **Response generated with PII**:

```python
response = "Contact us at support@acme.com for help."
```

2. **Presidio detects PII**:

```python
violations = await presidio.analyze(response)
# violations = [{
#     "entity_type": "EMAIL_ADDRESS",
#     "start": 11,
#     "end": 28,
#     "score": 0.95
# }]
```

3. **Create guardrail violation (PII-safe)**:

```python
violation = GuardrailViolation(
    guardrail_type="pii",
    severity="high",
    confidence=0.95,
    content_hash=hash_content("support@acme.com"),  # Hash only
    location="char 11-28",
    remediation="Redact email address"
)
```

4. **In shadow mode, log but don't block**:

```python
if manifest.guardrails["pii"].block_on_violation and mode == "enforce":
    # Enforce mode: block response
    raise GuardrailViolationError("PII detected in response")
else:
    # Shadow mode: log and continue
    logger.warning(
        "PII detected in shadow mode",
        extra={"violation": violation.model_dump()}
    )
```

5. **Return with violation metadata**:

```json
{
  "evaluation_id": "550e8400-e29b-41d4-a716-446655440000",
  "passed": false,
  "evidence_id": "evi_a1b2c3d4e5f6",
  "metrics": {...},
  "guardrail_violations": [
    {
      "guardrail_type": "pii",
      "severity": "high",
      "confidence": 0.95,
      "content_hash": "sha256:...",
      "location": "char 11-28",
      "remediation": "Redact email address"
    }
  ],
  "processing_time_ms": 1200,
  "mode": "shadow"
}
```

---

## Appendix

### A. Phase 1 Implementation Checklist

- [ ] **Core Service**
  - [ ] FastAPI application skeleton
  - [ ] Configuration management (Settings)
  - [ ] Structured logging setup
  - [ ] Health check endpoint
- [ ] **Data Models**
  - [ ] IntegrityDecision schema
  - [ ] EvaluationManifest schema
  - [ ] API request/response models
  - [ ] Validation tests
- [ ] **Evaluation Engine**
  - [ ] RAGAS integration (faithfulness, relevancy)
  - [ ] DeepEval integration (hallucination metric)
  - [ ] Timeout handling
  - [ ] Error handling
- [ ] **Guardrails** (Basic)
  - [ ] PII detection (Presidio)
  - [ ] Prompt injection (LLM Guard)
  - [ ] Violation sanitization
- [ ] **Integration**
  - [ ] certus-integrity client
  - [ ] Manifest store client
  - [ ] MLflow logging
  - [ ] OpenTelemetry tracing
- [ ] **Resilience**
  - [ ] Circuit breaker implementation
  - [ ] Graceful degradation
  - [ ] Timeout handling
- [ ] **Certus-Ask Client**
  - [ ] REST client with circuit breaker
  - [ ] Non-blocking evaluation wrapper
  - [ ] Integration tests
- [ ] **Testing**
  - [ ] Unit tests (models, utils)
  - [ ] Integration tests (end-to-end)
  - [ ] Performance tests (latency)
- [ ] **Documentation**
  - [ ] API reference
  - [ ] Integration guide
  - [ ] Deployment guide
- [ ] **Deployment**
  - [ ] Dockerfile
  - [ ] Kubernetes manifests
  - [ ] CI/CD pipeline

### B. Open Questions (from Proposal)

- [ ] **[P0, Phase 1]** What is acceptable evaluation timeout for inline mode (2s? 5s?)? – **Owner:** Performance Team
- [ ] **[P0, Phase 1]** Should circuit breaker state be per-workspace or global? – **Owner:** Architecture
- [ ] **[P1, Phase 2]** How should we surface guardrail failures to end users (custom message vs generic)? – **Owner:** Product

### C. Dependencies

**Python Packages** (`pyproject.toml`):

```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.109.0"
uvicorn = "^0.27.0"
pydantic = "^2.5.0"
pydantic-settings = "^2.1.0"
httpx = "^0.26.0"
ragas = "^0.1.0"
deepeval = "^0.21.0"
presidio-analyzer = "^2.2.0"
mlflow = "^2.9.0"
opentelemetry-api = "^1.22.0"
opentelemetry-sdk = "^1.22.0"
opentelemetry-exporter-otlp = "^1.22.0"
prometheus-client = "^0.19.0"
python-jose = "^3.3.0"
circuitbreaker = "^1.4.0"
slowapi = "^0.1.9"

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"
pytest-asyncio = "^0.23.0"
pytest-cov = "^4.1.0"
black = "^24.0.0"
ruff = "^0.1.0"
mypy = "^1.8.0"
```

### D. File Structure

```
certus-evaluate/
├── src/
│   └── certus_evaluate/
│       ├── __init__.py
│       ├── main.py                 # FastAPI app
│       ├── config.py               # Settings
│       ├── models/
│       │   ├── __init__.py
│       │   ├── integrity.py        # IntegrityDecision
│       │   ├── manifest.py         # EvaluationManifest
│       │   └── api.py              # Request/Response models
│       ├── api/
│       │   ├── __init__.py
│       │   ├── routes.py           # API endpoints
│       │   └── error_handlers.py
│       ├── engine/
│       │   ├── __init__.py
│       │   ├── evaluator.py        # Main evaluation engine
│       │   ├── ragas_adapter.py
│       │   └── deepeval_adapter.py
│       ├── guardrails/
│       │   ├── __init__.py
│       │   ├── pii_detector.py
│       │   └── injection_detector.py
│       ├── clients/
│       │   ├── __init__.py
│       │   ├── integrity_client.py
│       │   └── manifest_client.py
│       ├── observability/
│       │   ├── __init__.py
│       │   ├── logging.py
│       │   ├── metrics.py
│       │   ├── tracing.py
│       │   └── mlflow_logger.py
│       ├── security/
│       │   ├── __init__.py
│       │   ├── auth.py
│       │   └── hashing.py
│       └── exceptions.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── k8s/
│   ├── deployment.yaml
│   ├── service.yaml
│   ├── configmap.yaml
│   └── secrets.yaml
├── .env.example
├── Dockerfile
├── pyproject.toml
└── README.md
```

---

## Revision History

| Date       | Version | Changes                   |
| ---------- | ------- | ------------------------- |
| 2024-12-21 | 0.1.0   | Initial draft for Phase 1 |

---

**Next Steps**: Review with implementation team, resolve P0 open questions, begin Phase 1 development.
