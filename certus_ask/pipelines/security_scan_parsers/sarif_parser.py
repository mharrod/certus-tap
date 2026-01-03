"""SARIF (Static Analysis Results Interchange Format) parser.

Parses SARIF 2.1.0 compliant security scan results into UnifiedSecurityScan format.

SARIF is a standardized format used by many security tools including:
- Bandit (Python security)
- GitHub CodeQL
- Microsoft security analyzers
- SonarQube
- And many others
"""

from typing import Any

import structlog

from certus_ask.pipelines.security_scan_parsers.base import SecurityScanParser
from certus_ask.pipelines.security_scan_parsers.severity_mapping import normalize_severity
from certus_ask.schemas.unified_security_scan import (
    ScanMetadata,
    UnifiedFinding,
    UnifiedLocation,
    UnifiedSecurityScan,
)

logger = structlog.get_logger(__name__)


class SarifParser(SecurityScanParser):
    """Parser for SARIF (Static Analysis Results Interchange Format).

    SARIF 2.1.0 is the standard format for security analysis results.
    This parser extracts findings and metadata from SARIF JSON files.

    Reference: https://sarifweb.azurewebsites.net/
    """

    tool_name = "sarif"
    supported_versions = ["2.1.0", "2.0.0"]

    def validate(self, raw_json: dict[str, Any]) -> bool:
        """Check if JSON is SARIF format.

        SARIF files have:
        - A "$schema" field containing "sarif"
        - A "version" field (typically "2.1.0")
        - A "runs" array

        Args:
            raw_json: JSON data to validate

        Returns:
            True if appears to be SARIF format
        """
        try:
            schema = raw_json.get("$schema", "")
            version = raw_json.get("version", "")
            has_runs = "runs" in raw_json

            is_sarif = "sarif" in schema.lower() and has_runs
            logger.debug(
                "sarif_parser.validate",
                is_sarif=is_sarif,
                schema_found=bool(schema),
                version_found=bool(version),
                has_runs=has_runs,
            )
            return is_sarif
        except (AttributeError, TypeError):
            return False

    def parse(self, raw_json: dict[str, Any]) -> UnifiedSecurityScan:
        """Parse SARIF JSON into UnifiedSecurityScan.

        Args:
            raw_json: SARIF JSON data

        Returns:
            UnifiedSecurityScan with normalized findings

        Raises:
            ValueError: If SARIF structure is invalid
            KeyError: If required fields are missing
        """
        logger.info("sarif_parser.parse_start")

        # Extract runs (SARIF can have multiple runs)
        runs = raw_json.get("runs", [])
        if not runs:
            logger.warning("sarif_parser.no_runs")
            return UnifiedSecurityScan(
                metadata=ScanMetadata(tool_name="sarif"),
                findings=[],
            )

        # Use first run (most common case)
        run = runs[0]

        # Extract metadata
        tool_info = run.get("tool", {})
        driver = tool_info.get("driver", {})
        tool_name = driver.get("name", "unknown")
        tool_version = driver.get("version", "unknown")

        metadata = ScanMetadata(
            tool_name="sarif",
            tool_version=f"{tool_name}:{tool_version}",
            scan_target=raw_json.get("properties", {}).get("scanTarget"),
        )

        # Extract findings
        results = run.get("results", [])
        findings = []

        for result in results:
            finding = self._parse_result(result)
            findings.append(finding)

        logger.info("sarif_parser.parse_complete", finding_count=len(findings))

        return UnifiedSecurityScan(
            metadata=metadata,
            findings=findings,
        )

    def _parse_result(self, result: dict[str, Any]) -> UnifiedFinding:
        """Parse a single SARIF result into UnifiedFinding.

        Args:
            result: SARIF result object

        Returns:
            UnifiedFinding
        """
        # Extract basic fields
        finding_id = result.get("ruleId", result.get("guid", "unknown"))
        title = result.get("message", {}).get("text", "Unknown Issue")
        level = result.get("level", "warning")  # note, warning, error, none
        description = result.get("message", {}).get("text", "")

        # Map severity
        severity = normalize_severity(level, tool_name="sarif")

        # Extract locations
        location = self._extract_location(result)

        # Extract remediation and references
        remediation = self._extract_remediation(result)
        references = self._extract_references(result)

        # Extract tags/properties
        tags = self._extract_tags(result)

        return UnifiedFinding(
            id=finding_id,
            title=title,
            severity=severity,
            type="vulnerability",  # SARIF doesn't explicitly categorize, assume vulnerability
            location=location,
            description=description,
            remediation=remediation,
            references=references,
            tags=tags,
            raw_data=result,
        )

    def _extract_location(self, result: dict[str, Any]) -> UnifiedLocation | None:
        """Extract location information from SARIF result.

        Args:
            result: SARIF result object

        Returns:
            UnifiedLocation or None if not available
        """
        locations = result.get("locations", []) or []
        if not locations:
            return None

        # Use first location
        loc = locations[0]
        physical = loc.get("physicalLocation", {}) or {}
        artifact = physical.get("artifactLocation", {}) or {}
        region = physical.get("region", {}) or {}

        file_path = artifact.get("uri")
        if not file_path:
            return None

        line_start = region.get("startLine")
        line_end = region.get("endLine")
        column_start = region.get("startColumn")
        column_end = region.get("endColumn")

        # Extract code snippet
        code_snippet = None
        snippet = region.get("snippet", {}) or {}
        if snippet:
            code_snippet = snippet.get("text")

        return UnifiedLocation(
            file_path=file_path,
            line_start=line_start or 1,  # Default to line 1 if not specified
            line_end=line_end,
            code_snippet=code_snippet,
            column_start=column_start,
            column_end=column_end,
        )

    def _extract_remediation(self, result: dict[str, Any]) -> str | None:
        """Extract remediation/fix information.

        Args:
            result: SARIF result object

        Returns:
            Remediation text or None
        """
        fixes = result.get("fixes") or []
        if not fixes:
            return None

        first_fix = fixes[0]
        description = (first_fix.get("description", {}) or {}).get("text")
        return description

    def _extract_references(self, result: dict[str, Any]) -> list[str] | None:
        """Extract external references (CVE IDs, documentation, etc.).

        Args:
            result: SARIF result object

        Returns:
            List of reference strings or None
        """
        references = []

        # Rule references
        related_locations = result.get("relatedLocations", []) or []
        for loc in related_locations:
            message = loc.get("message", {}) or {}
            text = message.get("text")
            if text:
                references.append(text)

        # Properties may contain CVE references
        properties = result.get("properties", {}) or {}
        if "cve" in properties:
            references.append(str(properties["cve"]))

        return references if references else None

    def _extract_tags(self, result: dict[str, Any]) -> list[str] | None:
        """Extract tags/keywords for categorization.

        Args:
            result: SARIF result object

        Returns:
            List of tags or None
        """
        tags = []

        # Rule tags
        rule = result.get("rule", {}) or {}
        properties = rule.get("properties", {}) or {}
        keywords = properties.get("tags", [])
        if isinstance(keywords, list):
            tags.extend(keywords)

        # Result properties
        result_props = result.get("properties", {}) or {}
        if "tags" in result_props:
            result_tags = result_props["tags"]
            if isinstance(result_tags, list):
                tags.extend(result_tags)

        return list(set(tags)) if tags else None
