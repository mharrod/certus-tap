from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field, model_validator

from certus_assurance.jobs import ScanJob, ScanJobManager, ScanStatus, job_manager
from certus_assurance.logs import log_stream_manager
from certus_assurance.manifest import ManifestFetcher
from certus_assurance.models import ArtifactBundle, PipelineResult, ScanRequest
from certus_assurance.pipeline import CertusAssuranceRunner, ManagedRuntime
from certus_assurance.sample_scanner import SampleSecurityScanner
from certus_assurance.settings import CertusAssuranceSettings, settings
from certus_assurance.signing import CosignClient
from certus_assurance.storage import DockerRegistryPublisher, RegistryMirrorPublisher, TransformArtifactPublisher

logger = logging.getLogger(__name__)


def get_settings() -> CertusAssuranceSettings:
    return settings


def get_job_manager() -> ScanJobManager:
    return job_manager


_runner: CertusAssuranceRunner | None = None
_artifact_uploader: TransformArtifactPublisher | None = None
_registry_publisher: RegistryMirrorPublisher | DockerRegistryPublisher | None = None
_cosign_client: CosignClient | None = None


def get_runner(cfg: CertusAssuranceSettings = Depends(get_settings)) -> CertusAssuranceRunner:
    global _runner

    # Determine scanning mode
    use_sample_mode = cfg.use_sample_mode

    # Check if security_module is available
    security_module_available = ManagedRuntime is not None

    # If sample mode is requested but security_module is available, use sample mode anyway (explicit opt-in)
    # If sample mode is NOT requested and security_module is NOT available, raise error
    if not use_sample_mode and not security_module_available:
        raise RuntimeError(
            "Real scanning requires security_module, but it's not available.\n"
            "Install with: pip install -e dagger_modules/security\n"
            "Or set CERTUS_ASSURANCE_USE_SAMPLE_MODE=true for demo mode with pre-generated artifacts."
        )

    needs_refresh = (
        _runner is None
        or _runner.output_root != cfg.artifact_root
        or _runner.registry != cfg.registry.rstrip("/")
        or _runner.registry_repository != cfg.registry_repository.strip("/")
        or _runner.manifest_key_ref != cfg.manifest_verification_key_ref
        or _runner.require_manifest_verification != cfg.manifest_verification_required
    )
    if _runner is not None and _runner.preserve_sample_metadata != use_sample_mode:
        needs_refresh = True
    if needs_refresh:
        runtime_factory = None
        scanner_builder = None
        preserve_metadata = False

        if use_sample_mode:
            logger.warning(
                "⚠️  SAMPLE MODE: Using pre-generated artifacts from %s. "
                "Set CERTUS_ASSURANCE_USE_SAMPLE_MODE=false for real scanning.",
                cfg.case_study_source,
            )
            sample_scanner = SampleSecurityScanner(cfg.case_study_source)
            runtime_factory = lambda stream: None  # type: ignore[assignment]
            scanner_builder = lambda runtime: sample_scanner  # type: ignore[assignment]
            preserve_metadata = True

        _runner = CertusAssuranceRunner(
            output_root=cfg.artifact_root,
            registry=cfg.registry,
            registry_repository=cfg.registry_repository,
            trust_base_url=cfg.trust_base_url,
            manifest_fetcher=ManifestFetcher(cfg),
            cosign_client=get_cosign_client(cfg),
            manifest_key_ref=cfg.manifest_verification_key_ref,
            require_manifest_verification=cfg.manifest_verification_required,
            runtime_factory=runtime_factory,
            scanner_builder=scanner_builder,
            preserve_sample_metadata=preserve_metadata,
        )
    return _runner


