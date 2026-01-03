"""Standalone FastAPI app for the Certus Assurance prototype.

This keeps the incubating service self-contained so it can be run via
``uvicorn certus_assurance.service:app`` without touching the rest of TAP.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from pydantic import BaseModel, Field

from certus_assurance.api import router
from certus_assurance.jobs import ScanStatus, job_manager
from certus_assurance.logs import log_stream_manager
from certus_assurance.pipeline import ManagedRuntime
from certus_assurance.settings import settings

app = FastAPI(title="Certus Assurance Service", version="0.1.0")
app.include_router(router)


# ============================================================================
# Health & Stats
# ============================================================================


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    """Health check endpoint with scanning mode indicator."""
    scanning_mode = "sample" if settings.use_sample_mode else "production"
    security_module_available = ManagedRuntime is not None

    return {
        "status": "ok",
        "scanning_mode": scanning_mode,
        "security_module_available": str(security_module_available),
    }


class ServiceStats(BaseModel):
    """Statistics about Assurance service activity."""

    total_scans: int = Field(..., description="Total scans submitted")
    scans_by_status: dict[str, int] = Field(..., description="Scans grouped by status")
    upload_stats: dict[str, int] = Field(..., description="Upload request statistics")
    active_streams: int = Field(..., description="Active WebSocket streams")
    timestamp: datetime = Field(..., description="When stats were generated")


@app.get("/stats", response_model=ServiceStats, tags=["health"])
async def get_stats() -> ServiceStats:
    """
    Get statistics about Assurance service activity.

    Useful for monitoring, debugging, and AI agents analyzing Assurance behavior.
    """
    jobs = job_manager.list_jobs()

    scans_by_status = {
        "queued": len([j for j in jobs if j.status == ScanStatus.QUEUED]),
        "running": len([j for j in jobs if j.status == ScanStatus.RUNNING]),
        "succeeded": len([j for j in jobs if j.status == ScanStatus.SUCCEEDED]),
        "failed": len([j for j in jobs if j.status == ScanStatus.FAILED]),
    }

    upload_stats = {
        "pending": len([j for j in jobs if j.upload_status == "pending"]),
        "permitted": len([j for j in jobs if j.upload_status == "permitted"]),
        "uploaded": len([j for j in jobs if j.upload_status == "uploaded"]),
        "denied": len([j for j in jobs if j.upload_status == "denied"]),
    }

    return ServiceStats(
        total_scans=len(jobs),
        scans_by_status=scans_by_status,
        upload_stats=upload_stats,
        active_streams=len(log_stream_manager._streams),
        timestamp=datetime.now(timezone.utc),
    )
