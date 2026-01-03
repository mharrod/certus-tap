"""
API router with toggle support (mock/production).

This is an example showing how to use the new service layer.
To migrate:
1. Copy relevant endpoints from here to router.py
2. Replace old mock code with Depends() pattern
3. Endpoints automatically switch between mock/production based on config
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status

from ..services import (
    SigningService,
    TransparencyService,
    VerificationService,
    get_signing_service,
    get_transparency_service,
    get_verification_service,
)
from .models import (
    SignRequest,
    SignResponse,
    TransparencyLogEntry,
    VerifyRequest,
    VerifyResponse,
)

logger = logging.getLogger(__name__)

router_v2 = APIRouter(prefix="/v2", tags=["trust-v2"])


# ============================================================================
# Example: Sign Endpoint with Toggle Support
# ============================================================================


@router_v2.post(
    "/sign",
    response_model=SignResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sign an artifact (auto mock/production)",
    description="Automatically uses mock or production based on CERTUS_TRUST_MOCK_SIGSTORE",
)
async def sign_artifact_v2(
    request: SignRequest,
    signing_service: SigningService = Depends(get_signing_service),
) -> SignResponse:
    """
    Sign an artifact with automatic mock/production switching.

    - If CERTUS_TRUST_MOCK_SIGSTORE=true → uses mock (in-memory)
    - If CERTUS_TRUST_MOCK_SIGSTORE=false → uses real Sigstore (Rekor, Fulcio)

    No code changes needed to switch modes!
    """
    try:
        return await signing_service.sign(request)
    except Exception as e:
        logger.error(f"Signing failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signing failed",
        )


# ============================================================================
# Example: Verify Endpoint with Toggle Support
# ============================================================================


@router_v2.post(
    "/verify",
    response_model=VerifyResponse,
    summary="Verify a signature (auto mock/production)",
    description="Automatically uses mock or production based on configuration",
)
async def verify_signature_v2(
    request: VerifyRequest,
    verification_service: VerificationService = Depends(get_verification_service),
) -> VerifyResponse:
    """
    Verify a signature with automatic mock/production switching.

    - Mock mode: Checks in-memory log
    - Production mode: Verifies cryptographically + checks Rekor
    """
    try:
        return await verification_service.verify(request)
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed",
        )


# ============================================================================
# Example: Transparency Log Endpoints with Toggle Support
# ============================================================================


@router_v2.get(
    "/transparency/{entry_id}",
    response_model=TransparencyLogEntry,
    summary="Get transparency log entry (auto mock/production)",
)
async def get_transparency_entry_v2(
    entry_id: str,
    include_proof: bool = True,
    transparency_service: TransparencyService = Depends(get_transparency_service),
) -> TransparencyLogEntry:
    """
    Get a transparency log entry with automatic mock/production switching.

    - Mock mode: Returns from in-memory log with mock Merkle proof
    - Production mode: Queries real Rekor with real inclusion proof
    """
    entry = await transparency_service.get_entry(entry_id, include_proof)

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entry {entry_id} not found in transparency log",
        )

    return entry


@router_v2.get(
    "/transparency",
    response_model=list[TransparencyLogEntry],
    summary="Query transparency log (auto mock/production)",
)
async def query_transparency_log_v2(
    assessment_id: Optional[str] = None,
    signer: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    transparency_service: TransparencyService = Depends(get_transparency_service),
) -> list[TransparencyLogEntry]:
    """
    Query transparency log with automatic mock/production switching.

    - Mock mode: Searches in-memory log
    - Production mode: Queries real Rekor (limited filtering)
    """
    return await transparency_service.query_log(
        assessment_id=assessment_id,
        signer=signer,
        limit=limit,
        offset=offset,
    )


# ============================================================================
# Info Endpoint - Shows Current Mode
# ============================================================================


@router_v2.get("/mode", tags=["info"])
async def get_mode(request):
    """Show whether service is running in mock or production mode."""
    settings = request.app.state.settings

    return {
        "mode": "mock" if settings.mock_sigstore else "production",
        "mock_sigstore": settings.mock_sigstore,
        "enable_keyless": settings.enable_keyless,
        "enable_transparency": settings.enable_transparency,
        "rekor_addr": settings.rekor_addr,
        "fulcio_addr": settings.fulcio_addr,
        "message": (
            "Running in MOCK mode. Set CERTUS_TRUST_MOCK_SIGSTORE=false for production."
            if settings.mock_sigstore
            else "Running in PRODUCTION mode with real Sigstore."
        ),
    }
