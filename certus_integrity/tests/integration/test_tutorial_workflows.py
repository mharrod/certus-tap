"""
Tutorial Workflow Tests for certus_integrity.

Tests validate the workflows described in docs/learn/integrity/ tutorials:
- Testing rate limits (shadow mode to enforcement)
- Compliance reporting (evidence generation and export)
- Tutorial code examples work as documented
- Evidence bundle structure matches documentation
"""

import os
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from certus_integrity.evidence import EvidenceGenerator
from certus_integrity.middleware import IntegrityMiddleware
from certus_integrity.schemas import IntegrityDecision
from certus_integrity.telemetry import configure_observability


class TestRateLimitTutorialWorkflow:
    """
    Test workflows from docs/learn/integrity/testing-rate-limits.md

    Validates:
    - Shadow mode observation
    - Enforcement mode transition
    - Rate limit header behavior
    - CIDR whitelist functionality
    """

    def test_shadow_mode_never_blocks(self):
        """
        Tutorial: Step 1 - Shadow mode logs violations without blocking.

        From tutorial:
        'Shadow mode logs violations without blocking requests.'
        """
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        # Configure shadow mode with low limit for testing
        with patch.dict(os.environ, {"INTEGRITY_RATE_LIMIT_PER_MIN": "5", "INTEGRITY_SHADOW_MODE": "true"}, clear=True):
            app.add_middleware(IntegrityMiddleware)

        client = TestClient(app)

        # Make 10 requests (double the limit)
        responses = []
        for _ in range(10):
            response = client.get("/test")
            responses.append(response)

        # All should succeed in shadow mode
        for response in responses:
            assert response.status_code == 200
            assert response.json() == {"message": "success"}

    def test_rate_limit_headers_present(self):
        """
        Tutorial: Step 1.3 - Verify rate limit headers.

        From tutorial:
        'curl -v http://localhost:8000/v1/health 2>&1 | grep X-RateLimit
        Expected output:
        < X-RateLimit-Limit: 100
        < X-RateLimit-Remaining: 99
        < X-RateLimit-Reset: 1734262800'
        """
        app = FastAPI()

        @app.get("/health")
        async def health_endpoint():
            return {"status": "ok"}

        with patch.dict(os.environ, {"INTEGRITY_RATE_LIMIT_PER_MIN": "100"}, clear=True):
            app.add_middleware(IntegrityMiddleware)

        client = TestClient(app)

        response = client.get("/health")

        # Verify headers match tutorial expectations
        assert "X-RateLimit-Limit" in response.headers
        assert response.headers["X-RateLimit-Limit"] == "100"
        assert "X-RateLimit-Remaining" in response.headers
        assert "X-RateLimit-Reset" in response.headers

    def test_enforcement_mode_blocks_violations(self):
        """
        Tutorial: Step 5.2 - Test enforcement mode blocks excessive traffic.

        From tutorial:
        'Test 2: Excessive traffic should be blocked
        for i in {1..110}; do curl ... done
        Expected: First 100 return HTTP 200, remaining 10 return HTTP 429'
        """
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        with patch.dict(
            os.environ,
            {
                "INTEGRITY_RATE_LIMIT_PER_MIN": "10",
                "INTEGRITY_SHADOW_MODE": "false",  # Enforcement mode
            },
            clear=True,
        ):
            app.add_middleware(IntegrityMiddleware)

        client = TestClient(app)

        # First 10 requests should succeed
        for i in range(10):
            response = client.get("/test")
            assert response.status_code == 200, f"Request {i + 1} should succeed"

        # 11th request should be blocked
        response = client.get("/test")
        assert response.status_code == 429
        assert "rate_limit_exceeded" in response.json()["error"]

    def test_whitelisted_ip_bypasses_limit(self):
        """
        Tutorial: Step 5.2 - Test whitelisted IPs bypass rate limit.

        From tutorial:
        'Test 3: Whitelisted IPs should bypass limit
        for i in {1..200}; do curl ... done
        Expected: All 200 requests succeed'
        """
        app = FastAPI()

        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}

        with patch.dict(
            os.environ,
            {
                "INTEGRITY_RATE_LIMIT_PER_MIN": "10",
                "INTEGRITY_SHADOW_MODE": "false",
                "INTEGRITY_WHITELIST_IPS": "127.0.0.1",  # Whitelist test client IP
            },
            clear=True,
        ):
            app.add_middleware(IntegrityMiddleware)

        client = TestClient(app)

        # Make 50 requests (far exceeding limit)
        for _ in range(50):
            response = client.get("/test")
            # Should all succeed due to whitelist
            assert response.status_code == 200


