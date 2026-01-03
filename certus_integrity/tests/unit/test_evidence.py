"""Unit tests for evidence generation logic."""

import hashlib
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from certus_integrity.evidence import EvidenceGenerator
from certus_integrity.schemas import IntegrityDecision


class TestEvidenceHashConsistency:
    """Test evidence hash generation."""

    @pytest.mark.asyncio
    async def test_evidence_hash_consistency(self):
        """Test same decision produces same hash."""
        from datetime import datetime

        generator = EvidenceGenerator(service_name="test-service")

        # Use fixed timestamp to ensure consistent hashing
        fixed_timestamp = datetime(2025, 1, 1, 12, 0, 0)

        decision1 = IntegrityDecision(
            decision_id="test-123",
            timestamp=fixed_timestamp,
            trace_id="trace-abc",
            span_id="span-def",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        decision2 = IntegrityDecision(
            decision_id="test-123",
            timestamp=fixed_timestamp,
            trace_id="trace-abc",
            span_id="span-def",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        # Mock the signing and save operations
        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value={})):
            with patch.object(generator, "_save_to_disk"):
                bundle1 = await generator.process_decision(decision1)
                bundle2 = await generator.process_decision(decision2)

        # Same decision should produce same hash
        assert bundle1.content_hash == bundle2.content_hash

    @pytest.mark.asyncio
    async def test_evidence_hash_is_sha256(self):
        """Test hash is SHA256 format."""
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="test-456",
            trace_id="trace-xyz",
            span_id="span-123",
            service="test-service",
            decision="denied",
            reason="rate_limit",
            guardrail="rate_limit",
        )

        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value={})):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        # SHA256 hash is 64 hex characters
        assert len(bundle.content_hash) == 64
        assert all(c in "0123456789abcdef" for c in bundle.content_hash)

    @pytest.mark.asyncio
    async def test_evidence_json_canonicalization(self):
        """Test JSON canonicalization - key order doesn't matter."""
        generator = EvidenceGenerator(service_name="test-service")

        # Create decision with metadata in specific order
        decision = IntegrityDecision(
            decision_id="test-789",
            trace_id="trace-aaa",
            span_id="span-bbb",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
            metadata={"key1": "value1", "key2": "value2"},
        )

        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value={})):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        # Verify canonical JSON was used (sorted keys)
        content = decision.model_dump(mode="json")
        canonical_json = json.dumps(content, sort_keys=True, separators=(",", ":"))
        expected_hash = hashlib.sha256(canonical_json.encode()).hexdigest()

        assert bundle.content_hash == expected_hash


class TestEvidenceBundleStructure:
    """Test evidence bundle structure and fields."""

    @pytest.mark.asyncio
    async def test_evidence_bundle_required_fields(self):
        """Test all required fields present in bundle."""
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="bundle-001",
            trace_id="trace-001",
            span_id="span-001",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        mock_sig_data = {
            "signature": "test-signature",
            "certificate": "test-cert",
            "transparency_entry": {"log_id": "test-log"},
        }

        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value=mock_sig_data)):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        # Check all required fields
        assert bundle.evidence_id == "bundle-001"
        assert bundle.timestamp is not None
        assert bundle.decision is not None
        assert bundle.content_hash is not None
        assert bundle.signature == "test-signature"
        assert bundle.signer_certificate == "test-cert"
        assert bundle.transparency_log_entry == {"log_id": "test-log"}
        assert bundle.verification_status == "signed"

    @pytest.mark.asyncio
    async def test_evidence_timestamp_format_iso8601(self):
        """Test timestamp is ISO8601 format."""
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="time-test",
            trace_id="trace-time",
            span_id="span-time",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value={})):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        # Should be able to parse as datetime
        datetime.fromisoformat(bundle.timestamp)

    @pytest.mark.asyncio
    async def test_evidence_decision_object_embedded(self):
        """Test decision object properly embedded."""
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="embed-test",
            trace_id="trace-embed",
            span_id="span-embed",
            service="test-service",
            decision="denied",
            reason="rate_limit_exceeded",
            guardrail="rate_limit",
            metadata={"client_ip": "192.168.1.1"},
        )

        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value={})):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        # Decision should be embedded as dict
        assert isinstance(bundle.decision, dict)
        assert bundle.decision["decision_id"] == "embed-test"
        assert bundle.decision["decision"] == "denied"
        assert bundle.decision["metadata"]["client_ip"] == "192.168.1.1"


