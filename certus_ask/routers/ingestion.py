"""Ingestion router for document indexing from various sources.

Provides endpoints for uploading and indexing documents from multiple sources:
- Single file upload
- Folder/directory recursion
- GitHub repositories
- SARIF (vulnerability scan) files
- Web pages (scraping)
- Web domains (crawling)

All endpoints return structured responses with ingestion_id for tracing.
"""

import asyncio
import json
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from certus_ask.core.exceptions import (
    DocumentIngestionError,
    DocumentParseError,
    ValidationError,
)
from certus_ask.core.metrics import get_ingestion_metrics
from certus_ask.core.request_context import get_request_id

# Neo4j loaders and markdown generators now accessed via Neo4jService
# from certus_ask.pipelines.markdown_generators.sarif_markdown import SarifToMarkdown
# from certus_ask.pipelines.markdown_generators.spdx_markdown import SpdxToMarkdown
# from certus_ask.pipelines.neo4j_loaders.sarif_loader import SarifToNeo4j
# from certus_ask.pipelines.neo4j_loaders.spdx_loader import SpdxToNeo4j
from certus_ask.pipelines.preprocessing import (
    create_preprocessing_pipeline,
)
from certus_ask.pipelines.web_scrapy import create_scrapy_crawl_pipeline
from certus_ask.schemas.errors import (
    BadRequestErrorResponse,
    InternalServerErrorResponse,
)
from certus_ask.schemas.ingestion import (
    GitRepositoryRequest,
    IndexFolderRequest,
    S3IndexRequest,
    WebCrawlRequest,
    WebIngestionRequest,
)
from certus_ask.services.ingestion import (
    extract_metadata_preview,
    get_upload_file_size,
)
from certus_ask.services.opensearch import get_document_store_for_workspace
from certus_ask.services.privacy_logger import PrivacyLogger

router = APIRouter(prefix="/v1", tags=["ingestion"])

logger = structlog.get_logger(__name__)
privacy_logger = PrivacyLogger(strict_mode=False)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _enforce_verified_digest(
    file_bytes: bytes,
    artifact_locations: dict[str, Any] | None,
    s3_bucket: str | None,
    s3_key: str | None,
) -> str | None:
    """Verify file digest against expected digest from artifact_locations.

    This function is called by SecurityProcessor.verify_digest() to check that
    the downloaded file matches the expected digest from Trust verification.

    Args:
        file_bytes: Raw file bytes to verify
        artifact_locations: Expected artifact locations/digests from Trust
        s3_bucket: S3 bucket name
        s3_key: S3 object key

    Returns:
        Actual digest string (e.g., "sha256:abc123...") or None if no expected digest

    Raises:
        ValidationError: If digest verification fails (mismatch detected)
    """
    from certus_ask.services.ingestion.utils import enforce_verified_digest

    # Delegate to the utility function
    return enforce_verified_digest(file_bytes, artifact_locations, s3_bucket, s3_key)


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class IngestionBaseResponse(BaseModel):
    """Base response for all ingestion endpoints.

    Attributes:
        request_id: Unique identifier for correlating this HTTP request across services
        ingestion_id: Unique identifier for tracing this ingestion operation
        message: Human-readable summary of the operation
        document_count: Total documents in index after ingestion
    """

    request_id: str = Field(..., description="Unique ID for this HTTP request")
    ingestion_id: str = Field(..., description="Unique ID for this ingestion operation")
    message: str = Field(..., description="Human-readable success message")
    document_count: int = Field(..., description="Total documents in index after operation")
    metadata_preview: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Sample metadata envelopes captured during the ingestion run.",
    )


class DocumentIngestionResponse(IngestionBaseResponse):
    """Response for single document ingestion.

    Attributes:
        ingestion_id: Unique identifier for tracing
        message: Success message
        document_count: Total documents in index
    """

    pass


class FolderIngestionResponse(IngestionBaseResponse):
    """Response for folder ingestion.

    Attributes:
        ingestion_id: Unique identifier for tracing
        message: Success message
        processed_files: Number of files successfully processed
        failed_files: Number of files that failed processing
        quarantined_documents: Number of documents quarantined due to PII
        document_count: Total documents in index
    """

    processed_files: int = Field(..., description="Number of files successfully processed")
    failed_files: int = Field(default=0, description="Number of files that failed")
    quarantined_documents: int = Field(default=0, description="Documents quarantined due to PII")


class GitHubIngestionResponse(IngestionBaseResponse):
    """Response for GitHub repository ingestion.

    Attributes:
        ingestion_id: Unique identifier for tracing
        message: Success message
        file_count: Number of files indexed from repository
        quarantined_documents: Number of documents quarantined due to PII
        document_count: Total documents in index
    """

    file_count: int = Field(..., description="Number of files from repository")
    quarantined_documents: int = Field(default=0, description="Documents quarantined due to PII")


class SarifIngestionResponse(IngestionBaseResponse):
    """Response for SARIF file ingestion.

    Attributes:
        ingestion_id: Unique identifier for tracing
        message: Success message
        findings_indexed: Number of vulnerability findings indexed
        document_count: Total documents in index
    Attributes:
        findings_indexed: Number of vulnerability findings indexed
        neo4j_scan_id: Deterministic Scan node ID when SARIF data is graphed
        neo4j_sbom_id: Deterministic SBOM node ID when SPDX data is graphed
    """

    findings_indexed: int = Field(..., description="Number of SARIF/SPDX items indexed")
    neo4j_scan_id: str | None = Field(default=None, description="Neo4j Scan node ID when SARIF data is ingested")
    neo4j_sbom_id: str | None = Field(default=None, description="Neo4j SBOM node ID when SPDX data is ingested")


