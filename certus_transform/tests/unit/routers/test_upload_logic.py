"""Unit tests for upload logic in verification router."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from certus_transform.routers.verification import (
    _push_to_oci_registry,
    _upload_to_s3,
)


class TestUploadToS3:
    """Test S3 upload logic with metadata enrichment."""

    def test_upload_to_s3_s3_path_construction(self):
        """Test S3 path construction with prefix and artifact name."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            s3_path, _timestamp = _upload_to_s3(
                artifact_name="trivy.json",
                artifact_hash="sha256:abc123",
                s3_bucket="raw-bucket",
                s3_prefix="scans/abc/",
            )

        assert s3_path == "scans/abc/trivy.json"
        # Should not have leading slashes
        assert not s3_path.startswith("/")

    def test_upload_to_s3_s3_path_handles_trailing_slash(self):
        """Test S3 path construction strips trailing slash from prefix."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            s3_path, _ = _upload_to_s3(
                artifact_name="bandit.sarif",
                artifact_hash="sha256:def456",
                s3_bucket="bucket",
                s3_prefix="prefix/with/slash/",
            )

        assert s3_path == "prefix/with/slash/bandit.sarif"

    def test_upload_to_s3_metadata_structure(self):
        """Test all required metadata keys are created."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _upload_to_s3(
                artifact_name="test.json",
                artifact_hash="sha256:hash123",
                s3_bucket="bucket",
                s3_prefix="scans/",
                scan_id="scan_abc",
                tier="verified",
            )

        # Verify put_object was called
        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args[1]

        # Check required metadata fields
        metadata = call_args["Metadata"]
        assert "artifact-name" in metadata
        assert metadata["artifact-name"] == "test.json"
        assert "artifact-hash" in metadata
        assert metadata["artifact-hash"] == "sha256:hash123"
        assert "verification-required" in metadata
        assert "uploaded-by" in metadata
        assert metadata["uploaded-by"] == "certus-transform"
        assert "upload-timestamp" in metadata
        assert "scan-id" in metadata
        assert metadata["scan-id"] == "scan_abc"
        assert "trust-tier" in metadata
        assert metadata["trust-tier"] == "verified"

    def test_upload_to_s3_verification_proof_metadata(self):
        """Test verification proof fields added to metadata."""
        mock_s3 = Mock()

        verification_proof = {
            "chain_verified": True,
            "signer_inner": "certus-assurance@certus.cloud",
            "signer_outer": "certus-trust@certus.cloud",
            "verification_timestamp": "2025-12-18T10:00:00Z",
        }

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _upload_to_s3(
                artifact_name="test.json",
                artifact_hash="sha256:abc",
                s3_bucket="bucket",
                s3_prefix="scans/",
                verification_proof=verification_proof,
            )

        call_args = mock_s3.put_object.call_args[1]
        metadata = call_args["Metadata"]

        assert "chain-verified" in metadata
        assert metadata["chain-verified"] == "True"
        assert "signer-inner" in metadata
        assert metadata["signer-inner"] == "certus-assurance@certus.cloud"
        assert "signer-outer" in metadata
        assert metadata["signer-outer"] == "certus-trust@certus.cloud"
        assert "verification-timestamp" in metadata

    def test_upload_to_s3_scan_metadata_metadata(self):
        """Test scan metadata fields added to S3 metadata."""
        mock_s3 = Mock()

        scan_metadata = {
            "git_url": "https://github.com/example/repo",
            "commit": "abc123def456",
            "branch": "main",
        }

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _upload_to_s3(
                artifact_name="test.json",
                artifact_hash="sha256:abc",
                s3_bucket="bucket",
                s3_prefix="scans/",
                metadata=scan_metadata,
            )

        call_args = mock_s3.put_object.call_args[1]
        metadata = call_args["Metadata"]

        assert "git-url" in metadata
        assert metadata["git-url"] == "https://github.com/example/repo"
        assert "git-commit" in metadata
        assert metadata["git-commit"] == "abc123def456"
        assert "git-branch" in metadata
        assert metadata["git-branch"] == "main"

    def test_upload_to_s3_tag_construction(self):
        """Test S3 tags are constructed correctly."""
        mock_s3 = Mock()

        verification_proof = {"chain_verified": True}

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _upload_to_s3(
                artifact_name="test.json",
                artifact_hash="sha256:abc",
                s3_bucket="bucket",
                s3_prefix="scans/",
                tier="verified",
                verification_proof=verification_proof,
            )

        call_args = mock_s3.put_object.call_args[1]
        tagging = call_args.get("Tagging", "")

        assert "tier=verified" in tagging
        assert "verified=True" in tagging
        assert "service=certus-transform" in tagging

    def test_upload_to_s3_tag_construction_no_verification(self):
        """Test tags without verification proof."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _upload_to_s3(
                artifact_name="test.json",
                artifact_hash="sha256:abc",
                s3_bucket="bucket",
                s3_prefix="scans/",
                tier="basic",
            )

        call_args = mock_s3.put_object.call_args[1]
        tagging = call_args.get("Tagging", "")

        assert "tier=basic" in tagging
        assert "service=certus-transform" in tagging
        # Should not have verified tag
        assert "verified=" not in tagging

    def test_upload_to_s3_timestamp_format(self):
        """Test timestamp is ISO 8601 format."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _, timestamp = _upload_to_s3(
                artifact_name="test.json",
                artifact_hash="sha256:abc",
                s3_bucket="bucket",
                s3_prefix="scans/",
            )

        # Should be valid ISO format
        datetime.fromisoformat(timestamp)  # Will raise if invalid

    def test_upload_to_s3_content_format(self):
        """Test marker file content contains required information."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _upload_to_s3(
                artifact_name="trivy.json",
                artifact_hash="sha256:abc123",
                s3_bucket="bucket",
                s3_prefix="scans/",
            )

        call_args = mock_s3.put_object.call_args[1]
        content = call_args["Body"].decode("utf-8")

        assert "Artifact: trivy.json" in content
        assert "Hash: sha256:abc123" in content
        assert "Timestamp:" in content
        assert "Permission verified by Certus-Trust" in content

    def test_upload_to_s3_returns_path_and_timestamp(self):
        """Test returns tuple with s3_path and timestamp."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            result = _upload_to_s3(
                artifact_name="test.json",
                artifact_hash="sha256:abc",
                s3_bucket="bucket",
                s3_prefix="scans/",
            )

        assert isinstance(result, tuple)
        assert len(result) == 2
        s3_path, timestamp = result
        assert isinstance(s3_path, str)
        assert isinstance(timestamp, str)
        assert len(s3_path) > 0
        assert len(timestamp) > 0

    def test_upload_to_s3_error_handling(self):
        """Test exception is logged and re-raised."""
        mock_s3 = Mock()
        mock_s3.put_object.side_effect = Exception("S3 upload failed")

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            with pytest.raises(Exception) as exc_info:
                _upload_to_s3(
                    artifact_name="test.json",
                    artifact_hash="sha256:abc",
                    s3_bucket="bucket",
                    s3_prefix="scans/",
                )

        assert "S3 upload failed" in str(exc_info.value)

    def test_upload_to_s3_content_type(self):
        """Test content type is set to text/plain."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _upload_to_s3(
                artifact_name="test.json",
                artifact_hash="sha256:abc",
                s3_bucket="bucket",
                s3_prefix="scans/",
            )

        call_args = mock_s3.put_object.call_args[1]
        assert call_args["ContentType"] == "text/plain"

    def test_upload_to_s3_bucket_and_key(self):
        """Test correct bucket and key are used."""
        mock_s3 = Mock()

        with patch("certus_transform.routers.verification.get_s3_client", return_value=mock_s3):
            _upload_to_s3(
                artifact_name="artifact.sarif",
                artifact_hash="sha256:xyz",
                s3_bucket="my-raw-bucket",
                s3_prefix="security-scans/test/",
            )

        call_args = mock_s3.put_object.call_args[1]
        assert call_args["Bucket"] == "my-raw-bucket"
        assert call_args["Key"] == "security-scans/test/artifact.sarif"


class TestPushToOCIRegistry:
    """Test OCI registry push logic."""

    def test_push_to_oci_registry_reference_construction(self):
        """Test OCI reference format."""
        reference = _push_to_oci_registry(
            artifact_name="scan-artifacts",
            artifact_hash="sha256:abc123",
            oci_registry="registry.certus.cloud",
            oci_repository="security/scans",
            scan_id="abc123def456ghi789",
        )

        # Should have format: registry/repository:commit_short-timestamp
        assert reference.startswith("registry.certus.cloud/security/scans:")
        assert "abc123de" in reference  # First 8 chars of scan_id

    def test_push_to_oci_registry_commit_short(self):
        """Test commit_short uses first 8 characters of scan_id."""
        reference = _push_to_oci_registry(
            artifact_name="scan-artifacts",
            artifact_hash="sha256:abc",
            oci_registry="registry.example.com",
            oci_repository="repo/path",
            scan_id="abcdefghijklmnop",
        )

        # Should contain first 8 chars
        assert "abcdefgh" in reference

    def test_push_to_oci_registry_short_scan_id(self):
        """Test with scan_id shorter than 8 characters."""
        reference = _push_to_oci_registry(
            artifact_name="scan-artifacts",
            artifact_hash="sha256:abc",
            oci_registry="registry.example.com",
            oci_repository="repo",
            scan_id="short",
        )

        # Should handle short scan_id gracefully
        assert "registry.example.com/repo:" in reference

    def test_push_to_oci_registry_timestamp_in_reference(self):
        """Test timestamp is included in OCI reference."""
        reference = _push_to_oci_registry(
            artifact_name="scan-artifacts",
            artifact_hash="sha256:abc",
            oci_registry="registry.certus.cloud",
            oci_repository="scans",
            scan_id="abc123",
        )

        # Should contain a timestamp (numeric)
        parts = reference.split(":")
        assert len(parts) == 2
        tag = parts[1]
        # Tag format: commit_short-timestamp
        assert "-" in tag

    def test_push_to_oci_registry_returns_reference(self):
        """Test returns valid OCI reference string."""
        reference = _push_to_oci_registry(
            artifact_name="artifacts",
            artifact_hash="sha256:test",
            oci_registry="reg.io",
            oci_repository="path/to/repo",
            scan_id="test123",
        )

        assert isinstance(reference, str)
        assert len(reference) > 0
        assert "reg.io/path/to/repo:" in reference