def get_artifact_uploader(cfg: CertusAssuranceSettings = Depends(get_settings)) -> TransformArtifactPublisher | None:
    global _artifact_uploader
    if not cfg.enable_s3_upload:
        return None

    needs_refresh = _artifact_uploader is None

    if needs_refresh:
        client = boto3.client(
            "s3",
            endpoint_url=cfg.s3_endpoint_url,
            region_name=cfg.s3_region,
            aws_access_key_id=cfg.s3_access_key_id,
            aws_secret_access_key=cfg.s3_secret_access_key,
        )
        _artifact_uploader = TransformArtifactPublisher(
            client=client,
            raw_bucket=cfg.datalake_raw_bucket,
            golden_bucket=cfg.datalake_golden_bucket,
            raw_prefix=cfg.datalake_raw_prefix,
            golden_prefix=cfg.datalake_golden_prefix,
        )
    return _artifact_uploader


def get_cosign_client(cfg: CertusAssuranceSettings = Depends(get_settings)) -> CosignClient | None:
    global _cosign_client
    if not cfg.cosign_enabled and not cfg.manifest_verification_key_ref:
        return None

    if _cosign_client is None or _cosign_client.binary != cfg.cosign_path:
        _cosign_client = CosignClient(binary=cfg.cosign_path)
    return _cosign_client


def get_registry_publisher(
    cfg: CertusAssuranceSettings = Depends(get_settings),
    cosign: CosignClient | None = Depends(get_cosign_client),
) -> RegistryMirrorPublisher | DockerRegistryPublisher | None:
    global _registry_publisher
    if not cfg.enable_registry_push:
        return None

    if cfg.registry_push_strategy == "docker":
        if not isinstance(_registry_publisher, DockerRegistryPublisher):
            _registry_publisher = DockerRegistryPublisher(
                registry=cfg.registry,
                repository=cfg.registry_repository,
                username=cfg.registry_username,
                password=cfg.registry_password,
                cosign=cosign,
                cosign_key_ref=cfg.cosign_key_ref,
                cosign_password=cfg.cosign_password,
            )
    else:
        if (
            not isinstance(_registry_publisher, RegistryMirrorPublisher)
            or _registry_publisher.root != cfg.registry_mirror_dir
        ):
            _registry_publisher = RegistryMirrorPublisher(cfg.registry_mirror_dir)
    return _registry_publisher


router = APIRouter(prefix="/v1/security-scans", tags=["security-scans"])


class ArchiveUploadResponse(BaseModel):
    archive_path: str = Field(..., description="Path to uploaded archive file")
    archive_hash: str = Field(..., description="SHA256 hash of the uploaded archive")
    filename: str = Field(..., description="Original filename")
    size: int = Field(..., description="File size in bytes")


@router.post("/upload-archive", response_model=ArchiveUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_archive(
    file: UploadFile = File(..., description="Archive file (.tar.gz, .zip, etc.)"),
    cfg: CertusAssuranceSettings = Depends(get_settings),
) -> ArchiveUploadResponse:
    """Upload an archive file for scanning.

    The uploaded file is saved to the configured upload directory and can be
    referenced in subsequent scan requests using the returned archive_path.

    Supported formats: .tar, .tar.gz, .tgz, .tar.bz2, .zip
    """
    # Validate file extension
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Filename is required")

    suffix = Path(file.filename).suffix.lower()
    allowed_suffixes = {".tar", ".gz", ".tgz", ".zip", ".bz2"}

    # Check for compound extensions like .tar.gz
    if suffix not in allowed_suffixes:
        # Check for .tar.gz, .tar.bz2, etc.
        parts = file.filename.lower().split(".")
        if len(parts) >= 2:
            compound = f".{parts[-2]}.{parts[-1]}"
            if compound not in {".tar.gz", ".tar.bz2"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported file type. Allowed: .tar, .tar.gz, .tgz, .tar.bz2, .zip",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type. Allowed: .tar, .tar.gz, .tgz, .tar.bz2, .zip",
            )

    # Create upload directory if it doesn't exist
    upload_dir = Path(cfg.artifact_root) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique filename to avoid conflicts
    import time
    timestamp = int(time.time() * 1000)
    safe_filename = f"{timestamp}_{file.filename}"
    archive_path = upload_dir / safe_filename

    # Save uploaded file and calculate hash
    hasher = hashlib.sha256()
    file_size = 0

    try:
        with archive_path.open("wb") as f:
            while chunk := await file.read(8192):
                f.write(chunk)
                hasher.update(chunk)
                file_size += len(chunk)
    except Exception as e:
        # Cleanup on error
        if archive_path.exists():
            archive_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save uploaded file: {e!s}",
        )

    archive_hash = hasher.hexdigest()

    logger.info(
        f"Archive uploaded: {file.filename} -> {archive_path}",
        extra={
            "filename": file.filename,
            "archive_path": str(archive_path),
            "archive_hash": archive_hash,
            "size": file_size,
        },
    )

    return ArchiveUploadResponse(
        archive_path=str(archive_path),
        archive_hash=archive_hash,
        filename=file.filename,
        size=file_size,
    )


