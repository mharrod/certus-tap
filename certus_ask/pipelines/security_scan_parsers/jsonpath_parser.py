"""JSONPath-based parser for flexible security scan ingestion.

This parser enables parsing of custom security tool formats by providing
a JSONPath schema that maps tool output fields to UnifiedFinding fields.

Users can define schemas without modifying code, enabling community
contributions and support for new tools quickly.
"""

from typing import Any

import structlog
from jsonpath_ng import parse

from certus_ask.pipelines.security_scan_parsers.base import SecurityScanParser
from certus_ask.pipelines.security_scan_parsers.severity_mapping import normalize_severity
from certus_ask.schemas.unified_security_scan import (
    ScanMetadata,
    UnifiedFinding,
    UnifiedLocation,
    UnifiedSecurityScan,
)

logger = structlog.get_logger(__name__)


class JSONPathParser(SecurityScanParser):
    """Parser using JSONPath mappings to extract findings from any tool format.

    This parser accepts a schema that defines:
    - Where findings are located in the JSON (findings_path)
    - How to extract fields using JSONPath expressions (mapping)

    Example schema:
    ```json
    {
      "tool_name": "custom-scanner",
      "format": {
        "findings_path": "$.results[*]",
        "mapping": {
          "id": "$.id",
          "title": "$.title",
          "severity": "$.level",
          "file_path": "$.location.file"
        }
      }
    }
    ```
    """

    def __init__(self, schema: dict[str, Any]):
        """Initialize parser with a JSONPath schema.

        Args:
            schema: Schema dict containing tool_name, format, and mapping
        """
        self.schema = schema
        self.tool_name = schema.get("tool_name", "jsonpath-custom")
        self.version = schema.get("version", "1.0.0")

        format_config = schema.get("format", {})
        self.findings_path = format_config.get("findings_path", "$[*]")
        self.mapping = format_config.get("mapping", {})

        # Compile JSONPath expressions for performance
        self._compiled_paths = {}
        self._compile_paths()

        logger.info(
            "jsonpath_parser.initialized",
            tool_name=self.tool_name,
            findings_path=self.findings_path,
        )

    def _compile_paths(self) -> None:
        """Pre-compile all JSONPath expressions for efficiency."""
        try:
            self._compiled_paths["findings"] = parse(self.findings_path)
            for field, path in self.mapping.items():
                if path:  # Only compile non-empty paths
                    self._compiled_paths[field] = parse(path)
        except Exception as e:
            logger.error(
                "jsonpath_parser.compilation_error",
                error=str(e),
                findings_path=self.findings_path,
            )
            raise ValueError(f"Invalid JSONPath in schema: {e}") from e

    def validate(self, raw_json: dict[str, Any]) -> bool:
        """Check if JSON has findings at the expected path.

        Args:
            raw_json: Raw JSON data

        Returns:
            True if findings can be located, False otherwise
        """
        try:
            matches = self._compiled_paths["findings"].find(raw_json)
            has_findings = len(matches) > 0
            logger.debug(
                "jsonpath_parser.validate",
                tool_name=self.tool_name,
                has_findings=has_findings,
                match_count=len(matches),
            )
            return has_findings
        except Exception as e:
            logger.debug(
                "jsonpath_parser.validate_error",
                tool_name=self.tool_name,
                error=str(e),
            )
            return False

    def parse(self, raw_json: dict[str, Any]) -> UnifiedSecurityScan:
        """Parse JSON using JSONPath schema to extract findings.

        Args:
            raw_json: Raw JSON data to parse

        Returns:
            UnifiedSecurityScan with extracted findings

        Raises:
            ValueError: If schema is invalid or parsing fails
        """
        logger.info(
            "jsonpath_parser.parse_start",
            tool_name=self.tool_name,
        )

        # Extract findings using compiled path
        try:
            findings_matches = self._compiled_paths["findings"].find(raw_json)
            findings_data = [match.value for match in findings_matches]
        except Exception as e:
            logger.error(
                "jsonpath_parser.findings_extraction_error",
                tool_name=self.tool_name,
                error=str(e),
            )
            raise ValueError(f"Failed to extract findings: {e}") from e

        if not findings_data:
            logger.warning("jsonpath_parser.no_findings_found", tool_name=self.tool_name)
            return UnifiedSecurityScan(
                metadata=ScanMetadata(tool_name=self.tool_name),
                findings=[],
            )

        # Parse each finding
        findings = []
        for finding_data in findings_data:
            try:
                finding = self._parse_finding(finding_data)
                findings.append(finding)
            except Exception as e:
                logger.warning(
                    "jsonpath_parser.finding_parse_error",
                    tool_name=self.tool_name,
                    error=str(e),
                )
                # Continue parsing other findings on error
                continue

        metadata = ScanMetadata(tool_name=self.tool_name, tool_version=self.version)

        logger.info(
            "jsonpath_parser.parse_complete",
            tool_name=self.tool_name,
            finding_count=len(findings),
        )

        return UnifiedSecurityScan(
            metadata=metadata,
            findings=findings,
        )

    def _parse_finding(self, finding_data: dict[str, Any]) -> UnifiedFinding:
        """Extract a single finding using JSONPath mappings.

        Args:
            finding_data: Single finding data object

        Returns:
            UnifiedFinding
        """
        # Extract fields using compiled paths
        extracted = {}
        for field, path_expr in self._compiled_paths.items():
            if field == "findings":  # Skip the findings path itself
                continue

            if field not in self.mapping:
                continue

            try:
                matches = path_expr.find(finding_data)
                if matches:
                    # For arrays (multiple matches), collect all values
                    # For single values, extract the first match
                    if len(matches) > 1:
                        extracted[field] = [m.value for m in matches]
                    else:
                        extracted[field] = matches[0].value
                else:
                    extracted[field] = None
            except Exception:
                extracted[field] = None

        # Build finding with extracted data
        finding_id = extracted.get("id") or "unknown"
        title = extracted.get("title") or "Unknown Issue"
        severity = extracted.get("severity", "INFO")
        description = extracted.get("description") or title

        # Normalize severity
        normalized_severity = normalize_severity(severity, tool_name=self.tool_name)

        # Extract location if file path exists
        location = None
        if extracted.get("file_path"):
            location = UnifiedLocation(
                file_path=extracted["file_path"],
                line_start=extracted.get("line_start") or 1,
                line_end=extracted.get("line_end"),
                code_snippet=extracted.get("code_snippet"),
            )

        # Extract references (handle both single values and arrays)
        references = None
        if extracted.get("references"):
            refs = extracted["references"]
            if isinstance(refs, list):
                # Filter out None values
                references = [r for r in refs if r is not None]
                if not references:
                    references = None
            elif refs:
                references = [str(refs)]

        return UnifiedFinding(
            id=finding_id,
            title=title,
            severity=normalized_severity,
            type=extracted.get("type") or "vulnerability",
            location=location,
            description=description,
            remediation=extracted.get("remediation"),
            references=references,
            tags=extracted.get("tags"),
            raw_data=finding_data,
        )
