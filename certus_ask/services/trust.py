"""Client for Certus-Trust service (non-repudiation verification)."""

from __future__ import annotations

from typing import Any

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from certus_ask.core.config import get_settings

logger = structlog.get_logger(__name__)


class TrustClient:
    """Async client for Certus-Trust non-repudiation verification."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        verify_ssl: bool | None = None,
    ):
        """Initialize Trust client with configuration."""
        settings = get_settings()
        self.base_url = base_url or settings.trust_base_url
        self.api_key = api_key or settings.trust_api_key
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.trust_verify_ssl

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def verify_chain(
        self,
        artifact_locations: dict[str, Any],
        signatures: dict[str, Any],
        sigstore_entry_id: str | None = None,
    ) -> VerifyChainResponse:
        """
        Verify complete non-repudiation chain.

        Uses exponential backoff retry for transient network errors:
        - Retry on timeout or connection errors
        - 3 attempts max
        - Wait: 1s, 2s, 4s between retries

        Args:
            artifact_locations: Dict with S3 and Registry URIs
            signatures: Dict with inner and outer signature data
            sigstore_entry_id: Optional Rekor entry ID for verification

        Returns:
            VerifyChainResponse with verification results

        Raises:
            httpx.HTTPStatusError: If verification fails (4xx/5xx responses)
            httpx.TimeoutException: If all retry attempts timeout
            httpx.ConnectError: If service is unreachable after retries
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "artifact_locations": artifact_locations,
            "signatures": signatures,
            "sigstore_entry_id": sigstore_entry_id,
        }

        try:
            async with httpx.AsyncClient(
                base_url=self.base_url,
                headers=headers,
                timeout=60.0,
                verify=self.verify_ssl,
            ) as client:
                response = await client.post(
                    "/v1/verify-chain",
                    json=payload,
                )
                response.raise_for_status()
                return VerifyChainResponse(response.json())
        except httpx.HTTPStatusError as exc:
            logger.error(
                event="trust.verify_chain_failed",
                status_code=exc.response.status_code,
                detail=exc.response.text if exc.response.content else str(exc),
            )
            raise
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.error(
                event="trust.verify_chain_connection_error",
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise
        except Exception as exc:
            logger.error(
                event="trust.verify_chain_error",
                error=str(exc),
                exc_info=True,
            )
            raise


class VerifyChainResponse:
    """Response from Trust verification endpoint."""

    def __init__(self, data: dict[str, Any]):
        """Store verification response data."""
        self._data = data

    @property
    def chain_verified(self) -> bool:
        """Whether entire chain is valid."""
        return self._data.get("chain_verified", False)

    @property
    def signer_outer(self) -> str | None:
        """Trust signer identity."""
        return self._data.get("signer_outer")

    @property
    def sigstore_timestamp(self) -> str | None:
        """Timestamp from Sigstore."""
        return self._data.get("sigstore_timestamp")

    @property
    def verification_proof(self) -> dict[str, Any]:
        """Proof of verification for Neo4j linking and storage."""
        return {
            "chain_verified": self.chain_verified,
            "inner_signature_valid": self._data.get("inner_signature_valid", False),
            "outer_signature_valid": self._data.get("outer_signature_valid", False),
            "chain_unbroken": self._data.get("chain_unbroken", False),
            "signer_inner": self._data.get("signer_inner"),
            "signer_outer": self.signer_outer,
            "sigstore_timestamp": self.sigstore_timestamp,
            "non_repudiation": self._data.get("non_repudiation"),
        }

    @property
    def raw(self) -> dict[str, Any]:
        """Raw verification response data."""
        return self._data


_trust_client: TrustClient | None = None


def get_trust_client() -> TrustClient:
    """Get or create singleton Trust client."""
    global _trust_client
    if _trust_client is None:
        _trust_client = TrustClient()
    return _trust_client
