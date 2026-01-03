from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class IntegrityDecision(BaseModel):
    """
    Represents a single enforcement decision made by the Integrity layer.
    """

    decision_id: str = Field(..., description="Unique identifier for this specific decision event")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Time of the decision")
    trace_id: str = Field(..., description="OpenTelemetry Trace ID")
    span_id: str = Field(..., description="OpenTelemetry Span ID")
    service: str = Field(..., description="Service name issuing the decision")
    decision: Literal["allowed", "denied", "degraded"] = Field(..., description="The outcome")
    reason: str = Field(..., description="Human-readable reason for the decision")
    guardrail: str = Field(..., description="Name of the guardrail (e.g., 'rate_limit', 'graph_budget')")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Contextual metadata (e.g., node_count, budget_limit)"
    )


class IntegrityConfig(BaseModel):
    """
    Configuration for the Integrity layer.
    """

    service_name: str
    shadow_mode: bool = True

    # Rate Limiting
    rate_limit_enabled: bool = True
    rate_limit_per_minute: int = 100

    # Graph Budgets
    graph_budget_enabled: bool = True
    max_graph_nodes: int = 1000
