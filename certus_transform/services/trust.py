"""Client for Certus-Trust service (non-repudiation verification)."""

from __future__ import annotations

from typing import Any

import httpx

from certus_transform.core.config import settings


class TrustClient:
    """Async client for Certus-Trust non-repudiation verification."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None, verify_ssl: bool | None = None):
        """Initialize Trust client with configuration."""
        self.base_url = base_url or settings.trust_base_url
        self.api_key = api_key or settings.trust_api_key
        self.verify_ssl = verify_ssl if verify_ssl is not None else settings.trust_verify_ssl

    async def verify_chain(
        self,
        artifact_locations: dict[str, Any],
        signatures: dict[str, Any],
        sigstore_entry_id: str | None = None,
    ) -> VerifyChainResponse:
        """
        Verify complete non-repudiation chain.

        Args:
            artifact_locations: Dict with S3 and Registry URIs
            signatures: Dict with inner and outer signature data
            sigstore_entry_id: Optional Rekor entry ID for verification

        Returns:
            VerifyChainResponse with verification results
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload = {
            "artifact_locations": artifact_locations,
            "signatures": signatures,
            "sigstore_entry_id": sigstore_entry_id,
        }

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
    def verification_proof(self) -> dict[str, Any]:
        """Proof of verification for storage in metadata."""
        return {
            "chain_verified": self.chain_verified,
            "inner_signature_valid": self._data.get("inner_signature_valid", False),
            "outer_signature_valid": self._data.get("outer_signature_valid", False),
            "chain_unbroken": self._data.get("chain_unbroken", False),
            "signer_inner": self._data.get("signer_inner"),
            "signer_outer": self._data.get("signer_outer"),
            "sigstore_timestamp": self._data.get("sigstore_timestamp"),
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