class TestEvidenceSigning:
    """Test evidence signing with Trust service."""

    @pytest.mark.asyncio
    async def test_evidence_signing_success(self):
        """Test successful signing with Trust service."""
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="sign-success",
            trace_id="trace-sign",
            span_id="span-sign",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        # Mock _sign_hash directly to return signature data
        async def mock_sign_hash(digest, title):
            return {"signature": "sig-abc123", "certificate": "cert-xyz789"}

        with patch.object(generator, "_sign_hash", side_effect=mock_sign_hash):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        assert bundle.signature == "sig-abc123"
        assert bundle.signer_certificate == "cert-xyz789"
        assert bundle.verification_status == "signed"

    @pytest.mark.asyncio
    async def test_evidence_signing_timeout(self):
        """Test timeout handled gracefully."""
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="sign-timeout",
            trace_id="trace-timeout",
            span_id="span-timeout",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        with patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("timeout")):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        # Should create unsigned bundle
        assert bundle.signature is None
        assert bundle.verification_status == "offline"

    @pytest.mark.asyncio
    async def test_evidence_signing_unavailable(self):
        """Test Trust service unavailable handled gracefully."""
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="sign-unavail",
            trace_id="trace-unavail",
            span_id="span-unavail",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("connection refused")):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        # Should not raise exception
        assert bundle.verification_status == "offline"

    @pytest.mark.asyncio
    async def test_evidence_signing_http_error(self):
        """Test HTTP error from Trust service handled."""
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="sign-error",
            trace_id="trace-error",
            span_id="span-error",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        mock_response = AsyncMock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPStatusError("500 Server Error", request=Mock(), response=Mock(status_code=500))
        )

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        assert bundle.verification_status == "offline"


class TestEvidencePersistence:
    """Test evidence disk persistence."""

    @pytest.mark.asyncio
    async def test_evidence_disk_write_success(self, tmp_path):
        """Test file created at correct path."""
        generator = EvidenceGenerator(service_name="test-service")
        generator.storage_path = tmp_path

        decision = IntegrityDecision(
            decision_id="disk-success",
            trace_id="trace-disk",
            span_id="span-disk",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value={})):
            bundle = await generator.process_decision(decision)

        # Check file exists
        file_path = tmp_path / "dec_disk-success.json"
        assert file_path.exists()

        # Check JSON is valid
        with open(file_path) as f:
            data = json.load(f)
            assert data["evidence_id"] == "disk-success"

    @pytest.mark.asyncio
    async def test_evidence_disk_write_failure(self, tmp_path):
        """Test disk write failure handled gracefully."""
        generator = EvidenceGenerator(service_name="test-service")
        # Use invalid path to force write failure
        generator.storage_path = tmp_path / "nonexistent" / "deep" / "path"

        decision = IntegrityDecision(
            decision_id="disk-fail",
            trace_id="trace-fail",
            span_id="span-fail",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value={})):
            # Should not raise exception
            bundle = await generator.process_decision(decision)

        # Bundle still created
        assert bundle.evidence_id == "disk-fail"

    @pytest.mark.asyncio
    async def test_evidence_json_format_valid(self, tmp_path):
        """Test saved JSON format is valid."""
        generator = EvidenceGenerator(service_name="test-service")
        generator.storage_path = tmp_path

        decision = IntegrityDecision(
            decision_id="json-valid",
            trace_id="trace-json",
            span_id="span-json",
            service="test-service",
            decision="denied",
            reason="rate_limit",
            guardrail="rate_limit",
            metadata={"client_ip": "10.0.0.1"},
        )

        mock_sig = {"signature": "sig123", "certificate": "cert456"}

        with patch.object(generator, "_sign_hash", new=AsyncMock(return_value=mock_sig)):
            await generator.process_decision(decision)

        file_path = tmp_path / "dec_json-valid.json"
        with open(file_path) as f:
            data = json.load(f)

        # Verify structure
        assert "evidence_id" in data
        assert "timestamp" in data
        assert "decision" in data
        assert "content_hash" in data
        assert "signature" in data
        assert data["signature"] == "sig123"


class TestEvidenceErrorHandling:
    """Test error handling and fallback behavior."""

    @pytest.mark.asyncio
    async def test_evidence_generation_exception_fallback(self, tmp_path):
        """Test exception during generation creates fallback bundle."""
        generator = EvidenceGenerator(service_name="test-service")
        generator.storage_path = tmp_path

        decision = IntegrityDecision(
            decision_id="error-fallback",
            trace_id="trace-error",
            span_id="span-error",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        # Force an error during signing
        with patch.object(generator, "_sign_hash", side_effect=Exception("test error")):
            bundle = await generator.process_decision(decision)

        # Should create fallback bundle
        assert bundle.evidence_id == "error-fallback"
        assert bundle.verification_status == "failed"
        assert bundle.content_hash == "error"

    @pytest.mark.asyncio
    async def test_evidence_recovery_on_restart(self, tmp_path):
        """Test evidence persists across restarts."""
        # First generator creates evidence
        gen1 = EvidenceGenerator(service_name="test-service")
        gen1.storage_path = tmp_path

        decision = IntegrityDecision(
            decision_id="persist-test",
            trace_id="trace-persist",
            span_id="span-persist",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        with patch.object(gen1, "_sign_hash", new=AsyncMock(return_value={})):
            await gen1.process_decision(decision)

        # Second generator can read it
        gen2 = EvidenceGenerator(service_name="test-service")
        gen2.storage_path = tmp_path

        file_path = tmp_path / "dec_persist-test.json"
        assert file_path.exists()

        with open(file_path) as f:
            data = json.load(f)
            assert data["evidence_id"] == "persist-test"
