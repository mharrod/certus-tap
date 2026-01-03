"""File and document processing service.

Handles file I/O operations and document processing for general ingestion:
- S3 downloads (single file and batch)
- Temporary file creation and management
- Document processing through Haystack pipelines
- Folder and GitHub repository ingestion
- Web scraping and indexing
"""

import tempfile
from pathlib import Path
from typing import Any, Optional

import structlog

from certus_ask.core.exceptions import ValidationError

logger = structlog.get_logger(__name__)


class FileProcessor:
    """Service for file and document processing during ingestion.

    This service encapsulates:
    - File I/O operations (S3 downloads, temp files)
    - Document processing through Haystack pipelines
    - Batch processing (folders, GitHub repos)
    - Web scraping and indexing

    Dependencies are injected via constructor to enable testing and reuse.
    """

    def __init__(
        self,
        s3_client: Optional[Any] = None,
        document_store: Optional[Any] = None,
        storage_service: Optional[Any] = None,
    ):
        """Initialize the file processor.

        Args:
            s3_client: S3Client wrapper or boto3 S3 client (for backwards compatibility)
            document_store: OpenSearch document store
            storage_service: Storage service for file operations
        """
        # Support both S3Client wrapper and raw boto3 client for backwards compatibility
        from certus_ask.services.storage import S3Client

        if s3_client is not None and not isinstance(s3_client, S3Client):
            # Wrap raw boto3 client
            self.s3_client = S3Client(s3_client)
        else:
            self.s3_client = s3_client

        self.document_store = document_store
        self.storage_service = storage_service
        logger.info("FileProcessor initialized")

    def download_from_s3(
        self,
        bucket_name: str,
        key: str,
    ) -> bytes:
        """Download a file from S3 and return its contents as bytes.

        Args:
            bucket_name: S3 bucket name
            key: S3 object key

        Returns:
            File contents as bytes

        Raises:
            Exception: If S3 download fails (boto3 ClientError or other exceptions)
        """
        if self.s3_client is None:
            raise ValueError("S3 client not configured")

        return self.s3_client.download_object(bucket_name, key)

    def download_file_to_local(
        self,
        bucket_name: str,
        key: str,
        local_path: Path,
    ) -> None:
        """Download a file from S3 to a local file path.

        Args:
            bucket_name: S3 bucket name
            key: S3 object key
            local_path: Local filesystem path to save the file

        Raises:
            Exception: If S3 download fails (boto3 ClientError or other exceptions)
        """
        if self.s3_client is None:
            raise ValueError("S3 client not configured")

        self.s3_client.download_to_file(bucket_name, key, local_path)

    def save_to_temp(
        self,
        file_bytes: bytes,
        suffix: Optional[str] = None,
    ) -> Path:
        """Save bytes to a temporary file and return the path.

        The temporary file is created with delete=False, so the caller
        is responsible for cleanup.

        Args:
            file_bytes: File content as bytes
            suffix: File extension (e.g., ".sarif", ".json")

        Returns:
            Path to the temporary file

        Example:
            >>> file_path = file_processor.save_to_temp(sarif_bytes, ".sarif")
            >>> try:
            ...     # Process file_path
            ...     pass
            ... finally:
            ...     file_path.unlink()  # Clean up
        """
        if suffix is None:
            suffix = ".tmp"

        logger.debug(
            "save_to_temp.start",
            size_bytes=len(file_bytes),
            suffix=suffix,
        )

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp_file:
            file_path = Path(tmp_file.name)
            tmp_file.write(file_bytes)
            tmp_file.flush()

        logger.debug(
            "save_to_temp.complete",
            file_path=str(file_path),
            size_bytes=len(file_bytes),
        )

        return file_path

    def list_s3_objects(
        self,
        bucket_name: str,
        prefix: str = "",
    ) -> list[dict[str, Any]]:
        """List all objects in an S3 bucket with the given prefix.

        Automatically handles pagination to retrieve all objects.

        Args:
            bucket_name: S3 bucket name
            prefix: S3 key prefix to filter objects (default: "" for all objects)

        Returns:
            List of object dictionaries from S3, each containing:
            - Key: str (object key)
            - Size: int (size in bytes)
            - LastModified: datetime
            - ETag: str
            - StorageClass: str

        Raises:
            Exception: If S3 listing fails (boto3 ClientError or other exceptions)

        Example:
            >>> objects = file_processor.list_s3_objects("my-bucket", "scans/")
            >>> for obj in objects:
            ...     if not obj["Key"].endswith("/"):  # Skip directory markers
            ...         print(obj["Key"], obj["Size"])
        """
        if self.s3_client is None:
            raise ValueError("S3 client not configured")

        return self.s3_client.list_objects(bucket_name, prefix)

    async def process_file(
        self,
        file_content: bytes,
        filename: str,
        workspace_id: str,
        ingestion_id: str,
        upload_dir: Path,
    ) -> dict[str, Any]:
        """Process a single uploaded file through Haystack pipeline.

        Saves file locally, processes through preprocessing pipeline,
        and indexes documents in OpenSearch.

        Args:
            file_content: File bytes
            filename: Original filename
            workspace_id: Workspace identifier
            ingestion_id: Unique ingestion ID for tracking
            upload_dir: Directory to save file

        Returns:
            Dictionary with processing results:
            - documents_written: int
            - quarantined: list
            - metadata_preview: list

        Raises:
            Exception: If processing fails
        """
        from certus_ask.pipelines.preprocessing import create_preprocessing_pipeline

        logger.info(
            "process_file.start",
            filename=filename,
            workspace_id=workspace_id,
            ingestion_id=ingestion_id,
        )

        # Ensure upload directory exists
        if self.storage_service:
            self.storage_service.ensure_directory(upload_dir)
        else:
            upload_dir.mkdir(parents=True, exist_ok=True)

        file_path = upload_dir / filename

        try:
            # Save file locally
            if self.storage_service:
                self.storage_service.save_file_locally(file_content, file_path)
            else:
                file_path.write_bytes(file_content)

            logger.info(
                "process_file.file_saved",
                file_path=str(file_path),
                size_bytes=len(file_content),
            )

            # Create and run Haystack pipeline
            pipeline = create_preprocessing_pipeline(self.document_store)

            result = pipeline.run({
                "file_type_router": {"sources": [file_path]},
                "document_writer": {
                    "metadata_context": {
                        "workspace_id": workspace_id,
                        "ingestion_id": ingestion_id,
                        "source": "upload",
                        "source_location": str(file_path),
                        "extra_meta": {"filename": filename},
                    }
                },
            })

            # Extract results
            writer_result = result.get("document_writer") or {}
            documents_written = writer_result.get("documents_written", 0)
            metadata_preview = writer_result.get("metadata_preview", [])

            quarantined = result.get("presidio_anonymizer", {}).get("quarantined", [])
            if quarantined:
                logger.warning(
                    "process_file.quarantined",
                    filename=filename,
                    quarantined_count=len(quarantined),
                )

            logger.info(
                "process_file.complete",
                filename=filename,
                documents_written=documents_written,
                quarantined_count=len(quarantined),
            )

            return {
                "documents_written": documents_written,
                "quarantined": quarantined,
                "metadata_preview": metadata_preview[:3],  # First 3 for preview
            }

        finally:
            # Cleanup
            if file_path.exists():
                file_path.unlink()

    async def process_folder(
        self,
        folder_path: Path,
        workspace_id: str,
        ingestion_id: str,
        recursive: bool = False,
        pattern: str | None = None,
    ) -> dict[str, Any]:
        """Process all files in a folder through Haystack pipeline.

        Args:
            folder_path: Path to folder
            workspace_id: Workspace identifier
            ingestion_id: Unique ingestion ID for tracking
            recursive: Whether to process subfolders recursively
            pattern: Optional glob pattern override (e.g., "**/*.md")

        Returns:
            Dictionary with processing results:
            - processed_files: int
            - failed_files: int
            - metadata_preview: list

        Raises:
            ValueError: If folder_path is not a directory
        """
        from certus_ask.pipelines.preprocessing import create_preprocessing_pipeline

        if not folder_path.is_dir():
            raise ValueError(f"{folder_path} is not a valid directory")

        logger.info(
            "process_folder.start",
            folder_path=str(folder_path),
            workspace_id=workspace_id,
            recursive=recursive,
        )

        # Create pipeline
        pipeline = create_preprocessing_pipeline(self.document_store)

        processed_files = 0
        failed_files = 0
        quarantined_count = 0
        metadata_preview = []

        # Determine glob pattern
        glob_pattern = pattern if pattern else ("**/*" if recursive else "*")

        for file_path in folder_path.glob(glob_pattern):
            if not file_path.is_file():
                continue

            try:
                logger.info(
                    "process_folder.processing_file",
                    file_path=str(file_path),
                )

                result = pipeline.run({
                    "file_type_router": {"sources": [file_path]},
                    "document_writer": {
                        "metadata_context": {
                            "workspace_id": workspace_id,
                            "ingestion_id": ingestion_id,
                            "source": "folder",
                            "source_location": str(file_path),
                            "extra_meta": {"filename": file_path.name},
                        }
                    },
                })

                processed_files += 1

                # Track quarantined documents
                quarantined = result.get("presidio_anonymizer", {}).get("quarantined", [])
                if quarantined:
                    quarantined_count += len(quarantined)
                    logger.warning(
                        "process_folder.file_quarantined",
                        file_path=str(file_path),
                        quarantined_count=len(quarantined),
                    )

                # Collect metadata preview (up to 3 files)
                if len(metadata_preview) < 3:
                    writer_result = result.get("document_writer") or {}
                    preview = writer_result.get("metadata_preview", [])
                    metadata_preview.extend(preview[: 3 - len(metadata_preview)])

            except Exception as exc:
                failed_files += 1
                logger.error(
                    "process_folder.file_failed",
                    file_path=str(file_path),
                    error=str(exc),
                )
                continue

        logger.info(
            "process_folder.complete",
            folder_path=str(folder_path),
            processed_files=processed_files,
            failed_files=failed_files,
            quarantined_count=quarantined_count,
        )

        return {
            "processed_files": processed_files,
            "failed_files": failed_files,
            "quarantined_count": quarantined_count,
            "metadata_preview": metadata_preview,
        }

    async def process_github(
        self,
        repo_url: str,
        workspace_id: str,
        ingestion_id: str,
        branch: Optional[str] = None,
        include_globs: Optional[list[str]] = None,
        exclude_globs: Optional[list[str]] = None,
        max_file_size_kb: int = 256,
    ) -> dict[str, Any]:
        """Process files from a GitHub repository.

        Clones repository and processes matching files through Haystack pipeline.

        Args:
            repo_url: GitHub repository URL
            workspace_id: Workspace identifier
            ingestion_id: Unique ingestion ID for tracking
            branch: Git branch to clone (default: None for default branch)
            file_globs: List of glob patterns to match files (default: ["**/*.md"])

        Returns:
            Dictionary with processing results:
            - processed_files: int
            - failed_files: int
            - metadata_preview: list

        Raises:
            Exception: If cloning or processing fails
        """
        from certus_ask.pipelines.preprocessing import create_preprocessing_pipeline
        from certus_ask.services.github import clone_repository, iter_repository_files

        logger.info(
            "process_github.start",
            repo_url=repo_url,
            workspace_id=workspace_id,
            branch=branch,
        )

        requested_includes = include_globs or []
        requested_excludes = exclude_globs or []

        # Clone repository and ensure cleanup
        with clone_repository(repo_url, branch=branch) as repo:
            repo_path = repo.path

            pipeline = create_preprocessing_pipeline(self.document_store)
            matching_files = iter_repository_files(
                repo_path,
                include_globs=requested_includes or None,
                exclude_globs=requested_excludes or None,
                max_file_size_kb=max_file_size_kb,
            )

            if not matching_files:
                raise ValidationError(
                    message="No files matched the provided patterns",
                    error_code="no_matching_files",
                    details={
                        "include_globs": requested_includes or None,
                        "exclude_globs": requested_excludes or None,
                        "max_file_size_kb": max_file_size_kb,
                    },
                )

            file_count = 0
            failed_files = 0
            quarantined_count = 0
            metadata_preview: list[dict[str, Any]] = []

            for file_path in matching_files:
                try:
                    logger.info(
                        "process_github.processing_file",
                        file_path=str(file_path),
                        repo_url=repo_url,
                    )

                    result = pipeline.run({
                        "file_type_router": {"sources": [file_path]},
                        "document_writer": {
                            "metadata_context": {
                                "workspace_id": workspace_id,
                                "ingestion_id": ingestion_id,
                                "source": "github",
                                "source_location": repo_url,
                                "extra_meta": {
                                    "filename": file_path.name,
                                    "repo_url": repo_url,
                                    "branch": branch or "default",
                                },
                            }
                        },
                    })

                    file_count += 1

                    quarantined = result.get("presidio_anonymizer", {}).get("quarantined", [])
                    if quarantined:
                        quarantined_count += len(quarantined)
                        logger.warning(
                            "process_github.file_quarantined",
                            file_path=str(file_path),
                            quarantined_count=len(quarantined),
                        )

                    if len(metadata_preview) < 3:
                        writer_result = result.get("document_writer") or {}
                        preview = writer_result.get("metadata_preview", [])
                        metadata_preview.extend(preview[: 3 - len(metadata_preview)])

                except Exception as exc:
                    failed_files += 1
                    logger.error(
                        "process_github.file_failed",
                        file_path=str(file_path),
                        error=str(exc),
                    )

            logger.info(
                "process_github.complete",
                repo_url=repo_url,
                file_count=file_count,
                failed_files=failed_files,
                quarantined_count=quarantined_count,
            )

            return {
                "file_count": file_count,
                "failed_files": failed_files,
                "quarantined_count": quarantined_count,
                "metadata_preview": metadata_preview,
            }

    async def process_web(
        self,
        urls: list[str],
        workspace_id: str,
        ingestion_id: str,
    ) -> dict[str, Any]:
        """Process web pages by URL.

        Fetches HTML content and processes through Haystack pipeline.

        Args:
            urls: List of URLs to fetch and process
            workspace_id: Workspace identifier
            ingestion_id: Unique ingestion ID for tracking

        Returns:
            Dictionary with processing results:
            - processed_urls: int
            - failed_urls: int
            - metadata_preview: list

        Raises:
            Exception: If fetching or processing fails
        """
        import httpx
        from haystack.components.converters import HTMLToDocument

        from certus_ask.pipelines.preprocessing import create_preprocessing_pipeline

        logger.info(
            "process_web.start",
            url_count=len(urls),
            workspace_id=workspace_id,
        )

        # Create pipeline and converter
        pipeline = create_preprocessing_pipeline(self.document_store)
        html_converter = HTMLToDocument()

        processed_urls = 0
        failed_urls = 0
        metadata_preview = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for url in urls:
                try:
                    logger.info(
                        "process_web.fetching",
                        url=url,
                    )

                    # Fetch URL
                    response = await client.get(url, follow_redirects=True)
                    response.raise_for_status()

                    # Convert HTML to document
                    html_docs = html_converter.run(sources=[response.text])
                    documents = html_docs.get("documents", [])

                    if not documents:
                        logger.warning(
                            "process_web.no_content",
                            url=url,
                        )
                        failed_urls += 1
                        continue

                    # Add metadata and index
                    for doc in documents:
                        doc.meta.update({
                            "workspace_id": workspace_id,
                            "ingestion_id": ingestion_id,
                            "source": "web",
                            "source_location": url,
                            "url": url,
                        })

                    # Write to document store
                    from haystack.components.writers import DocumentWriter

                    writer = DocumentWriter(document_store=self.document_store)
                    writer.run(documents=documents)

                    processed_urls += 1

                    # Collect metadata preview
                    if len(metadata_preview) < 3 and documents:
                        metadata_preview.append({
                            "url": url,
                            "title": documents[0].meta.get("title", "Untitled"),
                        })

                    logger.info(
                        "process_web.processed",
                        url=url,
                        document_count=len(documents),
                    )

                except Exception as exc:
                    failed_urls += 1
                    logger.error(
                        "process_web.failed",
                        url=url,
                        error=str(exc),
                    )
                    continue

        logger.info(
            "process_web.complete",
            processed_urls=processed_urls,
            failed_urls=failed_urls,
        )

        return {
            "processed_urls": processed_urls,
            "failed_urls": failed_urls,
            "metadata_preview": metadata_preview,
        }
