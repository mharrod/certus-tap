"""Storage service for file operations.

Handles all storage operations including local file writes,
S3 uploads, and metadata management for ingestion workflows.
"""

from pathlib import Path
from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class StorageService:
    """Service for file storage operations during ingestion.

    This service encapsulates:
    - Local file system writes
    - S3 uploads with metadata
    - Directory creation and management
    - Verification metadata storage

    Dependencies are injected via constructor to enable testing and reuse.
    """

    def __init__(
        self,
        s3_client: Optional[Any] = None,
        default_bucket: Optional[str] = None,
    ):
        """Initialize the storage service.

        Args:
            s3_client: Boto3 S3 client instance (for S3 operations)
            default_bucket: Default S3 bucket name
        """
        self.s3_client = s3_client
        self.default_bucket = default_bucket
        logger.info("StorageService initialized", default_bucket=default_bucket)

    def save_file_locally(
        self,
        file_content: bytes,
        file_path: Path,
    ) -> Path:
        """Save file content to local filesystem.

        Creates parent directories if they don't exist.

        Args:
            file_content: File bytes to save
            file_path: Destination path (can be relative or absolute)

        Returns:
            Absolute path to saved file

        Raises:
            IOError: If file write fails

        Example:
            >>> storage = StorageService()
            >>> path = storage.save_file_locally(
            ...     b"content",
            ...     Path("uploads/doc.pdf")
            ... )
            >>> print(path)
            /full/path/to/uploads/doc.pdf
        """
        logger.info(
            "save_file_locally.start",
            file_path=str(file_path),
            size_bytes=len(file_content),
        )

        # Ensure parent directory exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        # Write file
        file_path.write_bytes(file_content)

        # Return absolute path
        absolute_path = file_path.absolute()

        logger.info(
            "save_file_locally.complete",
            file_path=str(absolute_path),
            size_bytes=len(file_content),
        )

        return absolute_path

    def ensure_directory(
        self,
        directory_path: Path,
    ) -> Path:
        """Ensure a directory exists, creating it if necessary.

        Args:
            directory_path: Path to directory

        Returns:
            Absolute path to directory

        Example:
            >>> storage = StorageService()
            >>> dir_path = storage.ensure_directory(Path("uploads/temp"))
            >>> print(dir_path.exists())
            True
        """
        logger.debug(
            "ensure_directory.start",
            directory_path=str(directory_path),
        )

        directory_path.mkdir(parents=True, exist_ok=True)
        absolute_path = directory_path.absolute()

        logger.debug(
            "ensure_directory.complete",
            directory_path=str(absolute_path),
        )

        return absolute_path

    def upload_to_s3(
        self,
        file_content: bytes,
        key: str,
        bucket: Optional[str] = None,
        metadata: Optional[dict[str, str]] = None,
        content_type: Optional[str] = None,
    ) -> dict[str, Any]:
        """Upload file to S3 with optional metadata.

        Args:
            file_content: File bytes to upload
            key: S3 object key
            bucket: S3 bucket (uses default if not specified)
            metadata: S3 object metadata (max 2KB)
            content_type: Content-Type header for S3 object

        Returns:
            Dictionary with upload results:
            - bucket: str (bucket name)
            - key: str (object key)
            - uri: str (s3://bucket/key)
            - etag: str (S3 ETag)

        Raises:
            ValueError: If bucket not specified and no default set
            Exception: If S3 upload fails (boto3 ClientError or other exceptions)

        Example:
            >>> import boto3
            >>> s3 = boto3.client('s3')
            >>> storage = StorageService(s3_client=s3, default_bucket="my-bucket")
            >>> result = storage.upload_to_s3(
            ...     b"content",
            ...     "scans/report.sarif",
            ...     metadata={"tier": "premium"}
            ... )
            >>> print(result['uri'])
            s3://my-bucket/scans/report.sarif
        """
        target_bucket = bucket or self.default_bucket
        if not target_bucket:
            raise ValueError("Bucket name must be specified or default_bucket set")

        logger.info(
            "upload_to_s3.start",
            bucket=target_bucket,
            key=key,
            size_bytes=len(file_content),
            has_metadata=metadata is not None,
        )

        # Prepare put_object arguments
        put_args: dict[str, Any] = {
            "Bucket": target_bucket,
            "Key": key,
            "Body": file_content,
        }

        if metadata:
            put_args["Metadata"] = metadata

        if content_type:
            put_args["ContentType"] = content_type

        # Upload to S3
        response = self.s3_client.put_object(**put_args)

        result = {
            "bucket": target_bucket,
            "key": key,
            "uri": f"s3://{target_bucket}/{key}",
            "etag": response.get("ETag", "").strip('"'),
        }

        logger.info(
            "upload_to_s3.complete",
            bucket=target_bucket,
            key=key,
            uri=result["uri"],
        )

        return result

    def store_verification_metadata(
        self,
        verification_proof: dict[str, Any],
        base_key: str,
        bucket: Optional[str] = None,
    ) -> dict[str, Any]:
        """Store verification metadata as JSON in S3.

        Creates a separate .metadata.json file alongside the artifact.

        Args:
            verification_proof: Verification proof data to store
            base_key: Base S3 key (e.g., "scans/report.sarif")
            bucket: S3 bucket (uses default if not specified)

        Returns:
            Dictionary with storage results:
            - bucket: str
            - key: str (metadata file key)
            - uri: str

        Raises:
            ValueError: If bucket not specified and no default set

        Example:
            >>> storage = StorageService(s3_client=s3, default_bucket="bucket")
            >>> proof = {"chain_verified": True, "signer": "user@example.com"}
            >>> result = storage.store_verification_metadata(
            ...     proof,
            ...     "scans/report.sarif"
            ... )
            >>> print(result['key'])
            scans/report.sarif.metadata.json
        """
        import json

        target_bucket = bucket or self.default_bucket
        if not target_bucket:
            raise ValueError("Bucket name must be specified or default_bucket set")

        # Generate metadata key
        metadata_key = f"{base_key}.metadata.json"

        logger.info(
            "store_verification_metadata.start",
            bucket=target_bucket,
            base_key=base_key,
            metadata_key=metadata_key,
        )

        # Convert to JSON
        metadata_json = json.dumps(verification_proof, indent=2).encode("utf-8")

        # Upload metadata file
        response = self.s3_client.put_object(
            Bucket=target_bucket,
            Key=metadata_key,
            Body=metadata_json,
            ContentType="application/json",
            Metadata={"type": "verification-proof"},
        )

        result = {
            "bucket": target_bucket,
            "key": metadata_key,
            "uri": f"s3://{target_bucket}/{metadata_key}",
            "etag": response.get("ETag", "").strip('"'),
        }

        logger.info(
            "store_verification_metadata.complete",
            bucket=target_bucket,
            metadata_key=metadata_key,
            uri=result["uri"],
        )

        return result
