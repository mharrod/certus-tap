from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

__all__ = ["MetadataEnvelope"]


class MetadataEnvelope(BaseModel):
    """Evidence envelope describing how a document entered the system."""

    version: str = Field(default="1.0", description="Envelope schema version.")
    workspace_id: str = Field(..., description="Workspace identifier for multi-tenant isolation.")
    ingestion_id: str = Field(..., description="Ingestion run identifier.")
    document_id: str = Field(..., description="Haystack document identifier.")
    source: str = Field(..., description="Connector emitting the document (upload, folder, web, etc.).")
    source_location: str | None = Field(None, description="URI, path, or bucket key associated with the document.")
    content_hash: str = Field(..., description="SHA256 hash of the document content.")
    captured_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when metadata was captured.",
    )
    extra: dict[str, Any] = Field(default_factory=dict, description="Connector-specific metadata.")

    def as_meta(self) -> dict[str, Any]:
        """Convert the envelope into a JSON-serialisable dict."""

        data = self.model_dump()
        data["captured_at"] = self.captured_at.isoformat()
        return data
