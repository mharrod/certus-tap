"""Unit tests for FileProcessor file I/O operations.

Tests the service layer abstraction for file operations including:
- S3 downloads (single file)
- S3 downloads (to local path)
- S3 object listing
- Temporary file creation
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from certus_ask.services.ingestion import FileProcessor

# Check if document processing dependencies are available
try:
    import pypdf

    DOCUMENT_PROCESSING_AVAILABLE = True
except ImportError:
    DOCUMENT_PROCESSING_AVAILABLE = False


@pytest.fixture
def mock_s3_client():
    """Create a mock S3 client for testing."""
    return MagicMock()


@pytest.fixture
def file_processor(mock_s3_client):
    """Create a FileProcessor instance with mocked S3 client."""
    return FileProcessor(s3_client=mock_s3_client)


class TestDownloadFromS3:
    """Tests for FileProcessor.download_from_s3()."""

    def test_download_from_s3_basic(self, file_processor, mock_s3_client):
        """Should download file from S3 and return bytes."""
        # Arrange
        test_content = b"test sarif content"
        mock_response = {"Body": Mock()}
        mock_response["Body"].read.return_value = test_content
        mock_s3_client.get_object.return_value = mock_response

        # Act
        result = file_processor.download_from_s3(
            bucket_name="test-bucket",
            key="scans/test.sarif",
        )

        # Assert
        assert result == test_content
        mock_s3_client.get_object.assert_called_once_with(
            Bucket="test-bucket",
            Key="scans/test.sarif",
        )

    def test_download_from_s3_empty_file(self, file_processor, mock_s3_client):
        """Should handle empty files."""
        # Arrange
        mock_response = {"Body": Mock()}
        mock_response["Body"].read.return_value = b""
        mock_s3_client.get_object.return_value = mock_response

        # Act
        result = file_processor.download_from_s3(
            bucket_name="test-bucket",
            key="empty.txt",
        )

        # Assert
        assert result == b""

    def test_download_from_s3_client_error(self, file_processor, mock_s3_client):
        """Should propagate S3 client errors."""
        from botocore.exceptions import ClientError

        # Arrange
        error_response = {"Error": {"Code": "NoSuchKey", "Message": "Not found"}}
        mock_s3_client.get_object.side_effect = ClientError(error_response, "GetObject")

        # Act & Assert
        with pytest.raises(ClientError) as exc_info:
            file_processor.download_from_s3(
                bucket_name="test-bucket",
                key="nonexistent.sarif",
            )

        assert exc_info.value.response["Error"]["Code"] == "NoSuchKey"


class TestDownloadFileToLocal:
    """Tests for FileProcessor.download_file_to_local()."""

    def test_download_file_to_local_basic(self, file_processor, mock_s3_client):
        """Should download file to local path."""
        # Arrange
        local_path = Path("/tmp/test.sarif")

        # Act
        file_processor.download_file_to_local(
            bucket_name="test-bucket",
            key="scans/test.sarif",
            local_path=local_path,
        )

        # Assert
        mock_s3_client.download_file.assert_called_once_with(
            "test-bucket",
            "scans/test.sarif",
            str(local_path),
        )

    def test_download_file_to_local_with_nested_path(self, file_processor, mock_s3_client):
        """Should handle nested local paths."""
        # Arrange
        local_path = Path("/tmp/nested/dir/test.json")

        # Act
        file_processor.download_file_to_local(
            bucket_name="my-bucket",
            key="data/nested/test.json",
            local_path=local_path,
        )

        # Assert
        mock_s3_client.download_file.assert_called_once_with(
            "my-bucket",
            "data/nested/test.json",
            str(local_path),
        )


class TestSaveToTemp:
    """Tests for FileProcessor.save_to_temp()."""

    def test_save_to_temp_basic(self, file_processor):
        """Should save bytes to temporary file."""
        # Arrange
        test_content = b'{"test": "data"}'

        # Act
        file_path = file_processor.save_to_temp(test_content, suffix=".json")

        try:
            # Assert
            assert file_path.exists()
            assert file_path.suffix == ".json"
            assert file_path.read_bytes() == test_content
        finally:
            # Cleanup
            if file_path.exists():
                file_path.unlink()

    def test_save_to_temp_sarif(self, file_processor):
        """Should save SARIF content with .sarif extension."""
        # Arrange
        sarif_content = b'{"version": "2.1.0"}'

        # Act
        file_path = file_processor.save_to_temp(sarif_content, suffix=".sarif")

        try:
            # Assert
            assert file_path.exists()
            assert file_path.suffix == ".sarif"
            content = file_path.read_bytes()
            assert content == sarif_content
        finally:
            if file_path.exists():
                file_path.unlink()

    def test_save_to_temp_default_suffix(self, file_processor):
        """Should use .tmp suffix when none provided."""
        # Arrange
        test_content = b"some data"

        # Act
        file_path = file_processor.save_to_temp(test_content)

        try:
            # Assert
            assert file_path.exists()
            assert file_path.suffix == ".tmp"
        finally:
            if file_path.exists():
                file_path.unlink()

    def test_save_to_temp_empty_content(self, file_processor):
        """Should handle empty byte content."""
        # Arrange
        empty_content = b""

        # Act
        file_path = file_processor.save_to_temp(empty_content, suffix=".txt")

        try:
            # Assert
            assert file_path.exists()
            assert file_path.read_bytes() == b""
        finally:
            if file_path.exists():
                file_path.unlink()

    def test_save_to_temp_large_content(self, file_processor):
        """Should handle large file content."""
        # Arrange
        large_content = b"x" * (10 * 1024 * 1024)  # 10MB

        # Act
        file_path = file_processor.save_to_temp(large_content, suffix=".bin")

        try:
            # Assert
            assert file_path.exists()
            assert file_path.stat().st_size == 10 * 1024 * 1024
        finally:
            if file_path.exists():
                file_path.unlink()


class TestListS3Objects:
    """Tests for FileProcessor.list_s3_objects()."""

    def test_list_s3_objects_basic(self, file_processor, mock_s3_client):
        """Should list objects in S3 bucket."""
        # Arrange
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator

        page1 = {
            "Contents": [
                {"Key": "file1.txt", "Size": 100},
                {"Key": "file2.txt", "Size": 200},
            ]
        }
        page2 = {
            "Contents": [
                {"Key": "file3.txt", "Size": 300},
            ]
        }
        mock_paginator.paginate.return_value = [page1, page2]

        # Act
        result = file_processor.list_s3_objects("test-bucket", prefix="data/")

        # Assert
        assert len(result) == 3
        assert result[0]["Key"] == "file1.txt"
        assert result[1]["Key"] == "file2.txt"
        assert result[2]["Key"] == "file3.txt"
        mock_paginator.paginate.assert_called_once_with(
            Bucket="test-bucket",
            Prefix="data/",
        )

    def test_list_s3_objects_empty_bucket(self, file_processor, mock_s3_client):
        """Should handle empty buckets."""
        # Arrange
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator
        mock_paginator.paginate.return_value = [{}]  # No "Contents" key

        # Act
        result = file_processor.list_s3_objects("empty-bucket", prefix="")

        # Assert
        assert result == []

    def test_list_s3_objects_no_prefix(self, file_processor, mock_s3_client):
        """Should list all objects when no prefix provided."""
        # Arrange
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator

        page = {
            "Contents": [
                {"Key": "root1.txt", "Size": 100},
                {"Key": "root2.txt", "Size": 200},
            ]
        }
        mock_paginator.paginate.return_value = [page]

        # Act
        result = file_processor.list_s3_objects("test-bucket")

        # Assert
        assert len(result) == 2
        mock_paginator.paginate.assert_called_once_with(
            Bucket="test-bucket",
            Prefix="",
        )

    def test_list_s3_objects_with_directory_markers(self, file_processor, mock_s3_client):
        """Should include directory markers (caller should filter them)."""
        # Arrange
        mock_paginator = Mock()
        mock_s3_client.get_paginator.return_value = mock_paginator

        page = {
            "Contents": [
                {"Key": "dir1/", "Size": 0},
                {"Key": "dir1/file.txt", "Size": 100},
                {"Key": "dir2/", "Size": 0},
            ]
        }
        mock_paginator.paginate.return_value = [page]

        # Act
        result = file_processor.list_s3_objects("test-bucket", prefix="")

        # Assert
        assert len(result) == 3
        assert any(obj["Key"] == "dir1/" for obj in result)
        assert any(obj["Key"] == "dir1/file.txt" for obj in result)


class TestFileProcessorInitialization:
    """Tests for FileProcessor initialization."""

    def test_initialization_with_s3_client(self, mock_s3_client):
        """Should initialize with S3 client."""
        from certus_ask.services.storage.s3_client import S3Client

        # Act
        processor = FileProcessor(s3_client=mock_s3_client)

        # Assert
        # FileProcessor wraps raw boto3 clients in S3Client
        assert isinstance(processor.s3_client, S3Client)
        assert processor.s3_client.client == mock_s3_client

    def test_initialization_without_s3_client(self):
        """Should initialize without S3 client (will be None)."""
        # Act
        processor = FileProcessor()

        # Assert
        assert processor.s3_client is None


class TestFileProcessorIntegration:
    """Integration-style tests combining multiple operations."""

    def test_download_and_save_workflow(self, file_processor, mock_s3_client):
        """Should download from S3 and save to temp file."""
        # Arrange
        sarif_content = b'{"version": "2.1.0", "runs": []}'
        mock_response = {"Body": Mock()}
        mock_response["Body"].read.return_value = sarif_content
        mock_s3_client.get_object.return_value = mock_response

        # Act
        downloaded_bytes = file_processor.download_from_s3("bucket", "scan.sarif")
        temp_file = file_processor.save_to_temp(downloaded_bytes, suffix=".sarif")

        try:
            # Assert
            assert temp_file.exists()
            assert temp_file.read_bytes() == sarif_content
        finally:
            if temp_file.exists():
                temp_file.unlink()


@pytest.fixture
def mock_document_store():
    """Create a mock document store for testing."""
    return MagicMock()


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service for testing."""
    return MagicMock()