class ScanCreateRequest(BaseModel):
    workspace_id: str = Field(..., description="Workspace/tenant identifier.")
    component_id: str = Field(..., description="Component or asset under test.")
    assessment_id: str = Field(..., description="Assessment campaign identifier.")

    # Source type selection
    source_type: str = Field(default="git", description="Type of source to scan: 'git', 'directory', or 'archive'")

    # Git source (existing)
    git_url: str | None = Field(None, description="Git URL or local path to scan (required if source_type='git').")
    branch: str | None = Field(None, description="Optional branch to checkout.")
    commit: str | None = Field(None, description="Optional commit hash.")

    # Directory source (Phase 1)
    directory_path: str | None = Field(None, description="Local directory path to scan (required if source_type='directory').")

    # Archive source (Phase 2)
    archive_path: str | None = Field(None, description="Path to archive file to scan (required if source_type='archive').")

    # Metadata
    requested_by: str | None = Field(None, description="Optional identifier for the caller.")
    profile: str = Field(default="light", description="Manifest profile to execute.")
    manifest: dict[str, Any] | None = Field(
        default=None,
        description="Manifest JSON exported from Cue (`cue export ...`).",
    )
    manifest_path: str | None = Field(
        default=None,
        description="Optional manifest path inside the repository if you prefer file-based resolution.",
    )
    manifest_uri: str | None = Field(
        default=None,
        description="Remote manifest location (file:///path, s3://bucket/key, oci://registry/repo:tag).",
    )
    manifest_signature_uri: str | None = Field(
        default=None,
        description="Remote signature matching `manifest_uri` (required when using manifest_uri).",
    )

    @model_validator(mode="after")
    def _validate_source_and_manifest(cls, values: ScanCreateRequest) -> ScanCreateRequest:
        # Validate source type fields
        if values.source_type == "git":
            if not values.git_url:
                raise ValueError("git_url is required when source_type='git'")
        elif values.source_type == "directory":
            if not values.directory_path:
                raise ValueError("directory_path is required when source_type='directory'")
        elif values.source_type == "archive":
            if not values.archive_path:
                raise ValueError("archive_path is required when source_type='archive'")
        else:
            raise ValueError(f"Invalid source_type: '{values.source_type}'. Must be 'git', 'directory', or 'archive'")

        # Validate manifest
        if not values.manifest and not values.manifest_path and not values.manifest_uri:
            raise ValueError("Provide one of 'manifest', 'manifest_path', or 'manifest_uri'")
        if values.manifest_uri and not values.manifest_signature_uri:
            raise ValueError("'manifest_signature_uri' is required when 'manifest_uri' is set")

        return values


class ScanCreateResponse(BaseModel):
    test_id: str
    workspace_id: str
    component_id: str
    assessment_id: str
    status: str
    profile: str
    manifest_digest: str | None = None
    stream_url: str


class ScanStatusResponse(BaseModel):
    test_id: str
    workspace_id: str
    component_id: str
    assessment_id: str
    status: str
    git_url: str
    branch: str | None
    commit: str | None
    requested_by: str | None
    profile: str
    started_at: datetime | None
    completed_at: datetime | None
    artifacts: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    remote_artifacts: dict[str, Any] | None = Field(default=None)
    registry: dict[str, Any] | None = Field(default=None)
    upload_status: str = Field(default="pending", description="pending, permitted, or failed")
    upload_permission_id: str | None = Field(default=None, description="Permission ID from Trust verification")
    verification_proof: dict[str, Any] | None = Field(
        default=None, description="Verification proof returned by Trust (if available)"
    )
    manifest_digest: str | None = Field(default=None)
    manifest_metadata: dict[str, Any] | None = Field(default=None)
    stream_url: str | None = Field(default=None)