class SpdxIngestionResponse(IngestionBaseResponse):
    """Response for SPDX SBOM file ingestion.

    Attributes:
        ingestion_id: Unique identifier for tracing
        message: Success message
        packages_indexed: Number of packages indexed from SBOM
        document_count: Total documents in index
    """

    packages_indexed: int = Field(..., description="Number of SPDX packages indexed")


class WebIngestionResponse(IngestionBaseResponse):
    """Response for web page ingestion.

    Attributes:
        ingestion_id: Unique identifier for tracing
        message: Success message
        indexed_count: Number of web pages successfully indexed
        skipped_urls: URLs that were skipped and not indexed
        document_count: Total documents in index
    """

    indexed_count: int = Field(..., description="Number of web pages indexed")
    skipped_urls: list[str] = Field(default_factory=list, description="URLs that were skipped")


class WebCrawlIngestionResponse(IngestionBaseResponse):
    """Response for web domain crawling.

    Attributes:
        ingestion_id: Unique identifier for tracing
        message: Success message
        indexed_count: Number of pages crawled and indexed
        skipped_urls: URLs encountered but not indexed
        document_count: Total documents in index
    """

    indexed_count: int = Field(..., description="Number of pages crawled and indexed")
    skipped_urls: list[str] = Field(default_factory=list, description="URLs that were skipped")


# ============================================================================
# CONSTANTS
# ============================================================================

MAX_UPLOAD_SIZE_MB = 100
MAX_UPLOAD_SIZE_BYTES = MAX_UPLOAD_SIZE_MB * 1024 * 1024


class SecurityS3IngestionRequest(BaseModel):
    """Request payload for streaming SARIF/SPDX ingestion from S3."""

    bucket_name: str = Field(..., description="S3 bucket that stores the security scan artifact.")
    key: str = Field(..., description="Object key for the scan artifact inside the bucket.")
    format: str = Field(
        "auto",
        description="Optional format override. Supports 'sarif', 'spdx', 'jsonpath', or 'auto' (default).",
    )
    tool_hint: str | None = Field(
        default=None,
        description="Optional parser hint when format='auto'. Useful for custom JSONPath schemas.",
    )
    schema_dict: dict | str | None = Field(
        default=None,
        description="Optional JSONPath schema definition when ingesting custom formats.",
    )
    # Non-repudiation fields (optional, for premium tier)
    tier: str = Field(
        default="free",
        description="Client tier: 'free' (no verification) or 'premium' (with Trust verification)",
    )
    assessment_id: str | None = Field(None, description="Assessment ID (required for premium tier)")
    signatures: dict[str, Any] | None = Field(None, description="Inner/outer signatures for premium tier verification")
    artifact_locations: dict[str, Any] | None = Field(None, description="S3 and Registry locations for premium tier")


async def _ingest_security_payload(
    workspace_id: str,
    *,
    file_bytes: bytes,
    source_name: str,
    requested_format: str,
    tool_hint: str | None,
    schema_dict: dict | str | None,
    ingestion_id: str,
    tier: str = "free",
    assessment_id: str | None = None,
    signatures: dict[str, Any] | None = None,
    artifact_locations: dict[str, Any] | None = None,
    s3_bucket: str | None = None,
    s3_key: str | None = None,
) -> SarifIngestionResponse:
    """Shared ingestion implementation for SARIF/SPDX inputs.

    This is now a thin wrapper (~75 lines) that delegates to SecurityProcessor.process().
    All business logic has been extracted into the service layer (Phase 1e complete).
    """
    from certus_ask.core.config import Settings
    from certus_ask.services.ingestion import Neo4jService, SecurityProcessor
    from certus_ask.services.trust import get_trust_client

    settings = Settings()
    document_store = get_document_store_for_workspace(workspace_id)

    # Parse schema_dict if it's a string
    schema_value: dict | None = None
    if isinstance(schema_dict, str):
        try:
            schema_value = json.loads(schema_dict)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                message="schema_dict must be valid JSON",
                error_code="invalid_schema",
                details={"error": str(exc)},
            ) from exc
    else:
        schema_value = schema_dict

    # Initialize services
    neo4j_service = None
    if settings.neo4j_enabled:
        neo4j_service = Neo4jService(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )

    trust_client = get_trust_client() if tier == "premium" else None

    processor = SecurityProcessor(
        trust_client=trust_client,
        neo4j_service=neo4j_service,
    )

    metrics = get_ingestion_metrics()

    try:
        # Delegate to SecurityProcessor.process()
        result = await processor.process(
            workspace_id=workspace_id,
            file_bytes=file_bytes,
            source_name=source_name,
            requested_format=requested_format,
            tool_hint=tool_hint,
            schema_dict=schema_value,
            ingestion_id=ingestion_id,
            tier=tier,
            assessment_id=assessment_id,
            signatures=signatures,
            artifact_locations=artifact_locations,
            s3_bucket=s3_bucket,
            s3_key=s3_key,
            document_store=document_store,
            settings=settings,
        )

        # Determine source type
        source_type = "sarif" if requested_format in ("auto", "sarif") else requested_format
        if requested_format == "spdx" or "spdx" in source_name.lower():
            source_type = "spdx"

        # Record successful ingestion
        metrics.record_ingestion(
            source=source_type,
            document_count=result.get("findings_indexed", 0),
            success=True,
        )

        # Return response
        return SarifIngestionResponse(
            request_id=get_request_id(),
            ingestion_id=result["ingestion_id"],
            message=f"Indexed {result['findings_indexed']} items from {source_name} (Neo4j + OpenSearch)",
            findings_indexed=result["findings_indexed"],
            document_count=result["document_count"],
            metadata_preview=[],
            neo4j_scan_id=result.get("neo4j_scan_id"),
            neo4j_sbom_id=result.get("neo4j_sbom_id"),
        )

    except Exception as exc:
        # Record failed ingestion
        source_type = "sarif" if requested_format in ("auto", "sarif") else requested_format
        metrics.record_ingestion(source=source_type, success=False)
        raise