@pytest.fixture
def file_processor_with_services(mock_s3_client, mock_document_store, mock_storage_service):
    """Create a FileProcessor with all dependencies mocked."""
    return FileProcessor(
        s3_client=mock_s3_client,
        document_store=mock_document_store,
        storage_service=mock_storage_service,
    )


class TestProcessFile:
    """Tests for FileProcessor.process_file()."""

    @pytest.mark.asyncio
    async def test_process_file_basic(self, file_processor_with_services, mock_storage_service):
        """Should process a single file through Haystack pipeline."""
        # Arrange
        file_content = b"test document content"
        filename = "test.txt"
        workspace_id = "workspace-123"
        ingestion_id = "ingestion-456"
        upload_dir = Path("/tmp/uploads")

        with patch("certus_ask.pipelines.preprocessing.create_preprocessing_pipeline") as mock_pipeline_factory:
            mock_pipeline = MagicMock()
            mock_pipeline_factory.return_value = mock_pipeline
            mock_pipeline.run.return_value = {
                "document_writer": {
                    "documents_written": 5,
                    "metadata_preview": [{"id": "doc1"}],
                },
                "presidio_anonymizer": {"quarantined": []},
            }

            # Act
            result = await file_processor_with_services.process_file(
                file_content=file_content,
                filename=filename,
                workspace_id=workspace_id,
                ingestion_id=ingestion_id,
                upload_dir=upload_dir,
            )

            # Assert
            assert result["documents_written"] == 5
            assert result["quarantined"] == []
            assert len(result["metadata_preview"]) == 1
            mock_storage_service.save_file_locally.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_file_with_quarantined(self, file_processor_with_services):
        """Should handle quarantined documents."""
        # Arrange
        file_content = b"sensitive content with PII"
        filename = "sensitive.txt"

        with patch("certus_ask.pipelines.preprocessing.create_preprocessing_pipeline") as mock_pipeline_factory:
            mock_pipeline = MagicMock()
            mock_pipeline_factory.return_value = mock_pipeline
            mock_pipeline.run.return_value = {
                "document_writer": {"documents_written": 0, "metadata_preview": []},
                "presidio_anonymizer": {"quarantined": ["doc1", "doc2"]},
            }

            # Act
            result = await file_processor_with_services.process_file(
                file_content=file_content,
                filename=filename,
                workspace_id="ws-1",
                ingestion_id="ing-1",
                upload_dir=Path("/tmp"),
            )

            # Assert
            assert result["quarantined"] == ["doc1", "doc2"]
            assert result["documents_written"] == 0