@router.post("", response_model=ScanCreateResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_scan(
    payload: ScanCreateRequest,
    jm: ScanJobManager = Depends(get_job_manager),
    pipeline_runner: CertusAssuranceRunner = Depends(get_runner),
    registry_publisher: RegistryMirrorPublisher | None = Depends(get_registry_publisher),
) -> ScanCreateResponse:
    manifest_text = None
    manifest_digest = None
    if payload.manifest:
        manifest_text = json.dumps(payload.manifest, sort_keys=True)
        manifest_digest = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()

    loop = asyncio.get_running_loop()
    test_id = jm.new_test_id()
    log_stream = log_stream_manager.register(test_id, loop)

    def run_with_publishers(request: ScanRequest):
        result = pipeline_runner.run(request)
        metadata_changed = False
        if registry_publisher:
            registry_info = registry_publisher.publish(result)
            result.metadata["registry"] = registry_info
            metadata_changed = True
        if metadata_changed:
            _rewrite_metadata_file(result)
        return result

    job = jm.submit(
        workspace_id=payload.workspace_id,
        component_id=payload.component_id,
        assessment_id=payload.assessment_id,
        source_type=payload.source_type,
        git_url=payload.git_url,
        branch=payload.branch,
        commit=payload.commit,
        directory_path=payload.directory_path,
        archive_path=payload.archive_path,
        requested_by=payload.requested_by,
        profile=payload.profile,
        manifest_text=manifest_text,
        manifest_path=payload.manifest_path,
        manifest_uri=payload.manifest_uri,
        manifest_signature_uri=payload.manifest_signature_uri,
        manifest_digest=manifest_digest,
        log_stream=log_stream,
        runner_fn=run_with_publishers,
        test_id=test_id,
    )

    await asyncio.sleep(0)

    return ScanCreateResponse(
        test_id=job.test_id,
        workspace_id=job.workspace_id,
        component_id=job.component_id,
        assessment_id=job.assessment_id,
        status=job.status,
        profile=job.profile,
        manifest_digest=manifest_digest,
        stream_url=f"/v1/security-scans/{job.test_id}/stream",
    )


@router.get("/{test_id}", response_model=ScanStatusResponse)
async def get_scan_status(test_id: str, jm: ScanJobManager = Depends(get_job_manager)) -> ScanStatusResponse:
    job = jm.get_job(test_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    return _serialize_job(job)


@router.websocket("/{test_id}/stream")
async def stream_scan_logs(test_id: str, websocket: WebSocket) -> None:
    stream = log_stream_manager.get(test_id)
    if not stream:
        await websocket.close(code=4404, reason="Scan not found")
        return

    await websocket.accept()
    try:
        for event in stream.history:
            await websocket.send_text(event.to_json())
        while True:
            event = await stream.queue.get()
            await websocket.send_text(event.to_json())
            if event.type == "scan_complete":
                break
    except WebSocketDisconnect:
        return


class UploadRequestBody(BaseModel):
    tier: str = Field(default="verified", description="Tier: 'basic' or 'verified'")
    signer: str | None = Field(
        default=None,
        description="Optional: Override signer identity for testing. Defaults to 'certus-assurance@certus.cloud'",
    )


class UploadRequestResponse(BaseModel):
    upload_permission_id: str | None = Field(None, description="Permission ID from Trust")
    upload_status: str = Field(description="Status: pending, permitted, or failed")


@router.post("/{test_id}/upload-request", response_model=UploadRequestResponse, status_code=status.HTTP_202_ACCEPTED)
async def submit_upload_request(
    test_id: str,
    body: UploadRequestBody,
    runner: CertusAssuranceRunner = Depends(get_runner),
    jm: ScanJobManager = Depends(get_job_manager),
    uploader: TransformArtifactPublisher | None = Depends(get_artifact_uploader),
    cfg: CertusAssuranceSettings = Depends(get_settings),
) -> UploadRequestResponse:
    """Submit an upload request to Trust for a completed scan.

    This is a separate step from scanning - only call after scan is SUCCEEDED.

    Flow:
    1. Submit upload request to Trust for verification
    2. If permitted, upload artifacts directly to S3
    3. Return permission status and upload results
    """
    job = jm.get_job(test_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Scan not found")

    if job.status != ScanStatus.SUCCEEDED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Scan must be SUCCEEDED to submit upload request. Current status: {job.status}",
        )

    # Load scan artifacts and metadata
    try:
        logger.info(f"Starting upload request for {test_id}")
        if not job.artifacts:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No scan artifacts found")

        logger.info(f"Job artifacts: {job.artifacts}")

        # Build upload request from stored artifacts (dict of paths)
        # job.artifacts is a dict like: {"sarif": "path/to/file", "sbom": "path/to/file", ...}

        from certus_assurance.verification_models import (
            ArtifactInfo,
            InnerSignature,
            ScanMetadata,
            StorageDestinations,
            UploadRequest,
        )

        logger.info("Verification models imported successfully")

        artifact_list: list[ArtifactInfo] = []

        # Extract relevant artifact files from the stored artifact paths
        # job.artifacts is a dict like: {"sarif": "reports/sast/trivy.sarif.json", ...}
        # Use the runner's artifact root instead of hardcoded path
        artifacts_dir = runner.output_root / test_id
        logger.info(f"Artifacts directory: {artifacts_dir}")

        for key in ["sarif", "sbom", "dast_json"]:
            if key in job.artifacts:
                artifact_path_str = job.artifacts[key]
                artifact_file = artifacts_dir / artifact_path_str
                logger.info(f"Checking {key}: {artifact_file}, exists={artifact_file.exists()}")
                if artifact_file.exists():
                    try:
                        logger.info(f"Calculating hash for {artifact_file}")
                        file_hash = runner._calculate_artifact_hash(artifact_file)
                        file_size = artifact_file.stat().st_size
                        logger.info(f"Hash calculated: {file_hash}, size: {file_size}")
                        artifact_list.append(
                            ArtifactInfo(
                                name=artifact_file.name,
                                hash=f"sha256:{file_hash}",
                                size=file_size,
                            )
                        )
                        logger.info(f"Added {key} to artifact list")
                    except Exception as e:
                        logger.error(f"Failed to process artifact {artifact_file}: {e}", exc_info=True)
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to process artifact {artifact_file.name}: {e!s}",
                        )

        if not artifact_list:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="No valid artifacts to upload"
            )

        # Create inner signature (allow signer override for testing)
        signer = body.signer or "certus-assurance@certus.cloud"
        inner_sig = InnerSignature(
            signer=signer,
            timestamp=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            signature="mock-signature-" + test_id[:12],
            algorithm="SHA256-RSA",
            certificate=None,
        )

        # Build upload request
        upload_req = UploadRequest(
            scan_id=test_id,
            tier=body.tier,
            inner_signature=inner_sig,
            artifacts=artifact_list,
            metadata=ScanMetadata(
                git_url=job.git_url,
                branch=job.branch or "main",
                commit=job.commit or "HEAD",
                requested_by=job.requested_by,
            ),
            storage_destinations=StorageDestinations(raw_s3=True, oci_registry=True),
        )

        # Submit to Trust for verification
        logger.info(f"Submitting upload request to Trust for {test_id}")
        permission = runner._submit_upload_request(upload_req)
        logger.info(f"Received permission response: {permission}")

        upload_permission_id = permission.get("upload_permission_id")
        permitted = permission.get("permitted", False)

        verification_proof = permission.get("verification_proof")
        if verification_proof and isinstance(verification_proof, str):
            try:
                verification_proof = json.loads(verification_proof)
            except json.JSONDecodeError:
                logger.warning("verification_proof from Trust is a non-JSON string: %s", verification_proof)
        job.verification_proof = verification_proof

        # Determine upload status
        if permitted:
            upload_status = "permitted"

            # If permitted and S3 uploader is configured, upload artifacts directly
            if uploader and cfg.enable_s3_upload:
                try:
                    artifact_bundle = ArtifactBundle.discover(artifacts_dir)
                    if verification_proof:
                        proof_file = artifacts_dir / "verification-proof.json"
                        proof_file.write_text(json.dumps(verification_proof, indent=2))

                    result = PipelineResult(
                        test_id=test_id,
                        workspace_id=job.workspace_id,
                        component_id=job.component_id,
                        assessment_id=job.assessment_id,
                        status=job.status,
                        artifacts=artifact_bundle,
                        steps=[],
                        metadata=job.metadata,
                        upload_status="uploading",
                        upload_permission_id=upload_permission_id,
                    )

                    remote_artifacts = uploader.stage_and_promote(result, manifest_digest=job.manifest_digest)

                    # Update job metadata with S3 locations
                    job.metadata["remote_artifacts"] = remote_artifacts
                    upload_status = "uploaded"

                    logger.info(
                        "Uploaded scan bundle for %s",
                        extra={
                            "test_id": test_id,
                            "permission_id": upload_permission_id,
                            "raw_count": len(remote_artifacts.get("raw", {})),
                            "golden_count": len(remote_artifacts.get("golden", {})),
                        },
                    )
                except Exception as upload_error:
                    logger.error(
                        f"Failed to upload artifacts to S3: {upload_error}",
                        extra={
                            "test_id": test_id,
                            "permission_id": upload_permission_id,
                            "error": str(upload_error),
                        },
                    )
                    upload_status = "upload_failed"
                    # Don't raise - permission was granted, just upload failed
            else:
                logger.warning(
                    f"Upload permitted but S3 uploader not configured for test {test_id}",
                    extra={"test_id": test_id, "permission_id": upload_permission_id},
                )
        else:
            upload_status = "denied"
            logger.info(
                f"Upload denied for test {test_id}: {permission.get('reason')}",
                extra={
                    "test_id": test_id,
                    "permission_id": upload_permission_id,
                    "reason": permission.get("reason"),
                },
            )

        # Update the job with upload status and permission ID
        job.upload_status = upload_status
        job.upload_permission_id = upload_permission_id

        return UploadRequestResponse(
            upload_permission_id=upload_permission_id,
            upload_status=upload_status,
        )
    except Exception as e:
        logger.error(f"Upload request failed: {e}", extra={"test_id": test_id, "error": str(e)}, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload request failed: {e!s}",
        )


