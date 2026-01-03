"""Unit tests for StorageService storage operations.

Tests the service layer abstraction for storage including:
- Local file writes
- Directory creation
- S3 uploads with metadata
- Verification metadata storage
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from certus_ask.services.ingestion import StorageService


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client for testing."""
    return MagicMock()


@pytest.fixture
def storage_service(mock_s3_client):
    """Create a StorageService instance with mocked S3 client."""
    return StorageService(s3_client=mock_s3_client, default_bucket="test-bucket")


@pytest.fixture
def storage_service_no_s3():
    """Create a StorageService instance without S3 client."""
    return StorageService()


class TestSaveFileLocally:
    """Tests for StorageService.save_file_locally()."""

    def test_save_file_locally_basic(self, storage_service_no_s3):
        """Should save file to local filesystem."""
        # Arrange
        test_content = b"test content"

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"

            # Act
            result = storage_service_no_s3.save_file_locally(test_content, file_path)

            # Assert
            assert result.exists()
            assert result.read_bytes() == test_content
            assert result.is_absolute()

    def test_save_file_locally_creates_parent_dirs(self, storage_service_no_s3):
        """Should create parent directories if they don't exist."""
        # Arrange
        test_content = b"nested content"

        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "level1" / "level2" / "test.txt"

            # Act
            result = storage_service_no_s3.save_file_locally(test_content, nested_path)

            # Assert
            assert result.exists()
            assert result.read_bytes() == test_content
            assert result.parent.exists()

    def test_save_file_locally_overwrites_existing(self, storage_service_no_s3):
        """Should overwrite existing file."""
        # Arrange
        original_content = b"original"
        new_content = b"new content"

        with tempfile.TemporaryDirectory() as temp_dir:
            file_path = Path(temp_dir) / "test.txt"
            file_path.write_bytes(original_content)

            # Act
            result = storage_service_no_s3.save_file_locally(new_content, file_path)

            # Assert
            assert result.read_bytes() == new_content

    def test_save_file_locally_returns_absolute_path(self, storage_service_no_s3):
        """Should return absolute path even if relative path provided."""
        # Arrange
        test_content = b"content"

        with tempfile.TemporaryDirectory() as temp_dir:
            # Use relative path
            relative_path = Path("test.txt")

            with patch.object(Path, "absolute", return_value=Path(temp_dir) / "test.txt"):
                # Act
                result = storage_service_no_s3.save_file_locally(test_content, relative_path)

                # Assert
                assert result.is_absolute()