class TestProcessFolder:
    """Tests for FileProcessor.process_folder()."""

    @pytest.mark.asyncio
    async def test_process_folder_basic(self, file_processor_with_services, tmp_path):
        """Should process all files in folder."""
        # Arrange
        folder = tmp_path / "docs"
        folder.mkdir()
        (folder / "file1.txt").write_text("content 1")
        (folder / "file2.txt").write_text("content 2")

        with patch("certus_ask.pipelines.preprocessing.create_preprocessing_pipeline") as mock_pipeline_factory:
            mock_pipeline = MagicMock()
            mock_pipeline_factory.return_value = mock_pipeline
            mock_pipeline.run.return_value = {
                "document_writer": {"documents_written": 1, "metadata_preview": []},
                "presidio_anonymizer": {"quarantined": []},
            }

            # Act
            result = await file_processor_with_services.process_folder(
                folder_path=folder,
                workspace_id="ws-1",
                ingestion_id="ing-1",
                recursive=True,
            )

            # Assert
            assert result["processed_files"] == 2
            assert result["failed_files"] == 0
            assert result["quarantined_count"] == 0

    @pytest.mark.asyncio
    async def test_process_folder_with_errors(self, file_processor_with_services, tmp_path):
        """Should handle errors gracefully and continue processing."""
        # Arrange
        folder = tmp_path / "docs"
        folder.mkdir()
        (folder / "good.txt").write_text("good content")
        (folder / "bad.txt").write_text("bad content")

        with patch("certus_ask.pipelines.preprocessing.create_preprocessing_pipeline") as mock_pipeline_factory:
            mock_pipeline = MagicMock()
            mock_pipeline_factory.return_value = mock_pipeline

            # First call succeeds, second call fails
            mock_pipeline.run.side_effect = [
                {
                    "document_writer": {"documents_written": 1, "metadata_preview": []},
                    "presidio_anonymizer": {"quarantined": []},
                },
                Exception("Processing failed"),
            ]

            # Act
            result = await file_processor_with_services.process_folder(
                folder_path=folder,
                workspace_id="ws-1",
                ingestion_id="ing-1",
                recursive=True,
            )

            # Assert
            assert result["processed_files"] == 1
            assert result["failed_files"] == 1


