"""Verification service with mock and production implementations."""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from fastapi import Request

from ..api.models import VerifyRequest, VerifyResponse
from ..clients import RekorClient, SigningClient
from ..config import CertusTrustSettings

logger = logging.getLogger(__name__)


class VerificationService(ABC):
    """Abstract verification service interface."""

    @abstractmethod
    async def verify(self, request: VerifyRequest) -> VerifyResponse:
        """Verify a signature."""
        pass


class MockVerificationService(VerificationService):
    """Mock verification service for development and testing."""

    def __init__(self):
        """Initialize mock verification service."""
        self._transparency_log = []
        self._verification_count = 0
        self._verification_success = 0
        self._verification_failed = 0

    async def verify(self, request: VerifyRequest) -> VerifyResponse:
        """Mock signature verification."""
        self._verification_count += 1
        timestamp = datetime.now(timezone.utc)

        # Mock verification - check against in-memory log
        valid = True
        signer = "certus-assurance@certus.cloud"
        transparency_index = 0

        # Search in transparency log
        for idx, entry in enumerate(self._transparency_log):
            if entry.get("signature") == request.signature and entry.get("artifact") == request.artifact:
                valid = True
                signer = entry.get("signer", signer)
                transparency_index = idx
                break

        # If identity was specified, verify it matches
        if request.identity and request.identity != signer:
            valid = False

        if valid:
            self._verification_success += 1
        else:
            self._verification_failed += 1

        response = VerifyResponse(
            valid=valid,
            verified_at=timestamp,
            signer=signer if valid else "unknown",
            transparency_index=transparency_index if valid else None,
            certificate_chain=None,
        )

        logger.info(
            f"[MOCK] Verified signature: {valid}",
            extra={
                "event_type": "verification_requested",
                "valid": valid,
                "signer": signer,
                "mode": "mock",
            },
        )

        return response


class ProductionVerificationService(VerificationService):
    """Production verification service using real Sigstore."""

    def __init__(
        self,
        rekor_client: RekorClient,
        signing_client: SigningClient,
        settings: CertusTrustSettings,
    ):
        """Initialize production verification service.

        Args:
            rekor_client: Rekor transparency log client
            signing_client: Signing/verification client
            settings: Service configuration
        """
        self.rekor_client = rekor_client
        self.signing_client = signing_client
        self.settings = settings

    async def verify(self, request: VerifyRequest) -> VerifyResponse:
        """Verify signature using real Sigstore."""
        try:
            timestamp = datetime.now(timezone.utc)

            # Convert signature and artifact to bytes
            signature = bytes.fromhex(request.signature)
            artifact_hash = request.artifact.replace("sha256:", "")
            artifact_bytes = bytes.fromhex(artifact_hash)

            # Verify signature cryptographically
            certificate = request.certificate.encode() if request.certificate else None

            is_valid = await self.signing_client.verify_signature(
                artifact_data=artifact_bytes,
                signature=signature,
                certificate=certificate,
            )

            if not is_valid:
                logger.warning(
                    "[PRODUCTION] Cryptographic verification failed",
                    extra={"mode": "production", "artifact": request.artifact},
                )
                return VerifyResponse(
                    valid=False,
                    verified_at=timestamp,
                    signer="unknown",
                    transparency_index=None,
                    certificate_chain=None,
                )

            # Search Rekor for this artifact
            computed_hash = self.signing_client.compute_artifact_hash(artifact_bytes)
            rekor_entries = await self.rekor_client.search_by_hash(computed_hash)

            if not rekor_entries:
                logger.warning(
                    "[PRODUCTION] No Rekor entries found for artifact",
                    extra={"mode": "production", "artifact_hash": computed_hash},
                )
                return VerifyResponse(
                    valid=False,
                    verified_at=timestamp,
                    signer="unknown",
                    transparency_index=None,
                    certificate_chain=None,
                )

            # Get first entry (most recent)
            entry = rekor_entries[0]

            # Extract signer from entry (simplified - real impl would parse cert)
            signer = "certus-trust@certus.cloud"  # TODO: Extract from certificate

            # Check identity if specified
            if request.identity and request.identity != signer:
                logger.warning(
                    f"[PRODUCTION] Identity mismatch: expected {request.identity}, got {signer}",
                    extra={"mode": "production"},
                )
                return VerifyResponse(
                    valid=False,
                    verified_at=timestamp,
                    signer=signer,
                    transparency_index=None,
                    certificate_chain=None,
                )

            response = VerifyResponse(
                valid=True,
                verified_at=timestamp,
                signer=signer,
                transparency_index=entry.get("logIndex"),
                certificate_chain=[certificate.decode()] if certificate else None,
            )

            logger.info(
                "[PRODUCTION] Verified signature successfully",
                extra={
                    "event_type": "verification_success",
                    "signer": signer,
                    "rekor_index": entry.get("logIndex"),
                    "mode": "production",
                },
            )

            return response

        except Exception as e:
            logger.error(
                f"[PRODUCTION] Verification failed: {e}",
                extra={"error": str(e), "mode": "production"},
            )
            return VerifyResponse(
                valid=False,
                verified_at=datetime.now(timezone.utc),
                signer="unknown",
                transparency_index=None,
                certificate_chain=None,
            )


def get_verification_service(request: Request) -> VerificationService:
    """Dependency injection for verification service.

    Returns mock or production service based on configuration.

    Args:
        request: FastAPI request (contains app state)

    Returns:
        VerificationService implementation (mock or production)
    """
    app = request.app
    settings: CertusTrustSettings = app.state.settings

    if settings.mock_sigstore:
        # Return mock service
        if not hasattr(app.state, "mock_verification_service"):
            app.state.mock_verification_service = MockVerificationService()
        return app.state.mock_verification_service
    else:
        # Return production service
        if not hasattr(app.state, "production_verification_service"):
            rekor_client = app.state.rekor_client
            signing_client = app.state.signing_client
            app.state.production_verification_service = ProductionVerificationService(
                rekor_client, signing_client, settings
            )
        return app.state.production_verification_service
