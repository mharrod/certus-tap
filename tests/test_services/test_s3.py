"""
Unit tests for S3 service layer.

Tests cover:
- S3 client initialization
- Bucket operations (create, exists, delete)
- File operations (upload, download, delete)
- Directory operations
- Error handling and resilience
"""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError, EndpointConnectionError

pytestmark = pytest.mark.integration


class TestS3ClientInitialization:
    """Tests for S3 client setup."""

    def test_client_initialization(self, mock_s3_client):
        """Test S3 client is properly initialized."""
        assert mock_s3_client is not None

    def test_client_with_custom_endpoint(self, override_s3_settings, mock_s3_client):
        """Test S3 client with custom endpoint (LocalStack)."""
        assert mock_s3_client is not None


class TestBucketOperations:
    """Tests for bucket-level operations."""

    def test_bucket_exists(self, s3_with_buckets):
        """Test checking if bucket exists."""
        # Create response
        response = s3_with_buckets.head_bucket(Bucket="raw-bucket")
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_bucket_not_exists(self, mock_s3_client):
        """Test checking non-existent bucket."""
        with pytest.raises(ClientError) as exc_info:
            mock_s3_client.head_bucket(Bucket="nonexistent-bucket")

        assert exc_info.value.response["Error"]["Code"] == "404"

    def test_create_bucket(self, mock_s3_client):
        """Test creating a bucket."""
        response = mock_s3_client.create_bucket(Bucket="test-bucket")
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_create_bucket_already_exists(self):
        """Simulate an error when creating an already existing bucket."""
        client = MagicMock()
        client.create_bucket.side_effect = ClientError({"Error": {"Code": "BucketAlreadyOwnedByYou"}}, "CreateBucket")

        with pytest.raises(ClientError):
            client.create_bucket(Bucket="raw-bucket")

    def test_delete_bucket(self, mock_s3_client):
        """Test deleting a bucket."""
        mock_s3_client.create_bucket(Bucket="test-delete")
        response = mock_s3_client.delete_bucket(Bucket="test-delete")
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 204

    def test_list_buckets(self, s3_with_buckets):
        """Test listing all buckets."""
        response = s3_with_buckets.list_buckets()
        assert len(response["Buckets"]) >= 2  # raw-bucket and golden-bucket


class TestFileOperations:
    """Tests for file-level operations."""

    def test_put_object(self, s3_with_buckets, sample_text_document):
        """Test uploading a file."""
        response = s3_with_buckets.put_object(
            Bucket="raw-bucket", Key="documents/test.txt", Body=sample_text_document.encode()
        )
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

    def test_get_object(self, s3_with_buckets, sample_text_document):
        """Test downloading a file."""
        # Upload first
        s3_with_buckets.put_object(Bucket="raw-bucket", Key="documents/test.txt", Body=sample_text_document.encode())

        # Download
        response = s3_with_buckets.get_object(Bucket="raw-bucket", Key="documents/test.txt")
        body = response["Body"].read()

        assert sample_text_document.encode() == body

    def test_get_nonexistent_object(self, s3_with_buckets):
        """Test getting non-existent object."""
        with pytest.raises(ClientError) as exc_info:
            s3_with_buckets.get_object(Bucket="raw-bucket", Key="nonexistent.txt")

        assert exc_info.value.response["Error"]["Code"] == "NoSuchKey"

    def test_delete_object(self, s3_with_buckets, sample_text_document):
        """Test deleting a file."""
        # Upload
        s3_with_buckets.put_object(Bucket="raw-bucket", Key="documents/test.txt", Body=sample_text_document.encode())

        # Delete
        response = s3_with_buckets.delete_object(Bucket="raw-bucket", Key="documents/test.txt")
        assert response["ResponseMetadata"]["HTTPStatusCode"] == 204

        # Verify deleted
        with pytest.raises(ClientError):
            s3_with_buckets.get_object(Bucket="raw-bucket", Key="documents/test.txt")

    def test_put_object_with_metadata(self, s3_with_buckets):
        """Test uploading file with metadata."""
        response = s3_with_buckets.put_object(
            Bucket="raw-bucket",
            Key="documents/metadata-test.txt",
            Body=b"test content",
            Metadata={"source": "test", "category": "privacy"},
        )

        assert response["ResponseMetadata"]["HTTPStatusCode"] == 200

        # Retrieve and verify metadata
        obj = s3_with_buckets.head_object(Bucket="raw-bucket", Key="documents/metadata-test.txt")
        assert obj["Metadata"]["source"] == "test"

    def test_copy_object(self, s3_with_buckets, sample_text_document):
        """Test copying a file."""
        # Upload original
        s3_with_buckets.put_object(
            Bucket="raw-bucket", Key="documents/original.txt", Body=sample_text_document.encode()
        )

        # Copy to another location
        s3_with_buckets.copy_object(
            CopySource={"Bucket": "raw-bucket", "Key": "documents/original.txt"},
            Bucket="golden-bucket",
            Key="documents/copy.txt",
        )

        # Verify copy exists
        obj = s3_with_buckets.get_object(Bucket="golden-bucket", Key="documents/copy.txt")
        assert obj["Body"].read() == sample_text_document.encode()


