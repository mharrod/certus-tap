"""Stack bootstrap helpers placeholder.

Future phases will orchestrate TAP services (OpenSearch, LocalStack, backend)
directly from the Dagger module.  For Phase 1 we only expose a small shim so
imports remain stable.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StackConfig:
    """Placeholder configuration for TAP bootstrap logic."""

    compose_file: str = "docker-compose.yml"
    services: tuple[str, ...] = ("ask-certus-backend", "opensearch", "localstack")
