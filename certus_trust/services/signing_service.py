"""Signing service with mock and production implementations."""

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from fastapi import Request

from ..api.models import SignRequest, SignResponse, TransparencyEntry
from ..clients import RekorClient, SigningClient
from ..config import CertusTrustSettings

logger = logging.getLogger(__name__)


class SigningService(ABC):
    """Abstract signing service interface."""

    @abstractmethod
    async def sign(self, request: SignRequest) -> SignResponse:
        """Sign an artifact and record in transparency log."""
        pass


class MockSigningService(SigningService):
    """Mock signing service for development and testing."""

    def __init__(self):
        """Initialize mock signing service."""
        self._signed_artifacts = {}
        self._transparency_log = []

    async def sign(self, request: SignRequest) -> SignResponse:
        """Mock artifact signing."""
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        # Mock signing response
        response = SignResponse(
            entry_id=entry_id,
            signature=f"mock-signature-{entry_id[:8]}",
            certificate=f"mock-certificate-{entry_id[:8]}",
            transparency_entry=TransparencyEntry(
                uuid=entry_id,
                index=len(self._transparency_log),
                timestamp=timestamp,
            ),
        )

        # Store in memory
        self._signed_artifacts[entry_id] = {
            "request": request.model_dump(),
            "response": response.model_dump(),
            "timestamp": timestamp,
        }

        # Add to transparency log
        self._transparency_log.append({
            "entry_id": entry_id,
            "artifact": request.artifact,
            "timestamp": timestamp,
            "signer": "certus-trust@certus.cloud",
            "signature": response.signature,
        })

        logger.info(
            f"[MOCK] Signed artifact {request.artifact_type}: {entry_id}",
            extra={
                "event_type": "artifact_signed",
                "artifact_type": request.artifact_type,
                "entry_id": entry_id,
                "mode": "mock",
            },
        )

        return response


class ProductionSigningService(SigningService):
    """Production signing service using real Sigstore."""

    def __init__(
        self,
        rekor_client: RekorClient,
        signing_client: SigningClient,
        settings: CertusTrustSettings,
    ):
        """Initialize production signing service.

        Args:
            rekor_client: Rekor transparency log client
            signing_client: Signing/verification client
            settings: Service configuration
        """
        self.rekor_client = rekor_client
        self.signing_client = signing_client
        self.settings = settings

    async def sign(self, request: SignRequest) -> SignResponse:
        """Sign artifact using real Sigstore."""
        try:
            # Convert artifact hash to bytes for signing
            artifact_hash = request.artifact.replace("sha256:", "")
            artifact_bytes = bytes.fromhex(artifact_hash)

            # Real cryptographic signing
            signature, certificate, computed_hash = await self.signing_client.sign_artifact(
                artifact_bytes,
                use_keyless=self.settings.enable_keyless,
            )

            # Submit to Rekor transparency log
            rekor_entry = await self.rekor_client.submit_entry(
                artifact_hash=computed_hash,
                signature=signature,
                certificate=certificate,
            )

            # Build response with real data
            response = SignResponse(
                entry_id=rekor_entry["uuid"],
                signature=signature.hex(),
                certificate=certificate.decode() if certificate else None,
                transparency_entry=TransparencyEntry(
                    uuid=rekor_entry["uuid"],
                    index=rekor_entry["index"],
                    timestamp=rekor_entry["integrated_time"],
                ),
            )

            logger.info(
                f"[PRODUCTION] Signed artifact {request.artifact_type}: {rekor_entry['uuid']}",
                extra={
                    "event_type": "artifact_signed",
                    "artifact_type": request.artifact_type,
                    "entry_id": rekor_entry["uuid"],
                    "rekor_index": rekor_entry["index"],
                    "mode": "production",
                },
            )

            return response

        except Exception as e:
            logger.error(
                f"[PRODUCTION] Signing failed: {e}",
                extra={"error": str(e), "mode": "production"},
            )
            raise


def get_signing_service(request: Request) -> SigningService:
    """Dependency injection for signing service.

    Returns mock or production service based on configuration.

    Args:
        request: FastAPI request (contains app state)

    Returns:
        SigningService implementation (mock or production)
    """
    app = request.app
    settings: CertusTrustSettings = app.state.settings

    if settings.mock_sigstore:
        # Return mock service
        if not hasattr(app.state, "mock_signing_service"):
            app.state.mock_signing_service = MockSigningService()
        return app.state.mock_signing_service
    else:
        # Return production service
        if not hasattr(app.state, "production_signing_service"):
            rekor_client = app.state.rekor_client
            signing_client = app.state.signing_client
            app.state.production_signing_service = ProductionSigningService(rekor_client, signing_client, settings)
        return app.state.production_signing_service