class TestFolderOperations:
    """Tests for directory/folder operations."""

    def test_create_folder_structure(self, s3_with_buckets):
        """Test creating folder structure."""
        folders = ["input", "processing", "output"]

        for folder in folders:
            s3_with_buckets.put_object(Bucket="raw-bucket", Key=f"{folder}/")

        # Verify folders created
        response = s3_with_buckets.list_objects_v2(Bucket="raw-bucket")
        keys = [obj["Key"] for obj in response.get("Contents", [])]

        assert any("input" in key for key in keys)
        assert any("processing" in key for key in keys)
        assert any("output" in key for key in keys)

    def test_list_objects_in_folder(self, s3_with_buckets, sample_text_document):
        """Test listing objects in a folder."""
        # Create files
        for i in range(3):
            s3_with_buckets.put_object(
                Bucket="raw-bucket", Key=f"documents/file{i}.txt", Body=sample_text_document.encode()
            )

        # List
        response = s3_with_buckets.list_objects_v2(Bucket="raw-bucket", Prefix="documents/")

        assert len(response["Contents"]) == 3

    def test_empty_folder(self, s3_with_buckets):
        """Test empty folder exists."""
        # Create empty folder
        s3_with_buckets.put_object(Bucket="raw-bucket", Key="empty-folder/")

        # List should show it
        response = s3_with_buckets.list_objects_v2(Bucket="raw-bucket", Prefix="empty-folder")

        assert "Contents" in response


class TestObjectMetadata:
    """Tests for object metadata operations."""

    def test_head_object(self, s3_with_buckets, sample_text_document):
        """Test getting object metadata without downloading."""
        s3_with_buckets.put_object(Bucket="raw-bucket", Key="documents/test.txt", Body=sample_text_document.encode())

        response = s3_with_buckets.head_object(Bucket="raw-bucket", Key="documents/test.txt")

        assert response["ContentLength"] == len(sample_text_document.encode())
        assert "LastModified" in response

    def test_get_object_size(self, s3_with_buckets, sample_text_document):
        """Test getting file size."""
        content = sample_text_document.encode()
        s3_with_buckets.put_object(Bucket="raw-bucket", Key="documents/test.txt", Body=content)
        response = s3_with_buckets.head_object(Bucket="raw-bucket", Key="documents/test.txt")
        assert response["ContentLength"] == len(content)

    def test_get_content_type(self, s3_with_buckets):
        """Test getting content type."""
        s3_with_buckets.put_object(
            Bucket="raw-bucket", Key="documents/test.pdf", Body=b"PDF content", ContentType="application/pdf"
        )

        response = s3_with_buckets.head_object(Bucket="raw-bucket", Key="documents/test.pdf")

        assert response["ContentType"] == "application/pdf"


def test_get_s3_client_is_cached(monkeypatch):
    """The S3 factory should cache the boto3 client and reuse credentials."""
    from certus_ask.services import s3 as s3_service

    created = []

    class DummyClient:
        pass

    def fake_client(*args, **kwargs):
        created.append(kwargs)
        return DummyClient()

    monkeypatch.setattr("certus_ask.services.s3.boto3.client", fake_client)
    monkeypatch.setattr(
        "certus_ask.services.s3.settings",
        SimpleNamespace(
            s3_endpoint_url="http://localhost:4566",
            aws_access_key_id="test",
            aws_secret_access_key="secret",
            aws_region="us-east-1",
        ),
    )

    s3_service.get_s3_client.cache_clear()
    client1 = s3_service.get_s3_client()
    client2 = s3_service.get_s3_client()

    assert client1 is client2
    assert created[0]["endpoint_url"] == "http://localhost:4566"