# ============================================================================
# ENDPOINTS
# ============================================================================


@router.post(
    "/{workspace_id}/index/",
    response_model=DocumentIngestionResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "File invalid or exceeds size limit"},
        500: {"model": InternalServerErrorResponse, "description": "Processing failed"},
    },
)
async def index_document(
    workspace_id: str,
    uploaded_file: Annotated[UploadFile, File(...)],
) -> DocumentIngestionResponse:
    """Upload and index a single document.

    Accepts a single file and processes it through the preprocessing pipeline,
    extracting text, splitting into chunks, and indexing in OpenSearch.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/index/" \\
      -H "Content-Type: multipart/form-data" \\
      -F "uploaded_file=@document.pdf"
    ```

    **Success Response (200):**
    ```json
    {
      "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
      "message": "Indexed document document.pdf",
      "document_count": 42
    }
    ```

    **Error Response (400 - File Too Large):**
    ```json
    {
      "error": "validation_failed",
      "message": "File exceeds maximum size of 100MB",
      "detail": {
        "max_size_mb": 100,
        "actual_size_mb": 256
      }
    }
    ```

    **Error Response (500 - Processing Failed):**
    ```json
    {
      "error": "processing_failed",
      "message": "An unexpected error occurred while processing your request",
      "detail": {
        "error_id": "req_xyz123"
      }
    }
    ```

    Args:
        uploaded_file: Document file to index (PDF, TXT, DOCX, etc.)

    Returns:
        DocumentIngestionResponse with ingestion_id, success message, and total document count

    Raises:
        HTTPException 400: If file is invalid or exceeds size limits (100MB max)
            - Error code: `file_too_large` - File size exceeds 100MB limit
            - Error code: `invalid_format` - Unsupported file format
        HTTPException 500: If processing fails
            - Error code: `parse_failed` - Document text extraction failed
            - Error code: `processing_failed` - Pipeline execution failed

    Error codes are documented in `ERROR_CODES_REFERENCE.md`
    """
    ingestion_id = str(uuid.uuid4())
    file_size = get_upload_file_size(uploaded_file)

    # Validate file size
    if file_size > MAX_UPLOAD_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size of {MAX_UPLOAD_SIZE_MB}MB",
        )

    sys.stderr.write(f"DEBUG: About to log upload_start for {uploaded_file.filename}\n")
    sys.stderr.flush()
    logger.info(
        event="document.upload_start",
        doc_id=uploaded_file.filename,
        filename=uploaded_file.filename,
        size_bytes=file_size,
        content_type=uploaded_file.content_type,
    )
    sys.stderr.write("DEBUG: Logged upload_start\n")
    sys.stderr.flush()

    from certus_ask.services.ingestion import FileProcessor, StorageService

    document_store = get_document_store_for_workspace(workspace_id)
    storage_service = StorageService()
    file_processor = FileProcessor(
        document_store=document_store,
        storage_service=storage_service,
    )

    upload_dir = Path("uploads")
    storage_service.ensure_directory(upload_dir)

    metrics = get_ingestion_metrics()

    try:
        file_content = await uploaded_file.read()

        logger.info(
            event="document.upload_complete",
            doc_id=uploaded_file.filename,
            size_bytes=len(file_content),
        )

        # Process file using FileProcessor service
        result = await file_processor.process_file(
            file_content=file_content,
            filename=uploaded_file.filename,
            workspace_id=workspace_id,
            ingestion_id=ingestion_id,
            upload_dir=upload_dir,
        )

        # Check if documents were quarantined
        if result.get("quarantined"):
            logger.warning(
                event="document.quarantined",
                doc_id=uploaded_file.filename,
                reason="PII detected",
            )

        logger.info(
            event="document.indexed",
            doc_id=uploaded_file.filename,
            index="ask_certus",
            chunks_indexed=result["documents_written"],
        )

        # Record successful ingestion
        metrics.record_ingestion(
            source="document",
            document_count=result.get("documents_written", 0),
            success=True,
        )

        return DocumentIngestionResponse(
            request_id=get_request_id(),
            ingestion_id=ingestion_id,
            message=f"Indexed document {uploaded_file.filename}",
            document_count=document_store.count_documents(),
            metadata_preview=result.get("metadata_preview", []),
        )

    except (ValueError, KeyError) as exc:
        # Record failed ingestion
        metrics.record_ingestion(source="document", success=False)

        raise DocumentParseError(
            message="Failed to parse document",
            error_code="parse_failed",
            details={"filename": uploaded_file.filename, "error": str(exc)},
        ) from exc
    except Exception as exc:
        # Record failed ingestion
        metrics.record_ingestion(source="document", success=False)

        logger.error(
            event="document.indexing_failed",
            doc_id=uploaded_file.filename,
            error=str(exc),
            exc_info=True,
        )
        raise DocumentIngestionError(
            message="Failed to process document",
            error_code="ingestion_failed",
            details={"filename": uploaded_file.filename},
        ) from exc


