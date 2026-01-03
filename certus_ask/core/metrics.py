"""Service metrics tracking for certus_ask.

Provides in-memory counters for monitoring ingestion and query activity.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class IngestionMetrics:
    """Metrics for document ingestion operations."""

    total_ingestions: int = 0
    successful_ingestions: int = 0
    failed_ingestions: int = 0
    documents_indexed: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_ingestion(
        self,
        source: str,
        document_count: int = 0,
        success: bool = True,
    ) -> None:
        """Record an ingestion operation.

        Args:
            source: Ingestion source type (e.g., "document", "github", "sarif")
            document_count: Number of documents indexed
            success: Whether ingestion succeeded
        """
        with self._lock:
            self.total_ingestions += 1
            if success:
                self.successful_ingestions += 1
                self.documents_indexed += document_count
            else:
                self.failed_ingestions += 1

            # Track by source
            self.by_source[source] = self.by_source.get(source, 0) + 1

    def to_dict(self) -> dict:
        """Export metrics as dictionary."""
        with self._lock:
            return {
                "total": self.total_ingestions,
                "successful": self.successful_ingestions,
                "failed": self.failed_ingestions,
                "documents_indexed": self.documents_indexed,
                "by_source": dict(self.by_source),
            }


@dataclass
class QueryMetrics:
    """Metrics for RAG query operations."""

    total_queries: int = 0
    successful_queries: int = 0
    failed_queries: int = 0
    total_response_time: float = 0.0
    min_response_time: float = float("inf")
    max_response_time: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def record_query(
        self,
        response_time: float,
        success: bool = True,
    ) -> None:
        """Record a query operation.

        Args:
            response_time: Query duration in seconds
            success: Whether query succeeded
        """
        with self._lock:
            self.total_queries += 1
            if success:
                self.successful_queries += 1
                self.total_response_time += response_time
                self.min_response_time = min(self.min_response_time, response_time)
                self.max_response_time = max(self.max_response_time, response_time)
            else:
                self.failed_queries += 1

    @property
    def avg_response_time(self) -> float:
        """Calculate average response time."""
        with self._lock:
            if self.successful_queries == 0:
                return 0.0
            return self.total_response_time / self.successful_queries

    def to_dict(self) -> dict:
        """Export metrics as dictionary."""
        with self._lock:
            return {
                "total": self.total_queries,
                "successful": self.successful_queries,
                "failed": self.failed_queries,
                "avg_response_time_seconds": self.avg_response_time,
                "min_response_time_seconds": self.min_response_time if self.min_response_time != float("inf") else 0.0,
                "max_response_time_seconds": self.max_response_time,
            }


# Global metrics instances
_ingestion_metrics = IngestionMetrics()
_query_metrics = QueryMetrics()
_service_start_time = time.time()


def get_ingestion_metrics() -> IngestionMetrics:
    """Get global ingestion metrics instance."""
    return _ingestion_metrics


def get_query_metrics() -> QueryMetrics:
    """Get global query metrics instance."""
    return _query_metrics


def get_service_uptime() -> float:
    """Get service uptime in seconds."""
    return time.time() - _service_start_time
