from fastapi import APIRouter
from pydantic import BaseModel, Field

from certus_transform.core.config import settings
from certus_transform.services.privacy import PrivacyScanResult, PrivacyScanSummary, scan_prefix

router = APIRouter(prefix="/v1/privacy", tags=["privacy"])


class PrivacyScanRequest(BaseModel):
    bucket: str | None = Field(default=None, description="S3 bucket to scan (defaults to raw bucket).")
    prefix: str | None = Field(default=None, description="Prefix to scan (e.g., security-scans/scan_123/).")
    scan_id: str | None = Field(default=None, description="Convenience flag to scan security-scans/<scan_id>/")
    quarantine_prefix: str | None = Field(
        default=None, description="Override quarantine prefix (defaults to <prefix>/quarantine/)."
    )
    report_key: str | None = Field(
        default=None,
        description="Optional key to write a plaintext report (stored in the same bucket).",
    )
    dry_run: bool = Field(default=False, description="If true, report findings but do not move objects.")


class PrivacyScanResponse(BaseModel):
    bucket: str
    prefix: str
    quarantine_prefix: str
    scanned: int
    quarantined: int
    clean: int
    report_object: str | None = None
    results: list[PrivacyScanResult]


@router.post("/scan", response_model=PrivacyScanResponse, summary="Run Presidio scanning on raw/active files")
def privacy_scan(request: PrivacyScanRequest) -> PrivacyScanResponse:
    bucket = request.bucket or settings.raw_bucket
    if request.scan_id:
        prefix = f"security-scans/{request.scan_id.rstrip('/')}/"
    elif request.prefix:
        prefix = request.prefix
    else:
        # Backwards compatibility: fall back to configured active prefix
        prefix = settings.active_prefix

    summary: PrivacyScanSummary = scan_prefix(
        bucket=bucket,
        prefix=prefix,
        quarantine_prefix=request.quarantine_prefix,
        dry_run=request.dry_run,
        report_key=request.report_key,
    )

    return PrivacyScanResponse(**summary.dict())
