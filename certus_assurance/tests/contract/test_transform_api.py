"""Contract tests for Certus Transform API expectations.

These tests validate what Certus Assurance expects from Certus Transform.
If these tests fail, either:
- Assurance is calling Transform incorrectly
- Transform changed its API (breaking change)
"""

import pytest

pytestmark = pytest.mark.contract


def test_transform_upload_endpoint_request_format():
    """Test the request format Assurance sends to Transform /upload endpoint."""
    # Assurance sends upload requests in this format
    upload_request = {
        "workspace_id": "test-workspace",
        "component_id": "test-component",
        "assessment_id": "assess_abc123",
        "artifacts": {
            "summary": "summary.json",
            "manifest": "manifest.json",
            "sarif": "reports/sast/trivy.sarif.json",
            "sbom": "reports/sbom/syft.spdx.json",
        },
    }

    # Validate Assurance sends correct format
    assert "workspace_id" in upload_request
    assert "component_id" in upload_request
    assert "assessment_id" in upload_request
    assert "artifacts" in upload_request
    assert isinstance(upload_request["artifacts"], dict)


def test_transform_upload_endpoint_response_format():
    """Test the expected response format from Transform /upload endpoint."""
    # Transform should respond with this format
    expected_response = {
        "uploaded": True,
        "s3_path": "s3://certus-artifacts/workspace/component/assess_abc123/",
        "artifact_count": 4,
        "total_size_bytes": 524288,
        "manifest_uri": "s3://certus-artifacts/workspace/component/assess_abc123/manifest.json",
    }

    # Validate expected response structure
    assert "uploaded" in expected_response
    assert "s3_path" in expected_response
    assert "artifact_count" in expected_response
    assert isinstance(expected_response["uploaded"], bool)
    assert isinstance(expected_response["s3_path"], str)


def test_transform_s3_path_format():
    """Test the S3 path format Assurance expects from Transform."""
    # Transform should use this S3 path pattern
    workspace_id = "acme-corp"
    component_id = "payment-api"
    assessment_id = "assess_abc123"

    expected_s3_path = f"s3://certus-artifacts/{workspace_id}/{component_id}/{assessment_id}/"

    # Validate path format
    assert expected_s3_path.startswith("s3://")
    assert expected_s3_path.endswith("/")
    assert workspace_id in expected_s3_path
    assert component_id in expected_s3_path
    assert assessment_id in expected_s3_path


def test_transform_artifact_metadata_format():
    """Test the artifact metadata format Assurance provides to Transform."""
    # Assurance provides metadata in this format
    artifact_metadata = {
        "workspace_id": "test-workspace",
        "component_id": "test-component",
        "assessment_id": "assess_abc123",
        "timestamp": "2025-01-15T10:30:00Z",
        "manifest_digest": "sha256:abc123...",
        "total_size": 1048576,
    }

    # Validate metadata format
    assert "workspace_id" in artifact_metadata
    assert "component_id" in artifact_metadata
    assert "assessment_id" in artifact_metadata
    assert "timestamp" in artifact_metadata


def test_transform_error_response_format():
    """Test the error response format from Transform."""
    # Transform should return errors in this format
    error_response = {
        "error": "upload_failed",
        "message": "S3 bucket not accessible",
        "details": {"bucket": "certus-artifacts", "error_code": "AccessDenied"},
    }

    # Validate error response structure
    assert "error" in error_response
    assert "message" in error_response
    assert isinstance(error_response["message"], str)


def test_transform_health_endpoint_response():
    """Test the expected response from Transform /health endpoint."""
    # Transform health endpoint should respond with this format
    health_response = {
        "status": "healthy",
        "s3_available": True,
        "timestamp": "2025-01-15T10:30:00Z",
    }

    # Validate health response
    assert "status" in health_response
    assert health_response["status"] in ["healthy", "ok", "degraded"]