class TestMultipartUpload:
    """Tests for multipart upload operations."""

    def test_multipart_upload(self, s3_with_buckets):
        """Test uploading large file in parts."""
        # Start multipart upload
        response = s3_with_buckets.create_multipart_upload(Bucket="raw-bucket", Key="documents/large-file.bin")

        upload_id = response["UploadId"]
        assert upload_id is not None

    def test_abort_multipart_upload(self, s3_with_buckets):
        """Test aborting multipart upload."""
        # Start
        response = s3_with_buckets.create_multipart_upload(Bucket="raw-bucket", Key="documents/large-file.bin")

        # Abort
        abort_response = s3_with_buckets.abort_multipart_upload(
            Bucket="raw-bucket", Key="documents/large-file.bin", UploadId=response["UploadId"]
        )

        assert abort_response["ResponseMetadata"]["HTTPStatusCode"] == 204


class TestErrorHandling:
    """Tests for error scenarios."""

    def test_bucket_not_found(self, mock_s3_client):
        """Test accessing non-existent bucket."""
        with pytest.raises(ClientError):
            mock_s3_client.put_object(Bucket="nonexistent-bucket", Key="test.txt", Body=b"test")

    def test_access_denied(self):
        """Test access denied error."""
        mock_s3_client = MagicMock()
        mock_s3_client.head_bucket.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}}, "HeadBucket"
        )

        with pytest.raises(ClientError):
            mock_s3_client.head_bucket(Bucket="restricted-bucket")

    def test_network_error(self):
        """Test network/connection error."""
        mock_s3_client = MagicMock()
        mock_s3_client.list_buckets.side_effect = EndpointConnectionError(endpoint_url="http://localhost:4566")

        with pytest.raises(EndpointConnectionError):
            mock_s3_client.list_buckets()


class TestS3WorkflowIntegration:
    """Integration tests for complete S3 workflows."""

    def test_document_processing_workflow(self, s3_with_buckets, sample_text_document):
        """Test complete document processing workflow."""
        # 1. Upload raw document
        raw_key = "raw/document.txt"
        s3_with_buckets.put_object(Bucket="raw-bucket", Key=raw_key, Body=sample_text_document.encode())

        # 2. Download for processing
        raw_obj = s3_with_buckets.get_object(Bucket="raw-bucket", Key=raw_key)
        content = raw_obj["Body"].read().decode()

        # 3. Process (simulate)
        processed_content = content.upper()

        # 4. Upload processed version
        golden_key = "processed/document.txt"
        s3_with_buckets.put_object(Bucket="golden-bucket", Key=golden_key, Body=processed_content.encode())

        # 5. Verify both versions exist
        raw = s3_with_buckets.get_object(Bucket="raw-bucket", Key=raw_key)
        processed = s3_with_buckets.get_object(Bucket="golden-bucket", Key=golden_key)

        assert raw["Body"].read().decode() == sample_text_document
        assert processed["Body"].read().decode() == processed_content

    def test_batch_file_upload(self, s3_with_buckets, document_factory):
        """Test uploading batch of files."""
        docs = document_factory.create_batch(count=5)

        # Upload all
        for i, doc in enumerate(docs):
            s3_with_buckets.put_object(Bucket="raw-bucket", Key=f"batch/document-{i}.txt", Body=doc["content"].encode())

        # Verify all uploaded
        response = s3_with_buckets.list_objects_v2(Bucket="raw-bucket", Prefix="batch/")

        assert len(response["Contents"]) == 5

    def test_move_file_between_buckets(self, s3_with_buckets, sample_text_document):
        """Test moving file from raw to golden bucket."""
        raw_key = "incoming/document.txt"
        golden_key = "approved/document.txt"

        # Upload to raw
        s3_with_buckets.put_object(Bucket="raw-bucket", Key=raw_key, Body=sample_text_document.encode())

        # Copy to golden
        s3_with_buckets.copy_object(
            CopySource={"Bucket": "raw-bucket", "Key": raw_key}, Bucket="golden-bucket", Key=golden_key
        )

        # Delete from raw
        s3_with_buckets.delete_object(Bucket="raw-bucket", Key=raw_key)

        # Verify: exists in golden, not in raw
        golden_obj = s3_with_buckets.get_object(Bucket="golden-bucket", Key=golden_key)
        assert golden_obj["Body"].read() == sample_text_document.encode()

        with pytest.raises(ClientError):
            s3_with_buckets.get_object(Bucket="raw-bucket", Key=raw_key)
