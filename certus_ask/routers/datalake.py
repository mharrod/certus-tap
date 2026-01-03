"""Datalake router for S3 data management and preprocessing.

Provides endpoints for:
- Uploading files/directories to S3 datalake
- Listing S3 objects
- Preprocessing (moving from raw to golden buckets)
- Ingesting documents from S3 to OpenSearch
"""

import json
import tempfile
from pathlib import Path

import structlog
from fastapi import APIRouter
from pydantic import BaseModel, Field

from certus_ask.core.config import settings
from certus_ask.core.exceptions import (
    BucketNotFoundError,
    FileUploadError,
    StorageError,
    StorageFileNotFoundError,
)
from certus_ask.pipelines.preprocessing import create_preprocessing_pipeline
from certus_ask.schemas.datalake import (
    BatchPreprocessRequest,
    BatchS3IngestRequest,
    PreprocessRequest,
    S3IngestRequest,
    UploadRequest,
)
from certus_ask.schemas.errors import (
    BadRequestErrorResponse,
    InternalServerErrorResponse,
    NotFoundErrorResponse,
)
from certus_ask.services import datalake as datalake_service
from certus_ask.services.opensearch import get_document_store
from certus_ask.services.s3 import get_s3_client

router = APIRouter(prefix="/v1/datalake", tags=["datalake"])

logger = structlog.get_logger(__name__)

SECURITY_SCANS_PREFIX = "security-scans"


def _extract_scan_id(path: str) -> str | None:
    """Return scan ID if path belongs to security-scans naming convention."""

    parts = path.strip("/").split("/")
    if len(parts) >= 2 and parts[0] == SECURITY_SCANS_PREFIX:
        return parts[1]
    return None


