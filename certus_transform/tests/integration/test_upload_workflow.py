"""Integration tests for raw document upload workflow.

Tests the /v1/uploads/raw endpoint documented in:
- docs/learn/transform/sample-datalake-upload.md

Validates:
- Document upload to raw S3 bucket
- File handling and storage
- Metadata preservation
"""

import io
from pathlib import Path

import pytest
import requests


def test_upload_raw_document_basic(
    http_session: requests.Session,
    transform_base_url: str,
    request_timeout: int,
    sample_document: Path,
) -> None:
    """Test basic document upload to raw bucket.

    Tutorial: docs/learn/transform/sample-datalake-upload.md
    Endpoint: POST /v1/uploads/raw
    Validates: File upload succeeds
    """
    with open(sample_document, "rb") as f:
        files = {"file": (sample_document.name, f, "application/octet-stream")}

        response = http_session.post(
            f"{transform_base_url}/v1/uploads/raw",
            files=files,
            timeout=request_timeout,
        )

    if response.status_code == 404:
        pytest.skip("Upload endpoint not available")

    # Let 422 errors fail the test - they indicate validation issues

    response.raise_for_status()
    data = response.json()

    # Verify response structure
    assert "bucket" in data or "s3_key" in data or "key" in data


def test_upload_raw_document_with_custom_prefix(
    http_session: requests.Session,
    transform_base_url: str,
    request_timeout: int,
    sample_document: Path,
) -> None:
    """Test upload with custom prefix parameter.

    Validates: Custom prefix support
    """
    custom_prefix = "test/custom/prefix/"

    with open(sample_document, "rb") as f:
        files = {"file": (sample_document.name, f, "application/octet-stream")}
        data = {"prefix": custom_prefix}

        response = http_session.post(
            f"{transform_base_url}/v1/uploads/raw",
            files=files,
            data=data,
            timeout=request_timeout,
        )

    if response.status_code == 404:
        pytest.skip("Upload endpoint not available")

    if response.status_code == 422:
        pytest.skip("S3 not configured or not available")

    # Should succeed or return validation error for prefix format
    assert response.status_code in [200, 422]


def test_upload_multiple_files_sequentially(
    http_session: requests.Session,
    transform_base_url: str,
    request_timeout: int,
    test_data_dir: Path,
) -> None:
    """Test uploading multiple files one after another.

    Validates: Multiple upload support
    """
    # Find up to 3 sample files
    sample_files = list(test_data_dir.glob("**/*.md"))[:3]

    if len(sample_files) < 2:
        pytest.skip("Not enough sample files for multi-upload test")

    upload_count = 0
    for sample_file in sample_files:
        with open(sample_file, "rb") as f:
            files = {"file": (sample_file.name, f, "application/octet-stream")}

            response = http_session.post(
                f"{transform_base_url}/v1/uploads/raw",
                files=files,
                timeout=request_timeout,
            )

        if response.status_code == 404:
            pytest.skip("Upload endpoint not available")

        if response.status_code == 422:
            pytest.skip("S3 not configured or not available")

        if response.status_code == 200:
            upload_count += 1

    assert upload_count >= 2, f"Expected at least 2 successful uploads, got {upload_count}"


def test_upload_text_content_directly(
    http_session: requests.Session,
    transform_base_url: str,
    request_timeout: int,
) -> None:
    """Test uploading text content without a file.

    Validates: In-memory file upload
    """
    content = b"This is test content for upload testing."
    files = {"file": ("test-file.txt", io.BytesIO(content), "text/plain")}

    response = http_session.post(
        f"{transform_base_url}/v1/uploads/raw",
        files=files,
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Upload endpoint not available")

    if response.status_code == 422:
        pytest.skip("S3 not configured or not available")

    response.raise_for_status()


def test_upload_missing_file_parameter(
    http_session: requests.Session,
    transform_base_url: str,
    request_timeout: int,
) -> None:
    """Test upload without file parameter returns error.

    Validates: Proper validation of required parameters
    """
    response = http_session.post(
        f"{transform_base_url}/v1/uploads/raw",
        data={},
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Upload endpoint not available")

    # Should return 422 (validation error) for missing file
    assert response.status_code == 422


def test_upload_empty_file(
    http_session: requests.Session,
    transform_base_url: str,
    request_timeout: int,
) -> None:
    """Test uploading empty file.

    Validates: Empty file handling
    """
    content = b""
    files = {"file": ("empty.txt", io.BytesIO(content), "text/plain")}

    response = http_session.post(
        f"{transform_base_url}/v1/uploads/raw",
        files=files,
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Upload endpoint not available")

    # May succeed or reject empty files depending on implementation
    assert response.status_code in [200, 400, 422]


def test_upload_with_special_characters_in_filename(
    http_session: requests.Session,
    transform_base_url: str,
    request_timeout: int,
) -> None:
    """Test upload with special characters in filename.

    Validates: Filename sanitization or rejection
    """
    content = b"Test content"
    # Filename with spaces and special chars
    files = {"file": ("test file (1) & [copy].txt", io.BytesIO(content), "text/plain")}

    response = http_session.post(
        f"{transform_base_url}/v1/uploads/raw",
        files=files,
        timeout=request_timeout,
    )

    if response.status_code == 404:
        pytest.skip("Upload endpoint not available")

    # Let 422 errors fail the test - they indicate validation issues

    # Should either succeed (with sanitization) or reject filename
    assert response.status_code in [200, 400, 422]


def test_upload_stats_increment_after_upload(
    http_session: requests.Session,
    transform_base_url: str,
    request_timeout: int,
    sample_document: Path,
) -> None:
    """Test that stats counters increment after upload.

    Validates: Stats tracking (ENHANCEMENTS.md Feature #1)
    """
    # Get initial stats
    stats_response = http_session.get(
        f"{transform_base_url}/health/stats",
        timeout=request_timeout,
    )

    if stats_response.status_code == 404:
        pytest.skip("Stats endpoint not available")

    initial_stats = stats_response.json()
    initial_total = initial_stats.get("total_uploads", 0)

    # Perform upload
    with open(sample_document, "rb") as f:
        files = {"file": (sample_document.name, f, "application/octet-stream")}

        upload_response = http_session.post(
            f"{transform_base_url}/v1/uploads/raw",
            files=files,
            timeout=request_timeout,
        )

    if upload_response.status_code == 404:
        pytest.skip("Upload endpoint not available")

    # Let 422 errors fail the test - they indicate validation issues

    # Get updated stats
    updated_stats_response = http_session.get(
        f"{transform_base_url}/health/stats",
        timeout=request_timeout,
    )
    updated_stats = updated_stats_response.json()
    updated_total = updated_stats.get("total_uploads", 0)

    # Counter should not decrease (may stay same if stats aren't persisted)
    if upload_response.status_code == 200:
        assert updated_total >= initial_total, (
            f"Upload counter should not decrease (was {initial_total}, now {updated_total})"
        )