class TestProcessGithub:
    """Tests for FileProcessor.process_github()."""

    @pytest.mark.skipif(
        not DOCUMENT_PROCESSING_AVAILABLE,
        reason="Document processing requires 'pypdf' (install with: pip install 'certus-tap[documents]')",
    )
    @pytest.mark.asyncio
    async def test_process_github_basic(self, file_processor_with_services, tmp_path):
        """Should clone repo and process files."""
        # Arrange
        # Create a temporary repo directory
        repo_dir = tmp_path / "repo"
        repo_dir.mkdir()

        with (
            patch("certus_ask.services.github.clone_repository") as mock_clone,
            patch("certus_ask.services.github.iter_repository_files") as mock_iter,
            patch("certus_ask.pipelines.preprocessing.create_preprocessing_pipeline") as mock_pipeline_factory,
        ):
            mock_repo = MagicMock()
            mock_repo.path = repo_dir
            mock_clone.return_value.__enter__.return_value = mock_repo
            mock_clone.return_value.__exit__.return_value = None

            mock_iter.return_value = [
                repo_dir / "README.md",
                repo_dir / "docs" / "guide.md",
            ]

            mock_pipeline = MagicMock()
            mock_pipeline_factory.return_value = mock_pipeline
            mock_pipeline.run.return_value = {
                "document_writer": {"documents_written": 2, "metadata_preview": []},
                "presidio_anonymizer": {"quarantined": []},
            }

            # Act
            result = await file_processor_with_services.process_github(
                repo_url="https://github.com/test/repo.git",
                workspace_id="ws-1",
                ingestion_id="ing-1",
                branch="main",
            )

            # Assert
            assert result["file_count"] == 2
            assert result["quarantined_count"] == 0
            mock_clone.assert_called_once()

    @pytest.mark.skipif(
        not DOCUMENT_PROCESSING_AVAILABLE,
        reason="Document processing requires 'pypdf' (install with: pip install 'certus-tap[documents]')",
    )
    @pytest.mark.asyncio
    async def test_process_github_no_files(self, file_processor_with_services, tmp_path):
        """Should raise ValidationError when no files match."""
        # Arrange
        from certus_ask.core.exceptions import ValidationError

        # Create a temporary repo directory
        repo_dir = tmp_path / "empty_repo"
        repo_dir.mkdir()

        with (
            patch("certus_ask.services.github.clone_repository") as mock_clone,
            patch("certus_ask.services.github.iter_repository_files") as mock_iter,
        ):
            mock_repo = MagicMock()
            mock_repo.path = repo_dir
            mock_clone.return_value.__enter__.return_value = mock_repo
            mock_clone.return_value.__exit__.return_value = None
            mock_iter.return_value = []  # No files found

            # Act & Assert
            with pytest.raises(ValidationError) as exc_info:
                await file_processor_with_services.process_github(
                    repo_url="https://github.com/test/empty.git",
                    workspace_id="ws-1",
                    ingestion_id="ing-1",
                )

            assert "No files matched" in str(exc_info.value)