def _serialize_job(job: ScanJob) -> ScanStatusResponse:
    def to_dt(ts: float | None) -> datetime | None:
        return datetime.utcfromtimestamp(ts) if ts else None

    return ScanStatusResponse(
        test_id=job.test_id,
        workspace_id=job.workspace_id,
        component_id=job.component_id,
        assessment_id=job.assessment_id,
        status=job.status,
        git_url=job.git_url,
        branch=job.branch,
        commit=job.commit,
        requested_by=job.requested_by,
        profile=job.profile,
        started_at=to_dt(job.started_at),
        completed_at=to_dt(job.completed_at),
        artifacts=job.artifacts,
        warnings=job.warnings,
        errors=job.errors,
        remote_artifacts=job.metadata.get("remote_artifacts"),
        registry=job.metadata.get("registry"),
        upload_status=job.upload_status,
        upload_permission_id=job.upload_permission_id,
        verification_proof=job.verification_proof,
        manifest_digest=job.manifest_digest,
        manifest_metadata=job.metadata.get("manifest_metadata"),
        stream_url=f"/v1/security-scans/{job.test_id}/stream",
    )


def _rewrite_metadata_file(result: PipelineResult) -> None:
    result.artifacts.metadata.write_text(json.dumps(result.metadata, indent=2), encoding="utf-8")