def _ensure_verified_scan(
    client,
    scan_id: str,
    verified_cache: set[str],
) -> None:
    """Ensure the verification proof for a scan exists and is chain_verified."""

    if scan_id in verified_cache:
        return

    proof_key = f"{SECURITY_SCANS_PREFIX}/{scan_id}/{scan_id}/verification-proof.json"
    try:
        response = client.get_object(
            Bucket=settings.datalake_raw_bucket,
            Key=proof_key,
        )
    except Exception as exc:  # pragma: no cover - surfaced as StorageError
        logger.error(
            "verification.proof_missing",
            scan_id=scan_id,
            proof_key=proof_key,
            error=str(exc),
        )
        raise StorageError(
            message="Verification proof missing for scan",
            error_code="verification_proof_missing",
            details={"scan_id": scan_id, "proof_key": proof_key},
        ) from exc

    try:
        payload = json.loads(response["Body"].read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover
        logger.error(
            "verification.proof_unreadable",
            scan_id=scan_id,
            proof_key=proof_key,
            error=str(exc),
        )
        raise StorageError(
            message="Verification proof unreadable",
            error_code="verification_proof_invalid",
            details={"scan_id": scan_id},
        ) from exc

    if not payload.get("chain_verified"):
        logger.error("verification.proof_failed", scan_id=scan_id, proof=payload)
        raise StorageError(
            message="Verification chain not complete for scan",
            error_code="verification_failed",
            details={"scan_id": scan_id},
        )

    verified_cache.add(scan_id)


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class DatalakeBaseResponse(BaseModel):
    """Base response for datalake operations.

    Attributes:
        message: Operation summary message
    """

    message: str = Field(..., description="Operation summary")

    def __getitem__(self, item: str):
        """Allow dict-like access for compatibility with legacy tests."""
        return getattr(self, item)


class UploadResponse(DatalakeBaseResponse):
    """Response for upload operation.

    Attributes:
        message: Upload completion message
    """

    pass


class ListResponse(BaseModel):
    """Response for list operation.

    Attributes:
        files: List of object keys in bucket
    """

    files: list[str] = Field(..., description="List of object keys")


class PreprocessResponse(DatalakeBaseResponse):
    """Response for single object preprocess operation.

    Attributes:
        message: Preprocessing summary
    """

    pass


class BatchPreprocessResponse(DatalakeBaseResponse):
    """Response for batch preprocess operation.

    Attributes:
        message: Batch operation summary
        promoted: List of successfully promoted keys
        failed: List of failed operations with error details
    """

    promoted: list[str] = Field(..., description="Successfully promoted keys")
    failed: list[dict[str, str]] = Field(default_factory=list, description="Failed operations")


class IngestResponse(DatalakeBaseResponse):
    """Response for ingest operation.

    Attributes:
        message: Ingestion summary
        document_count: Total documents in index after ingestion
    """

    document_count: int = Field(..., description="Total documents in index")


class BatchIngestResponse(DatalakeBaseResponse):
    """Response for batch ingest operation.

    Attributes:
        message: Batch operation summary
        ingested: List of successfully ingested keys
        failed: List of failed operations
        document_count: Total documents in index after ingestion
    """

    ingested: list[str] = Field(..., description="Successfully ingested keys")
    failed: list[dict[str, str]] = Field(default_factory=list, description="Failed operations")
    document_count: int = Field(..., description="Total documents in index")


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post(
    "/upload",
    response_model=UploadResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "Source path does not exist"},
        500: {"model": InternalServerErrorResponse, "description": "Upload failed"},
    },
)
async def upload(request: UploadRequest) -> UploadResponse:
    """Upload files or directories to S3 datalake.

    Uploads file or directory to raw bucket, applying privacy masking if needed.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/datalake/upload" \\
      -H "Content-Type: application/json" \\
      -d '{
        "source_path": "/local/documents",
        "target_folder": "2024/reports"
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "message": "Upload completed."
    }
    ```

    **Error Response (400 - Path Not Found):**
    ```json
    {
      "error": "file_not_found",
      "message": "Source path does not exist",
      "detail": {
        "path": "/nonexistent/path"
      }
    }
    ```

    Args:
        request: Upload request with source path and target S3 folder

    Returns:
        UploadResponse confirming completion

    Raises:
        HTTPException 400: If source path doesn't exist
        HTTPException 500: If upload fails
    """
    client = get_s3_client()
    datalake_service.initialize_datalake_structure(client)

    source_path = Path(request.source_path).expanduser().resolve()
    target_folder = request.target_folder.strip("/ ")

    if not source_path.exists():
        raise StorageFileNotFoundError(
            message="Source path does not exist",
            error_code="source_not_found",
            details={"path": str(source_path)},
        )

    try:
        logger.info(
            event="datalake.upload_start",
            source_path=str(source_path),
            target_folder=target_folder,
            is_directory=source_path.is_dir(),
        )

        if source_path.is_dir():
            datalake_service.upload_directory(
                client,
                source_path,
                settings.datalake_raw_bucket,
                target_folder,
            )
            logger.info(
                event="datalake.directory_uploaded",
                source_path=str(source_path),
                target_folder=target_folder,
            )
        else:
            upload_path = source_path
            try:
                analysis_results = datalake_service.scan_file_for_privacy_data(source_path)
            except UnicodeDecodeError:
                analysis_results = []

            if analysis_results:
                logger.warning(
                    event="datalake.file_privacy_detected",
                    source_path=str(source_path),
                    pii_count=len(analysis_results),
                )
                upload_path = datalake_service.mask_file(source_path)

            object_key = f"{target_folder}/{upload_path.name}".strip("/")
            datalake_service.upload_file(
                client,
                upload_path,
                settings.datalake_raw_bucket,
                object_key,
            )
            logger.info(
                event="datalake.file_uploaded",
                source_path=str(source_path),
                object_key=object_key,
            )
            if upload_path != source_path and upload_path.exists():
                upload_path.unlink(missing_ok=True)

        return UploadResponse(message="Upload completed.")

    except StorageFileNotFoundError:
        raise
    except Exception as exc:
        logger.error(
            event="datalake.upload_failed",
            source_path=str(source_path),
            target_folder=target_folder,
            error=str(exc),
            exc_info=True,
        )
        raise FileUploadError(
            message="Failed to upload file(s)",
            error_code="upload_failed",
            details={"source_path": str(source_path)},
        ) from exc


