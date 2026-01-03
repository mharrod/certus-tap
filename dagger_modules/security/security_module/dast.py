"""Placeholder DAST orchestration module.

Phase 2 of the roadmap will populate this module with OWASP ZAP, API fuzzing,
and supporting stack bootstrap helpers.  For Phase 1 we only establish the
module so documentation and imports remain stable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class DastPlan:
    """Represents a future DAST plan definition."""

    name: str = "zap-baseline"
    description: str = "Placeholder definition for future OWASP ZAP orchestration."
