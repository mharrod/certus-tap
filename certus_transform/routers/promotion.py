from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator

from certus_transform.core.config import settings
from certus_transform.services import get_s3_client

router = APIRouter(prefix="/v1/promotions", tags=["promotion"])

# Import stats counters from health module
from certus_transform.routers import health


class PromotionRequest(BaseModel):
    """Simple promotion request for legacy workflows.

    ⚠️ Legacy endpoint: Use verification-first workflow for new scans.
    See: POST /v1/execute-upload (verification-first model)
    """

    keys: list[str] = Field(
        ...,
        description="Keys inside the raw bucket to promote (relative to root).",
    )
    destination_prefix: str | None = Field(
        default=None,
        description="Optional override for the golden prefix (defaults to scans/).",
    )

    @validator("keys")
    def _ensure_keys(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("keys cannot be empty")
        return value


@router.post(
    "/golden",
    summary="Promote approved files to the golden bucket",
    deprecated=True,
)
async def promote_to_golden(request: PromotionRequest) -> dict[str, Any]:
    """
    ⚠️ DEPRECATED: Legacy promotion endpoint.

    This endpoint provides simple file promotion without verification.
    Artifacts are copied directly from raw bucket to golden bucket.

    **Recommendation:** For new workflows, use the verification-first model:
    - Certus-Assurance: Automatic upload request to Trust
    - Certus-Trust: Verification gatekeeper
    - Certus-Transform: POST /v1/execute-upload (receives permission from Trust)

    See trust-verification.md tutorial for verification-first workflow.

    Args:
        request: Promotion request with artifact keys and optional destination prefix

    Returns:
        Dict with list of promoted keys in golden bucket

    Raises:
        HTTPException: If S3 operations fail
    """
    s3_client = get_s3_client()
    destination_prefix = request.destination_prefix or settings.golden_destination_prefix

    try:
        promoted: list[str] = []
        for key in request.keys:
            filename = key.split("/")[-1]
            target_key = f"{destination_prefix.rstrip('/')}/{filename}"
            s3_client.copy_object(
                CopySource={"Bucket": settings.raw_bucket, "Key": key},
                Bucket=settings.golden_bucket,
                Key=target_key,
            )
            promoted.append(target_key)

        # Track successful promotion
        health._promotions_success += 1

        return {"promoted": promoted}

    except Exception as e:
        # Track failed promotion
        health._promotions_failed += 1

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Promotion failed: {e!s}",
        ) from e