@router.post(
    "/{workspace_id}/index_folder/",
    response_model=FolderIngestionResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "Path is not a valid directory"},
        500: {"model": InternalServerErrorResponse, "description": "Processing failed"},
    },
)
async def index_folder(
    workspace_id: str,
    request: IndexFolderRequest,
) -> FolderIngestionResponse:
    """Index all documents in a folder recursively.

    Walks through directory tree and processes all files matching supported
    formats. Continues on per-file errors to maximize indexing.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/index_folder/" \\
      -H "Content-Type: application/json" \\
      -d '{"local_directory": "/path/to/documents"}'
    ```

    **Success Response (200):**
    ```json
    {
      "ingestion_id": "550e8400-e29b-41d4-a716-446655440001",
      "message": "Indexed 15 files from /path/to/documents",
      "processed_files": 15,
      "failed_files": 2,
      "quarantined_documents": 3,
      "document_count": 127
    }
    ```

    **Error Response (400 - Invalid Path):**
    ```json
    {
      "error": "validation_failed",
      "message": "The provided path is not a valid directory",
      "detail": {
        "path": "/invalid/path"
      }
    }
    ```

    Args:
        request: Folder path to index (supports recursive walk)

    Returns:
        FolderIngestionResponse with processing stats (processed, failed, quarantined counts)

    Raises:
        HTTPException 400: If path is not a valid directory
        HTTPException 500: If critical error occurs
    """
    ingestion_id = str(uuid.uuid4())

    root_path = Path(request.local_directory).expanduser().resolve()
    if not root_path.is_dir():
        raise HTTPException(
            status_code=400,
            detail="The provided path is not a valid directory.",
        )

    logger.info(
        event="ingestion.folder_start",
        ingestion_id=ingestion_id,
        directory=str(root_path),
    )

    from certus_ask.services.ingestion import FileProcessor

    document_store = get_document_store_for_workspace(workspace_id)
    file_processor = FileProcessor(document_store=document_store)

    try:
        # Process folder using FileProcessor service
        result = await file_processor.process_folder(
            folder_path=root_path,
            workspace_id=workspace_id,
            ingestion_id=ingestion_id,
            recursive=True,  # Process all files recursively
        )

        logger.info(
            event="ingestion.folder_complete",
            ingestion_id=ingestion_id,
            directory=str(root_path),
            processed_files=result["processed_files"],
            failed_files=result["failed_files"],
            quarantined_count=result["quarantined_count"],
            total_documents=document_store.count_documents(),
        )

        return FolderIngestionResponse(
            request_id=get_request_id(),
            ingestion_id=ingestion_id,
            message=f"Indexed {result['processed_files']} files from {root_path}",
            processed_files=result["processed_files"],
            failed_files=result["failed_files"],
            quarantined_documents=result["quarantined_count"],
            document_count=document_store.count_documents(),
            metadata_preview=result.get("metadata_preview", [])[:3],
        )

    except Exception as exc:
        logger.error(
            event="ingestion.folder_failed",
            ingestion_id=ingestion_id,
            directory=str(root_path),
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process folder: {exc}",
        ) from exc