class TestEnsureDirectory:
    """Tests for StorageService.ensure_directory()."""

    def test_ensure_directory_creates_new(self, storage_service_no_s3):
        """Should create directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            new_dir = Path(temp_dir) / "new_directory"

            # Act
            result = storage_service_no_s3.ensure_directory(new_dir)

            # Assert
            assert result.exists()
            assert result.is_dir()
            assert result.is_absolute()

    def test_ensure_directory_handles_existing(self, storage_service_no_s3):
        """Should handle existing directories without error."""
        with tempfile.TemporaryDirectory() as temp_dir:
            existing_dir = Path(temp_dir)

            # Act
            result = storage_service_no_s3.ensure_directory(existing_dir)

            # Assert
            assert result.exists()
            assert result.is_dir()

    def test_ensure_directory_creates_nested(self, storage_service_no_s3):
        """Should create nested directories."""
        with tempfile.TemporaryDirectory() as temp_dir:
            nested_dir = Path(temp_dir) / "level1" / "level2" / "level3"

            # Act
            result = storage_service_no_s3.ensure_directory(nested_dir)

            # Assert
            assert result.exists()
            assert result.is_dir()


class TestUploadToS3:
    """Tests for StorageService.upload_to_s3()."""

    def test_upload_to_s3_basic(self, storage_service, mock_s3_client):
        """Should upload file to S3."""
        # Arrange
        test_content = b"test sarif content"
        mock_s3_client.put_object.return_value = {"ETag": '"abc123"'}

        # Act
        result = storage_service.upload_to_s3(
            file_content=test_content,
            key="scans/test.sarif",
        )

        # Assert
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "scans/test.sarif"
        assert result["uri"] == "s3://test-bucket/scans/test.sarif"
        assert result["etag"] == "abc123"

        mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="scans/test.sarif",
            Body=test_content,
        )

    def test_upload_to_s3_with_custom_bucket(self, storage_service, mock_s3_client):
        """Should use custom bucket when provided."""
        # Arrange
        test_content = b"content"
        mock_s3_client.put_object.return_value = {"ETag": '"xyz789"'}

        # Act
        result = storage_service.upload_to_s3(
            file_content=test_content,
            key="data/file.json",
            bucket="custom-bucket",
        )

        # Assert
        assert result["bucket"] == "custom-bucket"
        assert result["uri"] == "s3://custom-bucket/data/file.json"

    def test_upload_to_s3_with_metadata(self, storage_service, mock_s3_client):
        """Should include metadata in S3 upload."""
        # Arrange
        test_content = b"content"
        metadata = {"tier": "premium", "assessment_id": "assess-123"}
        mock_s3_client.put_object.return_value = {"ETag": '"def456"'}

        # Act
        result = storage_service.upload_to_s3(
            file_content=test_content,
            key="scans/premium.sarif",
            metadata=metadata,
        )

        # Assert
        mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="scans/premium.sarif",
            Body=test_content,
            Metadata=metadata,
        )

    def test_upload_to_s3_with_content_type(self, storage_service, mock_s3_client):
        """Should include content type in S3 upload."""
        # Arrange
        test_content = b'{"json": "data"}'
        mock_s3_client.put_object.return_value = {"ETag": '"ghi789"'}

        # Act
        result = storage_service.upload_to_s3(
            file_content=test_content,
            key="data/test.json",
            content_type="application/json",
        )

        # Assert
        mock_s3_client.put_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="data/test.json",
            Body=test_content,
            ContentType="application/json",
        )

    def test_upload_to_s3_no_default_bucket_raises(self, mock_s3_client):
        """Should raise ValueError when no bucket specified."""
        # Arrange
        storage = StorageService(s3_client=mock_s3_client)  # No default bucket

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            storage.upload_to_s3(
                file_content=b"content",
                key="file.txt",
            )

        assert "Bucket name must be specified" in str(exc_info.value)


class TestStoreVerificationMetadata:
    """Tests for StorageService.store_verification_metadata()."""

    def test_store_verification_metadata_basic(self, storage_service, mock_s3_client):
        """Should store verification proof as JSON in S3."""
        # Arrange
        verification_proof = {
            "chain_verified": True,
            "signer_outer": "user@example.com",
            "sigstore_timestamp": "2025-01-01T00:00:00Z",
        }
        mock_s3_client.put_object.return_value = {"ETag": '"meta123"'}

        # Act
        result = storage_service.store_verification_metadata(
            verification_proof=verification_proof,
            base_key="scans/report.sarif",
        )

        # Assert
        assert result["bucket"] == "test-bucket"
        assert result["key"] == "scans/report.sarif.metadata.json"
        assert result["uri"] == "s3://test-bucket/scans/report.sarif.metadata.json"

        # Verify S3 call
        call_args = mock_s3_client.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"] == "scans/report.sarif.metadata.json"
        assert call_args[1]["ContentType"] == "application/json"
        assert call_args[1]["Metadata"] == {"type": "verification-proof"}

        # Verify JSON content
        uploaded_json = call_args[1]["Body"]
        parsed = json.loads(uploaded_json)
        assert parsed == verification_proof

    def test_store_verification_metadata_with_custom_bucket(self, storage_service, mock_s3_client):
        """Should use custom bucket when provided."""
        # Arrange
        verification_proof = {"verified": True}
        mock_s3_client.put_object.return_value = {"ETag": '"custom123"'}

        # Act
        result = storage_service.store_verification_metadata(
            verification_proof=verification_proof,
            base_key="scans/test.sarif",
            bucket="custom-bucket",
        )

        # Assert
        assert result["bucket"] == "custom-bucket"
        assert "custom-bucket" in result["uri"]

    def test_store_verification_metadata_no_default_bucket_raises(self, mock_s3_client):
        """Should raise ValueError when no bucket specified."""
        # Arrange
        storage = StorageService(s3_client=mock_s3_client)  # No default bucket
        verification_proof = {"verified": True}

        # Act & Assert
        with pytest.raises(ValueError) as exc_info:
            storage.store_verification_metadata(
                verification_proof=verification_proof,
                base_key="scans/test.sarif",
            )

        assert "Bucket name must be specified" in str(exc_info.value)


class TestStorageServiceInitialization:
    """Tests for StorageService initialization."""

    def test_initialization_with_s3_and_bucket(self, mock_s3_client):
        """Should initialize with S3 client and default bucket."""
        # Act
        storage = StorageService(s3_client=mock_s3_client, default_bucket="my-bucket")

        # Assert
        assert storage.s3_client == mock_s3_client
        assert storage.default_bucket == "my-bucket"

    def test_initialization_without_s3(self):
        """Should initialize without S3 client (for local operations only)."""
        # Act
        storage = StorageService()

        # Assert
        assert storage.s3_client is None
        assert storage.default_bucket is None


class TestStorageServiceIntegration:
    """Integration-style tests combining multiple operations."""

    def test_save_and_upload_workflow(self, storage_service, mock_s3_client):
        """Should save locally then upload to S3."""
        # Arrange
        test_content = b"important data"
        mock_s3_client.put_object.return_value = {"ETag": '"workflow123"'}

        with tempfile.TemporaryDirectory() as temp_dir:
            local_path = Path(temp_dir) / "data.json"

            # Act - Save locally
            saved_path = storage_service.save_file_locally(test_content, local_path)

            # Act - Upload to S3
            s3_result = storage_service.upload_to_s3(
                file_content=saved_path.read_bytes(),
                key="backups/data.json",
            )

            # Assert
            assert saved_path.exists()
            assert s3_result["uri"] == "s3://test-bucket/backups/data.json"