class TestProcessWeb:
    """Tests for FileProcessor.process_web()."""

    @pytest.mark.skipif(
        not DOCUMENT_PROCESSING_AVAILABLE,
        reason="Document processing requires 'pypdf' (install with: pip install 'certus-tap[documents]')",
    )
    @pytest.mark.asyncio
    async def test_process_web_basic(self, file_processor_with_services):
        """Should fetch and process web pages."""
        # Arrange
        from unittest.mock import AsyncMock

        urls = ["https://example.com/page1", "https://example.com/page2"]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = AsyncMock()

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.text = "<html><body>Test content</body></html>"

            # Make get() return an awaitable
            async def mock_get(*args, **kwargs):
                return mock_response

            mock_client.get = mock_get

            with patch("haystack.components.converters.html.HTMLToDocument") as mock_converter_class:
                mock_converter = MagicMock()
                mock_converter_class.return_value = mock_converter
                from haystack import Document as HaystackDocument

                mock_converter.run.return_value = {"documents": [HaystackDocument(content="Test content")]}

                # Act
                result = await file_processor_with_services.process_web(
                    urls=urls,
                    workspace_id="ws-1",
                    ingestion_id="ing-1",
                )

                # Assert
                assert result["indexed_count"] == 2
                assert result["skipped_count"] == 0

    @pytest.mark.skipif(
        not DOCUMENT_PROCESSING_AVAILABLE,
        reason="Document processing requires 'pypdf' (install with: pip install 'certus-tap[documents]')",
    )
    @pytest.mark.asyncio
    async def test_process_web_with_failures(self, file_processor_with_services):
        """Should handle failed requests gracefully."""
        # Arrange
        from unittest.mock import AsyncMock

        urls = ["https://example.com/good", "https://example.com/bad"]

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value.__aenter__.return_value = mock_client
            mock_client_class.return_value.__aexit__.return_value = AsyncMock()

            # First request succeeds, second fails
            good_response = MagicMock()
            good_response.status_code = 200
            good_response.text = "<html>Good</html>"

            call_count = 0

            async def mock_get(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                if call_count == 1:
                    return good_response
                else:
                    raise Exception("Network error")

            mock_client.get = mock_get

            with patch("haystack.components.converters.html.HTMLToDocument") as mock_converter_class:
                mock_converter = MagicMock()
                mock_converter_class.return_value = mock_converter
                from haystack import Document as HaystackDocument

                mock_converter.run.return_value = {"documents": [HaystackDocument(content="Good")]}

                # Act
                result = await file_processor_with_services.process_web(
                    urls=urls,
                    workspace_id="ws-1",
                    ingestion_id="ing-1",
                )

                # Assert
                assert result["indexed_count"] == 1
                assert result["skipped_count"] == 1
                assert len(result["skipped_urls"]) == 1
