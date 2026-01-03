from __future__ import annotations

import time
from typing import Any

import structlog
from haystack import Document, component
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy

from certus_ask.pipelines.metadata import enrich_documents_with_metadata

logger = structlog.get_logger(__name__)


@component
class LoggingDocumentWriter:
    """DocumentWriter wrapper that logs indexing events and captures metadata envelopes."""

    def __init__(
        self,
        document_store,
        policy: DuplicatePolicy = DuplicatePolicy.SKIP,
        metadata_context: dict[str, Any] | None = None,
    ):
        self.writer = DocumentWriter(document_store, policy=policy)
        self.document_store = document_store
        self.policy = policy
        self.metadata_context = metadata_context or {}

    @component.output_types(documents_written=int, metadata_preview=list[dict[str, Any]])
    def run(self, documents: list[Document]) -> dict[str, object]:
        """Write documents to the store with metadata enrichment and structured logging."""
        if not documents:
            return {"documents_written": 0, "metadata_preview": []}

        metadata_preview: list[dict[str, Any]] = []
        if self.metadata_context:
            try:
                metadata_preview = enrich_documents_with_metadata(documents, **self.metadata_context)
            except TypeError:
                filtered = {k: v for k, v in self.metadata_context.items() if v is not None}
                metadata_preview = enrich_documents_with_metadata(documents, **filtered)

        logger.info(
            event="document.indexing_start",
            document_count=len(documents),
        )

        start_time = time.time()
        try:
            result = self.writer.run(documents=documents)
        except Exception as exc:  # pragma: no cover - passthrough to Haystack component
            logger.error(
                event="document.indexing_failed",
                document_count=len(documents),
                error=str(exc),
                exc_info=True,
            )
            raise

        written_count = result.get("documents_written", 0)
        duration_ms = int((time.time() - start_time) * 1000)
        workspace_id = self.metadata_context.get("workspace_id", "default")
        index_name = f"ask_certus_{workspace_id}"
        logger.info(
            event="document.indexed",
            index=index_name,
            chunks_indexed=written_count,
            duration_ms=duration_ms,
        )

        return {
            "documents_written": written_count,
            "metadata_preview": metadata_preview,
        }