@router.post(
    "/{workspace_id}/index/github",
    response_model=GitHubIngestionResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "No files match patterns"},
        500: {"model": InternalServerErrorResponse, "description": "Clone or processing failed"},
    },
)
async def index_github_repo(
    workspace_id: str,
    request: GitRepositoryRequest,
) -> GitHubIngestionResponse:
    """Clone and index documents from a GitHub repository.

    Clones repository (optionally to specific branch) and indexes all files
    matching include/exclude patterns.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/index/github" \\
      -H "Content-Type: application/json" \\
      -d '{
        "repo_url": "https://github.com/user/repo.git",
        "branch": "main",
        "include_globs": ["**/*.md", "**/*.txt"],
        "exclude_globs": ["node_modules/**"],
        "max_file_size_kb": 5000
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "ingestion_id": "550e8400-e29b-41d4-a716-446655440002",
      "message": "Indexed 42 files from https://github.com/user/repo.git",
      "file_count": 42,
      "quarantined_documents": 1,
      "document_count": 256
    }
    ```

    **Error Response (400 - No Files Match):**
    ```json
    {
      "error": "validation_failed",
      "message": "No files matched the provided patterns",
      "detail": {
        "include_globs": ["**/*.pdf"],
        "exclude_globs": ["node_modules/**"]
      }
    }
    ```

    Args:
        request: GitHub repository details (URL, branch, glob patterns, file size limit)

    Returns:
        GitHubIngestionResponse with file_count and quarantined_documents

    Raises:
        HTTPException 400: If no files match patterns or invalid patterns
        HTTPException 500: If clone or processing fails
    """
    ingestion_id = str(uuid.uuid4())

    logger.info(
        event="ingestion.github_start",
        ingestion_id=ingestion_id,
        repo_url=request.repo_url,
        branch=request.branch,
    )

    from certus_ask.services.ingestion import FileProcessor

    document_store = get_document_store_for_workspace(workspace_id)
    file_processor = FileProcessor(document_store=document_store)

    try:
        # Process GitHub repository using FileProcessor service
        result = await file_processor.process_github(
            repo_url=request.repo_url,
            workspace_id=workspace_id,
            ingestion_id=ingestion_id,
            branch=request.branch,
            include_globs=request.include_globs,
            exclude_globs=request.exclude_globs,
            max_file_size_kb=request.max_file_size_kb,
        )

        logger.info(
            event="ingestion.github_complete",
            ingestion_id=ingestion_id,
            repo_url=request.repo_url,
            file_count=result["file_count"],
            quarantined_count=result["quarantined_count"],
            total_documents=document_store.count_documents(),
        )

        return GitHubIngestionResponse(
            request_id=get_request_id(),
            ingestion_id=ingestion_id,
            message=f"Indexed {result['file_count']} files from {request.repo_url}",
            file_count=result["file_count"],
            quarantined_documents=result["quarantined_count"],
            document_count=document_store.count_documents(),
            metadata_preview=result.get("metadata_preview", []),
        )

    except ValidationError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except Exception as exc:
        logger.error(
            event="ingestion.github_failed",
            ingestion_id=ingestion_id,
            repo_url=request.repo_url,
            error=str(exc),
            exc_info=True,
        )
        raise DocumentIngestionError(
            message="Failed to process repository",
            error_code="github_ingestion_failed",
            details={"repo_url": request.repo_url},
        ) from exc


@router.post(
    "/{workspace_id}/index/security",
    response_model=SarifIngestionResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "Invalid file or file too large"},
        500: {"model": InternalServerErrorResponse, "description": "Processing failed"},
    },
)
async def index_security_file(
    workspace_id: str,
    uploaded_file: Annotated[UploadFile, File(...)],
    format: Annotated[str, Form()] = "auto",
    tool_hint: Annotated[str | None, Form()] = None,
    schema_dict: Annotated[dict | None, Form()] = None,
) -> SarifIngestionResponse:
    """Upload and index security files (SARIF, SPDX, or custom JSONPath-based formats).

    Parses security scanning format files and loads them into:
    1. Neo4j - for relationship/graph queries
    2. OpenSearch - for semantic search and RAG

    Supports three ingestion modes:
    1. **Auto-detect**: Automatically detects SARIF/SPDX from file extension
    2. **Tool-hint**: Uses tool_hint to locate a pre-registered parser
    3. **Custom JSONPath**: Uses schema_dict to parse custom tool formats via JSONPath

    **Request Examples:**

    Auto-detect (SARIF):
    ```bash
    curl -X POST "http://localhost:8000/v1/{workspace_id}/index/security" \\
      -H "Content-Type: multipart/form-data" \\
      -F "uploaded_file=@scan_results.sarif"
    ```

    Custom JSONPath schema:
    ```bash
    curl -X POST "http://localhost:8000/v1/{workspace_id}/index/security" \\
      -H "Content-Type: multipart/form-data" \\
      -F "uploaded_file=@custom_scan.json" \\
      -F "format=jsonpath" \\
      -F "schema_dict={\"tool_name\":\"my-scanner\",\"version\":\"1.0.0\",\"format\":{\"findings_path\":\"$.results[*]\",\"mapping\":{\"id\":\"$.id\",\"title\":\"$.title\",\"severity\":\"$.level\"}}}"
    ```

    Args:
        workspace_id: Workspace identifier
        uploaded_file: Security file (SARIF, SPDX JSON/YAML, or custom JSON, max 100MB)
        request: SecurityIngestionRequest with format, optional schema_dict, and optional tool_hint

    Returns:
        Response with findings/packages indexed count

    Raises:
        HTTPException 400: If file invalid, exceeds size limits, or schema is invalid
        HTTPException 500: If processing fails
    """
    from certus_ask.core.config import Settings

    ingestion_id = str(uuid.uuid4())
    settings = Settings()

    logger.info(
        event="ingestion.security_upload_start",
        ingestion_id=ingestion_id,
        filename=uploaded_file.filename,
        format=format,
        tool_hint=tool_hint,
        schema_provided=schema_dict is not None,
    )

    # Debug: Log parameter types and values
    logger.info(
        event="ingestion.security_parameters_debug",
        format_value=repr(format),
        format_type=type(format).__name__,
        tool_hint_value=repr(tool_hint),
        tool_hint_type=type(tool_hint).__name__ if tool_hint else "None",
    )

    # Note: File size validation skipped for now due to UploadFile pointer issues
    # In production, implement proper async file handling

    file_bytes = await uploaded_file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail="Uploaded file is empty",
        )

    return await _ingest_security_payload(
        workspace_id,
        file_bytes=file_bytes,
        source_name=uploaded_file.filename or "uploaded_security_file",
        requested_format=format,
        tool_hint=tool_hint,
        schema_dict=schema_dict,
        ingestion_id=ingestion_id,
    )


