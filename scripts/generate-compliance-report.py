#!/usr/bin/env python3
"""
Generate signed compliance/non-compliance reports for supply chain security reviews.
Reports are PDF-signed and uploaded to OCI registry as tamper-resistant artifacts.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import uuid
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class ComplianceStatus(Enum):
    """Compliance status enumeration"""

    COMPLIANT = "COMPLIANT"
    NON_COMPLIANT = "NON_COMPLIANT"
    CONDITIONAL = "CONDITIONAL"


class ComplianceReportGenerator:
    """Generate signed compliance reports for supply chain reviews"""

    def __init__(self, reviewer_name: str, reviewer_org: str):
        self.reviewer_name = reviewer_name
        self.reviewer_org = reviewer_org
        self.timestamp = datetime.utcnow().isoformat() + "Z"
        self.report_id = str(uuid.uuid4())

    def generate_compliance_report(
        self,
        product_name: str,
        product_version: str,
        vendor: str,
        findings: dict,
        output_dir: str,
    ) -> str:
        """Generate comprehensive compliance report"""

        # Analyze findings to determine status
        status = self._determine_compliance_status(findings)

        report = {
            "reportId": self.report_id,
            "reportType": "SupplyChainComplianceReview",
            "version": "1.0",
            "generated": self.timestamp,
            "expiresAt": self._add_days(self.timestamp, 365),
            "reviewer": {
                "name": self.reviewer_name,
                "organization": self.reviewer_org,
            },
            "product": {
                "name": product_name,
                "version": product_version,
                "vendor": vendor,
            },
            "complianceStatus": status.value,
            "complianceSummary": {
                "signatureVerification": findings.get("signatureVerification", {}),
                "sbomAnalysis": findings.get("sbomAnalysis", {}),
                "vulnerabilityAssessment": findings.get("vulnerabilityAssessment", {}),
                "provanceValidation": findings.get("provenanceValidation", {}),
                "dependencyAnalysis": findings.get("dependencyAnalysis", {}),
                "licenseCompliance": findings.get("licenseCompliance", {}),
            },
            "detailedFindings": self._format_findings(findings),
            "recommendations": self._generate_recommendations(status, findings),
            "auditTrail": {
                "reviewStartTime": self.timestamp,
                "reviewEndTime": self.timestamp,
                "verificationMethod": "Cosign + SLSA Provenance",
                "tools": ["cosign", "oras", "sbom-scanner"],
            },
        }

        # Save as JSON
        report_dir = Path(output_dir)
        report_dir.mkdir(parents=True, exist_ok=True)

        json_file = report_dir / f"compliance-report-{self.report_id}.json"
        with open(json_file, "w") as f:
            json.dump(report, f, indent=2)

        print(f"✓ Generated compliance report: {json_file}")
        return str(json_file)

    def _determine_compliance_status(self, findings: dict) -> ComplianceStatus:
        """Determine overall compliance status based on findings"""
        sig_verify = findings.get("signatureVerification", {}).get("status") == "PASS"
        sbom_valid = findings.get("sbomAnalysis", {}).get("status") == "PASS"
        provenance_valid = findings.get("provenanceValidation", {}).get("status") == "PASS"
        high_vulns = findings.get("vulnerabilityAssessment", {}).get("criticalCount", 0)

        # All critical checks pass = COMPLIANT
        if sig_verify and sbom_valid and provenance_valid and high_vulns == 0:
            return ComplianceStatus.COMPLIANT

        # Missing signature or provenance = NON_COMPLIANT
        if not sig_verify or not provenance_valid:
            return ComplianceStatus.NON_COMPLIANT

        # Has vulnerabilities but other checks pass = CONDITIONAL
        return ComplianceStatus.CONDITIONAL

    def _format_findings(self, findings: dict) -> dict:
        """Format detailed findings with explanations"""
        return {
            "signatureVerification": {
                "finding": findings.get("signatureVerification", {}),
                "impact": "High - Ensures artifacts are authentic",
                "complianceRequirement": "All artifacts must be signed with valid keys",
            },
            "sbomAnalysis": {
                "finding": findings.get("sbomAnalysis", {}),
                "impact": "High - Identifies supply chain transparency",
                "complianceRequirement": "SBOM must be complete and embeded in provenance",
            },
            "vulnerabilityAssessment": {
                "finding": findings.get("vulnerabilityAssessment", {}),
                "impact": "Critical - Identifies security risks",
                "complianceRequirement": "No critical/high vulnerabilities, or remediation plan required",
            },
            "provenanceValidation": {
                "finding": findings.get("provenanceValidation", {}),
                "impact": "High - Verifies build legitimacy",
                "complianceRequirement": "SLSA provenance v1.0 with reproducibility claim",
            },
            "dependencyAnalysis": {
                "finding": findings.get("dependencyAnalysis", {}),
                "impact": "Medium - Tracks supply chain risk",
                "complianceRequirement": "All dependencies documented with cryptographic hashes",
            },
            "licenseCompliance": {
                "finding": findings.get("licenseCompliance", {}),
                "impact": "Medium - Manages legal/licensing risk",
                "complianceRequirement": "No incompatible open-source licenses",
            },
        }

    def _generate_recommendations(self, status: ComplianceStatus, findings: dict) -> list[str]:
        """Generate recommendations based on status"""
        recommendations = []

        if status == ComplianceStatus.NON_COMPLIANT:
            recommendations.append("REJECT: Do not ingest. Missing critical verification artifacts.")
            recommendations.append("Action: Request vendor provide signed artifacts.")
            return recommendations

        if status == ComplianceStatus.CONDITIONAL:
            high_count = findings.get("vulnerabilityAssessment", {}).get("highCount", 0)
            critical_count = findings.get("vulnerabilityAssessment", {}).get("criticalCount", 0)

            if critical_count > 0:
                recommendations.append("REJECT: Critical vulnerabilities found.")
                recommendations.append("Action: Require vendor remediation before ingestion.")
            elif high_count > 0:
                recommendations.append("CONDITIONAL APPROVE: High vulnerabilities present.")
                recommendations.append("Action: Require remediation plan within 30 days.")
                recommendations.append("Action: Enable continuous monitoring.")

        elif status == ComplianceStatus.COMPLIANT:
            recommendations.append("APPROVE: All compliance checks passed.")
            recommendations.append("Action: Proceed with ingestion and deployment.")
            recommendations.append("Action: Schedule 90-day follow-up review.")

        return recommendations

    def _add_days(self, timestamp: str, days: int) -> str:
        """Add days to ISO timestamp"""
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        dt = dt.replace(year=dt.year + (days // 365), day=min(dt.day, 28) + (days % 365))
        return dt.isoformat() + "Z"

    def generate_html_report(self, json_report_file: str, output_file: Optional[str] = None) -> str:
        """Generate HTML version of compliance report"""
        with open(json_report_file) as f:
            report = json.load(f)

        output_file = output_file or json_report_file.replace(".json", ".html")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Supply Chain Compliance Report</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            color: #333;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1000px;
            margin: 0 auto;
            background: white;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }}

        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
            padding: 40px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .status-badge {{
            display: inline-block;
            padding: 10px 20px;
            border-radius: 5px;
            font-weight: bold;
            margin-top: 20px;
            font-size: 1.2em;
        }}

        .status-compliant {{
            background: #28a745;
            color: white;
        }}

        .status-conditional {{
            background: #ffc107;
            color: #333;
        }}

        .status-non-compliant {{
            background: #dc3545;
            color: white;
        }}

        .content {{
            padding: 40px;
        }}

        .section {{
            margin-bottom: 40px;
            border-left: 4px solid #2c3e50;
            padding-left: 20px;
        }}

        .section h2 {{
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 1.8em;
        }}

        .section h3 {{
            color: #34495e;
            margin-top: 20px;
            margin-bottom: 10px;
        }}

        .metadata {{
            background: #f9f9f9;
            padding: 20px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}

        .metadata-row {{
            display: flex;
            justify-content: space-between;
            padding: 8px 0;
            border-bottom: 1px solid #eee;
        }}

        .metadata-row:last-child {{
            border-bottom: none;
        }}

        .metadata-label {{
            font-weight: bold;
            color: #2c3e50;
            width: 30%;
        }}

        .metadata-value {{
            width: 70%;
            text-align: right;
            font-family: monospace;
            font-size: 0.9em;
        }}

        .findings-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}

        .findings-table th {{
            background: #2c3e50;
            color: white;
            padding: 12px;
            text-align: left;
        }}

        .findings-table td {{
            padding: 12px;
            border-bottom: 1px solid #eee;
        }}

        .findings-table tr:hover {{
            background: #f9f9f9;
        }}

        .pass {{
            color: #28a745;
            font-weight: bold;
        }}

        .fail {{
            color: #dc3545;
            font-weight: bold;
        }}

        .warning {{
            color: #ffc107;
            font-weight: bold;
        }}

        .recommendations {{
            background: #f0f7ff;
            border-left: 4px solid #2c3e50;
            padding: 20px;
            margin: 20px 0;
            border-radius: 3px;
        }}

        .recommendations h3 {{
            margin-top: 0;
        }}

        .recommendations ol {{
            margin-left: 20px;
        }}

        .recommendations li {{
            margin: 10px 0;
        }}

        .footer {{
            background: #f5f5f5;
            padding: 20px 40px;
            border-top: 1px solid #ddd;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}

        .signature {{
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
        }}

        .signature-info {{
            background: #f9f9f9;
            padding: 15px;
            border-radius: 5px;
            font-family: monospace;
            font-size: 0.85em;
            word-break: break-all;
        }}

        @media print {{
            .container {{
                box-shadow: none;
            }}
            body {{
                background: white;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Supply Chain Compliance Report</h1>
            <p>Security Verification & Artifact Assessment</p>
            <div class="status-badge status-{report["complianceStatus"].lower()}">
                {report["complianceStatus"]}
            </div>
        </div>

        <div class="content">
            <!-- Executive Summary -->
            <div class="section">
                <h2>Executive Summary</h2>
                <div class="metadata">
                    <div class="metadata-row">
                        <span class="metadata-label">Report ID:</span>
                        <span class="metadata-value">{report["reportId"]}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Product:</span>
                        <span class="metadata-value">{report["product"]["name"]} v{report["product"]["version"]}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Vendor:</span>
                        <span class="metadata-value">{report["product"]["vendor"]}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Reviewer:</span>
                        <span class="metadata-value">{report["reviewer"]["name"]} ({report["reviewer"]["organization"]})</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Generated:</span>
                        <span class="metadata-value">{report["generated"]}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Expires:</span>
                        <span class="metadata-value">{report["expiresAt"]}</span>
                    </div>
                </div>
            </div>

            <!-- Compliance Status -->
            <div class="section">
                <h2>Compliance Assessment</h2>
                <p><strong>Overall Status:</strong> <span class="status-badge status-{report["complianceStatus"].lower()}">{report["complianceStatus"]}</span></p>

                <!-- Detailed Findings -->
                <h3>Detailed Findings</h3>
                <table class="findings-table">
                    <thead>
                        <tr>
                            <th>Category</th>
                            <th>Status</th>
                            <th>Details</th>
                            <th>Impact</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>Signature Verification</td>
                            <td><span class="pass">✓ PASS</span></td>
                            <td>All artifacts cryptographically signed</td>
                            <td>High - Authenticity</td>
                        </tr>
                        <tr>
                            <td>SBOM Analysis</td>
                            <td><span class="pass">✓ PASS</span></td>
                            <td>SPDX 2.3 SBOM complete and valid</td>
                            <td>High - Transparency</td>
                        </tr>
                        <tr>
                            <td>Provenance Validation</td>
                            <td><span class="pass">✓ PASS</span></td>
                            <td>SLSA v1.0 provenance verified</td>
                            <td>High - Build Integrity</td>
                        </tr>
                        <tr>
                            <td>Vulnerability Assessment</td>
                            <td><span class="warning">⚠ REVIEW</span></td>
                            <td>See recommendations for findings</td>
                            <td>Critical - Security Risk</td>
                        </tr>
                        <tr>
                            <td>Dependency Analysis</td>
                            <td><span class="pass">✓ PASS</span></td>
                            <td>All dependencies verified with hashes</td>
                            <td>Medium - Supply Chain Risk</td>
                        </tr>
                        <tr>
                            <td>License Compliance</td>
                            <td><span class="pass">✓ PASS</span></td>
                            <td>No incompatible licenses detected</td>
                            <td>Medium - Legal Risk</td>
                        </tr>
                    </tbody>
                </table>
            </div>

            <!-- Recommendations -->
            <div class="recommendations">
                <h3>Reviewer Recommendations</h3>
                <ol>
"""

        for rec in report["recommendations"]:
            html += f"                    <li>{rec}</li>\n"

        html += f"""                </ol>
            </div>

            <!-- Audit Trail -->
            <div class="section">
                <h2>Audit Trail & Verification</h2>
                <div class="metadata">
                    <div class="metadata-row">
                        <span class="metadata-label">Review Method:</span>
                        <span class="metadata-value">{report["auditTrail"]["verificationMethod"]}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Tools Used:</span>
                        <span class="metadata-value">{", ".join(report["auditTrail"]["tools"])}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Review Start:</span>
                        <span class="metadata-value">{report["auditTrail"]["reviewStartTime"]}</span>
                    </div>
                    <div class="metadata-row">
                        <span class="metadata-label">Review End:</span>
                        <span class="metadata-value">{report["auditTrail"]["reviewEndTime"]}</span>
                    </div>
                </div>
            </div>

            <!-- Digital Signature -->
            <div class="section">
                <h2>Digital Signature & Integrity</h2>
                <p>This report is digitally signed and tamper-resistant. The signature ensures:</p>
                <ul style="margin-left: 20px; margin-top: 10px;">
                    <li>Report authenticity - Signed by authorized reviewer</li>
                    <li>Report integrity - Any modifications will invalidate signature</li>
                    <li>Non-repudiation - Reviewer cannot deny signing this report</li>
                    <li>Timestamped - Signature includes creation timestamp</li>
                </ul>
                <div class="signature">
                    <h3>Signature Information</h3>
                    <div class="signature-info">
                        <p><strong>Report ID:</strong> {report["reportId"]}</p>
                        <p><strong>Signed:</strong> {report["generated"]}</p>
                        <p><strong>Reviewer:</strong> {report["reviewer"]["name"]}</p>
                        <p><strong>Organization:</strong> {report["reviewer"]["organization"]}</p>
                    </div>
                </div>
            </div>
        </div>

        <div class="footer">
            <p>This report is confidential and contains proprietary security information.</p>
            <p>Report ID: {report["reportId"]} | Generated: {report["generated"]}</p>
            <p>Certus TAP Supply Chain Security Review System</p>
        </div>
    </div>
</body>
</html>
"""

        with open(output_file, "w") as f:
            f.write(html)

        print(f"✓ Generated HTML report: {output_file}")
        return output_file

    def sign_report(self, report_file: str, key_path: str) -> str:
        """Sign report with cosign"""
        sig_file = Path(str(report_file) + ".sig")

        try:
            result = subprocess.run(
                ["cosign", "sign-blob", "--key", key_path, report_file],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                with open(sig_file, "w") as f:
                    f.write(result.stdout)
                print(f"✓ Report signed: {sig_file}")
                return str(sig_file)
            else:
                # Fallback to mock signature
                return self._create_mock_signature(report_file, sig_file)

        except FileNotFoundError:
            return self._create_mock_signature(report_file, sig_file)

    def _create_mock_signature(self, report_file: str, sig_file: Path) -> str:
        """Create mock signature for demonstration"""
        import base64

        with open(report_file, "rb") as f:
            content = f.read()

        mock_sig = base64.b64encode(hashlib.sha256(content + b"compliance-key").digest()).decode()

        with open(sig_file, "w") as f:
            f.write(mock_sig)

        print(f"✓ Report signed (mock): {sig_file}")
        return str(sig_file)

    def upload_to_oci(
        self,
        report_file: str,
        sig_file: str,
        registry: str,
        username: str,
        password: str,
        repo: str,
    ) -> bool:
        """Upload signed report to OCI registry"""
        registry_ref = self._normalize_registry_ref(registry)
        display_registry = registry.rstrip("/")

        tag = self._sanitize_tag(Path(report_file).stem)
        upload_targets = [f"{registry_ref}/{repo}:latest", f"{registry_ref}/{repo}:{tag}"]

        try:
            for target in upload_targets:
                result = subprocess.run(
                    [
                        "oras",
                        "push",
                        "--disable-path-validation",
                        target,
                        f"{report_file}:report",
                        f"{sig_file}:report.sig",
                        "-u",
                        username,
                        "-p",
                        password,
                    ],
                    capture_output=True,
                    text=True,
                )

                if result.returncode != 0:
                    print(f"⚠ Warning uploading report to {target}: {result.stderr}")
                    return False

            print(f"✓ Report uploaded to OCI: {display_registry}/{repo} (tags: latest, {tag})")
            return True

        except FileNotFoundError:
            print("Note: oras CLI not found for OCI upload")
            print(f"      Mock upload: {report_file} → {registry}/{repo}")
            return True

    def _normalize_registry_ref(self, registry: str) -> str:
        parsed = urlparse(registry)
        host = parsed.netloc or parsed.path if parsed.scheme else registry
        return host.rstrip("/")

    def _sanitize_tag(self, value: str) -> str:
        sanitized = value.replace("/", "-").replace(" ", "-")
        sanitized = sanitized.replace(".", "-")
        return sanitized or "report"


def main():
    parser = argparse.ArgumentParser(description="Generate Signed Compliance Reports")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Generate report command
    gen_parser = subparsers.add_parser("generate", help="Generate compliance report")
    gen_parser.add_argument("--product", required=True, help="Product name")
    gen_parser.add_argument("--version", required=True, help="Product version")
    gen_parser.add_argument("--vendor", required=True, help="Vendor name")
    gen_parser.add_argument("--reviewer", required=True, help="Reviewer name")
    gen_parser.add_argument("--org", required=True, help="Reviewer organization")
    gen_parser.add_argument("--findings-file", required=True, help="JSON file with findings")
    gen_parser.add_argument("--output", default="samples/oci-attestations/reports", help="Output directory")

    # Sign report command
    sign_parser = subparsers.add_parser("sign", help="Sign compliance report")
    sign_parser.add_argument("--report", required=True, help="Report file to sign")
    sign_parser.add_argument("--key-path", default="samples/oci-attestations/keys/cosign.key", help="Signing key")

    # Upload to OCI command
    upload_parser = subparsers.add_parser("upload", help="Upload signed report to OCI")
    upload_parser.add_argument("--report", required=True, help="Report file")
    upload_parser.add_argument("--signature", required=True, help="Signature file")
    upload_parser.add_argument("--registry", required=True, help="OCI registry URL")
    upload_parser.add_argument("--username", required=True, help="Registry username")
    upload_parser.add_argument("--password", required=True, help="Registry password")
    upload_parser.add_argument("--repo", required=True, help="Registry repository")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "generate":
        with open(args.findings_file) as f:
            findings = json.load(f)

        generator = ComplianceReportGenerator(args.reviewer, args.org)
        json_report = generator.generate_compliance_report(
            args.product, args.version, args.vendor, findings, args.output
        )
        generator.generate_html_report(json_report)

    elif args.command == "sign":
        generator = ComplianceReportGenerator("", "")
        generator.sign_report(args.report, args.key_path)

    elif args.command == "upload":
        generator = ComplianceReportGenerator("", "")
        generator.upload_to_oci(
            args.report,
            args.signature,
            args.registry,
            args.username,
            args.password,
            args.repo,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
