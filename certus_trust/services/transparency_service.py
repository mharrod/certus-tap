"""Transparency log service with mock and production implementations."""

import hashlib
import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from fastapi import Request

from ..api.models import TransparencyLogEntry
from ..clients import RekorClient
from ..config import CertusTrustSettings

logger = logging.getLogger(__name__)


class TransparencyService(ABC):
    """Abstract transparency log service interface."""

    @abstractmethod
    async def get_entry(self, entry_id: str, include_proof: bool = True) -> Optional[TransparencyLogEntry]:
        """Get a transparency log entry by ID."""
        pass

    @abstractmethod
    async def query_log(
        self,
        assessment_id: Optional[str] = None,
        signer: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[TransparencyLogEntry]:
        """Query transparency log with filters."""
        pass


class MockTransparencyService(TransparencyService):
    """Mock transparency service for development and testing."""

    def __init__(self):
        """Initialize mock transparency service."""
        self._transparency_log: list[dict] = []

    def _build_merkle_proof(self, entry_index: int) -> dict:
        """Build a mock Merkle proof."""
        tree_size = len(self._transparency_log)
        proof_hashes = []

        current_index = entry_index
        level = 0
        while current_index < tree_size - 1:
            sibling_index = current_index ^ 1
            mock_data = f"node-{sibling_index}-level-{level}".encode()
            proof_hash = hashlib.sha256(mock_data).hexdigest()
            proof_hashes.append(f"sha256:{proof_hash}")
            current_index = current_index // 2
            level += 1

        return {
            "tree_size": tree_size,
            "leaf_index": entry_index,
            "hashes": proof_hashes,
            "root_hash": f"sha256:{hashlib.sha256(f'root-{tree_size}'.encode()).hexdigest()}",
        }

    async def get_entry(self, entry_id: str, include_proof: bool = True) -> Optional[TransparencyLogEntry]:
        """Get mock transparency log entry."""
        for idx, entry in enumerate(self._transparency_log):
            if entry.get("entry_id") == entry_id:
                log_entry = TransparencyLogEntry(
                    entry_id=entry_id,
                    artifact=entry.get("artifact"),
                    timestamp=entry.get("timestamp", datetime.now(timezone.utc)),
                    signer=entry.get("signer", "unknown"),
                    signature=entry.get("signature", ""),
                )

                if include_proof:
                    log_entry.proof = self._build_merkle_proof(idx)

                logger.info(
                    f"[MOCK] Retrieved transparency entry: {entry_id}",
                    extra={"event_type": "transparency_query", "entry_id": entry_id, "mode": "mock"},
                )

                return log_entry

        return None

    async def query_log(
        self,
        assessment_id: Optional[str] = None,
        signer: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[TransparencyLogEntry]:
        """Query mock transparency log."""
        results = self._transparency_log.copy()

        # Apply filters
        if assessment_id:
            results = [e for e in results if e.get("assessment_id") == assessment_id]

        if signer:
            results = [e for e in results if e.get("signer") == signer]

        # Apply pagination
        results = results[offset : offset + limit]

        # Convert to models
        entries = []
        for entry in results:
            entries.append(
                TransparencyLogEntry(
                    entry_id=entry.get("entry_id", ""),
                    artifact=entry.get("artifact"),
                    timestamp=entry.get("timestamp", datetime.now(timezone.utc)),
                    signer=entry.get("signer", "unknown"),
                    signature=entry.get("signature", ""),
                )
            )

        logger.info(
            f"[MOCK] Queried transparency log: {len(entries)} results",
            extra={
                "event_type": "transparency_query",
                "results_count": len(entries),
                "mode": "mock",
            },
        )

        return entries


class ProductionTransparencyService(TransparencyService):
    """Production transparency service using real Rekor."""

    def __init__(self, rekor_client: RekorClient, settings: CertusTrustSettings):
        """Initialize production transparency service.

        Args:
            rekor_client: Rekor transparency log client
            settings: Service configuration
        """
        self.rekor_client = rekor_client
        self.settings = settings

    async def get_entry(self, entry_id: str, include_proof: bool = True) -> Optional[TransparencyLogEntry]:
        """Get entry from real Rekor."""
        try:
            # Get entry from Rekor
            entry = await self.rekor_client.get_entry(entry_id)

            if not entry:
                return None

            # Get inclusion proof if requested
            proof = None
            if include_proof:
                proof = await self.rekor_client.get_inclusion_proof(entry_id)

            # Extract data from Rekor entry (simplified)
            # TODO: Proper parsing of Rekor entry structure
            artifact = None  # Extract from entry body
            signer = "certus-trust@certus.cloud"  # Extract from certificate
            signature = ""  # Extract from entry

            log_entry = TransparencyLogEntry(
                entry_id=entry_id,
                artifact=artifact,
                timestamp=datetime.fromtimestamp(entry.get("integratedTime", 0), tz=timezone.utc),
                signer=signer,
                signature=signature,
                proof=proof,
            )

            logger.info(
                f"[PRODUCTION] Retrieved transparency entry: {entry_id}",
                extra={
                    "event_type": "transparency_query",
                    "entry_id": entry_id,
                    "rekor_index": entry.get("logIndex"),
                    "mode": "production",
                },
            )

            return log_entry

        except Exception as e:
            logger.error(
                f"[PRODUCTION] Failed to get transparency entry: {e}",
                extra={"error": str(e), "entry_id": entry_id, "mode": "production"},
            )
            return None

    async def query_log(
        self,
        assessment_id: Optional[str] = None,
        signer: Optional[str] = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[TransparencyLogEntry]:
        """Query real Rekor log."""
        # NOTE: Rekor doesn't support all these query parameters directly
        # This is a simplified implementation
        # In production, you'd need to implement more sophisticated querying

        logger.warning(
            "[PRODUCTION] Advanced transparency log querying not fully implemented",
            extra={"mode": "production"},
        )

        # For now, return empty list
        # Full implementation would involve:
        # 1. Search by hash if we have artifact info
        # 2. Iterate through log entries with pagination
        # 3. Filter client-side (not ideal but Rekor has limited query support)

        return []


def get_transparency_service(request: Request) -> TransparencyService:
    """Dependency injection for transparency service.

    Returns mock or production service based on configuration.

    Args:
        request: FastAPI request (contains app state)

    Returns:
        TransparencyService implementation (mock or production)
    """
    app = request.app
    settings: CertusTrustSettings = app.state.settings

    if settings.mock_sigstore:
        # Return mock service
        if not hasattr(app.state, "mock_transparency_service"):
            app.state.mock_transparency_service = MockTransparencyService()
        return app.state.mock_transparency_service
    else:
        # Return production service
        if not hasattr(app.state, "production_transparency_service"):
            rekor_client = app.state.rekor_client
            app.state.production_transparency_service = ProductionTransparencyService(rekor_client, settings)
        return app.state.production_transparency_service
