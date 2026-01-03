"""Utility functions for ingestion services.

This module contains reusable utility functions that were previously
embedded in routers. Moving them here improves testability and reusability.
"""

import hashlib
from typing import Any
from urllib.parse import urlparse

from fastapi import UploadFile

from certus_ask.core.exceptions import ValidationError


def extract_metadata_preview(writer_result: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
    """Extract metadata preview from document writer results.

    Args:
        writer_result: Result dictionary from DocumentWriter
        limit: Maximum number of preview items to return (default: 3)

    Returns:
        List of metadata dictionaries (up to limit items)
    """
    preview = writer_result.get("metadata_preview") or []
    if limit <= 0:
        return list(preview)
    return list(preview[:limit])


def get_upload_file_size(uploaded_file: UploadFile) -> int:
    """Get the size of an uploaded file without relying on UploadFile.size.

    This is more reliable than using UploadFile.size which may not be set.

    Args:
        uploaded_file: FastAPI UploadFile instance

    Returns:
        File size in bytes (0 if file object is not available)
    """
    import os

    file_obj = getattr(uploaded_file, "file", None)
    if file_obj is None:
        return 0

    current_position = file_obj.tell()
    file_obj.seek(0, os.SEEK_END)
    size = file_obj.tell()
    file_obj.seek(current_position)
    return size


def extract_filename_from_source(source_name: str) -> str:
    """Extract filename component from a source identifier.

    Handles various source formats including S3 URIs, file paths, etc.

    Args:
        source_name: Source identifier (e.g., "s3://bucket/path/file.json", "/path/file.json", "file.json")

    Returns:
        Filename component (e.g., "file.json")

    Examples:
        >>> extract_filename_from_source("s3://bucket/scans/scan.sarif")
        'scan.sarif'
        >>> extract_filename_from_source("/tmp/upload.json")
        'upload.json'
        >>> extract_filename_from_source("scan.sarif")
        'scan.sarif'
    """
    if "/" in source_name:
        return source_name.rsplit("/", 1)[-1] or source_name
    return source_name


def compute_sha256_digest(payload: bytes) -> str:
    """Compute SHA256 digest of a byte payload.

    Args:
        payload: Bytes to hash

    Returns:
        SHA256 digest string prefixed with "sha256:" (e.g., "sha256:abc123...")
    """
    digest = hashlib.sha256()
    digest.update(payload)
    return f"sha256:{digest.hexdigest()}"


def match_expected_digest(
    artifact_locations: dict[str, Any] | None,
    bucket: str,
    key: str,
) -> str | None:
    """Find expected digest for an S3 object from artifact_locations metadata.

    Searches artifact_locations for a matching S3 entry and returns its digest.
    Supports both explicit bucket/key fields and URI parsing.

    Args:
        artifact_locations: Artifact locations dictionary from trust verification
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        Expected digest string (e.g., "sha256:abc123...") or None if not found

    Example artifact_locations:
        {
            "s3": [
                {
                    "bucket": "raw-bucket",
                    "key": "scans/scan.sarif",
                    "digest": "sha256:abc123..."
                }
            ]
        }
    """
    if not artifact_locations:
        return None

    s3_entry = artifact_locations.get("s3")
    if not s3_entry:
        return None

    entries = s3_entry if isinstance(s3_entry, list) else [s3_entry]
    for entry in entries:
        digest = entry.get("digest")
        if not digest:
            continue

        entry_bucket = entry.get("bucket")
        entry_key = entry.get("key", "")
        uri = entry.get("uri") or entry.get("url")

        # Parse URI if provided
        if uri:
            parsed = urlparse(uri)
            entry_bucket = entry_bucket or parsed.netloc
            entry_key = entry_key or parsed.path.lstrip("/")

        if not entry_bucket:
            continue

        if entry_bucket != bucket:
            continue

        normalized_key = entry_key.strip("/")
        if not normalized_key:
            continue

        # Match exact key or prefix
        if key == normalized_key or key.startswith(normalized_key.rstrip("/") + "/"):
            return digest

    return None


def enforce_verified_digest(
    file_bytes: bytes,
    artifact_locations: dict[str, Any] | None,
    bucket: str | None,
    key: str | None,
) -> str | None:
    """Verify file digest matches expected value from artifact_locations.

    Args:
        file_bytes: File content as bytes
        artifact_locations: Artifact locations dictionary from trust verification
        bucket: S3 bucket name (optional)
        key: S3 object key (optional)

    Returns:
        Actual digest if verification succeeds or no expected digest exists

    Raises:
        ValidationError: If expected digest exists but doesn't match actual digest
    """
    if not bucket or not key or not artifact_locations:
        return None

    expected_digest = match_expected_digest(artifact_locations, bucket, key)
    if not expected_digest:
        return None

    actual_digest = compute_sha256_digest(file_bytes)
    if actual_digest != expected_digest:
        raise ValidationError(
            message="Artifact digest does not match verification record",
            error_code="digest_mismatch",
            details={
                "expected": expected_digest,
                "actual": actual_digest,
                "bucket": bucket,
                "key": key,
            },
        )

    return actual_digest