@router.post(
    "/{workspace_id}/index/security/s3",
    response_model=SarifIngestionResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "Invalid bucket/key or schema"},
        500: {"model": InternalServerErrorResponse, "description": "Processing failed"},
    },
)
async def index_security_file_from_s3(
    workspace_id: str,
    request: SecurityS3IngestionRequest,
) -> SarifIngestionResponse:
    """Stream security scans (SARIF/SPDX) directly from S3 without downloading locally."""
    import boto3
    from botocore.exceptions import ClientError

    from certus_ask.core.config import Settings
    from certus_ask.services.ingestion import FileProcessor

    ingestion_id = str(uuid.uuid4())
    settings = Settings()
    source_name = f"s3://{request.bucket_name}/{request.key}"

    logger.info(
        event="ingestion.security_s3_start",
        ingestion_id=ingestion_id,
        bucket=request.bucket_name,
        key=request.key,
        format=request.format,
        tool_hint=request.tool_hint,
        schema_provided=request.schema_dict is not None,
    )

    # Create S3 client and FileProcessor
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        endpoint_url=settings.s3_endpoint_url,
        region_name=settings.aws_region,
    )
    file_processor = FileProcessor(s3_client=s3_client)

    try:
        file_bytes = file_processor.download_from_s3(
            bucket_name=request.bucket_name,
            key=request.key,
        )
    except ClientError as exc:
        logger.error(
            event="ingestion.security_s3_failed",
            ingestion_id=ingestion_id,
            bucket=request.bucket_name,
            key=request.key,
            error=str(exc),
        )
        raise HTTPException(
            status_code=400,
            detail=f"Unable to fetch s3://{request.bucket_name}/{request.key}: {exc!s}",
        ) from exc
    except Exception as exc:
        logger.error(
            event="ingestion.security_s3_failed",
            ingestion_id=ingestion_id,
            bucket=request.bucket_name,
            key=request.key,
            error=str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Unexpected error while fetching the S3 object",
        ) from exc

    if not file_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"S3 object s3://{request.bucket_name}/{request.key} is empty",
        )

    return await _ingest_security_payload(
        workspace_id,
        file_bytes=file_bytes,
        source_name=source_name,
        requested_format=request.format,
        tool_hint=request.tool_hint,
        schema_dict=request.schema_dict,
        ingestion_id=ingestion_id,
        tier=request.tier,
        assessment_id=request.assessment_id,
        signatures=request.signatures,
        artifact_locations=request.artifact_locations,
        s3_bucket=request.bucket_name,
        s3_key=request.key,
    )


@router.post(
    "/{workspace_id}/index/web",
    response_model=WebIngestionResponse,
    responses={
        500: {"model": InternalServerErrorResponse, "description": "Web scraping failed"},
    },
)
async def index_web_pages(
    workspace_id: str,
    request: WebIngestionRequest,
) -> WebIngestionResponse:
    """Scrape and index documents from web URLs.

    Fetches and parses web pages, extracting content for indexing.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/index/web" \\
      -H "Content-Type: application/json" \\
      -d '{
        "urls": [
          "https://example.com/article1",
          "https://example.com/article2"
        ],
        "render": false
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "ingestion_id": "550e8400-e29b-41d4-a716-446655440004",
      "message": "Indexed 2 web pages.",
      "indexed_count": 2,
      "skipped_urls": [],
      "document_count": 512
    }
    ```

    **Error Response (500 - Scraping Failed):**
    ```json
    {
      "error": "processing_failed",
      "message": "An unexpected error occurred while processing your request",
      "detail": {
        "error_id": "req_abc456"
      }
    }
    ```

    Args:
        request: URLs to scrape and render preference (JavaScript rendering available)

    Returns:
        WebIngestionResponse with indexed_count and skipped_urls list

    Raises:
        HTTPException 500: If scraping fails
    """
    ingestion_id = str(uuid.uuid4())

    logger.info(
        event="ingestion.web_scrape_start",
        ingestion_id=ingestion_id,
        url_count=len(request.urls),
        render=request.render,
    )

    from certus_ask.services.ingestion import FileProcessor

    document_store = get_document_store_for_workspace(workspace_id)
    file_processor = FileProcessor(document_store=document_store)

    try:
        # Process web pages using FileProcessor service
        result = await file_processor.process_web(
            urls=request.urls,
            workspace_id=workspace_id,
            ingestion_id=ingestion_id,
        )

        logger.info(
            event="ingestion.web_scrape_complete",
            ingestion_id=ingestion_id,
            indexed_count=result["indexed_count"],
            skipped_count=result["skipped_count"],
            total_documents=document_store.count_documents(),
        )

        return WebIngestionResponse(
            request_id=get_request_id(),
            ingestion_id=ingestion_id,
            message=f"Indexed {result['indexed_count']} web pages.",
            indexed_count=result["indexed_count"],
            skipped_urls=result.get("skipped_urls", []),
            document_count=document_store.count_documents(),
            metadata_preview=result.get("metadata_preview", []),
        )

    except Exception as exc:
        logger.error(
            event="ingestion.web_scrape_failed",
            ingestion_id=ingestion_id,
            url_count=len(request.urls),
            error=str(exc),
            exc_info=True,
        )
        raise DocumentIngestionError(
            message="Failed to scrape URLs",
            error_code="web_scraping_failed",
            details={"url_count": len(request.urls)},
        ) from exc


