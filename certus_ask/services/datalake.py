import os
from collections.abc import Iterable
from pathlib import Path

from botocore.client import BaseClient
from botocore.exceptions import ClientError

from certus_ask.core.config import settings
from certus_ask.core.logging import get_logger
from certus_integrity.services import get_analyzer, get_anonymizer

logger = get_logger(__name__)


def bucket_exists(client: BaseClient, bucket_name: str) -> bool:
    """Check if a bucket exists in S3."""
    try:
        client.head_bucket(Bucket=bucket_name)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code == "404":
            logger.debug("bucket.not_found", bucket_name=bucket_name)
            return False
        logger.exception("bucket.check_failed", bucket_name=bucket_name, error=str(exc))
        raise
    else:
        logger.debug("bucket.exists", bucket_name=bucket_name)
        return True


def ensure_bucket(client: BaseClient, bucket_name: str) -> None:
    """Create a bucket if it doesn't exist."""
    if bucket_exists(client, bucket_name):
        return

    logger.info("bucket.create", bucket_name=bucket_name)
    try:
        client.create_bucket(Bucket=bucket_name)
        logger.info("bucket.created", bucket_name=bucket_name)
    except Exception as exc:
        logger.exception("bucket.create_failed", bucket_name=bucket_name, error=str(exc))
        raise


def ensure_folders(client: BaseClient, bucket_name: str, folders: Iterable[str]) -> None:
    """Create folder structure in a bucket."""
    folder_list = list(folders)
    logger.info("folders.create_start", bucket_name=bucket_name, folder_count=len(folder_list))

    try:
        for folder in folder_list:
            key = folder.rstrip("/") + "/"
            client.put_object(Bucket=bucket_name, Key=key)
            logger.debug("folder.created", bucket_name=bucket_name, folder=folder)

        logger.info("folders.create_complete", bucket_name=bucket_name, folder_count=len(folder_list))
    except Exception as exc:
        logger.exception("folders.create_failed", bucket_name=bucket_name, error=str(exc))
        raise


def upload_file(client: BaseClient, file_path: Path, bucket_name: str, target_key: str) -> None:
    """Upload a file to S3."""
    file_size = file_path.stat().st_size if file_path.exists() else 0

    logger.info(
        "file.upload_start",
        bucket_name=bucket_name,
        file_path=str(file_path),
        target_key=target_key,
        file_size_bytes=file_size,
    )

    try:
        client.upload_file(str(file_path), bucket_name, target_key)
        logger.info(
            "file.upload_complete",
            bucket_name=bucket_name,
            target_key=target_key,
            file_size_bytes=file_size,
        )
    except Exception as exc:
        logger.exception(
            "file.upload_failed",
            bucket_name=bucket_name,
            target_key=target_key,
            error=str(exc),
        )
        raise


def upload_directory(client: BaseClient, directory: Path, bucket_name: str, target_prefix: str = "") -> None:
    """Upload an entire directory to S3."""
    directory = directory.resolve()
    file_count = 0

    logger.info(
        "directory.upload_start",
        bucket_name=bucket_name,
        directory=str(directory),
        target_prefix=target_prefix,
    )

    try:
        for root, _, files in os.walk(directory):
            for filename in files:
                file_path = Path(root) / filename
                relative_path = file_path.relative_to(directory)
                key = str(Path(target_prefix) / relative_path).replace("\\", "/")
                upload_file(client, file_path, bucket_name, key)
                file_count += 1

        logger.info(
            "directory.upload_complete",
            bucket_name=bucket_name,
            directory=str(directory),
            file_count=file_count,
        )
    except Exception as exc:
        logger.exception(
            "directory.upload_failed",
            bucket_name=bucket_name,
            directory=str(directory),
            file_count=file_count,
            error=str(exc),
        )
        raise


def scan_file_for_privacy_data(file_path: Path) -> list:
    """Scan a file for privacy/PII data."""
    logger.info("privacy.scan_start", file_path=str(file_path))

    try:
        analyzer = get_analyzer()
        text = file_path.read_text(encoding="utf-8")
        results = analyzer.analyze(text=text, language="en")
    except Exception as exc:
        logger.exception("privacy.scan_failed", file_path=str(file_path), error=str(exc))
        raise
    else:
        logger.info(
            "privacy.scan_complete",
            file_path=str(file_path),
            pii_entities_found=len(results),
        )

        return results


def mask_file(file_path: Path) -> Path:
    """Mask/anonymize privacy data in a file."""
    logger.info("file.mask_start", file_path=str(file_path))

    try:
        anonymizer = get_anonymizer()
        text = file_path.read_text(encoding="utf-8")
        analysis_results = scan_file_for_privacy_data(file_path)
        logger.debug("file.anonymizing", file_path=str(file_path), entity_count=len(analysis_results))
        masked_text = anonymizer.anonymize(text=text, analyzer_results=analysis_results)
        masked_path = file_path.with_suffix(file_path.suffix + ".masked")
        masked_path.write_text(masked_text.text, encoding="utf-8")
    except Exception as exc:
        logger.exception("file.mask_failed", file_path=str(file_path), error=str(exc))
        raise
    else:
        logger.info(
            "file.mask_complete",
            original_path=str(file_path),
            masked_path=str(masked_path),
            entities_masked=len(analysis_results),
        )

        return masked_path


def initialize_datalake_structure(client: BaseClient) -> None:
    """Initialize the datalake bucket structure."""
    logger.info("datalake.initialization_start")

    try:
        ensure_bucket(client, settings.datalake_raw_bucket)
        ensure_bucket(client, settings.datalake_golden_bucket)
        ensure_folders(client, settings.datalake_raw_bucket, settings.datalake_default_folders)

        logger.info(
            "datalake.initialization_complete",
            raw_bucket=settings.datalake_raw_bucket,
            golden_bucket=settings.datalake_golden_bucket,
            folder_count=len(settings.datalake_default_folders),
        )
    except Exception as exc:
        logger.exception("datalake.initialization_failed", error=str(exc))
        raise


__all__ = [
    "bucket_exists",
    "ensure_bucket",
    "ensure_folders",
    "initialize_datalake_structure",
    "mask_file",
    "scan_file_for_privacy_data",
    "upload_directory",
    "upload_file",
]
