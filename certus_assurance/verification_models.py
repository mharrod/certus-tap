"""Data models for verification-first upload workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


@dataclass(slots=True)
class ArtifactInfo:
    """Information about an artifact to be uploaded."""

    name: str
    hash: str  # sha256:abc123...
    size: int  # bytes


@dataclass(slots=True)
class InnerSignature:
    """Inner signature from Certus-Assurance."""

    signer: str
    timestamp: str  # ISO 8601
    signature: str  # base64-encoded
    algorithm: str  # e.g., "SHA256-RSA"
    certificate: str | None = None


@dataclass(slots=True)
class ScanMetadata:
    """Scan metadata for audit trail."""

    git_url: str
    branch: str
    commit: str
    requested_by: str | None = None


@dataclass(slots=True)
class StorageDestinations:
    """Where to upload artifacts."""

    raw_s3: bool = True
    oci_registry: bool = True


@dataclass(slots=True)
class UploadRequest:
    """Request from Assurance to Trust to verify and permit upload.

    This is the gatekeeper request - Trust must verify and approve before
    any artifacts are stored.
    """

    scan_id: str
    tier: Literal["basic", "verified"]
    inner_signature: InnerSignature
    artifacts: list[ArtifactInfo]
    metadata: ScanMetadata
    storage_destinations: StorageDestinations = field(default_factory=StorageDestinations)


@dataclass(slots=True)
class VerificationProof:
    """Proof that Trust verified the scan."""

    chain_verified: bool
    inner_signature_valid: bool
    outer_signature_valid: bool
    chain_unbroken: bool
    signer_inner: str
    signer_outer: str | None = None
    sigstore_timestamp: str | None = None  # ISO 8601
    verification_timestamp: str | None = None  # ISO 8601
    rekor_entry_uuid: str | None = None
    cosign_signature: str | None = None


@dataclass(slots=True)
class StorageConfig:
    """Storage configuration for Transform to use."""

    raw_s3_bucket: str
    raw_s3_prefix: str
    oci_registry: str | None = None
    oci_repository: str | None = None
    upload_to_s3: bool = True
    upload_to_oci: bool = True


@dataclass(slots=True)
class UploadPermission:
    """Permission from Trust to upload artifacts.

    If permitted=False, artifacts must NOT be stored. This is the gatekeeper.
    """

    upload_permission_id: str
    scan_id: str
    tier: Literal["basic", "verified"]
    permitted: bool
    reason: str | None = None  # reason for rejection, if any
    detail: str | None = None  # detailed rejection message
    verification_proof: VerificationProof | None = None
    storage_config: StorageConfig | None = None


@dataclass(slots=True)
class ExecuteUploadRequest:
    """Request from Trust to Transform to execute upload.

    This is only sent if verification passed (permitted=True).
    Transform is the executor - it handles the actual upload operations.
    """

    upload_permission_id: str
    scan_id: str
    tier: Literal["basic", "verified"]
    artifacts: list[ArtifactInfo]
    metadata: ScanMetadata
    verification_proof: VerificationProof | None = None
    storage_config: StorageConfig | None = None


@dataclass(slots=True)
class UploadConfirmation:
    """Confirmation from Transform that upload completed."""

    upload_permission_id: str
    scan_id: str
    status: Literal["success", "failed"]
    uploaded_artifacts: list[str] = field(default_factory=list)  # paths in storage
    s3_prefix: str | None = None
    oci_reference: str | None = None
    error_detail: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
