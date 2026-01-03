"""Unified security scan data models.

This module defines the UnifiedSecurityScan model, which represents findings
from any security scanning tool in a consistent, tool-agnostic format.

All security tools (SARIF, Bandit, OpenGrep, Trivy, etc.) are normalized to
this format for consistent indexing and querying.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class UnifiedLocation(BaseModel):
    """Location information for a security finding.

    Attributes:
        file_path: Path to the file containing the finding
        line_start: Starting line number (1-indexed)
        line_end: Ending line number (optional, for multi-line findings)
        code_snippet: Optional code snippet showing the vulnerability
        column_start: Starting column number (optional)
        column_end: Ending column number (optional)
    """

    file_path: str = Field(..., description="Path to file with finding")
    line_start: int = Field(..., description="Starting line number (1-indexed)")
    line_end: Optional[int] = Field(None, description="Ending line number")
    code_snippet: Optional[str] = Field(None, description="Code snippet showing vulnerability")
    column_start: Optional[int] = Field(None, description="Starting column number")
    column_end: Optional[int] = Field(None, description="Ending column number")


class UnifiedFinding(BaseModel):
    """A security finding from any scanning tool.

    Represents a single vulnerability, code quality issue, secret, or other
    security-related finding. Normalized across all tool formats.

    Attributes:
        id: Unique identifier for this finding (tool-specific ID)
        title: Human-readable title/summary of the finding
        severity: Normalized severity level (CRITICAL, HIGH, MEDIUM, LOW, INFO)
        type: Category of finding (vulnerability, code_quality, secret, dependency, config)
        location: Where the finding was detected (file, line, column)
        description: Detailed description of the issue
        remediation: How to fix the issue (optional)
        references: External references (CVE IDs, docs, etc.) (optional)
        tags: Custom tags for categorization (optional)
        raw_data: Original tool-specific data (preserve for debugging)
    """

    id: str = Field(..., description="Unique identifier for this finding")
    title: str = Field(..., description="Human-readable title")
    severity: str = Field(..., description="CRITICAL | HIGH | MEDIUM | LOW | INFO")
    type: str = Field(..., description="vulnerability | code_quality | secret | dependency | config")
    location: Optional[UnifiedLocation] = Field(None, description="Where the finding was detected")
    description: str = Field(..., description="Detailed description")
    remediation: Optional[str] = Field(None, description="How to fix it")
    references: Optional[list[str]] = Field(None, description="CVE IDs, external links")
    tags: Optional[list[str]] = Field(None, description="Custom categorization tags")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Original tool data")


class UnifiedDependency(BaseModel):
    """A software dependency/package found in a scan.

    Used for SBOM-like data from security tools that scan dependencies.

    Attributes:
        name: Package/dependency name
        version: Version string
        license: License type (optional)
        vulnerabilities: List of CVE IDs affecting this dependency (optional)
        raw_data: Original tool-specific data
    """

    name: str = Field(..., description="Package name")
    version: str = Field(..., description="Version string")
    license: Optional[str] = Field(None, description="License type")
    vulnerabilities: Optional[list[str]] = Field(None, description="CVE IDs")
    raw_data: dict[str, Any] = Field(default_factory=dict, description="Original tool data")


class ScanMetadata(BaseModel):
    """Metadata about the security scan.

    Attributes:
        tool_name: Name of the scanning tool (sarif, bandit, opengrep, trivy)
        tool_version: Version of the scanning tool
        scan_timestamp: When the scan was performed
        scan_target: What was scanned (repo, image, codebase, etc.)
    """

    tool_name: str = Field(..., description="Scanner tool name")
    tool_version: Optional[str] = Field(None, description="Scanner version")
    scan_timestamp: Optional[datetime] = Field(None, description="When scan was performed")
    scan_target: Optional[str] = Field(None, description="What was scanned")


class UnifiedSecurityScan(BaseModel):
    """Unified representation of security scan results.

    This is the standard format for all security tool outputs. Each tool's
    native format is parsed and normalized to this model.

    Tools: SARIF, Bandit, OpenGrep, Trivy, and any custom JSON via JSONPath mapping.

    Attributes:
        metadata: Information about the scan and tool
        findings: List of security findings
        dependencies: Optional list of dependencies (for SBOM-related data)
    """

    metadata: ScanMetadata = Field(..., description="Scan metadata")
    findings: list[UnifiedFinding] = Field(default_factory=list, description="Security findings")
    dependencies: Optional[list[UnifiedDependency]] = Field(None, description="Dependencies found in scan")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "metadata": {
                    "tool_name": "sarif",
                    "tool_version": "2.1.0",
                    "scan_timestamp": "2025-01-15T10:30:00Z",
                    "scan_target": "src/",
                },
                "findings": [
                    {
                        "id": "RULE001",
                        "title": "SQL Injection Vulnerability",
                        "severity": "CRITICAL",
                        "type": "vulnerability",
                        "location": {
                            "file_path": "src/auth.py",
                            "line_start": 42,
                            "code_snippet": 'query = f"SELECT * FROM users WHERE id={user_id}"',
                        },
                        "description": "User input used directly in SQL query without parameterization",
                        "remediation": "Use parameterized queries or prepared statements",
                        "references": ["CWE-89", "OWASP-A01:2021"],
                        "tags": ["injection", "database"],
                        "raw_data": {},
                    }
                ],
            }
        }
