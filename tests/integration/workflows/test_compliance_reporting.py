"""Integration tests for compliance report generation and signing.

This test suite validates the compliance reporting workflow described in
docs/learn/trust/vendor-review.md Step 7, including report generation,
signing, and distribution.

Tutorial reference: docs/learn/trust/vendor-review.md (Step 7)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# Test data
SAMPLES_ROOT = Path(__file__).resolve().parents[3] / "samples"
KEYS_DIR = SAMPLES_ROOT / "oci-attestations/keys"
REPORTS_DIR = SAMPLES_ROOT / "oci-attestations/reports"


def test_create_compliance_findings_json() -> None:
    """
    Test Step 7.1: Create compliance findings JSON.

    Validates:
    - Findings structure is correct
    - All required sections present
    - JSON is valid
    """
    findings = {
        "signatureVerification": {
            "status": "PASS",
            "details": "All artifacts verified",
            "trustUploadPermission": "test-permission-123",
        },
        "sbomAnalysis": {
            "status": "PASS",
            "format": "SPDX 2.3",
            "packageCount": 5,
        },
        "provenanceValidation": {
            "status": "PASS",
            "format": "SLSA v1.0",
            "reproducible": True,
        },
        "vulnerabilityAssessment": {
            "status": "CONDITIONAL",
            "highCount": 2,
            "findings": [
                {"id": "CWE-89", "severity": "HIGH"},
                {"id": "CWE-78", "severity": "HIGH"},
            ],
        },
    }

    # Validate structure
    assert "signatureVerification" in findings
    assert "sbomAnalysis" in findings
    assert "provenanceValidation" in findings
    assert "vulnerabilityAssessment" in findings

    # Validate JSON serializable
    json_str = json.dumps(findings, indent=2)
    assert json_str

    print("✓ Compliance findings structure validated")


def test_generate_compliance_report() -> None:
    """
    Test Step 7.2: Generate JSON + HTML reports.

    Validates:
    - Report generation command works
    - JSON report created
    - HTML report created
    - Reports contain expected data
    """
    # TODO: Requires `just generate-compliance-report` command
    pytest.skip("Requires compliance report generation script")

    # Example implementation:
    # REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    #
    # result = subprocess.run(
    #     [
    #         "just", "generate-compliance-report",
    #         "Test Product",
    #         "Test Vendor",
    #         "Security Team",
    #         "Test Org",
    #         "/tmp/test-findings.json",
    #         str(REPORTS_DIR),
    #     ],
    #     capture_output=True,
    #     text=True,
    # )
    #
    # assert result.returncode == 0
    #
    # # Find generated reports
    # json_reports = list(REPORTS_DIR.glob("compliance-report-*.json"))
    # html_reports = list(REPORTS_DIR.glob("compliance-report-*.html"))
    #
    # assert len(json_reports) > 0, "JSON report not generated"
    # assert len(html_reports) > 0, "HTML report not generated"


def test_sign_compliance_report() -> None:
    """
    Test Step 7.3: Sign compliance report with cosign.

    Validates:
    - Signing command succeeds
    - Signature file created
    - Signature is valid
    """
    # TODO: Requires generated report and cosign
    pytest.skip("Requires generated compliance report and cosign")

    # Example implementation:
    # report_file = REPORTS_DIR / "test-compliance-report.json"
    # private_key = KEYS_DIR / "cosign.key"
    #
    # if not all([report_file.exists(), private_key.exists()]):
    #     pytest.skip("Test files not available")
    #
    # result = subprocess.run(
    #     [
    #         "cosign", "sign-blob",
    #         "--key", str(private_key),
    #         "--output-signature", f"{report_file}.sig",
    #         str(report_file),
    #     ],
    #     capture_output=True,
    #     text=True,
    #     env={"COSIGN_PASSWORD": "", "COSIGN_YES": "true"},
    # )
    #
    # assert result.returncode == 0
    # assert Path(f"{report_file}.sig").exists()


def test_verify_signed_compliance_report() -> None:
    """
    Verify signed compliance report.

    Validates:
    - Signature verification succeeds
    - Public key matches
    - Report integrity preserved
    """
    # TODO: Requires signed report
    pytest.skip("Requires signed compliance report")

    # Example implementation:
    # report_file = REPORTS_DIR / "test-compliance-report.json"
    # sig_file = Path(f"{report_file}.sig")
    # public_key = KEYS_DIR / "cosign.pub"
    #
    # result = subprocess.run(
    #     [
    #         "cosign", "verify-blob",
    #         "--insecure-ignore-tlog",
    #         "--key", str(public_key),
    #         "--signature", str(sig_file),
    #         str(report_file),
    #     ],
    #     capture_output=True,
    #     text=True,
    # )
    #
    # assert result.returncode == 0


def test_upload_compliance_report_to_oci() -> None:
    """
    Test Step 7.4: Upload compliance report to OCI registry.

    Validates:
    - Upload command succeeds
    - Report accessible via ORAS pull
    """
    # TODO: Requires OCI registry and signed report
    pytest.skip("Requires OCI registry and signed report")

    # Example implementation:
    # result = subprocess.run(
    #     [
    #         "just", "upload-compliance-report",
    #         str(REPORTS_DIR / "test-report.json"),
    #         str(REPORTS_DIR / "test-report.json.sig"),
    #         "http://localhost:5000",
    #         "", "",  # username, password
    #         "product-acquisition/compliance-reports",
    #     ],
    #     capture_output=True,
    #     text=True,
    # )
    #
    # assert result.returncode == 0


def test_pull_and_verify_compliance_report_from_oci() -> None:
    """
    Test Step 7.5: Pull and verify report from OCI.

    Validates:
    - Can pull report from registry
    - Signature verification succeeds
    - Report content matches original
    """
    # TODO: Requires uploaded report in OCI
    pytest.skip("Requires report uploaded to OCI registry")


def test_compliance_report_contains_trust_reference() -> None:
    """
    Validate compliance report references Trust upload permission.

    Validates:
    - Upload permission ID present
    - Trust verification proof referenced
    - Audit trail complete
    """
    # TODO: Requires generated report
    pytest.skip("Requires generated compliance report")

    # Example implementation:
    # report_file = REPORTS_DIR / "test-compliance-report.json"
    # with report_file.open() as f:
    #     report = json.load(f)
    #
    # assert "trustUploadPermission" in report["signatureVerification"]
    # assert report["signatureVerification"]["trustUploadPermission"]


# NOTE: Additional tests to implement:
# - test_generate_html_report_formatting()
# - test_report_includes_all_findings()
# - test_report_versioning()
# - test_multiple_report_formats()