@router.get(
    "/list/{bucket_name}",
    response_model=ListResponse,
    responses={
        404: {"model": NotFoundErrorResponse, "description": "Bucket does not exist"},
        500: {"model": InternalServerErrorResponse, "description": "Listing failed"},
    },
)
async def list_objects(bucket_name: str) -> ListResponse:
    """List all objects in a bucket.

    **Request Example:**
    ```bash
    curl -X GET "http://localhost:8000/v1/datalake/list/my-bucket"
    ```

    **Success Response (200):**
    ```json
    {
      "files": [
        "documents/2024/report1.pdf",
        "documents/2024/report2.pdf",
        "logs/error_log.txt"
      ]
    }
    ```

    **Error Response (404 - Bucket Not Found):**
    ```json
    {
      "error": "bucket_not_found",
      "message": "Bucket does not exist",
      "detail": {
        "bucket_name": "nonexistent-bucket"
      }
    }
    ```

    Args:
        bucket_name: S3 bucket name to list

    Returns:
        ListResponse with list of all object keys in bucket

    Raises:
        HTTPException 404: If bucket doesn't exist
        HTTPException 500: If listing fails
    """
    client = get_s3_client()

    if not datalake_service.bucket_exists(client, bucket_name):
        raise BucketNotFoundError(
            message="Bucket does not exist",
            error_code="bucket_not_found",
            details={"bucket_name": bucket_name},
        )

    try:
        logger.info(
            event="datalake.list_start",
            bucket_name=bucket_name,
        )
        response = client.list_objects_v2(Bucket=bucket_name)
        contents = response.get("Contents", [])
        files = [item["Key"] for item in contents]

        logger.info(
            event="datalake.list_complete",
            bucket_name=bucket_name,
            object_count=len(files),
        )
        return ListResponse(files=files)
    except Exception as exc:
        logger.error(
            event="datalake.list_failed",
            bucket_name=bucket_name,
            error=str(exc),
            exc_info=True,
        )
        raise StorageError(
            message="Failed to list bucket contents",
            error_code="list_failed",
            details={"bucket_name": bucket_name},
        ) from exc


@router.post(
    "/preprocess",
    response_model=PreprocessResponse,
    responses={
        500: {"model": InternalServerErrorResponse, "description": "Preprocessing failed"},
    },
)
async def promote_object(request: PreprocessRequest) -> PreprocessResponse:
    """Move single object from raw to golden bucket.

    Downloads file from raw bucket, processes it, uploads to golden bucket.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/datalake/preprocess" \\
      -H "Content-Type: application/json" \\
      -d '{
        "source_key": "raw/documents/report.pdf",
        "destination_prefix": "golden/2024"
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "message": "Promoted raw/documents/report.pdf to golden/2024/report.pdf"
    }
    ```

    **Error Response (500 - Processing Failed):**
    ```json
    {
      "error": "processing_failed",
      "message": "An unexpected error occurred while processing your request",
      "detail": {
        "error_id": "req_ghi012"
      }
    }
    ```

    Args:
        request: Preprocess request with source key and destination prefix

    Returns:
        PreprocessResponse confirming completion

    Raises:
        HTTPException 500: If preprocessing fails
    """
    client = get_s3_client()
    datalake_service.initialize_datalake_structure(client)

    source_key = request.source_key.strip("/")
    destination_prefix = request.destination_prefix.strip("/ ") if request.destination_prefix else ""

    tmp_path = None
    verified_scans: set[str] = set()
    scan_id = _extract_scan_id(source_key)
    if scan_id:
        _ensure_verified_scan(client, scan_id, verified_scans)
    try:
        suffix = Path(source_key).suffix or ""
        original_name = Path(source_key).name
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = Path(tmp_file.name)
            client.download_file(settings.datalake_raw_bucket, source_key, str(tmp_path))

        destination_key = f"{destination_prefix}/{original_name}".strip("/")
        datalake_service.upload_file(
            client,
            tmp_path,
            settings.datalake_golden_bucket,
            destination_key,
        )

        return PreprocessResponse(
            message=f"Promoted {source_key} to {destination_key}",
        )

    except Exception as exc:
        logger.exception("Failed to promote %s", source_key)
        raise StorageError(
            message="Failed to preprocess object",
            error_code="preprocess_failed",
            details={"source_key": source_key},
        ) from exc
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)


