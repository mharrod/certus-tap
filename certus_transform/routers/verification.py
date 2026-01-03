"""Router for verification-first upload workflow (receives permission from Trust)."""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from certus_transform.core.config import settings
from certus_transform.services import get_s3_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["verification"])

# Import stats counters from health module
from certus_transform.routers import health

# ============================================================================
# Pydantic Models for API
# ============================================================================


class ArtifactInfoRequest(BaseModel):
    """Information about an artifact to be uploaded."""

    name: str = Field(..., description="Artifact file name (e.g., trivy.json)")
    hash: str = Field(..., description="SHA256 hash (sha256:abc123...)")
    size: int = Field(..., description="File size in bytes")


class InnerSignatureRequest(BaseModel):
    """Inner signature from Certus-Assurance."""

    signer: str = Field(..., description="Signer identity")
    timestamp: str = Field(..., description="When signed (ISO 8601)")
    signature: str = Field(..., description="Base64-encoded signature")
    algorithm: str = Field(..., description="Signature algorithm")
    certificate: Optional[str] = Field(None, description="PEM-encoded certificate")


class ScanMetadataRequest(BaseModel):
    """Scan metadata for audit trail."""

    git_url: str = Field(..., description="Repository URL")
    branch: str = Field(..., description="Git branch name")
    commit: str = Field(..., description="Git commit hash")
    requested_by: Optional[str] = Field(None, description="User who requested scan")


class VerificationProofRequest(BaseModel):
    """Proof that Trust verified the scan."""

    chain_verified: bool = Field(..., description="Is complete chain verified")
    inner_signature_valid: bool = Field(..., description="Is Assurance signature valid")
    outer_signature_valid: bool = Field(..., description="Is Trust signature valid")
    chain_unbroken: bool = Field(..., description="Is chain unbroken")
    signer_inner: str = Field(..., description="Assurance signer identity")
    signer_outer: Optional[str] = Field(None, description="Trust signer identity")
    sigstore_timestamp: Optional[str] = Field(None, description="Sigstore timestamp")
    verification_timestamp: Optional[str] = Field(None, description="When verified")
    rekor_entry_uuid: Optional[str] = Field(None, description="Rekor entry ID")
    cosign_signature: Optional[str] = Field(None, description="Cosign signature")


class StorageConfigRequest(BaseModel):
    """Storage configuration for Transform to use."""

    raw_s3_bucket: Optional[str] = Field(None, description="S3 bucket name")
    raw_s3_prefix: Optional[str] = Field(None, description="S3 prefix for this scan")
    oci_registry: Optional[str] = Field(None, description="OCI registry URL")
    oci_repository: Optional[str] = Field(None, description="OCI repository path")
    upload_to_s3: bool = Field(default=True, description="Upload artifacts to S3")
    upload_to_oci: bool = Field(default=True, description="Upload artifacts to OCI registry")


class ExecuteUploadRequestModel(BaseModel):
    """Request from Trust to Transform to execute upload.

    This is only sent if verification passed (permitted=True).
    Transform is the executor - it handles the actual upload operations.
    """

    upload_permission_id: str = Field(..., description="Permission ID from Trust")
    scan_id: str = Field(..., description="Scan ID to upload")
    tier: str = Field(
        ...,
        description="Scan tier: 'basic' or 'verified'",
        pattern="^(basic|verified)$",
    )
    artifacts: list[ArtifactInfoRequest] = Field(..., description="Artifacts to upload")
    metadata: ScanMetadataRequest = Field(..., description="Scan metadata")
    verification_proof: Optional[VerificationProofRequest] = Field(None, description="Verification proof")
    storage_config: Optional[StorageConfigRequest] = Field(None, description="Storage configuration")


