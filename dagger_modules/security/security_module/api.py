"""API regression placeholder used by future phases."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApiTestSuite:
    """Represents a Postman/Newman suite placeholder."""

    name: str = "baseline"
    description: str = "API regression plan will be defined in Phase 2."