@router.post(
    "/preprocess/batch",
    response_model=BatchPreprocessResponse,
    responses={
        404: {"model": NotFoundErrorResponse, "description": "No objects match prefix"},
        500: {"model": InternalServerErrorResponse, "description": "Batch preprocessing failed"},
    },
)
async def promote_prefix(
    request: BatchPreprocessRequest,
) -> BatchPreprocessResponse:
    """Move all objects with prefix from raw to golden bucket.

    Batch preprocesses all objects matching source prefix.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/datalake/preprocess/batch" \\
      -H "Content-Type: application/json" \\
      -d '{
        "source_prefix": "raw/2024/january",
        "destination_prefix": "golden/2024/january"
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "message": "Promoted 12 objects under raw/2024/january",
      "promoted": [
        "raw/2024/january/doc1.pdf",
        "raw/2024/january/doc2.txt"
      ],
      "failed": []
    }
    ```

    **Error Response (404 - No Objects Found):**
    ```json
    {
      "error": "file_not_found",
      "message": "No objects found under prefix",
      "detail": {
        "prefix": "raw/nonexistent"
      }
    }
    ```

    Args:
        request: Batch preprocess with source and destination prefixes

    Returns:
        BatchPreprocessResponse with promoted list and failed list

    Raises:
        HTTPException 404: If no objects match prefix
        HTTPException 500: If all objects fail or operation fails
    """
    client = get_s3_client()
    datalake_service.initialize_datalake_structure(client)

    source_prefix = request.source_prefix.strip("/ ")
    destination_prefix = request.destination_prefix.strip("/ ") if request.destination_prefix else source_prefix

    try:
        objects = client.list_objects_v2(
            Bucket=settings.datalake_raw_bucket,
            Prefix=source_prefix,
        )
        keys = [item["Key"] for item in objects.get("Contents", []) if not item["Key"].endswith("/")]
    except Exception as exc:
        logger.exception("Failed to list objects for prefix %s", source_prefix)
        raise StorageError(
            message="Failed to list objects",
            error_code="list_prefix_failed",
            details={"prefix": source_prefix},
        ) from exc

    if not keys:
        raise StorageFileNotFoundError(
            message="No objects found under prefix",
            error_code="prefix_not_found",
            details={"prefix": source_prefix},
        )

    promoted: list[str] = []
    failed: list[dict[str, str]] = []
    verified_scans: set[str] = set()

    for key in keys:
        tmp_path: Path | None = None
        try:
            scan_id = _extract_scan_id(key)
            if scan_id:
                _ensure_verified_scan(client, scan_id, verified_scans)

            suffix = Path(key).suffix or ""
            original_name = Path(key).name
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_path = Path(tmp_file.name)
                client.download_file(
                    settings.datalake_raw_bucket,
                    key,
                    str(tmp_path),
                )

            destination_key = f"{destination_prefix}/{original_name}".strip("/")
            datalake_service.upload_file(
                client,
                tmp_path,
                settings.datalake_golden_bucket,
                destination_key,
            )
            promoted.append(key)
        except Exception as exc:
            failed.append({"key": key, "error": str(exc)})
            logger.exception("Failed to promote %s during batch", key)
        finally:
            if tmp_path:
                tmp_path.unlink(missing_ok=True)

    if not promoted:
        raise StorageError(
            message="Failed to promote any objects",
            error_code="batch_promote_failed",
            details={"prefix": source_prefix, "total": len(keys)},
        )

    return BatchPreprocessResponse(
        message=f"Promoted {len(promoted)} objects under {source_prefix}",
        promoted=promoted,
        failed=failed,
    )


@router.post(
    "/ingest",
    response_model=IngestResponse,
    responses={
        500: {"model": InternalServerErrorResponse, "description": "Ingestion failed"},
    },
)
async def ingest_from_s3(request: S3IngestRequest) -> IngestResponse:
    """Ingest single object from S3 to OpenSearch.

    Downloads file from bucket and indexes it via preprocessing pipeline.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/datalake/ingest" \\
      -H "Content-Type: application/json" \\
      -d '{
        "bucket": "my-golden-bucket",
        "key": "documents/2024/report.pdf"
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "message": "Ingested documents/2024/report.pdf from my-golden-bucket",
      "document_count": 598
    }
    ```

    **Error Response (500 - Ingestion Failed):**
    ```json
    {
      "error": "storage_error",
      "message": "Failed to ingest object",
      "detail": {
        "bucket": "my-golden-bucket",
        "key": "documents/2024/report.pdf"
      }
    }
    ```

    Args:
        request: S3 ingest request with bucket and object key

    Returns:
        IngestResponse with updated document count

    Raises:
        HTTPException 500: If ingestion fails
    """
    client = get_s3_client()
    datalake_service.initialize_datalake_structure(client)

    bucket = (request.bucket or settings.datalake_raw_bucket).strip()
    key = request.key.strip().lstrip("/")

    document_store = get_document_store()
    pipeline = create_preprocessing_pipeline(document_store)

    tmp_path: Path | None = None
    try:
        suffix = Path(key).suffix or ""
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
            tmp_path = Path(tmp_file.name)
            client.download_file(bucket, key, str(tmp_path))

        pipeline.run({"file_type_router": {"sources": [tmp_path]}})

        return IngestResponse(
            message=f"Ingested {key} from {bucket}",
            document_count=document_store.count_documents(),
        )

    except Exception as exc:
        logger.exception("Failed to ingest %s from bucket %s", key, bucket)
        raise StorageError(
            message="Failed to ingest object",
            error_code="ingest_failed",
            details={"bucket": bucket, "key": key},
        ) from exc
    finally:
        if tmp_path:
            tmp_path.unlink(missing_ok=True)


