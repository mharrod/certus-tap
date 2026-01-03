"""API router for Certus-Trust service."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Request, status

from ..config import get_settings
from .models import (
    ArtifactLocationVerification,
    ExecuteUploadRequestModel,
    HealthStatus,
    NonRepudiationGuarantee,
    OuterSignature,
    ProvenanceChain,
    ReadinessStatus,
    ServiceStats,
    SignArtifactRequest,
    SignArtifactResponse,
    SignRequest,
    SignResponse,
    TransparencyEntry,
    TransparencyLogEntry,
    UploadPermissionModel,
    UploadRequestModel,
    VerificationProof,
    VerificationProofModel,
    VerifyChainRequest,
    VerifyChainResponse,
    VerifyRequest,
    VerifyResponse,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter()

# In-memory storage for demo (replace with database in production)
_signed_artifacts: dict[str, Any] = {}
_transparency_log: list[TransparencyLogEntry] = []
_component_status: dict[str, bool] = {
    "fulcio": True,
    "rekor": True,
    "tuf": True,
    "keycloak": True,
}
_verification_count: int = 0
_verification_success: int = 0
_verification_failed: int = 0

# Mock scenarios for realistic testing
MOCK_SCENARIOS = {
    "verified_premium_scan": {
        "inner_signature_valid": True,
        "outer_signature_valid": True,
        "trust_level": "high",
        "chain_status": "complete",
        "tier": "verified",
    },
    "unverified_basic_scan": {
        "inner_signature_valid": True,
        "outer_signature_valid": False,
        "trust_level": "low",
        "chain_status": "partial",
        "tier": "basic",
    },
    "tampered_scan": {
        "inner_signature_valid": False,
        "outer_signature_valid": False,
        "trust_level": "none",
        "chain_status": "broken",
        "tier": "basic",
    },
    "expired_certificate": {
        "inner_signature_valid": False,
        "outer_signature_valid": False,
        "reason": "certificate_expired",
        "trust_level": "untrusted",
        "chain_status": "broken",
        "tier": "verified",
    },
    "invalid_signer": {
        "inner_signature_valid": False,
        "outer_signature_valid": False,
        "reason": "invalid_signer",
        "trust_level": "untrusted",
        "chain_status": "broken",
        "tier": "verified",
    },
}


# ============================================================================
# Phase 1: Core Signing Endpoint
# ============================================================================


@router.post(
    "/v1/sign",
    response_model=SignResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sign an artifact",
    description="Sign an artifact using Fulcio/keyless signing and record in Rekor",
)
async def sign_artifact(request: SignRequest) -> SignResponse:
    """
    Sign an artifact with keyless signing via Fulcio.

    The signature is recorded in the Rekor transparency log for verification.

    Phase 1 implementation: Returns mock response with realistic structure.
    Future phases will integrate with real Fulcio/Rekor.
    """
    try:
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        # Mock signing response
        response = SignResponse(
            entry_id=entry_id,
            signature=f"mock-signature-{entry_id[:8]}",
            certificate=f"mock-certificate-{entry_id[:8]}",
            transparency_entry=TransparencyEntry(
                uuid=entry_id,
                index=len(_transparency_log),
                timestamp=timestamp,
            ),
        )

        # Store in memory
        _signed_artifacts[entry_id] = {
            "request": request.model_dump(),
            "response": response.model_dump(),
            "timestamp": timestamp,
        }

        # Add to transparency log
        log_entry = TransparencyLogEntry(
            entry_id=entry_id,
            artifact=request.artifact,
            timestamp=timestamp,
            signer="certus-trust@certus.cloud",
            signature=response.signature,
        )
        _transparency_log.append(log_entry)

        logger.info(
            f"Signed artifact {request.artifact_type}: {entry_id}",
            extra={
                "event_type": "artifact_signed",
                "artifact_type": request.artifact_type,
                "entry_id": entry_id,
            },
        )

        return response

    except Exception as e:
        logger.error(f"Signing failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Signing failed",
        )


# ============================================================================
# Phase 2: Verification Endpoint
# ============================================================================


@router.post(
    "/v1/verify",
    response_model=VerifyResponse,
    summary="Verify a signature",
    description="Verify that a signature is valid using Rekor",
)
async def verify_signature(
    request: VerifyRequest,
    simulate_failure: bool = False,
    scenario: Optional[str] = None,
) -> VerifyResponse:
    """
    Verify a signature by checking against the transparency log.

    Phase 1 implementation: Mocks verification using in-memory storage.
    Future phases will integrate with real Rekor.

    Args:
        request: Verification request
        simulate_failure: If True, simulate a verification failure
        scenario: Optional scenario name from MOCK_SCENARIOS to simulate
    """
    global _verification_count, _verification_success, _verification_failed

    try:
        _verification_count += 1
        timestamp = datetime.now(timezone.utc)

        # If simulating failure, return failed verification
        if simulate_failure:
            _verification_failed += 1
            response = VerifyResponse(
                valid=False,
                verified_at=timestamp,
                signer="unknown",
                transparency_index=None,
                certificate_chain=None,
            )

            logger.warning(
                "Simulated verification failure",
                extra={
                    "event_type": "verification_simulated_failure",
                    "artifact": request.artifact,
                },
            )
            return response

        # If scenario specified, use it
        if scenario and scenario in MOCK_SCENARIOS:
            scenario_config = MOCK_SCENARIOS[scenario]
            valid = scenario_config["inner_signature_valid"]

            if valid:
                _verification_success += 1
            else:
                _verification_failed += 1

            response = VerifyResponse(
                valid=valid,
                verified_at=timestamp,
                signer="certus-assurance@certus.cloud" if valid else "unknown",
                transparency_index=0 if valid else None,
                certificate_chain=None,
            )

            logger.info(
                f"Verification with scenario {scenario}: {valid}",
                extra={
                    "event_type": "verification_scenario",
                    "scenario": scenario,
                    "valid": valid,
                },
            )
            return response

        # Mock verification - in real implementation, would check Rekor
        valid = True
        signer = "certus-assurance@certus.cloud"
        transparency_index = 0

        # Check if we have this signature in our log
        for idx, entry in enumerate(_transparency_log):
            if entry.signature == request.signature and entry.artifact == request.artifact:
                valid = True
                signer = entry.signer
                transparency_index = idx
                break

        # If identity was specified, verify it matches
        if request.identity and request.identity != signer:
            valid = False

        if valid:
            _verification_success += 1
        else:
            _verification_failed += 1

        response = VerifyResponse(
            valid=valid,
            verified_at=timestamp,
            signer=signer,
            transparency_index=transparency_index if valid else None,
            certificate_chain=None,
        )

        logger.info(
            f"Verified signature: {valid}",
            extra={
                "event_type": "verification_requested",
                "valid": valid,
                "signer": signer,
            },
        )

        return response

    except Exception as e:
        _verification_failed += 1
        logger.error(f"Verification failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Verification failed",
        )


# ============================================================================
# Phase 3: Transparency Log Query Endpoint
# ============================================================================


def _build_merkle_proof(entry_index: int) -> dict:
    """Build a mock Merkle proof for an entry.

    In a real implementation, this would generate actual Merkle tree proofs
    from the transparency log. For mock purposes, we generate realistic-looking
    proof hashes.
    """
    import hashlib

    tree_size = len(_transparency_log)
    proof_hashes = []

    # Generate mock proof hashes based on tree structure
    # In reality, these would be actual hashes from the Merkle tree
    current_index = entry_index
    level = 0
    while current_index < tree_size - 1:
        sibling_index = current_index ^ 1  # XOR to get sibling
        mock_data = f"node-{sibling_index}-level-{level}".encode()
        proof_hash = hashlib.sha256(mock_data).hexdigest()
        proof_hashes.append(f"sha256:{proof_hash}")
        current_index = current_index // 2
        level += 1

    return {
        "tree_size": tree_size,
        "leaf_index": entry_index,
        "hashes": proof_hashes,
        "root_hash": f"sha256:{hashlib.sha256(f'root-{tree_size}'.encode()).hexdigest()}",
    }


@router.get(
    "/v1/transparency/{entry_id}",
    response_model=TransparencyLogEntry,
    summary="Get transparency log entry",
    description="Query a specific entry from the Rekor transparency log",
)
async def get_transparency_entry(
    entry_id: str,
    include_proof: bool = True,
) -> TransparencyLogEntry:
    """
    Retrieve a specific transparency log entry by ID.

    Phase 1 implementation: Returns from in-memory storage with mock Merkle proof.
    Future phases will query real Rekor.

    Args:
        entry_id: Transparency log entry ID
        include_proof: Whether to include Merkle proof (default: True)
    """
    try:
        # Search for entry in log
        for idx, entry in enumerate(_transparency_log):
            if entry.entry_id == entry_id:
                # Add Merkle proof if requested
                if include_proof:
                    entry.proof = _build_merkle_proof(idx)

                logger.info(
                    f"Retrieved transparency entry: {entry_id}",
                    extra={
                        "event_type": "transparency_query",
                        "entry_id": entry_id,
                        "include_proof": include_proof,
                    },
                )
                return entry

        # Entry not found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entry {entry_id} not found in transparency log",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Transparency query failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transparency query failed",
        )


@router.get(
    "/v1/transparency",
    response_model=list[TransparencyLogEntry],
    summary="Query transparency log",
    description="Query transparency log entries with optional filters",
)
async def query_transparency_log(
    assessment_id: Optional[str] = None,
    signer: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
) -> list[TransparencyLogEntry]:
    """
    Query the transparency log with optional filtering.

    Phase 1 implementation: Searches in-memory storage.
    Future phases will query real Rekor.
    """
    try:
        results = _transparency_log

        # Apply filters
        if assessment_id:
            results = [e for e in results if hasattr(e, "assessment_id") and e.assessment_id == assessment_id]

        if signer:
            results = [e for e in results if e.signer == signer]

        # Apply pagination
        results = results[offset : offset + limit]

        logger.info(
            "Queried transparency log",
            extra={
                "event_type": "transparency_query",
                "filters": {"assessment_id": assessment_id, "signer": signer},
                "results_count": len(results),
            },
        )

        return results

    except Exception as e:
        logger.error(f"Transparency query failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Transparency query failed",
        )


# ============================================================================
# Non-Repudiation Endpoints (Future - Phase 4-5)
# ============================================================================


@router.post(
    "/v1/sign-artifact",
    response_model=SignArtifactResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Sign assessment artifact with dual signatures",
    description="Create outer signature for assessment (non-repudiation)",
)
async def sign_artifact_dual(request: SignArtifactRequest) -> SignArtifactResponse:
    """
    Sign an assessment artifact with dual signatures.

    This endpoint:
    1. Verifies inner signatures from Certus-Assurance
    2. Creates outer signature from Certus-Trust
    3. Records in Sigstore/Rekor for timestamp authority
    4. Returns verification proof

    Phase 1 implementation: Mocked responses with realistic structure.
    Future phases will implement real verification.
    """
    try:
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        # Mock verification of inner signatures
        inner_sigs_verified = all(f.verified for f in request.inner_signatures.files)

        # Mock artifact location validation
        artifact_locations_valid = all(loc.uri for loc in request.artifact_locations.values())

        # Create outer signature response
        outer_signature = OuterSignature(
            signer="certus-trust@certus.cloud",
            timestamp=timestamp,
            signature=f"mock-outer-sig-{entry_id[:8]}",
            sigstore_entry_id=f"rekor-entry-{entry_id[:8]}",
            transparency_log_url=f"https://rekor.sigstore.dev/api/v1/log/entries/{entry_id}",
        )

        # Create verification proof
        verification_proof = VerificationProof(
            inner_signatures_verified=inner_sigs_verified,
            artifact_locations_valid=artifact_locations_valid,
            chain_of_custody="complete" if (inner_sigs_verified and artifact_locations_valid) else "broken",
            both_locations_identical=True,  # Mock: assume identical
        )

        response = SignArtifactResponse(
            status="signed",
            assessment_id=request.assessment_metadata.assessment_id,
            outer_signature=outer_signature,
            verification_proof=verification_proof,
        )

        # Store in memory
        _signed_artifacts[entry_id] = {
            "request": request.model_dump(),
            "response": response.model_dump(),
            "timestamp": timestamp,
        }

        # Add to transparency log
        log_entry = TransparencyLogEntry(
            entry_id=entry_id,
            artifact=None,  # Assessment, not single artifact
            timestamp=timestamp,
            signer="certus-trust@certus.cloud",
            signature=outer_signature.signature,
        )
        _transparency_log.append(log_entry)

        logger.info(
            f"Signed assessment artifact: {request.assessment_metadata.assessment_id}",
            extra={
                "event_type": "artifact_signed",
                "assessment_id": request.assessment_metadata.assessment_id,
                "entry_id": entry_id,
                "inner_signatures_verified": inner_sigs_verified,
            },
        )

        return response

    except Exception as e:
        logger.error(f"Artifact signing failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Artifact signing failed",
        )


@router.post(
    "/v1/verify-chain",
    response_model=VerifyChainResponse,
    summary="Verify non-repudiation chain",
    description="Verify complete inner + outer signature chain",
)
async def verify_chain(request: VerifyChainRequest) -> VerifyChainResponse:
    """
    Verify the complete non-repudiation chain.

    This endpoint verifies:
    1. Inner signatures from Certus-Assurance
    2. Outer signatures from Certus-Trust
    3. Artifact location consistency
    4. Sigstore timestamp authority

    Phase 1 implementation: Mocked verification.
    Future phases will implement real verification.
    """
    try:
        timestamp = datetime.now(timezone.utc)

        # Mock verification
        inner_valid = True
        outer_valid = True
        chain_unbroken = inner_valid and outer_valid

        response = VerifyChainResponse(
            chain_verified=chain_unbroken,
            inner_signature_valid=inner_valid,
            outer_signature_valid=outer_valid,
            chain_unbroken=chain_unbroken,
            signer_inner="certus-assurance@certus.cloud",
            signer_outer="certus-trust@certus.cloud",
            sigstore_timestamp=timestamp,
            artifact_locations=ArtifactLocationVerification(
                s3_valid=True,
                registry_valid=True,
                digests_match=True,
                content_identical=True,
            ),
            non_repudiation=NonRepudiationGuarantee(
                assurance_accountable=inner_valid,
                trust_verified=outer_valid,
                timestamp_authority="sigstore",
                provenance_chain="complete" if chain_unbroken else "broken",
            ),
        )

        logger.info(
            f"Verified chain: {chain_unbroken}",
            extra={
                "event_type": "chain_verified",
                "chain_valid": chain_unbroken,
            },
        )

        return response

    except Exception as e:
        logger.error(f"Chain verification failed: {e!s}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Chain verification failed",
        )


# ============================================================================
# Verification-First Upload Workflow: Gatekeeper Endpoint
# ============================================================================


async def _call_transform_execute_upload(
    execute_request: ExecuteUploadRequestModel,
    transform_base_url: str = "http://certus-transform:8100",
) -> dict[str, Any]:
    """Call Transform service to execute upload after verification.

    This is the async callback - Trust calls Transform directly if verification passes.
    """
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{transform_base_url}/v1/execute-upload",
                json=_dataclass_to_dict(execute_request),
            )
            response.raise_for_status()
            return response.json()
    except httpx.HTTPError as e:
        logger.error(
            f"Failed to call Transform execute-upload: {e!s}",
            extra={
                "event_type": "transform_call_failed",
                "scan_id": execute_request.scan_id,
                "permission_id": execute_request.upload_permission_id,
            },
        )
        # Don't raise - Transform being down shouldn't block permission
        # Return mock response for development
        return {
            "status": "pending",
            "message": "Transform service unavailable, upload queued for retry",
        }


def _dataclass_to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass or Pydantic model to dict for serialization."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(exclude_none=True)
    elif hasattr(obj, "__dataclass_fields__"):
        return {k: _dataclass_to_dict(v) if hasattr(v, "__dataclass_fields__") else v for k, v in obj.__dict__.items()}
    else:
        return obj


@router.post(
    "/v1/verify-and-permit-upload",
    response_model=UploadPermissionModel,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Verify upload request and permit if valid",
    description="Gatekeeper endpoint for verification-first workflow",
)
async def verify_and_permit_upload(
    request: UploadRequestModel,
    http_request: Request,
) -> UploadPermissionModel:
    """
    Verify an upload request from Certus-Assurance and decide whether to permit.

    This is the gatekeeper endpoint - if verification passes, this endpoint:
    1. Creates an UploadPermission with permitted=True
    2. Calls Transform's /v1/execute-upload endpoint asynchronously
    3. Returns immediately (async callback model)

    If verification fails, this endpoint:
    1. Creates an UploadPermission with permitted=False
    2. Does NOT call Transform
    3. Returns the rejection reason

    This prevents unverified artifacts from ever reaching storage.
    """
    try:
        permission_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)

        # Verify the inner signature from Assurance
        # For now: basic tier always passes, verified tier requires valid signature
        inner_signature_valid = True
        reason = None
        detail = None

        if request.tier == "verified":
            # In real implementation: verify signature with Assurance's public key
            # For mock: assume valid if signer is correct
            if request.inner_signature.signer != "certus-assurance@certus.cloud":
                inner_signature_valid = False
                reason = "invalid_signer"
                detail = f"Expected certus-assurance@certus.cloud, got {request.inner_signature.signer}"

        # Check artifact integrity
        artifacts_valid = len(request.artifacts) > 0
        if not artifacts_valid:
            inner_signature_valid = False
            reason = "no_artifacts"
            detail = "Upload request contains no artifacts"

        # Make permission decision
        permitted = inner_signature_valid and artifacts_valid
        chain_unbroken = permitted

        # Sign the upload request if permitted (using production or mock signing service)
        rekor_entry_uuid = None
        cosign_signature = None

        if permitted:
            from ..services.signing_service import get_signing_service

            # Get the signing service (automatically mock or production based on config)
            signing_service = get_signing_service(http_request)

            # Create a hash of the artifacts for signing
            import hashlib

            artifact_data = f"{request.scan_id}:{','.join(a.hash for a in request.artifacts)}".encode()
            artifact_hash = hashlib.sha256(artifact_data).hexdigest()

            # Sign the artifact bundle
            sign_request = SignRequest(
                artifact=f"sha256:{artifact_hash}",
                artifact_type="upload_request",
                subject=f"scan:{request.scan_id}",
            )

            sign_response = await signing_service.sign(sign_request)
            rekor_entry_uuid = sign_response.entry_id
            cosign_signature = sign_response.signature

        # Create verification proof
        verification_proof = VerificationProofModel(
            chain_verified=permitted,
            inner_signature_valid=inner_signature_valid,
            outer_signature_valid=permitted,
            chain_unbroken=chain_unbroken,
            signer_inner=request.inner_signature.signer,
            signer_outer="certus-trust@certus.cloud" if permitted else None,
            sigstore_timestamp=timestamp.isoformat() if permitted else None,
            verification_timestamp=timestamp.isoformat(),
            rekor_entry_uuid=rekor_entry_uuid,
            cosign_signature=cosign_signature,
        )

        # If permitted, call Transform to execute upload
        # This is async - we return immediately, Transform processes in background
        if permitted:
            from .models import StorageConfigModel

            storage_config = StorageConfigModel(
                raw_s3_bucket=settings.s3_raw_bucket,
                raw_s3_prefix=f"{request.metadata.git_url.replace('/', '-')}/{request.metadata.commit[:8]}",
                oci_registry="registry.certus.cloud",
                oci_repository=f"scans/{request.metadata.git_url.replace('/', '-')}",
                upload_to_s3=request.storage_destinations.raw_s3,
                upload_to_oci=request.storage_destinations.oci_registry,
            )

            # Build execute upload request
            execute_request = ExecuteUploadRequestModel(
                upload_permission_id=permission_id,
                scan_id=request.scan_id,
                tier=request.tier,
                artifacts=request.artifacts,
                metadata=request.metadata,
                verification_proof=verification_proof,
                storage_config=storage_config,
            )

            # Call Transform asynchronously (don't wait for response)
            # In production: use async task queue (Celery, etc.)
            # For development: use asyncio.create_task or similar
            import asyncio

            # Global or module-level set to hold references to background tasks
            if not hasattr(verify_and_permit_upload, "background_tasks"):
                verify_and_permit_upload.background_tasks = set()

            task = asyncio.create_task(_call_transform_execute_upload(execute_request))
            verify_and_permit_upload.background_tasks.add(task)
            task.add_done_callback(verify_and_permit_upload.background_tasks.discard)

            logger.info(
                "Upload permitted, calling Transform to execute",
                extra={
                    "event_type": "upload_permitted",
                    "scan_id": request.scan_id,
                    "permission_id": permission_id,
                    "tier": request.tier,
                },
            )
        else:
            logger.info(
                f"Upload denied: {reason}",
                extra={
                    "event_type": "upload_denied",
                    "scan_id": request.scan_id,
                    "permission_id": permission_id,
                    "reason": reason,
                },
            )

        # Create permission response
        permission = UploadPermissionModel(
            upload_permission_id=permission_id,
            scan_id=request.scan_id,
            tier=request.tier,
            permitted=permitted,
            reason=reason,
            detail=detail,
            verification_proof=verification_proof if permitted else None,
            storage_config=StorageConfigModel(
                raw_s3_bucket=settings.s3_raw_bucket,
                raw_s3_prefix=f"{request.metadata.git_url.replace('/', '-')}/{request.metadata.commit[:8]}",
                upload_to_s3=request.storage_destinations.raw_s3,
                upload_to_oci=request.storage_destinations.oci_registry,
            )
            if permitted
            else None,
        )

        return permission

    except Exception as e:
        logger.error(
            f"Upload verification failed: {e!s}",
            extra={
                "event_type": "verification_failed",
                "scan_id": request.scan_id,
                "error": str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Upload verification failed",
        )


# ============================================================================
# Stats Endpoint
# ============================================================================


@router.get(
    "/v1/stats",
    response_model=ServiceStats,
    summary="Get service statistics",
    description="Get statistics about Trust service activity",
)
async def get_stats():
    """
    Get statistics about Trust service activity.

    Useful for debugging, demos, and AI agents analyzing Trust behavior.
    """
    return ServiceStats(
        total_signatures=len(_signed_artifacts),
        total_transparency_entries=len(_transparency_log),
        verification_stats={
            "total": _verification_count,
            "successful": _verification_success,
            "failed": _verification_failed,
        },
        signers=list({e.signer for e in _transparency_log}),
        timestamp=datetime.now(timezone.utc),
    )


# ============================================================================
# Provenance Chain Endpoint
# ============================================================================


@router.get(
    "/v1/provenance/{scan_id}",
    response_model=ProvenanceChain,
    summary="Get complete provenance chain for a scan",
    description="Return complete provenance history including manifest, scans, and verification trail",
)
async def get_scan_provenance(scan_id: str, scenario: Optional[str] = None):
    """
    Return complete provenance chain for a scan.

    Useful for AI agents to understand:
    - Who signed what and when
    - What manifest version was used
    - What tools ran
    - Complete verification trail

    Args:
        scan_id: Scan identifier
        scenario: Optional scenario name to simulate different provenance states
    """
    from .models import (
        ManifestProvenance,
        ScanToolProvenance,
        StorageLocations,
        VerificationTrailEntry,
    )

    # Use scenario if provided
    if scenario and scenario in MOCK_SCENARIOS:
        scenario_config = MOCK_SCENARIOS[scenario]
        chain_status = scenario_config["chain_status"]
        trust_level = scenario_config["trust_level"]
    else:
        chain_status = "complete"
        trust_level = "high"

    # Mock manifest provenance
    manifest = ManifestProvenance(
        version="v1.2.3",
        digest="sha256:abc123def456...",
        signed_by="certus-assurance@certus.cloud",
        signed_at="2025-12-13T10:00:00Z",
    )

    # Mock scan tool executions
    scans = [
        ScanToolProvenance(
            tool="trivy",
            version="0.45.0",
            signed_by="certus-assurance@certus.cloud",
            verified_by="certus-trust@certus.cloud" if chain_status == "complete" else None,
            timestamp="2025-12-13T10:01:00Z",
        ),
        ScanToolProvenance(
            tool="semgrep",
            version="1.45.0",
            signed_by="certus-assurance@certus.cloud",
            verified_by="certus-trust@certus.cloud" if chain_status == "complete" else None,
            timestamp="2025-12-13T10:02:00Z",
        ),
    ]

    # Mock verification trail
    verification_trail = [
        VerificationTrailEntry(
            timestamp="2025-12-13T10:05:00Z",
            verifier="certus-trust@certus.cloud",
            result="verified" if chain_status != "broken" else "failed",
            details="All signatures valid" if chain_status == "complete" else "Signature validation failed",
        ),
    ]

    # Mock storage locations
    storage_locations = StorageLocations(
        s3=f"s3://raw/scans/{scan_id}",
        oci=f"registry.certus.cloud/scans/{scan_id}:latest",
    )

    return ProvenanceChain(
        scan_id=scan_id,
        manifest=manifest,
        scans=scans,
        verification_trail=verification_trail,
        storage_locations=storage_locations,
        chain_status=chain_status,
        trust_level=trust_level,
    )


# ============================================================================
# Health Check Endpoints
# ============================================================================


@router.get(
    "/v1/health",
    response_model=HealthStatus,
    summary="Health check",
    description="Liveness probe - is service running?",
)
async def health_check() -> HealthStatus:
    """
    Liveness probe for service orchestration.

    Always returns 200 if service is running.
    """
    return HealthStatus(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/v1/ready",
    response_model=ReadinessStatus,
    summary="Readiness check",
    description="Readiness probe - can service handle requests?",
)
async def readiness_check() -> ReadinessStatus:
    """
    Readiness probe for service orchestration.

    Checks status of all dependencies:
    - Fulcio (certificate authority)
    - Rekor (transparency log)
    - TUF (metadata server)
    - Keycloak (OIDC provider)

    Phase 1 implementation: Always reports ready (dependencies not actually checked).
    Future phases will implement real health checks.
    """
    checks = {
        "fulcio": _component_status.get("fulcio", False),
        "rekor": _component_status.get("rekor", False),
        "tuf": _component_status.get("tuf", False),
        "keycloak": _component_status.get("keycloak", False),
    }

    ready = all(checks.values())

    return ReadinessStatus(
        ready=ready,
        checks=checks,
        timestamp=datetime.now(timezone.utc),
    )


# ============================================================================
# Public Key Distribution (TUF)
# ============================================================================


@router.get(
    "/v1/keys/root.json",
    summary="Get TUF root metadata",
    description="Public key distribution via TUF",
)
async def get_tuf_root() -> dict[str, Any]:
    """Get TUF root metadata for key distribution."""
    return {
        "signed": {
            "_type": "root",
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "spec_version": "1.0.0",
            "keys": {},
            "roles": {
                "root": {"threshold": 1, "keyids": []},
                "snapshot": {"threshold": 1, "keyids": []},
                "targets": {"threshold": 1, "keyids": []},
                "timestamp": {"threshold": 1, "keyids": []},
            },
        },
        "signatures": [],
    }


@router.get(
    "/v1/keys/targets.json",
    summary="Get TUF targets metadata",
)
async def get_tuf_targets() -> dict[str, Any]:
    """Get TUF targets metadata."""
    return {
        "signed": {
            "_type": "targets",
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "spec_version": "1.0.0",
            "targets": {},
            "delegations": None,
        },
        "signatures": [],
    }


@router.get(
    "/v1/keys/timestamp.json",
    summary="Get TUF timestamp metadata",
)
async def get_tuf_timestamp() -> dict[str, Any]:
    """Get TUF timestamp metadata."""
    return {
        "signed": {
            "_type": "timestamp",
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "spec_version": "1.0.0",
            "meta": {
                "snapshot.json": {
                    "version": 1,
                    "hashes": {},
                }
            },
        },
        "signatures": [],
    }


@router.get(
    "/v1/keys/snapshot.json",
    summary="Get TUF snapshot metadata",
)
async def get_tuf_snapshot() -> dict[str, Any]:
    """Get TUF snapshot metadata."""
    return {
        "signed": {
            "_type": "snapshot",
            "version": 1,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "spec_version": "1.0.0",
            "meta": {
                "targets.json": {
                    "version": 1,
                }
            },
        },
        "signatures": [],
    }
