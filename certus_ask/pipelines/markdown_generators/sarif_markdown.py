"""Generate markdown from SARIF data stored in Neo4j."""

from __future__ import annotations

import structlog
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError

logger = structlog.get_logger(__name__)


class SarifToMarkdown:
    """Generate readable markdown from SARIF findings in Neo4j."""

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """Initialize Neo4j connection.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))

    def close(self):
        """Close Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    def generate(self, scan_id: str) -> str:
        """Generate markdown report from SARIF scan in Neo4j.

        Args:
            scan_id: The scan ID to generate markdown for

        Returns:
            Markdown-formatted string with all findings
        """
        try:
            with self.driver.session() as session:
                # Get scan info
                scan_result = session.run(
                    """
                    MATCH (scan:Scan {id: $scan_id})-[:SCANNED_WITH]->(tool:Tool)
                    RETURN tool.name as tool_name, tool.version as tool_version, scan.timestamp as timestamp
                    """,
                    scan_id=scan_id,
                )

                scan_record = scan_result.single()
                if not scan_record:
                    logger.warning(event="sarif.markdown.scan_not_found", scan_id=scan_id)
                    return ""

                tool_name = scan_record["tool_name"]
                tool_version = scan_record["tool_version"]
                timestamp = scan_record["timestamp"]

                # Get all findings with their rules, severity, and locations
                findings_result = session.run(
                    """
                    MATCH (scan:Scan {id: $scan_id})-[:CONTAINS]->(f:Finding)
                    OPTIONAL MATCH (f)-[:VIOLATES]->(rule:Rule)
                    OPTIONAL MATCH (f)-[:HAS_SEVERITY]->(sev:Severity)
                    OPTIONAL MATCH (f)-[:LOCATED_AT]->(loc:Location)
                    RETURN
                        f.id as finding_id,
                        f.rule_id as rule_id,
                        f.message as message,
                        rule.name as rule_name,
                        rule.description as rule_description,
                        sev.level as severity,
                        collect({uri: loc.uri, line: loc.line}) as locations
                    ORDER BY sev.level DESC, rule_id ASC
                    """,
                    scan_id=scan_id,
                )

                findings = findings_result.data()

                # Build markdown
                md = "# SARIF Security Scan Report\n\n"
                md += f"**Scan Tool:** {tool_name}\n"
                md += f"**Tool Version:** {tool_version}\n"
                md += f"**Scan Time:** {timestamp}\n"
                md += f"**Scan ID:** {scan_id}\n\n"
                md += "## Summary\n\n"
                md += f"**Total Findings:** {len(findings)}\n\n"

                # Group by severity
                severity_counts = {}
                for finding in findings:
                    sev = finding["severity"] or "none"
                    severity_counts[sev] = severity_counts.get(sev, 0) + 1

                md += "**Findings by Severity:**\n\n"
                for sev in ["error", "warning", "note", "none"]:
                    if sev in severity_counts:
                        md += f"- {sev.upper()}: {severity_counts[sev]}\n"
                md += "\n---\n\n"

                # List findings
                md += "## Findings\n\n"

                current_severity = None
                for i, finding in enumerate(findings, 1):
                    severity = finding["severity"] or "none"

                    # Add severity header if changed
                    if severity != current_severity:
                        current_severity = severity
                        md += f"### {severity.upper()} Severity\n\n"

                    rule_id = finding["rule_id"] or "unknown"
                    rule_name = finding["rule_name"] or rule_id
                    message = finding["message"] or "No message"
                    description = finding["rule_description"] or ""
                    locations = finding["locations"] or []

                    md += f"#### Finding {i}: {rule_id} - {rule_name}\n\n"
                    md += f"**Severity:** `{severity}`\n\n"

                    if locations:
                        md += "**Locations:**\n\n"
                        for loc in locations:
                            uri = loc.get("uri", "unknown")
                            line = loc.get("line", 0)
                            md += f"- `{uri}:{line}`\n"
                        md += "\n"

                    md += f"**Message:** {message}\n\n"

                    if description:
                        md += f"**Description:** {description}\n\n"

                    md += f"**Graph ID:** `Finding_{finding['finding_id']}`\n\n"
                    md += "---\n\n"

                logger.info(event="sarif.markdown.generated", scan_id=scan_id, finding_count=len(findings))

                return md

        except DriverError as exc:
            logger.error(event="sarif.markdown.generation_failed", scan_id=scan_id, error=str(exc), exc_info=True)
            return ""
