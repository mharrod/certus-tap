from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from pydantic import BaseModel

from certus_integrity.services import get_analyzer
from certus_transform.core.config import settings
from certus_transform.services import get_s3_client

SKIP_FILE_BASENAMES = {
    "verification-proof.json",
    "scan.json",
}


class PrivacyScanResult(BaseModel):
    key: str
    quarantined: bool
    findings: int


class PrivacyScanSummary(BaseModel):
    bucket: str
    prefix: str
    quarantine_prefix: str
    scanned: int
    quarantined: int
    clean: int
    results: list[PrivacyScanResult]
    report_object: str | None = None


def _format_report(bucket: str, results: Iterable[PrivacyScanResult]) -> str:
    lines = []
    for item in results:
        status = "BLOCK" if item.quarantined else "OK"
        lines.append(f"[{status}] s3://{bucket}/{item.key}")
    if not lines:
        lines.append("No objects scanned.")
    return "\n".join(lines) + "\n"


def scan_prefix(
    bucket: str,
    prefix: str,
    *,
    quarantine_prefix: str | None = None,
    dry_run: bool = False,
    report_key: str | None = None,
) -> PrivacyScanSummary:
    """Scan a specific S3 prefix for PII and optionally quarantine offending files."""

    s3_client = get_s3_client()
    analyzer = get_analyzer()

    normalized_prefix = prefix if prefix.endswith("/") else f"{prefix}/"
    normalized_quarantine = (
        quarantine_prefix.rstrip("/") + "/" if quarantine_prefix else f"{normalized_prefix.rstrip('/')}/quarantine/"
    )

    paginator = s3_client.get_paginator("list_objects_v2")
    pages = paginator.paginate(Bucket=bucket, Prefix=normalized_prefix)

    results: list[PrivacyScanResult] = []
    for page in pages:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith("/") or key.startswith(normalized_quarantine):
                continue

            # skip directory markers
            filename = Path(key).name
            if not filename or filename in SKIP_FILE_BASENAMES:
                continue

            file_obj = s3_client.get_object(Bucket=bucket, Key=key)
            body: bytes = file_obj["Body"].read()
            text = body.decode("utf-8", errors="ignore")
            findings = analyzer.analyze(text=text, language="en")
            if findings:
                quarantine_key = f"{normalized_quarantine}{filename}"
                if not dry_run:
                    s3_client.copy_object(
                        CopySource={"Bucket": bucket, "Key": key},
                        Bucket=bucket,
                        Key=quarantine_key,
                    )
                    s3_client.delete_object(Bucket=bucket, Key=key)
                results.append(PrivacyScanResult(key=key, quarantined=True, findings=len(findings)))
            else:
                results.append(PrivacyScanResult(key=key, quarantined=False, findings=0))

    report_object = None
    if report_key:
        report_object = report_key
        report_body = _format_report(bucket, results)
        s3_client.put_object(Bucket=bucket, Key=report_key, Body=report_body.encode("utf-8"))

    return PrivacyScanSummary(
        bucket=bucket,
        prefix=normalized_prefix,
        quarantine_prefix=normalized_quarantine,
        scanned=len(results),
        quarantined=len([r for r in results if r.quarantined]),
        clean=len([r for r in results if not r.quarantined]),
        results=results,
        report_object=report_object,
    )


def scan_active_prefix(prefix: str | None = None) -> list[PrivacyScanResult]:
    """Backwards-compatible helper for legacy callers."""
    summary = scan_prefix(
        bucket=settings.raw_bucket,
        prefix=prefix or settings.active_prefix,
        quarantine_prefix=settings.quarantine_prefix,
    )
    return summary.results