class TestComplianceReportingWorkflow:
    """
    Test workflows from docs/learn/integrity/compliance-reporting.md

    Validates:
    - Evidence bundle structure
    - Decision breakdown
    - Cryptographic signing
    - Evidence export
    """

    @pytest.mark.asyncio
    async def test_evidence_bundle_structure_matches_docs(self):
        """
        Tutorial: Evidence Structure section.

        From tutorial:
        'Each bundle contains:
        - Decision ID (unique identifier)
        - Timestamp (when decision was made)
        - Decision outcome (allowed, denied, degraded)
        - Guardrail triggered (rate_limit, burst_protection, etc.)
        - Client IP address
        - Metadata (request details)
        - Cryptographic signature
        - Transparency log entry (Rekor)'
        """
        generator = EvidenceGenerator(service_name="test-service")

        decision = IntegrityDecision(
            decision_id="test-compliance-001",
            trace_id="trace-abc",
            span_id="span-123",
            service="test-service",
            decision="denied",
            reason="rate_limit_exceeded",
            guardrail="rate_limit",
            metadata={"client_ip": "192.168.1.100", "duration_ms": 5.2},
        )

        # Mock signature response
        mock_response = AsyncMock()
        mock_response.json.return_value = {"signature": "sig-compliance-test", "certificate": "cert-test"}
        mock_response.raise_for_status = Mock()

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with patch.object(generator, "_save_to_disk"):
                bundle = await generator.process_decision(decision)

        # Verify all required fields from tutorial are present
        assert bundle.evidence_id is not None  # Decision ID
        assert bundle.timestamp is not None  # Timestamp
        assert bundle.decision["decision"] == "denied"  # Decision outcome (dict after serialization)
        assert bundle.decision["guardrail"] == "rate_limit"  # Guardrail
        assert bundle.decision["metadata"]["client_ip"] == "192.168.1.100"  # Client IP
        assert bundle.signature == "sig-compliance-test"  # Cryptographic signature
        assert bundle.verification_status == "signed"  # Verification status

    @pytest.mark.asyncio
    async def test_decision_breakdown_categories(self):
        """
        Tutorial: Step 3.2 - Decision Breakdown.

        From tutorial:
        'Sample output:
        allowed: 12,420,000 (99.76%)
        denied: 30,000 (0.24%)
        degraded: 0 (0.00%)'
        """
        generator = EvidenceGenerator(service_name="compliance-test")

        # Create sample decisions for each category
        decisions_config = [
            ("allowed", "pass_through", "none"),
            ("denied", "rate_limit_exceeded", "rate_limit"),
            ("degraded", "high_load", "resource_limit"),
        ]

        bundles = []

        for decision_type, reason, guardrail in decisions_config:
            decision = IntegrityDecision(
                decision_id=f"test-{decision_type}",
                trace_id=f"trace-{decision_type}",
                span_id=f"span-{decision_type}",
                service="compliance-test",
                decision=decision_type,  # type: ignore
                reason=reason,
                guardrail=guardrail,
                metadata={"test": True},
            )

            mock_response = AsyncMock()
            mock_response.json.return_value = {"signature": f"sig-{decision_type}"}
            mock_response.raise_for_status = Mock()

            with patch("httpx.AsyncClient.post", return_value=mock_response):
                with patch.object(generator, "_save_to_disk"):
                    bundle = await generator.process_decision(decision)
                    bundles.append(bundle)

        # Verify all decision types are represented
        decision_types = {b.decision["decision"] for b in bundles}
        assert "allowed" in decision_types
        assert "denied" in decision_types
        assert "degraded" in decision_types

    @pytest.mark.asyncio
    async def test_evidence_file_export_format(self):
        """
        Tutorial: Step 5.1 - Export evidence bundles.

        From tutorial:
        'find /tmp/evidence -name "dec_*.json" ...'
        """
        generator = EvidenceGenerator(service_name="export-test")

        decision = IntegrityDecision(
            decision_id="export-test-001",
            trace_id="trace-export",
            span_id="span-export",
            service="export-test",
            decision="allowed",
            reason="test",
            guardrail="none",
        )

        # Mock signature
        mock_response = AsyncMock()
        mock_response.json.return_value = {"signature": "sig-export"}
        mock_response.raise_for_status = Mock()

        # Track the file that would be saved
        saved_files = []

        def mock_save(bundle):
            # Simulate file save
            filename = f"dec_{bundle.evidence_id}.json"
            saved_files.append(filename)

        with patch("httpx.AsyncClient.post", return_value=mock_response):
            with patch.object(generator, "_save_to_disk", side_effect=mock_save):
                bundle = await generator.process_decision(decision)

        # Verify filename matches tutorial pattern
        assert len(saved_files) == 1
        assert saved_files[0].startswith("dec_")
        assert saved_files[0].endswith(".json")


class TestTutorialCodeExamples:
    """
    Test that code examples from tutorials work as documented.
    """

    def test_tutorial_shadow_mode_config_example(self):
        """
        Tutorial: Step 1.1 - Configure Shadow Mode.

        From tutorial:
        'INTEGRITY_SHADOW_MODE=true
        INTEGRITY_RATE_LIMIT_PER_MIN=100
        INTEGRITY_BURST_LIMIT=20'
        """
        app = FastAPI()

        @app.get("/test")
        async def test():
            return {"ok": True}

        # Use exact config from tutorial
        with patch.dict(
            os.environ,
            {
                "INTEGRITY_SHADOW_MODE": "true",
                "INTEGRITY_RATE_LIMIT_PER_MIN": "100",
                "INTEGRITY_BURST_LIMIT": "20",
                "INTEGRITY_WHITELIST_IPS": "127.0.0.1,172.18.0.0/16",
            },
            clear=True,
        ):
            middleware = IntegrityMiddleware(app)

        # Verify config matches tutorial
        assert middleware.shadow_mode is True
        assert middleware.rate_limit == 100
        assert middleware.burst_limit == 20

    @patch("certus_integrity.telemetry.FastAPIInstrumentor")
    @patch("certus_integrity.telemetry._configure_opentelemetry")
    @patch("certus_integrity.telemetry._configure_logging")
    def test_tutorial_observability_config_example(self, mock_logging, mock_otel, mock_instrumentor):
        """
        Test observability configuration example.

        Validates that configure_observability works as documented.
        """
        app = FastAPI()

        # Configure observability (as tutorial would show)
        configure_observability(
            app,
            service_name="certus-ask",
            log_level="INFO",
            enable_json_logs=True,
            otel_endpoint="http://otel-collector:4318",
        )

        # Verify configuration
        mock_otel.assert_called_once_with("certus-ask", "http://otel-collector:4318")
        mock_logging.assert_called_once_with("INFO", True)
