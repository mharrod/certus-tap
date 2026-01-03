"""Report formatting utilities for SAST scan results."""

from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Finding:
    """A single security finding from a SAST tool."""

    tool: str
    severity: str
    title: str
    file: str
    line: int | None = None
    message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ReportFormatter:
    """Parse and format SAST scan reports."""

    @staticmethod
    def parse_trivy(report_path: pathlib.Path) -> list[Finding]:
        """Parse Trivy JSON report.

        Args:
            report_path: Path to trivy.json

        Returns:
            List of findings
        """
        findings: list[Finding] = []

        if not report_path.exists():
            return findings

        try:
            with open(report_path) as f:
                data = json.load(f)

            # Trivy format: Results[].Misconfigurations, Vulnerabilities, etc.
            for result in data.get("Results", []):
                # Handle vulnerabilities
                for vuln in result.get("Vulnerabilities", []):
                    findings.append(
                        Finding(
                            tool="trivy",
                            severity=vuln.get("Severity", "UNKNOWN"),
                            title=vuln.get("Title", "Unknown vulnerability"),
                            file=result.get("Target", "unknown"),
                            message=vuln.get("Description", ""),
                        )
                    )

                # Handle misconfigurations
                for misconfig in result.get("Misconfigurations", []):
                    findings.append(
                        Finding(
                            tool="trivy",
                            severity=misconfig.get("Severity", "UNKNOWN"),
                            title=misconfig.get("Title", "Unknown misconfiguration"),
                            file=result.get("Target", "unknown"),
                            message=misconfig.get("Description", ""),
                        )
                    )

                # Handle secrets
                for secret in result.get("Secrets", []):
                    findings.append(
                        Finding(
                            tool="trivy",
                            severity="CRITICAL",
                            title=secret.get("Title", "Secret detected"),
                            file=result.get("Target", "unknown"),
                            line=secret.get("StartLine"),
                            message=f"Found {secret.get('Rule', 'unknown')} secret",
                        )
                    )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️  Error parsing Trivy report: {e}")

        return findings

    @staticmethod
    def parse_bandit(report_path: pathlib.Path) -> list[Finding]:
        """Parse Bandit JSON report.

        Args:
            report_path: Path to bandit.json

        Returns:
            List of findings
        """
        findings: list[Finding] = []

        if not report_path.exists():
            return findings

        try:
            with open(report_path) as f:
                data = json.load(f)

            for result in data.get("results", []):
                findings.append(
                    Finding(
                        tool="bandit",
                        severity=result.get("severity", "UNKNOWN").upper(),
                        title=result.get("issue_text", "Unknown issue"),
                        file=result.get("filename", "unknown"),
                        line=result.get("line_number"),
                        message=result.get("issue_cwe", {}).get("link", ""),
                    )
                )
        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️  Error parsing Bandit report: {e}")

        return findings

    @staticmethod
    def parse_ruff(report_path: pathlib.Path) -> list[Finding]:
        """Parse Ruff text report.

        Simple line-by-line parser for Ruff output.
        Format: file.py:line:col: CODE Message

        Args:
            report_path: Path to ruff.txt

        Returns:
            List of findings
        """
        findings: list[Finding] = []

        if not report_path.exists():
            return findings

        try:
            with open(report_path) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("Found"):
                        continue

                    # Parse: file.py:line:col: CODE Message
                    parts = line.split(":", 4)
                    if len(parts) >= 4:
                        file_path = parts[0]
                        try:
                            line_num = int(parts[1])
                        except ValueError:
                            continue

                        code_and_msg = parts[3].strip()
                        code, *msg_parts = code_and_msg.split(" ", 1)
                        message = " ".join(msg_parts) if msg_parts else ""

                        findings.append(
                            Finding(
                                tool="ruff",
                                severity="WARNING",  # Ruff doesn't assign severity
                                title=f"[{code}] {message}",
                                file=file_path,
                                line=line_num,
                                message=message,
                            )
                        )
        except Exception as e:
            print(f"⚠️  Error parsing Ruff report: {e}")

        return findings

    @staticmethod
    def format_human_readable(findings: list[Finding]) -> str:
        """Format findings as human-readable text.

        Args:
            findings: List of findings

        Returns:
            Formatted text
        """
        if not findings:
            return "✅ No findings detected."

        # Group by severity
        by_severity = {}
        for finding in findings:
            severity = finding.severity
            if severity not in by_severity:
                by_severity[severity] = []
            by_severity[severity].append(finding)

        output = []
        severity_order = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "WARNING", "INFO"]

        for severity in severity_order:
            if severity not in by_severity:
                continue

            items = by_severity[severity]
            output.append(f"\n{severity} ({len(items)} issues):")
            output.append("-" * 80)

            for finding in items:
                location = f"{finding.file}"
                if finding.line:
                    location += f":{finding.line}"

                output.append(f"  [{finding.tool}] {finding.title}")
                output.append(f"    Location: {location}")
                if finding.message:
                    output.append(f"    {finding.message}")
                output.append("")

        return "\n".join(output)

    @staticmethod
    def format_json(findings: list[Finding]) -> str:
        """Format findings as JSON.

        Args:
            findings: List of findings

        Returns:
            JSON string
        """
        return json.dumps(
            [f.to_dict() for f in findings],
            indent=2,
        )

    @staticmethod
    def aggregate_reports(
        report_dir: pathlib.Path,
    ) -> tuple[list[Finding], dict[str, int]]:
        """Aggregate findings from all report files.

        Args:
            report_dir: Directory containing scan reports

        Returns:
            Tuple of (all_findings, summary_stats)
        """
        all_findings: list[Finding] = []

        # Parse each report format
        all_findings.extend(ReportFormatter.parse_trivy(report_dir / "trivy.json"))
        all_findings.extend(ReportFormatter.parse_bandit(report_dir / "bandit.json"))
        all_findings.extend(ReportFormatter.parse_ruff(report_dir / "ruff.txt"))

        # Compute summary
        summary = {
            "total": len(all_findings),
            "critical": sum(1 for f in all_findings if f.severity == "CRITICAL"),
            "high": sum(1 for f in all_findings if f.severity == "HIGH"),
            "medium": sum(1 for f in all_findings if f.severity == "MEDIUM"),
            "low": sum(1 for f in all_findings if f.severity == "LOW"),
            "warning": sum(1 for f in all_findings if f.severity == "WARNING"),
        }

        return all_findings, summary