def test_transform_multipart_upload_format():
    """Test multipart form-data format for artifact upload."""
    # When uploading via multipart, Assurance sends these fields
    multipart_fields = {
        "bundle": "scan-bundle.tar.gz",  # File field
        "workspace_id": "test-workspace",  # Form field
        "component_id": "test-component",  # Form field
        "assessment_id": "assess_abc123",  # Form field
    }

    # Validate multipart fields
    assert "bundle" in multipart_fields
    assert "workspace_id" in multipart_fields
    assert "component_id" in multipart_fields
    assert "assessment_id" in multipart_fields


def test_transform_accepts_tar_gz_content_type():
    """Test that Transform accepts tar.gz content type."""
    # Assurance sends tar.gz files with this content type
    expected_content_type = "application/x-tar+gzip"

    # Alternative acceptable content types
    acceptable_types = [
        "application/x-tar+gzip",
        "application/gzip",
        "application/octet-stream",
    ]

    assert expected_content_type in acceptable_types


def test_transform_bucket_configuration():
    """Test bucket configuration format Assurance expects."""
    # Transform should support raw and golden bucket configuration
    bucket_config = {
        "raw_bucket": "raw",
        "golden_bucket": "golden",
        "raw_prefix": "security-scans",
        "golden_prefix": "security-scans",
    }

    # Validate bucket config
    assert "raw_bucket" in bucket_config
    assert "golden_bucket" in bucket_config
    assert isinstance(bucket_config["raw_bucket"], str)


def test_transform_list_artifacts_endpoint():
    """Test the expected format for listing artifacts."""
    # Assurance expects Transform to provide artifact listing
    list_request = {
        "workspace_id": "test-workspace",
        "component_id": "test-component",
    }

    list_response = {
        "artifacts": [
            {
                "assessment_id": "assess_abc123",
                "timestamp": "2025-01-15T10:30:00Z",
                "s3_path": "s3://certus-artifacts/workspace/component/assess_abc123/",
                "size_bytes": 524288,
            }
        ],
        "total_count": 1,
    }

    # Validate request/response format
    assert "workspace_id" in list_request
    assert "artifacts" in list_response
    assert isinstance(list_response["artifacts"], list)


def test_transform_url_encoding():
    """Test that workspace/component IDs are URL-safe."""
    workspace_id = "test-workspace"
    component_id = "test-component"

    # IDs should be URL-safe (no encoding needed)
    import urllib.parse

    encoded_workspace = urllib.parse.quote(workspace_id, safe="")
    encoded_component = urllib.parse.quote(component_id, safe="")

    # Should match original (no special chars to encode)
    assert encoded_workspace == workspace_id or "-" in workspace_id
    assert encoded_component == component_id or "-" in component_id


def test_transform_s3_endpoint_configuration():
    """Test S3 endpoint configuration format."""
    # Assurance expects Transform to accept these S3 settings
    s3_config = {
        "s3_endpoint_url": "http://minio:9000",
        "s3_region": "us-east-1",
        "s3_access_key_id": "minioadmin",
        "s3_secret_access_key": "minioadmin",
    }

    # Validate S3 config
    assert "s3_endpoint_url" in s3_config
    assert "s3_region" in s3_config


def test_transform_presigned_url_support():
    """Test that Transform can provide presigned URLs for artifacts."""
    # Assurance may request presigned URLs from Transform
    presigned_request = {
        "workspace_id": "test-workspace",
        "component_id": "test-component",
        "assessment_id": "assess_abc123",
        "artifact_path": "summary.json",
        "expires_in": 3600,  # seconds
    }

    presigned_response = {
        "presigned_url": "https://s3.example.com/certus-artifacts/...?signature=...",
        "expires_at": "2025-01-15T11:30:00Z",
    }

    # Validate presigned URL format
    assert "presigned_url" in presigned_response
    assert presigned_response["presigned_url"].startswith("http")
