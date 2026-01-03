"""Load SARIF security scan results into Neo4j knowledge graph."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError

logger = structlog.get_logger(__name__)


class SarifToNeo4j:
    """Load SARIF findings into Neo4j knowledge graph.

    Creates nodes for:
    - SecurityScan: represents the scan event (with assessment_id for compliance)
    - Tool: the scanning tool (Bandit, Snyk, etc.)
    - Rule: security rules that were violated
    - Finding: individual findings/results
    - Severity: severity levels
    - Location: file locations where findings occur

    And creates relationships:
    - (SecurityScan)-[:SCANNED_WITH]->(Tool)
    - (SecurityScan)-[:CONTAINS]->(Finding)
    - (Finding)-[:VIOLATES]->(Rule)
    - (Finding)-[:HAS_SEVERITY]->(Severity)
    - (Finding)-[:LOCATED_AT]->(Location)
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """Initialize Neo4j connection.

        Args:
            neo4j_uri: Neo4j connection URI (e.g., "neo4j://localhost:7687")
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.neo4j_uri = neo4j_uri

    def close(self):
        """Close Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    def load(
        self,
        sarif_data: dict,
        scan_id: str,
        verification_proof: dict[str, Any] | None = None,
        assessment_id: str | None = None,
    ) -> dict[str, Any]:
        """Load SARIF data into Neo4j.

        Args:
            sarif_data: Parsed SARIF JSON data
            scan_id: Unique ID for this scan (e.g., ingestion_id)
            verification_proof: Optional non-repudiation verification proof from Trust service
            assessment_id: Optional assessment ID for premium tier scans

        Returns:
            Dict containing:
            - scan_node_id: ID of created SecurityScan node
            - finding_ids: List of Finding node IDs
            - rule_ids: List of Rule node IDs
            - finding_count: Total findings indexed
        """
        try:
            with self.driver.session() as session:
                session.execute_write(self._cleanup_existing_scan, scan_id, assessment_id)
                # Create scan node
                scan_node_id = session.execute_write(
                    self._create_scan_node, scan_id, sarif_data.get("creationInfo", {}), assessment_id
                )

                # Link verification proof if premium tier
                if verification_proof:
                    session.execute_write(self._link_verification_to_scan, scan_id, verification_proof)
                    logger.info(
                        event="sarif.neo4j.verification_linked",
                        scan_id=scan_id,
                        chain_verified=verification_proof.get("chain_verified"),
                    )

                logger.info(event="sarif.neo4j.scan_created", scan_id=scan_id, scan_node_id=scan_node_id)

                finding_ids = []
                rule_ids = []

                # Process each run
                for run in sarif_data.get("runs", []):
                    tool_info = run.get("tool", {}).get("driver", {})
                    tool_name = tool_info.get("name", "unknown_tool")
                    tool_version = tool_info.get("version", "unknown")

                    # Create tool node
                    tool_id = session.execute_write(self._create_tool_node, tool_name, tool_version)

                    # Link scan to tool
                    session.execute_write(self._link_scan_to_tool, scan_node_id, tool_id)

                    # Create rule nodes
                    rules = tool_info.get("rules", [])
                    rule_map = {}

                    for rule in rules:
                        rule_id = rule.get("id")
                        rule_node_id = session.execute_write(
                            self._create_rule_node,
                            rule_id,
                            rule.get("name", rule_id),
                            rule.get("shortDescription", {}).get("text", ""),
                            rule.get("help", {}).get("text", ""),
                        )
                        rule_map[rule_id] = rule_node_id
                        rule_ids.append(rule_node_id)

                        # Link tool to rule
                        session.execute_write(self._link_tool_to_rule, tool_id, rule_node_id)

                    # Create severity nodes and findings
                    for result in run.get("results", []):
                        rule_id = result.get("ruleId") or (result.get("rule", {}) or {}).get("id")
                        severity = result.get("level", "none")
                        message = (result.get("message", {}) or {}).get("text", "")

                        # Create severity node
                        severity_id = session.execute_write(self._create_or_get_severity_node, severity)

                        # Create finding node
                        finding_node_id = session.execute_write(
                            self._create_finding_node, scan_node_id, rule_id, severity, message
                        )
                        finding_ids.append(finding_node_id)

                        # Link finding to scan
                        session.execute_write(self._link_finding_to_scan, finding_node_id, scan_node_id)

                        # Link finding to rule
                        if rule_id in rule_map:
                            session.execute_write(self._link_finding_to_rule, finding_node_id, rule_map[rule_id])

                        # Link finding to severity
                        session.execute_write(self._link_finding_to_severity, finding_node_id, severity_id)

                        # Create and link locations
                        for location in result.get("locations", []):
                            physical = location.get("physicalLocation", {}) or {}
                            artifact = physical.get("artifactLocation", {}) or {}
                            uri = artifact.get("uri")
                            start_line = physical.get("region", {}).get("startLine")

                            if uri:
                                location_id = session.execute_write(
                                    self._create_or_get_location_node, uri, start_line or 0
                                )
                                session.execute_write(self._link_finding_to_location, finding_node_id, location_id)

                logger.info(
                    event="sarif.neo4j.load_complete",
                    scan_id=scan_id,
                    finding_count=len(finding_ids),
                    rule_count=len(rule_ids),
                )

                return {
                    "scan_node_id": scan_node_id,
                    "finding_ids": finding_ids,
                    "rule_ids": rule_ids,
                    "finding_count": len(finding_ids),
                }

        except DriverError as exc:
            logger.error(event="sarif.neo4j.load_failed", scan_id=scan_id, error=str(exc), exc_info=True)
            raise

    @staticmethod
    def _create_scan_node(tx, scan_id: str, creation_info: dict, assessment_id: str | None = None) -> str:
        """Create a SecurityScan node."""
        result = tx.run(
            """
            MERGE (s:SecurityScan {
                id: $scan_id,
                assessment_id: $assessment_id,
                timestamp: datetime($timestamp),
                spdx_version: $spdx_version
            })
            RETURN s.id as id
            """,
            scan_id=scan_id,
            assessment_id=assessment_id or scan_id,
            timestamp=creation_info.get("created", datetime.utcnow().isoformat()),
            spdx_version="SARIF-2.1.0",
        )
        return result.single()["id"]

    @staticmethod
    def _cleanup_existing_scan(tx, scan_id: str, assessment_id: str | None = None):
        """Remove an existing scan graph before reloading."""
        # Clean up by scan_id or assessment_id
        if assessment_id:
            tx.run(
                """
                MATCH (scan:SecurityScan)
                WHERE scan.id = $scan_id OR scan.assessment_id = $assessment_id
                OPTIONAL MATCH (scan)-[:CONTAINS]->(finding:Finding)
                OPTIONAL MATCH (finding)-[:LOCATED_AT]->(loc:Location)
                DETACH DELETE scan, finding, loc
                """,
                scan_id=scan_id,
                assessment_id=assessment_id,
            )
        else:
            tx.run(
                """
                MATCH (scan:SecurityScan {id: $scan_id})
                OPTIONAL MATCH (scan)-[:CONTAINS]->(finding:Finding)
                OPTIONAL MATCH (finding)-[:LOCATED_AT]->(loc:Location)
                DETACH DELETE scan, finding, loc
                """,
                scan_id=scan_id,
            )

    @staticmethod
    def _create_tool_node(tx, tool_name: str, version: str) -> str:
        """Create or get a Tool node."""
        result = tx.run(
            """
            MERGE (t:Tool {name: $name, version: $version})
            RETURN t.name as id
            """,
            name=tool_name,
            version=version or "unknown",
        )
        return result.single()["id"]

    @staticmethod
    def _create_rule_node(tx, rule_id: str, name: str, description: str, help_text: str) -> str:
        """Create a Rule node."""
        result = tx.run(
            """
            CREATE (r:Rule {
                id: $id,
                name: $name,
                description: $description,
                help: $help
            })
            RETURN r.id as id
            """,
            id=rule_id,
            name=name or rule_id,
            description=description or "",
            help=help_text or "",
        )
        return result.single()["id"]

    @staticmethod
    def _create_finding_node(tx, scan_id: str, rule_id: str, severity: str, message: str) -> str:
        """Create a Finding node."""
        result = tx.run(
            """
            CREATE (f:Finding {
                id: randomUUID(),
                scan_id: $scan_id,
                rule_id: $rule_id,
                severity: $severity,
                message: $message,
                created_at: datetime()
            })
            RETURN f.id as id
            """,
            scan_id=scan_id,
            rule_id=rule_id,
            severity=severity,
            message=message,
        )
        return result.single()["id"]

    @staticmethod
    def _create_or_get_severity_node(tx, severity: str) -> str:
        """Create or get a Severity node."""
        result = tx.run(
            """
            MERGE (s:Severity {level: $severity})
            RETURN s.level as id
            """,
            severity=severity,
        )
        return result.single()["id"]

    @staticmethod
    def _create_or_get_location_node(tx, uri: str, line: int) -> str:
        """Create or get a Location node."""
        result = tx.run(
            """
            MERGE (loc:Location {uri: $uri, line: $line})
            RETURN loc.uri + ':' + toString(loc.line) as id
            """,
            uri=uri,
            line=line,
        )
        return result.single()["id"]

    @staticmethod
    def _link_scan_to_tool(tx, scan_id: str, tool_id: str):
        """Link SecurityScan to Tool."""
        tx.run(
            """
            MATCH (s:SecurityScan {id: $scan_id})
            MATCH (t:Tool {name: $tool_id})
            MERGE (s)-[:SCANNED_WITH]->(t)
            """,
            scan_id=scan_id,
            tool_id=tool_id,
        )

    @staticmethod
    def _link_finding_to_scan(tx, finding_id: str, scan_id: str):
        """Link Finding to SecurityScan."""
        tx.run(
            """
            MATCH (f:Finding {id: $finding_id})
            MATCH (s:SecurityScan {id: $scan_id})
            MERGE (s)-[:CONTAINS]->(f)
            """,
            finding_id=finding_id,
            scan_id=scan_id,
        )

    @staticmethod
    def _link_finding_to_rule(tx, finding_id: str, rule_id: str):
        """Link Finding to Rule."""
        tx.run(
            """
            MATCH (f:Finding {id: $finding_id})
            MATCH (r:Rule {id: $rule_id})
            MERGE (f)-[:VIOLATES]->(r)
            """,
            finding_id=finding_id,
            rule_id=rule_id,
        )

    @staticmethod
    def _link_finding_to_severity(tx, finding_id: str, severity_id: str):
        """Link Finding to Severity."""
        tx.run(
            """
            MATCH (f:Finding {id: $finding_id})
            MATCH (s:Severity {level: $severity})
            MERGE (f)-[:HAS_SEVERITY]->(s)
            """,
            finding_id=finding_id,
            severity=severity_id,
        )

    @staticmethod
    def _link_finding_to_location(tx, finding_id: str, location_id: str):
        """Link Finding to Location."""
        uri, line = location_id.rsplit(":", 1)
        tx.run(
            """
            MATCH (f:Finding {id: $finding_id})
            MATCH (loc:Location {uri: $uri, line: $line})
            MERGE (f)-[:LOCATED_AT]->(loc)
            """,
            finding_id=finding_id,
            uri=uri,
            line=int(line),
        )

    @staticmethod
    def _link_tool_to_rule(tx, tool_id: str, rule_id: str):
        """Link Tool to Rule."""
        tx.run(
            """
            MATCH (t:Tool {name: $tool_id})
            MATCH (r:Rule {id: $rule_id})
            MERGE (t)-[:DEFINES]->(r)
            """,
            tool_id=tool_id,
            rule_id=rule_id,
        )

    @staticmethod
    def _link_verification_to_scan(tx, scan_id: str, verification_proof: dict[str, Any]):
        """Link non-repudiation verification proof to SecurityScan node.

        Adds properties to the SecurityScan node for audit trail and compliance.
        """
        tx.run(
            """
            MATCH (s:SecurityScan {id: $scan_id})
            SET s += {
                chain_verified: $chain_verified,
                inner_signature_valid: $inner_signature_valid,
                outer_signature_valid: $outer_signature_valid,
                chain_unbroken: $chain_unbroken,
                signer_inner: $signer_inner,
                signer_outer: $signer_outer,
                sigstore_timestamp: $sigstore_timestamp,
                verification_timestamp: datetime($verification_timestamp)
            }
            """,
            scan_id=scan_id,
            chain_verified=verification_proof.get("chain_verified", False),
            inner_signature_valid=verification_proof.get("inner_signature_valid", False),
            outer_signature_valid=verification_proof.get("outer_signature_valid", False),
            chain_unbroken=verification_proof.get("chain_unbroken", False),
            signer_inner=verification_proof.get("signer_inner"),
            signer_outer=verification_proof.get("signer_outer"),
            sigstore_timestamp=verification_proof.get("sigstore_timestamp"),
            verification_timestamp=datetime.now(timezone.utc).isoformat(),
        )
