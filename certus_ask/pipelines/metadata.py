from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any

from haystack import Document

from certus_ask.schemas.metadata import MetadataEnvelope

__all__ = ["enrich_documents_with_metadata"]


def enrich_documents_with_metadata(
    documents: list[Document],
    *,
    workspace_id: str,
    ingestion_id: str,
    source: str,
    source_location: str | None = None,
    extra_meta: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Apply metadata envelopes to documents and return the envelopes."""

    timestamp = datetime.now(timezone.utc)
    envelopes: list[dict[str, Any]] = []

    for doc in documents:
        meta = dict(doc.meta or {})
        doc_ingestion_id = ingestion_id or meta.get("ingestion_id") or str(uuid.uuid4())
        location = source_location or meta.get("file_path") or meta.get("url") or meta.get("source_location")
        payload_extra = dict(meta.get("metadata_extra") or {})
        if extra_meta:
            payload_extra.update(extra_meta)

        envelope = MetadataEnvelope(
            version="1.0",
            workspace_id=workspace_id,
            ingestion_id=doc_ingestion_id,
            document_id=str(doc.id),
            source=source,
            source_location=location,
            content_hash=_hash_content(doc.content),
            captured_at=timestamp,
            extra=payload_extra,
        )
        envelope_dict = envelope.as_meta()

        meta.update({
            "ingestion_id": doc_ingestion_id,
            "source": source,
            "metadata_envelope": envelope_dict,
        })
        if location:
            meta.setdefault("source_location", location)

        doc.meta = meta
        envelopes.append(envelope_dict)

    return envelopes


def _hash_content(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
