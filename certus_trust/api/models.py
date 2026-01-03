"""Request and response models for Certus-Trust API."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

# ============================================================================
# Sign Endpoint Models
# ============================================================================


class SignRequest(BaseModel):
    """Request to sign an artifact."""

    artifact: str = Field(..., description="SHA256 digest of artifact")
    artifact_type: str = Field(
        ...,
        description="Type of artifact: image, sbom, report, assessment",
    )
    subject: str = Field(..., description="Subject identifier (e.g., myapp:v1.0.0)")
    predicates: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional predicates for the signature",
    )


class TransparencyEntry(BaseModel):
    """Transparency log entry from Rekor."""

    uuid: str = Field(..., description="Unique entry ID in transparency log")
    index: int = Field(..., description="Index in transparency log")
    timestamp: datetime = Field(..., description="When entry was recorded")


class SignResponse(BaseModel):
    """Response after signing an artifact."""

    entry_id: str = Field(..., description="Unique ID for this signing operation")
    signature: str = Field(..., description="Base64-encoded signature")
    certificate: Optional[str] = Field(None, description="PEM-encoded certificate (for keyless signing)")
    transparency_entry: TransparencyEntry = Field(..., description="Entry in transparency log")


# ============================================================================
# Verify Endpoint Models
# ============================================================================


class VerifyRequest(BaseModel):
    """Request to verify a signature."""

    artifact: str = Field(..., description="SHA256 digest of artifact")
    signature: str = Field(..., description="Base64-encoded signature")
    certificate: Optional[str] = Field(None, description="PEM-encoded certificate")
    identity: Optional[str] = Field(None, description="Optional: verify signer identity")


class VerifyResponse(BaseModel):
    """Response after verifying a signature."""

    valid: bool = Field(..., description="Whether signature is valid")
    verified_at: datetime = Field(..., description="When verification occurred")
    signer: str = Field(..., description="Signer identity")
    transparency_index: Optional[int] = Field(None, description="Index in transparency log")
    certificate_chain: Optional[list[str]] = Field(None, description="Certificate chain (PEM-encoded)")


# ============================================================================
# Dual-Signature (Non-Repudiation) Models
# ============================================================================


class InnerSignatureFile(BaseModel):
    """Individual file signature from Certus-Assurance."""

    path: str = Field(..., description="File path (e.g., SECURITY/trivy.json)")
    signature: str = Field(..., description="Base64-encoded signature")
    verified: bool = Field(default=False, description="Whether signature was verified")


class InnerSignature(BaseModel):
    """Inner signature from Certus-Assurance."""

    signer: str = Field(..., description="Signer identity (certus-assurance@certus.cloud)")
    timestamp: datetime = Field(..., description="When assessment was signed")
    signature: str = Field(..., description="Primary signature")
    files: list[InnerSignatureFile] = Field(..., description="Individual file signatures")


class ArtifactLocation(BaseModel):
    """Storage location for assessment artifact."""

    uri: str = Field(..., description="S3 or Registry URI")
    digest: Optional[str] = Field(None, description="SHA256 digest of content")
    verified_at: Optional[datetime] = Field(None, description="When verified")


class AssessmentMetadata(BaseModel):
    """Metadata about the assessment being signed."""

    assessment_id: str = Field(..., description="Unique assessment ID")
    client_id: str = Field(..., description="Client identifier")
    assessment_type: str = Field(
        default="unified_risk_assessment",
        description="Type of assessment",
    )
    domains: Optional[list[str]] = Field(
        default_factory=list,
        description="Domains (security, supply_chain, privacy, ai_assurance)",
    )


class SignArtifactRequest(BaseModel):
    """Request to sign assessment artifact with dual signatures."""

    artifact_locations: dict[str, ArtifactLocation] = Field(..., description="S3 and Registry storage locations")
    inner_signatures: InnerSignature = Field(..., description="Inner signatures from Certus-Assurance")
    assessment_metadata: AssessmentMetadata = Field(..., description="Assessment context")


class VerificationProof(BaseModel):
    """Proof of verification for non-repudiation."""

    inner_signatures_verified: bool = Field(..., description="Whether inner signatures are valid")
    artifact_locations_valid: bool = Field(..., description="Whether artifact locations are accessible")
    chain_of_custody: str = Field(..., description="Status: complete, broken, or warning")
    both_locations_identical: bool = Field(..., description="Whether S3 and Registry digests match")


class OuterSignature(BaseModel):
    """Outer signature from Certus-Trust."""

    signer: str = Field(..., description="Signer identity (certus-trust@certus.cloud)")
    timestamp: datetime = Field(..., description="When Trust signed this")
    signature: str = Field(..., description="Base64-encoded outer signature")
    sigstore_entry_id: str = Field(..., description="Rekor transparency log entry ID")
    transparency_log_url: Optional[str] = Field(None, description="URL to Sigstore transparency log entry")


class SignArtifactResponse(BaseModel):
    """Response after signing assessment artifact."""

    status: str = Field(..., description="Status: signed, pending, or failed")
    assessment_id: str = Field(..., description="Assessment being signed")
    outer_signature: OuterSignature = Field(..., description="Trust's outer signature")
    verification_proof: VerificationProof = Field(..., description="Verification results")


# ============================================================================
# Verify Chain (Non-Repudiation) Models
# ============================================================================


class SignatureSet(BaseModel):
    """Inner and outer signatures to verify."""

    inner: Optional[dict[str, Any]] = Field(None, description="Inner signature data")
    outer: Optional[dict[str, Any]] = Field(None, description="Outer signature data")


class VerifyChainRequest(BaseModel):
    """Request to verify complete non-repudiation chain."""

    artifact_locations: dict[str, Any] = Field(..., description="S3 and Registry URIs")
    signatures: SignatureSet = Field(..., description="Inner and outer signatures")
    sigstore_entry_id: Optional[str] = Field(None, description="Rekor entry ID for verification")


class ArtifactLocationVerification(BaseModel):
    """Verification results for artifact locations."""

    s3_valid: bool = Field(..., description="Whether S3 location is valid")
    registry_valid: bool = Field(..., description="Whether Registry location is valid")
    digests_match: bool = Field(..., description="Whether digests match")
    content_identical: bool = Field(..., description="Whether content is identical")


class NonRepudiationGuarantee(BaseModel):
    """Non-repudiation guarantees provided."""

    assurance_accountable: bool = Field(..., description="Certus-Assurance cannot deny creating this")
    trust_verified: bool = Field(..., description="Certus-Trust verified the assessment")
    timestamp_authority: str = Field(..., description="Timestamp authority (sigstore)")
    provenance_chain: str = Field(..., description="Status: complete, partial, or broken")


class VerifyChainResponse(BaseModel):
    """Response after verifying non-repudiation chain."""

    chain_verified: bool = Field(..., description="Whether entire chain is valid")
    inner_signature_valid: bool = Field(..., description="Whether Assurance signature is valid")
    outer_signature_valid: bool = Field(..., description="Whether Trust signature is valid")
    chain_unbroken: bool = Field(..., description="Whether chain has no breaks")
    signer_inner: str = Field(..., description="Assurance signer identity")
    signer_outer: str = Field(..., description="Trust signer identity")
    sigstore_timestamp: Optional[datetime] = Field(None, description="Timestamp from Sigstore")
    artifact_locations: ArtifactLocationVerification = Field(..., description="Artifact location verification")
    non_repudiation: NonRepudiationGuarantee = Field(..., description="Non-repudiation guarantees")


# ============================================================================
# Transparency Log Models
# ============================================================================


class TransparencyLogEntry(BaseModel):
    """Entry in the transparency log."""

    entry_id: str = Field(..., description="Entry UUID")
    artifact: Optional[str] = Field(None, description="SHA256 of artifact")
    timestamp: datetime = Field(..., description="When logged")
    signer: str = Field(..., description="Signer identity")
    signature: str = Field(..., description="Base64-encoded signature")
    proof: Optional[dict[str, Any]] = Field(None, description="Merkle proof")


class TransparencyQuery(BaseModel):
    """Query for transparency log entries."""

    assessment_id: Optional[str] = Field(None, description="Filter by assessment ID")
    signer: Optional[str] = Field(None, description="Filter by signer")
    limit: int = Field(default=10, description="Max entries to return")
    offset: int = Field(default=0, description="Offset for pagination")


# ============================================================================
# Health Check Models
# ============================================================================


class HealthStatus(BaseModel):
    """Health check response."""

    status: str = Field(..., description="healthy or unhealthy")
    timestamp: datetime = Field(..., description="Check timestamp")


class ComponentHealthCheck(BaseModel):
    """Health status of a component."""

    name: str = Field(..., description="Component name")
    healthy: bool = Field(..., description="Whether component is healthy")
    error: Optional[str] = Field(None, description="Error message if unhealthy")


class ReadinessStatus(BaseModel):
    """Readiness check response."""

    ready: bool = Field(..., description="Whether service is ready")
    checks: dict[str, bool] = Field(..., description="Per-component readiness")
    timestamp: datetime = Field(..., description="Check timestamp")


# ============================================================================
# Error Models
# ============================================================================


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    timestamp: datetime = Field(..., description="When error occurred")
    request_id: Optional[str] = Field(None, description="Request tracking ID")


class ValidationError(ErrorResponse):
    """Validation error response."""

    details: dict[str, Any] = Field(..., description="Field-level errors")


# ============================================================================
# Stats Models
# ============================================================================


class ServiceStats(BaseModel):
    """Statistics about Trust service activity."""

    total_signatures: int = Field(..., description="Total signatures created")
    total_transparency_entries: int = Field(..., description="Total transparency log entries")
    verification_stats: dict[str, int] = Field(..., description="Verification statistics")
    signers: list[str] = Field(..., description="List of unique signers")
    timestamp: datetime = Field(..., description="When stats were generated")


# ============================================================================
# Provenance Chain Models
# ============================================================================


class ManifestProvenance(BaseModel):
    """Provenance information for a manifest."""

    version: str = Field(..., description="Manifest version")
    digest: str = Field(..., description="SHA256 digest of manifest")
    signed_by: str = Field(..., description="Who signed the manifest")
    signed_at: str = Field(..., description="When manifest was signed (ISO 8601)")


class ScanToolProvenance(BaseModel):
    """Provenance information for a scan tool execution."""

    tool: str = Field(..., description="Tool name (e.g., trivy, semgrep)")
    version: str = Field(..., description="Tool version")
    signed_by: str = Field(..., description="Who signed the scan results")
    verified_by: Optional[str] = Field(None, description="Who verified the scan")
    timestamp: str = Field(..., description="When scan was executed (ISO 8601)")


class VerificationTrailEntry(BaseModel):
    """Single entry in verification trail."""

    timestamp: str = Field(..., description="When verification occurred (ISO 8601)")
    verifier: str = Field(..., description="Who performed verification")
    result: str = Field(..., description="Verification result: verified, failed, partial")
    details: Optional[str] = Field(None, description="Additional details")


class StorageLocations(BaseModel):
    """Storage locations for scan artifacts."""

    s3: Optional[str] = Field(None, description="S3 URI")
    oci: Optional[str] = Field(None, description="OCI registry reference")


class ProvenanceChain(BaseModel):
    """Complete provenance chain for a scan."""

    scan_id: str = Field(..., description="Scan identifier")
    manifest: ManifestProvenance = Field(..., description="Manifest provenance")
    scans: list[ScanToolProvenance] = Field(..., description="Scan tool executions")
    verification_trail: list[VerificationTrailEntry] = Field(..., description="Verification history")
    storage_locations: StorageLocations = Field(..., description="Where artifacts are stored")
    chain_status: str = Field(..., description="Overall chain status: complete, partial, broken")
    trust_level: str = Field(..., description="Trust level: high, medium, low, untrusted")


# ============================================================================
# Verification-First Upload Workflow Models
# ============================================================================


class ArtifactInfoModel(BaseModel):
    """Information about an artifact to be uploaded."""

    name: str = Field(..., description="Artifact file name (e.g., trivy.json)")
    hash: str = Field(..., description="SHA256 hash (sha256:abc123...)")
    size: int = Field(..., description="File size in bytes")


class InnerSignatureModel(BaseModel):
    """Inner signature from Certus-Assurance."""

    signer: str = Field(..., description="Signer identity (certus-assurance@certus.cloud)")
    timestamp: str = Field(..., description="When signed (ISO 8601)")
    signature: str = Field(..., description="Base64-encoded signature")
    algorithm: str = Field(..., description="Signature algorithm (e.g., SHA256-RSA)")
    certificate: Optional[str] = Field(None, description="PEM-encoded certificate")


class ScanMetadataModel(BaseModel):
    """Scan metadata for audit trail."""

    git_url: str = Field(..., description="Repository URL")
    branch: str = Field(..., description="Git branch name")
    commit: str = Field(..., description="Git commit hash")
    requested_by: Optional[str] = Field(None, description="User who requested scan")


class StorageDestinationsModel(BaseModel):
    """Where to upload artifacts."""

    raw_s3: bool = Field(default=True, description="Upload to S3 raw bucket")
    oci_registry: bool = Field(default=True, description="Upload to OCI registry")


class UploadRequestModel(BaseModel):
    """Request from Assurance to Trust to verify and permit upload.

    This is the gatekeeper request - Trust must verify and approve before
    any artifacts are stored.
    """

    scan_id: str = Field(..., description="Unique scan ID from Assurance")
    tier: str = Field(
        ...,
        description="Scan tier: 'basic' or 'verified'",
        pattern="^(basic|verified)$",
    )
    inner_signature: InnerSignatureModel = Field(..., description="Signature from Assurance")
    artifacts: list[ArtifactInfoModel] = Field(..., description="Artifacts to be uploaded")
    metadata: ScanMetadataModel = Field(..., description="Scan metadata")
    storage_destinations: StorageDestinationsModel = Field(
        default_factory=StorageDestinationsModel,
        description="Upload destinations",
    )


class VerificationProofModel(BaseModel):
    """Proof that Trust verified the scan."""

    chain_verified: bool = Field(..., description="Is complete chain verified")
    inner_signature_valid: bool = Field(..., description="Is Assurance signature valid")
    outer_signature_valid: bool = Field(..., description="Is Trust signature valid")
    chain_unbroken: bool = Field(..., description="Is chain unbroken")
    signer_inner: str = Field(..., description="Assurance signer identity")
    signer_outer: Optional[str] = Field(None, description="Trust signer identity")
    sigstore_timestamp: Optional[str] = Field(None, description="Sigstore timestamp (ISO 8601)")
    verification_timestamp: Optional[str] = Field(None, description="When verified (ISO 8601)")
    rekor_entry_uuid: Optional[str] = Field(None, description="Rekor entry ID")
    cosign_signature: Optional[str] = Field(None, description="Cosign signature")


class StorageConfigModel(BaseModel):
    """Storage configuration for Transform to use."""

    raw_s3_bucket: str = Field(..., description="S3 bucket name for raw artifacts")
    raw_s3_prefix: str = Field(..., description="S3 prefix for this scan")
    oci_registry: Optional[str] = Field(None, description="OCI registry URL")
    oci_repository: Optional[str] = Field(None, description="OCI repository path")
    upload_to_s3: bool = Field(default=True, description="Upload artifacts to S3")
    upload_to_oci: bool = Field(default=True, description="Upload artifacts to OCI registry")


class UploadPermissionModel(BaseModel):
    """Permission from Trust to upload artifacts.

    If permitted=False, artifacts must NOT be stored. This is the gatekeeper.
    """

    upload_permission_id: str = Field(..., description="Unique permission ID")
    scan_id: str = Field(..., description="Associated scan ID")
    tier: str = Field(
        ...,
        description="Scan tier: 'basic' or 'verified'",
        pattern="^(basic|verified)$",
    )
    permitted: bool = Field(..., description="Whether upload is permitted (gatekeeper decision)")
    reason: Optional[str] = Field(None, description="Reason for permission decision")
    detail: Optional[str] = Field(None, description="Detailed message")
    verification_proof: Optional[VerificationProofModel] = Field(None, description="Verification results")
    storage_config: Optional[StorageConfigModel] = Field(None, description="Storage configuration if permitted")


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
    artifacts: list[ArtifactInfoModel] = Field(..., description="Artifacts to upload")
    metadata: ScanMetadataModel = Field(..., description="Scan metadata")
    verification_proof: Optional[VerificationProofModel] = Field(None, description="Verification proof")
    storage_config: Optional[StorageConfigModel] = Field(None, description="Storage configuration")


class UploadConfirmationModel(BaseModel):
    """Confirmation from Transform that upload completed."""

    upload_permission_id: str = Field(..., description="Permission ID")
    scan_id: str = Field(..., description="Scan ID that was uploaded")
    status: str = Field(
        ...,
        description="Upload status: 'success' or 'failed'",
        pattern="^(success|failed)$",
    )
    uploaded_artifacts: list[str] = Field(default_factory=list, description="Paths of uploaded artifacts")
    s3_prefix: Optional[str] = Field(None, description="S3 prefix where stored")
    oci_reference: Optional[str] = Field(None, description="OCI reference (tag)")
    error_detail: Optional[str] = Field(None, description="Error message if failed")
    timestamp: str = Field(..., description="When upload completed (ISO 8601)")
