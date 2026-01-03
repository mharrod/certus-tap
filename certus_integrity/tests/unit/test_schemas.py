"""Unit tests for Pydantic schema validation."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from certus_integrity.evidence import SignedEvidence
from certus_integrity.schemas import IntegrityConfig, IntegrityDecision


class TestIntegrityDecisionValidation:
    """Test IntegrityDecision Pydantic model validation."""

    def test_integrity_decision_required_fields(self):
        """Test all required fields must be provided."""
        # Should work with all required fields
        decision = IntegrityDecision(
            decision_id="test-123",
            trace_id="trace-abc",
            span_id="span-def",
            service="test-service",
            decision="allowed",
            reason="test_reason",
            guardrail="none",
        )
        assert decision.decision_id == "test-123"

    def test_integrity_decision_missing_required_field(self):
        """Test missing required field raises ValidationError."""
        with pytest.raises(ValidationError):
            IntegrityDecision(
                decision_id="test-123",
                # Missing trace_id
                span_id="span-def",
                service="test-service",
                decision="allowed",
                reason="test_reason",
                guardrail="none",
            )

    def test_integrity_decision_timestamp_auto_generated(self):
        """Test timestamp auto-generated if not provided."""
        decision = IntegrityDecision(
            decision_id="test-456",
            trace_id="trace-xyz",
            span_id="span-123",
            service="test-service",
            decision="denied",
            reason="rate_limit",
            guardrail="rate_limit",
        )

        assert decision.timestamp is not None
        assert isinstance(decision.timestamp, datetime)

    def test_integrity_decision_custom_timestamp(self):
        """Test custom timestamp accepted."""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        decision = IntegrityDecision(
            decision_id="test-789",
            timestamp=custom_time,
            trace_id="trace-custom",
            span_id="span-custom",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        assert decision.timestamp == custom_time

    def test_integrity_decision_literal_values(self):
        """Test decision field only accepts literal values."""
        # Valid values
        for valid_decision in ["allowed", "denied", "degraded"]:
            decision = IntegrityDecision(
                decision_id=f"test-{valid_decision}",
                trace_id="trace-lit",
                span_id="span-lit",
                service="test-service",
                decision=valid_decision,  # type: ignore
                reason="test",
                guardrail="none",
            )
            assert decision.decision == valid_decision

        # Invalid value should fail validation
        with pytest.raises(ValidationError):
            IntegrityDecision(
                decision_id="test-invalid",
                trace_id="trace-inv",
                span_id="span-inv",
                service="test-service",
                decision="invalid_value",  # type: ignore
                reason="test",
                guardrail="none",
            )

    def test_integrity_decision_metadata_optional(self):
        """Test metadata field is optional."""
        decision = IntegrityDecision(
            decision_id="test-meta",
            trace_id="trace-meta",
            span_id="span-meta",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        # Should default to empty dict
        assert decision.metadata == {}

    def test_integrity_decision_metadata_dict(self):
        """Test metadata accepts any dict."""
        metadata = {"client_ip": "192.168.1.1", "duration_ms": 42, "nested": {"key": "value"}}

        decision = IntegrityDecision(
            decision_id="test-dict",
            trace_id="trace-dict",
            span_id="span-dict",
            service="test-service",
            decision="allowed",
            reason="test",
            guardrail="none",
            metadata=metadata,
        )

        assert decision.metadata == metadata


class TestIntegrityConfigValidation:
    """Test IntegrityConfig Pydantic model validation."""

    def test_integrity_config_required_fields(self):
        """Test service_name is required."""
        config = IntegrityConfig(service_name="test-service")
        assert config.service_name == "test-service"

    def test_integrity_config_missing_service_name(self):
        """Test missing service_name raises error."""
        with pytest.raises(ValidationError):
            IntegrityConfig()  # type: ignore

    def test_integrity_config_shadow_mode_default(self):
        """Test shadow_mode defaults to True."""
        config = IntegrityConfig(service_name="test")
        assert config.shadow_mode is True

    def test_integrity_config_rate_limit_enabled_default(self):
        """Test rate_limit_enabled defaults to True."""
        config = IntegrityConfig(service_name="test")
        assert config.rate_limit_enabled is True

    def test_integrity_config_rate_limit_per_minute_default(self):
        """Test rate_limit_per_minute defaults to 100."""
        config = IntegrityConfig(service_name="test")
        assert config.rate_limit_per_minute == 100

    def test_integrity_config_graph_budget_enabled_default(self):
        """Test graph_budget_enabled defaults to True."""
        config = IntegrityConfig(service_name="test")
        assert config.graph_budget_enabled is True

    def test_integrity_config_max_graph_nodes_default(self):
        """Test max_graph_nodes defaults to 1000."""
        config = IntegrityConfig(service_name="test")
        assert config.max_graph_nodes == 1000

    def test_integrity_config_custom_values(self):
        """Test custom values override defaults."""
        config = IntegrityConfig(
            service_name="custom-service",
            shadow_mode=False,
            rate_limit_enabled=False,
            rate_limit_per_minute=200,
            graph_budget_enabled=False,
            max_graph_nodes=5000,
        )

        assert config.service_name == "custom-service"
        assert config.shadow_mode is False
        assert config.rate_limit_enabled is False
        assert config.rate_limit_per_minute == 200
        assert config.graph_budget_enabled is False
        assert config.max_graph_nodes == 5000


class TestSignedEvidenceValidation:
    """Test SignedEvidence Pydantic model validation."""

    def test_signed_evidence_required_fields(self):
        """Test all required fields must be provided."""
        evidence = SignedEvidence(
            evidence_id="ev-123",
            timestamp="2024-01-01T12:00:00",
            decision={"decision_id": "test"},
            content_hash="abc123",
        )

        assert evidence.evidence_id == "ev-123"
        assert evidence.content_hash == "abc123"

    def test_signed_evidence_optional_fields(self):
        """Test optional fields default to None."""
        evidence = SignedEvidence(
            evidence_id="ev-456",
            timestamp="2024-01-01T12:00:00",
            decision={},
            content_hash="def456",
        )

        assert evidence.signature is None
        assert evidence.signer_certificate is None
        assert evidence.transparency_log_entry is None

    def test_signed_evidence_verification_status_default(self):
        """Test verification_status defaults to 'unsigned'."""
        evidence = SignedEvidence(
            evidence_id="ev-789",
            timestamp="2024-01-01T12:00:00",
            decision={},
            content_hash="ghi789",
        )

        assert evidence.verification_status == "unsigned"

    def test_signed_evidence_verification_status_values(self):
        """Test verification_status accepts valid values."""
        for status in ["unsigned", "signed", "failed", "offline"]:
            evidence = SignedEvidence(
                evidence_id=f"ev-{status}",
                timestamp="2024-01-01T12:00:00",
                decision={},
                content_hash="hash123",
                verification_status=status,
            )
            assert evidence.verification_status == status

    def test_signed_evidence_with_signature(self):
        """Test evidence with signature data."""
        evidence = SignedEvidence(
            evidence_id="ev-sig",
            timestamp="2024-01-01T12:00:00",
            decision={"test": "data"},
            content_hash="sig-hash",
            signature="base64-signature",
            signer_certificate="PEM-cert",
            transparency_log_entry={"log_id": "rekor-123"},
            verification_status="signed",
        )

        assert evidence.signature == "base64-signature"
        assert evidence.signer_certificate == "PEM-cert"
        assert evidence.transparency_log_entry == {"log_id": "rekor-123"}
        assert evidence.verification_status == "signed"

    def test_signed_evidence_decision_as_dict(self):
        """Test decision field accepts dict."""
        decision_data = {"decision_id": "test-123", "decision": "allowed", "metadata": {"key": "value"}}

        evidence = SignedEvidence(
            evidence_id="ev-dict",
            timestamp="2024-01-01T12:00:00",
            decision=decision_data,
            content_hash="dict-hash",
        )

        assert evidence.decision == decision_data
        assert evidence.decision["metadata"]["key"] == "value"
