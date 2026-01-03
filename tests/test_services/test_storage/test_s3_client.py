"""Unit tests for S3Client wrapper."""

from unittest.mock import MagicMock, Mock

import pytest

from certus_ask.services.storage import S3Client


@pytest.fixture
def mock_boto3_client():
    """Create a mock boto3 S3 client."""
    return MagicMock()


@pytest.fixture
def s3_client(mock_boto3_client):
    """Create S3Client with mocked boto3 client."""
    return S3Client(mock_boto3_client)


class TestS3ClientDownload:
    """Tests for S3Client download operations."""

    def test_download_object_basic(self, s3_client, mock_boto3_client):
        """Should download object and return bytes."""
        # Arrange
        test_content = b"test file content"
        mock_response = {"Body": Mock()}
        mock_response["Body"].read.return_value = test_content
        mock_boto3_client.get_object.return_value = mock_response

        # Act
        result = s3_client.download_object("test-bucket", "path/to/file.txt")

        # Assert
        assert result == test_content
        mock_boto3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="path/to/file.txt",
        )

    def test_download_to_file_basic(self, s3_client, mock_boto3_client, tmp_path):
        """Should download object to local file."""
        # Arrange
        local_file = tmp_path / "downloaded.txt"

        # Act
        s3_client.download_to_file("test-bucket", "file.txt", local_file)

        # Assert
        mock_boto3_client.download_file.assert_called_once_with(
            "test-bucket",
            "file.txt",
            str(local_file),
        )

    def test_download_to_file_with_string_path(self, s3_client, mock_boto3_client):
        """Should accept string path."""
        # Act
        s3_client.download_to_file("bucket", "key", "/tmp/file.txt")

        # Assert
        mock_boto3_client.download_file.assert_called_once_with(
            "bucket",
            "key",
            "/tmp/file.txt",
        )


class TestS3ClientList:
    """Tests for S3Client list operations."""

    def test_list_objects_basic(self, s3_client, mock_boto3_client):
        """Should list all objects with pagination."""
        # Arrange
        mock_paginator = Mock()
        mock_boto3_client.get_paginator.return_value = mock_paginator

        page1 = {"Contents": [{"Key": "file1.txt", "Size": 100}]}
        page2 = {"Contents": [{"Key": "file2.txt", "Size": 200}]}
        mock_paginator.paginate.return_value = [page1, page2]

        # Act
        result = s3_client.list_objects("test-bucket", "prefix/")

        # Assert
        assert len(result) == 2
        assert result[0]["Key"] == "file1.txt"
        assert result[1]["Key"] == "file2.txt"
        mock_paginator.paginate.assert_called_once_with(
            Bucket="test-bucket",
            Prefix="prefix/",
        )

    def test_list_objects_empty_bucket(self, s3_client, mock_boto3_client):
        """Should handle empty bucket."""
        # Arrange
        mock_paginator = Mock()
        mock_boto3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]  # No "Contents" key

        # Act
        result = s3_client.list_objects("empty-bucket")

        # Assert
        assert result == []

    def test_list_objects_no_prefix(self, s3_client, mock_boto3_client):
        """Should list all objects when no prefix provided."""
        # Arrange
        mock_paginator = Mock()
        mock_boto3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{"Contents": [{"Key": "file.txt", "Size": 100}]}]

        # Act
        result = s3_client.list_objects("bucket")

        # Assert
        assert len(result) == 1
        mock_paginator.paginate.assert_called_once_with(
            Bucket="bucket",
            Prefix="",
        )


class TestS3ClientUpload:
    """Tests for S3Client upload operations."""

    def test_upload_object_basic(self, s3_client, mock_boto3_client):
        """Should upload bytes to S3."""
        # Arrange
        data = b"file content to upload"

        # Act
        s3_client.upload_object("bucket", "path/file.txt", data)

        # Assert
        mock_boto3_client.put_object.assert_called_once_with(
            Bucket="bucket",
            Key="path/file.txt",
            Body=data,
        )

    def test_upload_object_with_metadata(self, s3_client, mock_boto3_client):
        """Should upload with metadata."""
        # Arrange
        data = b"content"
        metadata = {"author": "test", "version": "1.0"}

        # Act
        s3_client.upload_object("bucket", "file.txt", data, metadata=metadata)

        # Assert
        mock_boto3_client.put_object.assert_called_once_with(
            Bucket="bucket",
            Key="file.txt",
            Body=data,
            Metadata=metadata,
        )

    def test_upload_file_basic(self, s3_client, mock_boto3_client, tmp_path):
        """Should upload local file to S3."""
        # Arrange
        local_file = tmp_path / "upload.txt"
        local_file.write_text("test content")

        # Act
        s3_client.upload_file("bucket", "remote/file.txt", local_file)

        # Assert
        mock_boto3_client.upload_file.assert_called_once_with(
            str(local_file),
            "bucket",
            "remote/file.txt",
            ExtraArgs=None,
        )

    def test_upload_file_with_metadata(self, s3_client, mock_boto3_client, tmp_path):
        """Should upload file with metadata."""
        # Arrange
        local_file = tmp_path / "upload.txt"
        local_file.write_text("content")
        metadata = {"type": "document"}

        # Act
        s3_client.upload_file("bucket", "file.txt", local_file, metadata=metadata)

        # Assert
        mock_boto3_client.upload_file.assert_called_once()
        call_args = mock_boto3_client.upload_file.call_args
        assert call_args[1]["ExtraArgs"]["Metadata"] == metadata


class TestS3ClientDelete:
    """Tests for S3Client delete operations."""

    def test_delete_object(self, s3_client, mock_boto3_client):
        """Should delete object from S3."""
        # Act
        s3_client.delete_object("bucket", "file.txt")

        # Assert
        mock_boto3_client.delete_object.assert_called_once_with(
            Bucket="bucket",
            Key="file.txt",
        )


class TestS3ClientUtility:
    """Tests for S3Client utility operations."""

    def test_object_exists_true(self, s3_client, mock_boto3_client):
        """Should return True when object exists."""
        # Arrange
        mock_boto3_client.head_object.return_value = {"ContentLength": 100}

        # Act
        result = s3_client.object_exists("bucket", "file.txt")

        # Assert
        assert result is True
        mock_boto3_client.head_object.assert_called_once_with(
            Bucket="bucket",
            Key="file.txt",
        )

    def test_object_exists_false(self, s3_client, mock_boto3_client):
        """Should return False when object does not exist."""
        # Arrange
        from botocore.exceptions import ClientError

        error_response = {"Error": {"Code": "404", "Message": "Not Found"}}
        mock_boto3_client.head_object.side_effect = ClientError(error_response, "HeadObject")

        # Act
        result = s3_client.object_exists("bucket", "missing.txt")

        # Assert
        assert result is False


class TestS3ClientInitialization:
    """Tests for S3Client initialization."""

    def test_initialization(self, mock_boto3_client):
        """Should initialize with boto3 client."""
        # Act
        client = S3Client(mock_boto3_client)

        # Assert
        assert client.client == mock_boto3_client
