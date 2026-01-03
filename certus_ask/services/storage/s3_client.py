"""S3 client wrapper for file storage operations.

Centralizes all S3/MinIO interactions with consistent error handling and configuration.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class S3Client:
    """Wrapper for AWS S3/MinIO operations with centralized configuration."""

    def __init__(self, s3_client: Any):
        """Initialize S3Client with boto3 client.

        Args:
            s3_client: Configured boto3 S3 client instance
        """
        self.client = s3_client

    def download_object(self, bucket_name: str, key: str) -> bytes:
        """Download file from S3 and return bytes.

        Args:
            bucket_name: S3 bucket name
            key: Object key (path) in bucket

        Returns:
            File content as bytes

        Raises:
            ClientError: If download fails
        """
        logger.info(
            event="s3.download_start",
            bucket=bucket_name,
            key=key,
        )

        response = self.client.get_object(Bucket=bucket_name, Key=key)
        content = response["Body"].read()

        logger.info(
            event="s3.download_complete",
            bucket=bucket_name,
            key=key,
            size_bytes=len(content),
        )

        return content

    def download_to_file(
        self,
        bucket_name: str,
        key: str,
        local_path: Path | str,
    ) -> None:
        """Download S3 object directly to local file.

        Args:
            bucket_name: S3 bucket name
            key: Object key (path) in bucket
            local_path: Local file path to save to

        Raises:
            ClientError: If download fails
        """
        local_path = Path(local_path)

        logger.info(
            event="s3.download_to_file_start",
            bucket=bucket_name,
            key=key,
            local_path=str(local_path),
        )

        self.client.download_file(
            bucket_name,
            key,
            str(local_path),
        )

        logger.info(
            event="s3.download_to_file_complete",
            bucket=bucket_name,
            key=key,
            local_path=str(local_path),
        )

    def list_objects(
        self,
        bucket_name: str,
        prefix: str = "",
    ) -> list[dict[str, Any]]:
        """List all objects in bucket with given prefix.

        Args:
            bucket_name: S3 bucket name
            prefix: Optional prefix to filter objects

        Returns:
            List of object metadata dicts

        Raises:
            ClientError: If listing fails
        """
        logger.info(
            event="s3.list_objects_start",
            bucket=bucket_name,
            prefix=prefix,
        )

        paginator = self.client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)

        objects = []
        for page in pages:
            if "Contents" in page:
                objects.extend(page["Contents"])

        logger.info(
            event="s3.list_objects_complete",
            bucket=bucket_name,
            prefix=prefix,
            object_count=len(objects),
        )

        return objects

    def upload_object(
        self,
        bucket_name: str,
        key: str,
        data: bytes,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Upload bytes to S3 object.

        Args:
            bucket_name: S3 bucket name
            key: Object key (path) in bucket
            data: File content as bytes
            metadata: Optional object metadata

        Raises:
            ClientError: If upload fails
        """
        logger.info(
            event="s3.upload_start",
            bucket=bucket_name,
            key=key,
            size_bytes=len(data),
        )

        extra_args = {}
        if metadata:
            extra_args["Metadata"] = metadata

        self.client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=data,
            **extra_args,
        )

        logger.info(
            event="s3.upload_complete",
            bucket=bucket_name,
            key=key,
        )

    def upload_file(
        self,
        bucket_name: str,
        key: str,
        local_path: Path | str,
        metadata: dict[str, str] | None = None,
    ) -> None:
        """Upload local file to S3.

        Args:
            bucket_name: S3 bucket name
            key: Object key (path) in bucket
            local_path: Local file path to upload
            metadata: Optional object metadata

        Raises:
            ClientError: If upload fails
        """
        local_path = Path(local_path)

        logger.info(
            event="s3.upload_file_start",
            bucket=bucket_name,
            key=key,
            local_path=str(local_path),
        )

        extra_args = {}
        if metadata:
            extra_args["Metadata"] = metadata

        self.client.upload_file(
            str(local_path),
            bucket_name,
            key,
            ExtraArgs=extra_args if extra_args else None,
        )

        logger.info(
            event="s3.upload_file_complete",
            bucket=bucket_name,
            key=key,
        )

    def delete_object(self, bucket_name: str, key: str) -> None:
        """Delete object from S3.

        Args:
            bucket_name: S3 bucket name
            key: Object key (path) in bucket

        Raises:
            ClientError: If deletion fails
        """
        logger.info(
            event="s3.delete_start",
            bucket=bucket_name,
            key=key,
        )

        self.client.delete_object(Bucket=bucket_name, Key=key)

        logger.info(
            event="s3.delete_complete",
            bucket=bucket_name,
            key=key,
        )

    def object_exists(self, bucket_name: str, key: str) -> bool:
        """Check if object exists in S3.

        Args:
            bucket_name: S3 bucket name
            key: Object key (path) in bucket

        Returns:
            True if object exists, False otherwise
        """
        try:
            self.client.head_object(Bucket=bucket_name, Key=key)
            return True
        except Exception:
            return False