@router.post(
    "/{workspace_id}/index/web/crawl",
    response_model=WebCrawlIngestionResponse,
    responses={
        500: {"model": InternalServerErrorResponse, "description": "Web crawling failed"},
    },
)
async def crawl_web_domain(
    workspace_id: str,
    request: WebCrawlRequest,
) -> WebCrawlIngestionResponse:
    """Crawl and index documents from web domains.

    Recursively crawls website starting from seed URLs, respecting depth,
    page count, and pattern constraints.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/index/web/crawl" \\
      -H "Content-Type: application/json" \\
      -d '{
        "seed_urls": ["https://example.com"],
        "allowed_domains": ["example.com"],
        "allow_patterns": ["/docs/**", "/guides/**"],
        "deny_patterns": ["/admin/**"],
        "max_pages": 100,
        "max_depth": 3,
        "render": false
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "ingestion_id": "550e8400-e29b-41d4-a716-446655440005",
      "message": "Crawled 87 pages (limit 100).",
      "indexed_count": 87,
      "skipped_urls": ["https://example.com/admin/settings"],
      "document_count": 768
    }
    ```

    **Error Response (500 - Crawling Failed):**
    ```json
    {
      "error": "processing_failed",
      "message": "An unexpected error occurred while processing your request",
      "detail": {
        "error_id": "req_def789"
      }
    }
    ```

    Args:
        request: Crawl configuration with seed URLs, domain restrictions, patterns, and depth/page limits

    Returns:
        WebCrawlIngestionResponse with indexed_count and skipped_urls

    Raises:
        HTTPException 500: If crawling fails
    """
    ingestion_id = str(uuid.uuid4())

    logger.info(
        event="ingestion.web_crawl_start",
        ingestion_id=ingestion_id,
        seed_urls=request.seed_urls,
        max_pages=request.max_pages,
        max_depth=request.max_depth,
    )

    document_store = get_document_store_for_workspace(workspace_id)
    pipeline = create_scrapy_crawl_pipeline(document_store)

    try:
        loop = asyncio.get_running_loop()
        metadata_params = {
            "metadata_context": {
                "workspace_id": workspace_id,
                "ingestion_id": ingestion_id,
                "source": "web_crawl",
                "extra_meta": {
                    "allowed_domains": request.allowed_domains,
                    "max_pages": request.max_pages,
                    "max_depth": request.max_depth,
                },
            }
        }
        result = await loop.run_in_executor(
            None,
            lambda: pipeline.run({
                "crawler": {
                    "seed_urls": request.seed_urls,
                    "allowed_domains": request.allowed_domains,
                    "allow_patterns": request.allow_patterns,
                    "deny_patterns": request.deny_patterns,
                    "max_pages": request.max_pages,
                    "max_depth": request.max_depth,
                    "render": request.render,
                },
                "document_writer": metadata_params,
            }),
        )

        crawler_output = result.get("crawler", {})
        indexed_documents = crawler_output.get("documents", [])
        skipped_urls = crawler_output.get("skipped", [])

        logger.info(
            event="ingestion.web_crawl_complete",
            ingestion_id=ingestion_id,
            indexed_count=len(indexed_documents),
            skipped_count=len(skipped_urls),
            total_documents=document_store.count_documents(),
        )

        metadata_preview = extract_metadata_preview(result.get("document_writer") or {})

        return WebCrawlIngestionResponse(
            request_id=get_request_id(),
            ingestion_id=ingestion_id,
            message=f"Crawled {len(indexed_documents)} pages (limit {request.max_pages}).",
            indexed_count=len(indexed_documents),
            skipped_urls=skipped_urls,
            document_count=document_store.count_documents(),
            metadata_preview=metadata_preview,
        )

    except Exception as exc:
        logger.error(
            event="ingestion.web_crawl_failed",
            ingestion_id=ingestion_id,
            seed_urls=request.seed_urls,
            error=str(exc),
            exc_info=True,
        )
        raise DocumentIngestionError(
            message="Failed to crawl URLs",
            error_code="web_crawling_failed",
            details={"seed_urls": request.seed_urls},
        ) from exc


