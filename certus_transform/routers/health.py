from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter(prefix="/health", tags=["health"])

# ============================================================================
# In-memory statistics (reset on service restart)
# ============================================================================

_upload_count: int = 0
_upload_success: int = 0
_upload_failed: int = 0
_privacy_scans: int = 0
_artifacts_quarantined: int = 0
_promotions_success: int = 0
_promotions_failed: int = 0
_service_started_at = datetime.now(timezone.utc)


# ============================================================================
# Models
# ============================================================================


class ServiceStats(BaseModel):
    """Statistics about Transform service activity."""

    total_uploads: int = Field(..., description="Total upload requests received")
    successful_uploads: int = Field(..., description="Successfully completed uploads")
    failed_uploads: int = Field(..., description="Failed upload attempts")
    privacy_scans: int = Field(..., description="Privacy scans executed")
    artifacts_quarantined: int = Field(..., description="Artifacts moved to quarantine")
    promotion_stats: dict[str, int] = Field(..., description="Promotion statistics")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    timestamp: datetime = Field(..., description="When stats were generated")


# ============================================================================
# Endpoints
# ============================================================================


@router.get("", summary="Service heartbeat")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@router.get(
    "/stats",
    response_model=ServiceStats,
    summary="Get service statistics",
    description="Get statistics about Transform service activity",
)
async def get_stats() -> ServiceStats:
    """
    Get statistics about Transform service activity.

    Useful for monitoring, debugging, and AI agents analyzing Transform behavior.
    """
    uptime = (datetime.now(timezone.utc) - _service_started_at).total_seconds()

    return ServiceStats(
        total_uploads=_upload_count,
        successful_uploads=_upload_success,
        failed_uploads=_upload_failed,
        privacy_scans=_privacy_scans,
        artifacts_quarantined=_artifacts_quarantined,
        promotion_stats={
            "successful": _promotions_success,
            "failed": _promotions_failed,
        },
        uptime_seconds=uptime,
        timestamp=datetime.now(timezone.utc),
    )