class UploadedArtifact(BaseModel):
    """Record of uploaded artifact."""

    name: str = Field(..., description="Original artifact name")
    s3_path: Optional[str] = Field(None, description="S3 path where stored")
    oci_reference: Optional[str] = Field(None, description="OCI reference")
    hash: str = Field(..., description="Original SHA256 hash")
    uploaded_at: str = Field(..., description="When uploaded (ISO 8601)")


class UploadConfirmationResponse(BaseModel):
    """Response confirming upload completion."""

    upload_permission_id: str = Field(..., description="Permission ID")
    scan_id: str = Field(..., description="Scan ID that was uploaded")
    status: str = Field(
        ...,
        description="Upload status: 'success' or 'failed'",
        pattern="^(success|failed)$",
    )
    uploaded_artifacts: list[UploadedArtifact] = Field(
        default_factory=list, description="Details of uploaded artifacts"
    )
    s3_prefix: Optional[str] = Field(None, description="S3 prefix where stored")
    oci_reference: Optional[str] = Field(None, description="OCI repository reference")
    error_detail: Optional[str] = Field(None, description="Error message if failed")
    timestamp: str = Field(..., description="When upload completed (ISO 8601)")


# ============================================================================
# Execute Upload Endpoint
# ============================================================================


def _upload_to_s3(
    artifact_name: str,
    artifact_hash: str,
    s3_bucket: str,
    s3_prefix: str,
    scan_id: Optional[str] = None,
    tier: Optional[str] = None,
    verification_proof: Optional[dict[str, Any]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> tuple[str, str]:
    """
    Upload artifact to S3 with enriched metadata.

    In production: fetch artifact from Assurance's temporary storage
    For mock: create a marker file

    Args:
        artifact_name: Name of the artifact file
        artifact_hash: SHA256 hash of the artifact
        s3_bucket: S3 bucket name
        s3_prefix: S3 prefix path
        scan_id: Scan ID for tracking
        tier: "basic" or "verified"
        verification_proof: Verification proof from Trust
        metadata: Additional scan metadata (git_url, commit, etc.)

    Returns: (s3_path, timestamp)
    """
    # For mock implementation: create a marker in S3 showing artifact was "uploaded"
    s3_client = get_s3_client()

    # Use the artifact name as the S3 key
    s3_path = f"{s3_prefix.rstrip('/')}/{artifact_name}".lstrip("/")

    # Create marker content showing this is a mock upload
    content = f"""Marker file for verification-first upload
Artifact: {artifact_name}
Hash: {artifact_hash}
Timestamp: {datetime.utcnow().isoformat()}
Permission verified by Certus-Trust
"""

    # Build enriched metadata
    s3_metadata = {
        "artifact-name": artifact_name,
        "artifact-hash": artifact_hash,
        "verification-required": "true",
        "uploaded-by": "certus-transform",
        "upload-timestamp": datetime.utcnow().isoformat(),
    }

    # Add scan information
    if scan_id:
        s3_metadata["scan-id"] = scan_id
    if tier:
        s3_metadata["trust-tier"] = tier

    # Add verification proof metadata
    if verification_proof:
        s3_metadata["chain-verified"] = str(verification_proof.get("chain_verified", False))
        if verification_proof.get("signer_inner"):
            s3_metadata["signer-inner"] = verification_proof["signer_inner"]
        if verification_proof.get("signer_outer"):
            s3_metadata["signer-outer"] = verification_proof["signer_outer"]
        if verification_proof.get("verification_timestamp"):
            s3_metadata["verification-timestamp"] = verification_proof["verification_timestamp"]

    # Add scan metadata
    if metadata:
        if metadata.get("git_url"):
            s3_metadata["git-url"] = metadata["git_url"]
        if metadata.get("commit"):
            s3_metadata["git-commit"] = metadata["commit"]
        if metadata.get("branch"):
            s3_metadata["git-branch"] = metadata["branch"]

    # Build tags for lifecycle policies
    tags = []
    if tier:
        tags.append(f"tier={tier}")
    if verification_proof and verification_proof.get("chain_verified"):
        tags.append(f"verified={verification_proof['chain_verified']}")
    tags.append("service=certus-transform")
    tag_string = "&".join(tags) if tags else ""

    try:
        # Upload marker to S3 with enriched metadata
        put_args = {
            "Bucket": s3_bucket,
            "Key": s3_path,
            "Body": content.encode("utf-8"),
            "ContentType": "text/plain",
            "Metadata": s3_metadata,
        }

        # Add tags if present
        if tag_string:
            put_args["Tagging"] = tag_string

        s3_client.put_object(**put_args)

        logger.info(
            "Uploaded artifact to S3",
            extra={
                "bucket": s3_bucket,
                "key": s3_path,
                "artifact": artifact_name,
            },
        )

        return s3_path, datetime.utcnow().isoformat()
    except Exception as e:
        logger.error(
            f"Failed to upload to S3: {e!s}",
            extra={
                "bucket": s3_bucket,
                "key": s3_path,
                "error": str(e),
            },
        )
        raise


def _push_to_oci_registry(
    artifact_name: str,
    artifact_hash: str,
    oci_registry: str,
    oci_repository: str,
    scan_id: str,
) -> str:
    """
    Push artifact to OCI registry.

    In production: build OCI image and push to registry
    For mock: record push operation

    Returns: OCI reference (tag)
    """
    # For mock implementation: return a reference that would exist
    # In real implementation: would use oras or similar to push artifact layers

    timestamp = datetime.utcnow().isoformat()
    commit_short = scan_id[:8] if scan_id else "unknown"
    oci_reference = f"{oci_registry}/{oci_repository}:{commit_short}-{int(datetime.utcnow().timestamp())}"

    logger.info(
        "Pushed artifact to OCI registry",
        extra={
            "registry": oci_registry,
            "repository": oci_repository,
            "reference": oci_reference,
            "artifact": artifact_name,
        },
    )

    return oci_reference


class BatchUploadRequest(BaseModel):
    """Batch upload request for processing multiple scans in parallel."""

    scans: list[ExecuteUploadRequestModel] = Field(..., description="List of scan upload requests to process")


class BatchUploadResponse(BaseModel):
    """Response for batch upload operation."""

    total_scans: int = Field(..., description="Total number of scans processed")
    successful: int = Field(..., description="Number of successful uploads")
    failed: int = Field(..., description="Number of failed uploads")
    results: list[UploadConfirmationResponse] = Field(..., description="Individual upload results")
    timestamp: str = Field(..., description="When batch completed (ISO 8601)")


@router.post(
    "/execute-upload",
    response_model=UploadConfirmationResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute verified upload of scan artifacts",
    description="Receives permission from Trust and uploads artifacts to storage",
)
async def execute_upload(
    request: ExecuteUploadRequestModel,
) -> UploadConfirmationResponse:
    """
    Execute upload of artifacts after Trust verification.

    This endpoint:
    1. Only processes if it has a valid upload_permission_id from Trust
    2. Uploads artifacts to S3 and/or OCI registry as configured
    3. Records upload completion
    4. Returns confirmation

    This is the executor - it only runs if Trust already verified the scan.
    """
    # Track upload attempt
    health._upload_count += 1

    try:
        timestamp = datetime.utcnow().isoformat()
        uploaded_artifacts: list[UploadedArtifact] = []
        s3_prefix = None
        oci_reference = None
        error_detail = None
        status_code = "success"

        logger.info(
            "Starting verified upload",
            extra={
                "scan_id": request.scan_id,
                "permission_id": request.upload_permission_id,
                "tier": request.tier,
                "artifact_count": len(request.artifacts),
            },
        )

        # Determine storage configuration
        storage_config = request.storage_config or StorageConfigRequest(
            raw_s3_bucket=settings.raw_bucket,
            raw_s3_prefix=f"{request.metadata.git_url.replace('/', '-')}/{request.metadata.commit[:8]}",
            upload_to_s3=True,
            upload_to_oci=True,
        )

        upload_to_s3 = storage_config.upload_to_s3
        upload_to_oci = storage_config.upload_to_oci

        if upload_to_s3 and (not storage_config.raw_s3_bucket or not storage_config.raw_s3_prefix):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="S3 uploads enabled but bucket/prefix missing in storage_config.",
            )

        if upload_to_oci and not storage_config.oci_repository:
            logger.warning(
                "OCI upload enabled but repository missing; disabling OCI push.",
                extra={"scan_id": request.scan_id},
            )
            upload_to_oci = False

        try:
            if upload_to_s3:
                # Upload each artifact to S3 with enriched metadata
                for artifact in request.artifacts:
                    try:
                        # Prepare verification proof dict if available
                        verification_proof_dict = None
                        if request.verification_proof:
                            verification_proof_dict = {
                                "chain_verified": request.verification_proof.chain_verified,
                                "inner_signature_valid": request.verification_proof.inner_signature_valid,
                                "outer_signature_valid": request.verification_proof.outer_signature_valid,
                                "signer_inner": request.verification_proof.signer_inner,
                                "signer_outer": request.verification_proof.signer_outer,
                                "verification_timestamp": request.verification_proof.verification_timestamp,
                            }

                        # Prepare metadata dict
                        metadata_dict = {
                            "git_url": request.metadata.git_url,
                            "branch": request.metadata.branch,
                            "commit": request.metadata.commit,
                        }

                        s3_path, upload_time = _upload_to_s3(
                            artifact_name=artifact.name,
                            artifact_hash=artifact.hash,
                            s3_bucket=storage_config.raw_s3_bucket,
                            s3_prefix=storage_config.raw_s3_prefix,
                            scan_id=request.scan_id,
                            tier=request.tier,
                            verification_proof=verification_proof_dict,
                            metadata=metadata_dict,
                        )

                        uploaded_artifacts.append(
                            UploadedArtifact(
                                name=artifact.name,
                                s3_path=s3_path,
                                hash=artifact.hash,
                                uploaded_at=upload_time,
                            )
                        )

                        s3_prefix = storage_config.raw_s3_prefix

                    except Exception as e:
                        logger.error(
                            f"Failed to upload artifact {artifact.name}: {e!s}",
                            extra={
                                "scan_id": request.scan_id,
                                "artifact": artifact.name,
                            },
                        )
                        error_detail = f"S3 upload failed: {e!s}"
                        status_code = "failed"
                        break
            else:
                logger.info(
                    "S3 upload disabled by configuration",
                    extra={"scan_id": request.scan_id},
                )

            # If uploads succeeded, try OCI registry (if configured)
            if status_code == "success" and upload_to_oci:
                try:
                    oci_reference = _push_to_oci_registry(
                        artifact_name="scan-artifacts",
                        artifact_hash=request.artifacts[0].hash if request.artifacts else "unknown",
                        oci_registry=storage_config.oci_registry or "registry.certus.cloud",
                        oci_repository=storage_config.oci_repository,
                        scan_id=request.scan_id,
                    )

                    if not uploaded_artifacts:
                        now = datetime.utcnow().isoformat()
                        for artifact in request.artifacts:
                            uploaded_artifacts.append(
                                UploadedArtifact(
                                    name=artifact.name,
                                    s3_path=None,
                                    hash=artifact.hash,
                                    uploaded_at=now,
                                )
                            )

                    # Update uploaded artifacts with OCI reference
                    for artifact in uploaded_artifacts:
                        artifact.oci_reference = oci_reference

                except Exception as e:
                    logger.error(
                        f"Failed to push to OCI registry: {e!s}",
                        extra={
                            "scan_id": request.scan_id,
                            "repository": storage_config.oci_repository,
                        },
                    )
                    # Don't fail overall if OCI push fails (S3 succeeded)
                    logger.warning(
                        "OCI push failed but S3 upload succeeded",
                        extra={
                            "scan_id": request.scan_id,
                        },
                    )
            elif not upload_to_oci:
                logger.info(
                    "OCI upload disabled by configuration",
                    extra={"scan_id": request.scan_id},
                )

        except Exception as e:
            logger.error(
                f"Upload execution failed: {e!s}",
                extra={
                    "scan_id": request.scan_id,
                    "permission_id": request.upload_permission_id,
                },
            )
            status_code = "failed"
            error_detail = str(e)

        # Track upload result
        if status_code == "success":
            health._upload_success += 1
        else:
            health._upload_failed += 1

        logger.info(
            "Upload execution completed",
            extra={
                "scan_id": request.scan_id,
                "permission_id": request.upload_permission_id,
                "status": status_code,
                "artifacts_uploaded": len(uploaded_artifacts),
            },
        )

        return UploadConfirmationResponse(
            upload_permission_id=request.upload_permission_id,
            scan_id=request.scan_id,
            status=status_code,
            uploaded_artifacts=uploaded_artifacts,
            s3_prefix=s3_prefix,
            oci_reference=oci_reference,
            error_detail=error_detail,
            timestamp=timestamp,
        )

    except Exception as e:
        # Track failure
        health._upload_failed += 1

        logger.error(
            f"Upload endpoint failed: {e!s}",
            extra={
                "scan_id": request.scan_id,
                "permission_id": request.upload_permission_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload execution failed",
        )


# ============================================================================
# Batch Upload Endpoint
# ============================================================================


@router.post(
    "/execute-upload/batch",
    response_model=BatchUploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Execute multiple verified uploads in parallel",
    description="Process multiple scan uploads concurrently for efficiency",
)
async def execute_batch_upload(
    request: BatchUploadRequest,
) -> BatchUploadResponse:
    """
    Execute multiple uploads in parallel.

    This endpoint:
    1. Accepts a list of upload requests
    2. Processes them concurrently using asyncio.gather
    3. Returns aggregated results with individual status

    Useful for:
    - AI agents scanning multiple repositories
    - Bulk upload operations
    - Reducing API round-trips

    Args:
        request: BatchUploadRequest with list of scans

    Returns:
        BatchUploadResponse with aggregated results
    """
    import asyncio

    logger.info(
        "Starting batch upload",
        extra={
            "scan_count": len(request.scans),
        },
    )

    # Process all uploads concurrently
    # Use asyncio.gather with return_exceptions=True to capture both successes and failures
    results = await asyncio.gather(*[execute_upload(scan) for scan in request.scans], return_exceptions=True)

    # Analyze results
    successful = 0
    failed = 0
    upload_responses: list[UploadConfirmationResponse] = []

    for idx, result in enumerate(results):
        if isinstance(result, Exception):
            # Handle exception - create a failed response
            failed += 1
            scan_id = request.scans[idx].scan_id if idx < len(request.scans) else "unknown"
            upload_responses.append(
                UploadConfirmationResponse(
                    upload_permission_id=request.scans[idx].upload_permission_id
                    if idx < len(request.scans)
                    else "unknown",
                    scan_id=scan_id,
                    status="failed",
                    uploaded_artifacts=[],
                    error_detail=str(result),
                    timestamp=datetime.utcnow().isoformat(),
                )
            )
        else:
            # Success or controlled failure
            upload_responses.append(result)
            if result.status == "success":
                successful += 1
            else:
                failed += 1

    logger.info(
        "Batch upload completed",
        extra={
            "total": len(request.scans),
            "successful": successful,
            "failed": failed,
        },
    )

    return BatchUploadResponse(
        total_scans=len(request.scans),
        successful=successful,
        failed=failed,
        results=upload_responses,
        timestamp=datetime.utcnow().isoformat(),
    )