@router.post(
    "/ingest/batch",
    response_model=BatchIngestResponse,
    responses={
        404: {"model": NotFoundErrorResponse, "description": "No objects match prefix"},
        500: {"model": InternalServerErrorResponse, "description": "Batch ingestion failed"},
    },
)
async def ingest_prefix(
    request: BatchS3IngestRequest,
) -> BatchIngestResponse:
    """Ingest all objects with prefix from S3 to OpenSearch.

    Batch ingests all objects matching prefix to index.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/datalake/ingest/batch" \\
      -H "Content-Type: application/json" \\
      -d '{
        "bucket": "my-golden-bucket",
        "prefix": "documents/2024/january"
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "message": "Ingested 18 objects under my-golden-bucket/documents/2024/january",
      "ingested": [
        "documents/2024/january/doc1.pdf",
        "documents/2024/january/doc2.pdf"
      ],
      "failed": [],
      "document_count": 1240
    }
    ```

    **Error Response (404 - No Objects Found):**
    ```json
    {
      "error": "file_not_found",
      "message": "No objects found under prefix",
      "detail": {
        "bucket": "my-golden-bucket",
        "prefix": "nonexistent"
      }
    }
    ```

    Args:
        request: Batch ingest request with bucket and object prefix

    Returns:
        BatchIngestResponse with ingested list, failed list, and document count

    Raises:
        HTTPException 404: If no objects match prefix
        HTTPException 500: If all objects fail or operation fails
    """
    client = get_s3_client()
    datalake_service.initialize_datalake_structure(client)

    bucket = (request.bucket or settings.datalake_raw_bucket).strip()
    prefix = request.prefix.strip().lstrip("/")

    try:
        objects = client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        keys = [item["Key"] for item in objects.get("Contents", []) if not item["Key"].endswith("/")]
    except Exception as exc:
        logger.exception("Failed to list objects for prefix %s in bucket %s", prefix, bucket)
        raise StorageError(
            message="Failed to list objects",
            error_code="list_prefix_failed",
            details={"bucket": bucket, "prefix": prefix},
        ) from exc

    if not keys:
        raise StorageFileNotFoundError(
            message="No objects found under prefix",
            error_code="prefix_not_found",
            details={"bucket": bucket, "prefix": prefix},
        )

    document_store = get_document_store()
    pipeline = create_preprocessing_pipeline(document_store)

    ingested: list[str] = []
    failed: list[dict[str, str]] = []

    for key in keys:
        tmp_path: Path | None = None
        try:
            suffix = Path(key).suffix or ""
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp_file:
                tmp_path = Path(tmp_file.name)
                client.download_file(bucket, key, str(tmp_path))
            pipeline.run({"file_type_router": {"sources": [tmp_path]}})
            ingested.append(key)
        except Exception as exc:
            failed.append({"key": key, "error": str(exc)})
            logger.exception("Failed to ingest %s during batch", key)
        finally:
            if tmp_path:
                tmp_path.unlink(missing_ok=True)

    if not ingested:
        raise StorageError(
            message="Failed to ingest any objects",
            error_code="batch_ingest_failed",
            details={"bucket": bucket, "prefix": prefix, "total": len(keys)},
        )

    return BatchIngestResponse(
        message=f"Ingested {len(ingested)} objects under {bucket}/{prefix}",
        ingested=ingested,
        failed=failed,
        document_count=document_store.count_documents(),
    )
