"""Unit tests for router request validation logic."""

import pytest
from pydantic import ValidationError

from certus_transform.routers.ingest import SecurityIngestRequest
from certus_transform.routers.promotion import PromotionRequest
from certus_transform.routers.verification import (
    ArtifactInfoRequest,
    BatchUploadRequest,
    ExecuteUploadRequestModel,
    InnerSignatureRequest,
    ScanMetadataRequest,
    StorageConfigRequest,
    VerificationProofRequest,
)


class TestSecurityIngestValidation:
    """Test validation for ingest router."""

    def test_security_ingest_request_keys_validator_empty_list(self):
        """Test that empty keys list raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            SecurityIngestRequest(keys=[])

        assert "keys cannot be empty" in str(exc_info.value)

    def test_security_ingest_request_keys_validator_valid(self):
        """Test that non-empty keys list passes validation."""
        request = SecurityIngestRequest(
            workspace_id="test-workspace",
            keys=["scans/trivy.json", "scans/bandit.sarif"],
        )
        assert len(request.keys) == 2
        assert request.keys[0] == "scans/trivy.json"

    def test_security_ingest_request_workspace_id_default(self):
        """Test workspace_id defaults to None."""
        request = SecurityIngestRequest(keys=["test.json"])
        assert request.workspace_id is None

    def test_security_ingest_request_workspace_id_custom(self):
        """Test workspace_id can be set."""
        request = SecurityIngestRequest(workspace_id="custom-workspace", keys=["test.json"])
        assert request.workspace_id == "custom-workspace"


class TestPromotionRequestValidation:
    """Test validation for promotion router."""

    def test_promotion_request_keys_validator_empty_list(self):
        """Test that empty keys list raises ValueError."""
        with pytest.raises(ValidationError) as exc_info:
            PromotionRequest(keys=[])

        assert "keys cannot be empty" in str(exc_info.value)

    def test_promotion_request_keys_validator_valid(self):
        """Test that non-empty keys list passes validation."""
        request = PromotionRequest(keys=["active/file1.txt", "active/file2.json"])
        assert len(request.keys) == 2

    def test_promotion_request_destination_prefix_optional(self):
        """Test destination_prefix is optional and defaults to None."""
        request = PromotionRequest(keys=["file.txt"])
        assert request.destination_prefix is None

    def test_promotion_request_destination_prefix_custom(self):
        """Test destination_prefix can be set."""
        request = PromotionRequest(keys=["file.txt"], destination_prefix="custom-scans/")
        assert request.destination_prefix == "custom-scans/"


class TestVerificationRequestValidation:
    """Test validation for verification router models."""

    def test_artifact_info_request_valid(self):
        """Test ArtifactInfoRequest with all required fields."""
        artifact = ArtifactInfoRequest(name="trivy.json", hash="sha256:abc123", size=1024)
        assert artifact.name == "trivy.json"
        assert artifact.hash == "sha256:abc123"
        assert artifact.size == 1024

    def test_artifact_info_request_missing_fields(self):
        """Test ArtifactInfoRequest requires all fields."""
        with pytest.raises(ValidationError):
            ArtifactInfoRequest(name="trivy.json")  # Missing hash and size

    def test_inner_signature_request_optional_certificate(self):
        """Test certificate field is optional."""
        signature = InnerSignatureRequest(
            signer="certus-assurance@certus.cloud",
            timestamp="2025-12-18T10:00:00Z",
            signature="base64signature",
            algorithm="RSA-SHA256",
        )
        assert signature.certificate is None

        # With certificate
        signature_with_cert = InnerSignatureRequest(
            signer="certus-assurance@certus.cloud",
            timestamp="2025-12-18T10:00:00Z",
            signature="base64signature",
            algorithm="RSA-SHA256",
            certificate="-----BEGIN CERTIFICATE-----\n...",
        )
        assert signature_with_cert.certificate is not None

    def test_scan_metadata_request_requested_by_optional(self):
        """Test requested_by field is optional."""
        metadata = ScanMetadataRequest(
            git_url="https://github.com/example/repo",
            branch="main",
            commit="abc123def456",
        )
        assert metadata.requested_by is None

        # With requested_by
        metadata_with_user = ScanMetadataRequest(
            git_url="https://github.com/example/repo",
            branch="main",
            commit="abc123def456",
            requested_by="user@example.com",
        )
        assert metadata_with_user.requested_by == "user@example.com"

    def test_verification_proof_request_valid(self):
        """Test VerificationProofRequest with all required fields."""
        proof = VerificationProofRequest(
            chain_verified=True,
            inner_signature_valid=True,
            outer_signature_valid=True,
            chain_unbroken=True,
            signer_inner="certus-assurance@certus.cloud",
            signer_outer="certus-trust@certus.cloud",
        )
        assert proof.chain_verified is True
        assert proof.signer_inner == "certus-assurance@certus.cloud"

    def test_verification_proof_request_optional_fields(self):
        """Test optional fields in VerificationProofRequest."""
        proof = VerificationProofRequest(
            chain_verified=False,
            inner_signature_valid=True,
            outer_signature_valid=False,
            chain_unbroken=False,
            signer_inner="certus-assurance@certus.cloud",
        )
        # Optional fields should be None
        assert proof.signer_outer is None
        assert proof.sigstore_timestamp is None
        assert proof.verification_timestamp is None
        assert proof.rekor_entry_uuid is None

    def test_storage_config_request_defaults(self):
        """Test boolean defaults for StorageConfigRequest."""
        config = StorageConfigRequest()
        assert config.upload_to_s3 is True
        assert config.upload_to_oci is True
        assert config.raw_s3_bucket is None
        assert config.raw_s3_prefix is None

    def test_storage_config_request_custom_values(self):
        """Test custom values override defaults."""
        config = StorageConfigRequest(
            raw_s3_bucket="my-bucket",
            raw_s3_prefix="scans/abc/",
            upload_to_s3=True,
            upload_to_oci=False,
        )
        assert config.raw_s3_bucket == "my-bucket"
        assert config.upload_to_s3 is True
        assert config.upload_to_oci is False

    def test_execute_upload_request_tier_pattern(self):
        """Test tier field validates pattern 'basic' or 'verified'."""
        # Valid tiers
        request_basic = ExecuteUploadRequestModel(
            upload_permission_id="perm123",
            scan_id="scan456",
            tier="basic",
            artifacts=[ArtifactInfoRequest(name="trivy.json", hash="sha256:abc", size=100)],
            metadata=ScanMetadataRequest(
                git_url="https://github.com/test/repo",
                branch="main",
                commit="abc123",
            ),
        )
        assert request_basic.tier == "basic"

        request_verified = ExecuteUploadRequestModel(
            upload_permission_id="perm123",
            scan_id="scan456",
            tier="verified",
            artifacts=[ArtifactInfoRequest(name="trivy.json", hash="sha256:abc", size=100)],
            metadata=ScanMetadataRequest(
                git_url="https://github.com/test/repo",
                branch="main",
                commit="abc123",
            ),
        )
        assert request_verified.tier == "verified"

        # Invalid tier should fail validation
        with pytest.raises(ValidationError) as exc_info:
            ExecuteUploadRequestModel(
                upload_permission_id="perm123",
                scan_id="scan456",
                tier="invalid",
                artifacts=[ArtifactInfoRequest(name="trivy.json", hash="sha256:abc", size=100)],
                metadata=ScanMetadataRequest(
                    git_url="https://github.com/test/repo",
                    branch="main",
                    commit="abc123",
                ),
            )

        assert "tier" in str(exc_info.value)

    def test_execute_upload_request_model_valid(self):
        """Test valid ExecuteUploadRequestModel."""
        request = ExecuteUploadRequestModel(
            upload_permission_id="perm_abc123",
            scan_id="scan_xyz789",
            tier="verified",
            artifacts=[
                ArtifactInfoRequest(name="trivy.json", hash="sha256:abc123", size=2048),
                ArtifactInfoRequest(name="bandit.sarif", hash="sha256:def456", size=4096),
            ],
            metadata=ScanMetadataRequest(
                git_url="https://github.com/example/repo",
                branch="feature/test",
                commit="abc123def456",
                requested_by="developer@example.com",
            ),
            verification_proof=VerificationProofRequest(
                chain_verified=True,
                inner_signature_valid=True,
                outer_signature_valid=True,
                chain_unbroken=True,
                signer_inner="certus-assurance@certus.cloud",
                signer_outer="certus-trust@certus.cloud",
                verification_timestamp="2025-12-18T10:00:00Z",
            ),
            storage_config=StorageConfigRequest(
                raw_s3_bucket="raw-bucket",
                raw_s3_prefix="scans/test/",
                upload_to_s3=True,
                upload_to_oci=False,
            ),
        )

        assert request.upload_permission_id == "perm_abc123"
        assert len(request.artifacts) == 2
        assert request.metadata.git_url == "https://github.com/example/repo"
        assert request.verification_proof.chain_verified is True
        assert request.storage_config.upload_to_oci is False

    def test_execute_upload_request_missing_required_fields(self):
        """Test ExecuteUploadRequestModel requires key fields."""
        with pytest.raises(ValidationError):
            ExecuteUploadRequestModel(
                upload_permission_id="perm123",
                # Missing scan_id, tier, artifacts, metadata
            )

    def test_batch_upload_request_list_validation(self):
        """Test BatchUploadRequest validates list of ExecuteUploadRequestModel."""
        scan1 = ExecuteUploadRequestModel(
            upload_permission_id="perm1",
            scan_id="scan1",
            tier="basic",
            artifacts=[ArtifactInfoRequest(name="trivy.json", hash="sha256:abc", size=100)],
            metadata=ScanMetadataRequest(
                git_url="https://github.com/test/repo1",
                branch="main",
                commit="abc123",
            ),
        )

        scan2 = ExecuteUploadRequestModel(
            upload_permission_id="perm2",
            scan_id="scan2",
            tier="verified",
            artifacts=[ArtifactInfoRequest(name="bandit.sarif", hash="sha256:def", size=200)],
            metadata=ScanMetadataRequest(
                git_url="https://github.com/test/repo2",
                branch="develop",
                commit="def456",
            ),
        )

        batch = BatchUploadRequest(scans=[scan1, scan2])
        assert len(batch.scans) == 2
        assert batch.scans[0].tier == "basic"
        assert batch.scans[1].tier == "verified"

    def test_batch_upload_request_empty_list(self):
        """Test BatchUploadRequest accepts empty list."""
        batch = BatchUploadRequest(scans=[])
        assert len(batch.scans) == 0
