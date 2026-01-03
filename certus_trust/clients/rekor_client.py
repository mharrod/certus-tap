"""Rekor transparency log client wrapper."""

import base64
import logging
from datetime import datetime, timezone
from typing import Any, Optional

import httpx

from ..config import CertusTrustSettings

logger = logging.getLogger(__name__)


class RekorClient:
    """
    Direct HTTP client for Rekor transparency log operations.

    Provides interface for:
    - Submitting entries to Rekor transparency log
    - Querying entries by UUID
    - Searching entries by artifact hash
    - Retrieving inclusion proofs

    Uses direct HTTP API calls instead of sigstore library internals.
    """

    def __init__(self, settings: CertusTrustSettings):
        """Initialize Rekor client.

        Args:
            settings: Certus-Trust configuration
        """
        self.settings = settings
        self.rekor_url = settings.rekor_addr
        logger.info(f"Initialized Rekor client for {self.rekor_url}")

    async def submit_entry(
        self,
        artifact_hash: str,
        signature: bytes,
        certificate: Optional[bytes] = None,
        public_key: Optional[bytes] = None,
    ) -> dict[str, Any]:
        """
        Submit an entry to Rekor transparency log.

        Args:
            artifact_hash: SHA256 hash of the artifact
            signature: Signature bytes
            certificate: Optional certificate (for keyless signing)
            public_key: Optional public key (for key-based signing)

        Returns:
            Dictionary with:
                - uuid: Rekor entry UUID
                - index: Log index
                - integrated_time: Timestamp from Rekor
                - log_id: Log identifier
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Prepare entry data - Rekor expects base64-encoded content
                entry_data = {
                    "kind": "hashedrekord",
                    "apiVersion": "0.0.1",
                    "spec": {
                        "signature": {
                            "content": base64.b64encode(signature).decode("utf-8"),
                            "publicKey": {
                                "content": (
                                    base64.b64encode(certificate).decode("utf-8")
                                    if certificate
                                    else base64.b64encode(public_key).decode("utf-8")
                                    if public_key
                                    else None
                                )
                            },
                        },
                        "data": {"hash": {"algorithm": "sha256", "value": artifact_hash}},
                    },
                }

                # Submit to Rekor
                response = await client.post(
                    f"{self.rekor_url}/api/v1/log/entries",
                    json=entry_data,
                )
                response.raise_for_status()

                # Parse response
                entry = response.json()

                # Extract UUID from Location header or response
                location = response.headers.get("Location", "")
                uuid = location.split("/")[-1] if location else next(iter(entry.keys()))

                entry_details = entry[uuid]

                result = {
                    "uuid": uuid,
                    "index": entry_details.get("logIndex"),
                    "integrated_time": datetime.fromtimestamp(entry_details.get("integratedTime", 0), tz=timezone.utc),
                    "log_id": entry_details.get("logID"),
                    "body": entry_details.get("body"),
                }

                logger.info(
                    f"Submitted entry to Rekor: {uuid}",
                    extra={
                        "event_type": "rekor_entry_submitted",
                        "uuid": uuid,
                        "index": result["index"],
                    },
                )

                return result

        except httpx.HTTPError as e:
            logger.error(f"Failed to submit to Rekor: {e}")
            raise RuntimeError(f"Rekor submission failed: {e}")

    async def get_entry(self, uuid: str) -> Optional[dict[str, Any]]:
        """
        Retrieve an entry from Rekor by UUID.

        Args:
            uuid: Rekor entry UUID

        Returns:
            Entry data or None if not found
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.rekor_url}/api/v1/log/entries/{uuid}")

                if response.status_code == 404:
                    return None

                response.raise_for_status()
                entry = response.json()

                return entry.get(uuid)

        except httpx.HTTPError as e:
            logger.error(f"Failed to get Rekor entry {uuid}: {e}")
            return None

    async def search_by_hash(self, artifact_hash: str) -> list[dict[str, Any]]:
        """
        Search Rekor for entries matching an artifact hash.

        Args:
            artifact_hash: SHA256 hash to search for

        Returns:
            List of matching entries
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.rekor_url}/api/v1/index/retrieve", json={"hash": f"sha256:{artifact_hash}"}
                )
                response.raise_for_status()

                uuids = response.json()

                # Fetch full entries for each UUID
                entries = []
                for uuid in uuids:
                    entry = await self.get_entry(uuid)
                    if entry:
                        entries.append(entry)

                return entries

        except httpx.HTTPError as e:
            logger.error(f"Failed to search Rekor: {e}")
            return []

    async def get_inclusion_proof(self, uuid: str, tree_size: Optional[int] = None) -> Optional[dict[str, Any]]:
        """
        Get inclusion proof for an entry.

        Args:
            uuid: Rekor entry UUID
            tree_size: Optional tree size for the proof

        Returns:
            Inclusion proof data
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.rekor_url}/api/v1/log/entries/{uuid}/proof"
                params = {}
                if tree_size:
                    params["treeSize"] = tree_size

                response = await client.get(url, params=params)
                response.raise_for_status()

                return response.json()

        except httpx.HTTPError as e:
            logger.error(f"Failed to get inclusion proof: {e}")
            return None