@router.post(
    "/{workspace_id}/index/s3",
    response_model=FolderIngestionResponse,
    responses={
        400: {"model": BadRequestErrorResponse, "description": "Invalid S3 path or bucket"},
        500: {"model": InternalServerErrorResponse, "description": "Processing failed"},
    },
)
async def index_s3_folder(
    workspace_id: str,
    request: S3IndexRequest,
) -> FolderIngestionResponse:
    """Index all documents in an S3 bucket/prefix.

    Downloads files from S3 to temp storage, processes them through the preprocessing pipeline,
    and indexes them in OpenSearch. Continues on per-file errors.

    **Request Example:**
    ```bash
    curl -X POST "http://localhost:8000/v1/my-workspace/index/s3" \\
      -H "Content-Type: application/json" \\
      -d '{
        "bucket_name": "my-bucket",
        "prefix": "corpus"
      }'
    ```

    **Success Response (200):**
    ```json
    {
      "ingestion_id": "550e8400-e29b-41d4-a716-446655440001",
      "message": "Indexed 15 files from s3://my-bucket/corpus",
      "processed_files": 15,
      "failed_files": 2,
      "quarantined_documents": 3,
      "document_count": 127
    }
    ```

    Args:
        workspace_id: Workspace ID to index documents into
        request: S3IndexRequest with bucket_name and optional prefix

    Returns:
        FolderIngestionResponse with processing stats

    Raises:
        HTTPException 400: If bucket doesn't exist or prefix is invalid
        HTTPException 500: If processing fails
    """
    import boto3
    from botocore.exceptions import ClientError

    from certus_ask.core.config import Settings

    ingestion_id = str(uuid.uuid4())
    settings = Settings()

    bucket_name = request.bucket_name
    prefix = request.prefix or ""

    if not bucket_name:
        raise HTTPException(
            status_code=400,
            detail="bucket_name is required",
        )

    logger.info(
        event="ingestion.s3_start",
        ingestion_id=ingestion_id,
        bucket=bucket_name,
        prefix=prefix,
    )

    document_store = get_document_store_for_workspace(workspace_id)
    pipeline = create_preprocessing_pipeline(document_store)

    # Create S3 client
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
            endpoint_url=settings.s3_endpoint_url,
            region_name=settings.aws_region,
        )

        # Verify bucket exists
        s3_client.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            raise HTTPException(
                status_code=400,
                detail=f"Bucket '{bucket_name}' not found",
            ) from e
        raise HTTPException(
            status_code=400,
            detail=f"Cannot access bucket '{bucket_name}': {e!s}",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"S3 connection failed: {e!s}",
        ) from e

    # Download and process files from S3
    from certus_ask.services.ingestion import FileProcessor

    file_processor = FileProcessor(s3_client=s3_client)
    processed_files = 0
    failed_files = 0
    quarantined_count = 0
    metadata_preview: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        try:
            # List objects in S3 using FileProcessor
            objects = file_processor.list_s3_objects(bucket_name, prefix)

            for obj in objects:
                if obj["Key"].endswith("/"):
                    # Skip directory markers
                    continue

                s3_key = obj["Key"]
                file_name = Path(s3_key).name
                local_file_path = temp_path / file_name

                try:
                    logger.info(
                        event="ingestion.s3_downloading",
                        ingestion_id=ingestion_id,
                        s3_key=s3_key,
                    )

                    # Download file using FileProcessor
                    file_processor.download_file_to_local(
                        bucket_name=bucket_name,
                        key=s3_key,
                        local_path=local_file_path,
                    )

                    logger.info(
                        event="ingestion.s3_processing",
                        ingestion_id=ingestion_id,
                        s3_key=s3_key,
                        local_path=str(local_file_path),
                    )

                    # Process file
                    result = pipeline.run({
                        "file_type_router": {"sources": [local_file_path]},
                        "document_writer": {
                            "metadata_context": {
                                "workspace_id": workspace_id,
                                "ingestion_id": ingestion_id,
                                "source": "s3",
                                "source_location": f"s3://{bucket_name}/{s3_key}",
                                "extra_meta": {
                                    "bucket": bucket_name,
                                    "s3_prefix": prefix,
                                },
                            }
                        },
                    })

                    processed_files += 1

                    if len(metadata_preview) < 3:
                        writer_result = result.get("document_writer") or {}
                        metadata_preview.extend(
                            extract_metadata_preview(writer_result, limit=3 - len(metadata_preview))
                        )

                    # Track quarantined documents
                    quarantined = result.get("presidio_anonymizer", {}).get("quarantined", [])
                    if quarantined:
                        quarantined_count += len(quarantined)
                        logger.warning(
                            event="ingestion.s3_file_quarantined",
                            ingestion_id=ingestion_id,
                            s3_key=s3_key,
                            quarantined_count=len(quarantined),
                        )

                except Exception as exc:
                    failed_files += 1
                    logger.error(
                        event="ingestion.s3_file_processing_failed",
                        ingestion_id=ingestion_id,
                        s3_key=s3_key,
                        error=str(exc),
                        exc_info=True,
                    )
                    continue

        except Exception as exc:
            logger.error(
                event="ingestion.s3_listing_failed",
                ingestion_id=ingestion_id,
                bucket=bucket_name,
                prefix=prefix,
                error=str(exc),
                exc_info=True,
            )
            raise DocumentIngestionError(
                message="Failed to list S3 objects",
                error_code="s3_listing_failed",
                details={"bucket": bucket_name, "prefix": prefix},
            ) from exc

    logger.info(
        event="ingestion.s3_complete",
        ingestion_id=ingestion_id,
        bucket=bucket_name,
        prefix=prefix,
        processed_files=processed_files,
        failed_files=failed_files,
        quarantined_count=quarantined_count,
        total_documents=document_store.count_documents(),
    )

    return FolderIngestionResponse(
        request_id=get_request_id(),
        ingestion_id=ingestion_id,
        message=f"Indexed {processed_files} files from s3://{bucket_name}/{prefix}",
        processed_files=processed_files,
        failed_files=failed_files,
        quarantined_documents=quarantined_count,
        document_count=document_store.count_documents(),
        metadata_preview=metadata_preview[:3],
    )
