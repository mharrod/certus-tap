"""
Evidence Envelope to Neo4j Data Loader

Converts Evidence Envelopes (from WALK.1) into Neo4j nodes and relationships.
Supports all evidence types: SARIF, control frameworks, threat models, services.
"""

import logging
from datetime import datetime
from typing import Any

from neo4j import Driver, Session
from neo4j.exceptions import Neo4jError

logger = logging.getLogger(__name__)


class EvidenceGraphLoader:
    """
    Load Evidence Envelopes into Neo4j graph

    Supports:
    - SARIF findings → Finding nodes
    - Control frameworks → Control nodes
    - Threat models → Threat nodes
    - Services → Service nodes

    All operations are idempotent (using MERGE).
    """

    def __init__(self, driver: Driver):
        """
        Initialize loader with Neo4j driver

        Args:
            driver: Neo4j driver instance
        """
        self.driver = driver
        self.stats = {
            "findings_created": 0,
            "findings_updated": 0,
            "controls_created": 0,
            "controls_updated": 0,
            "threats_created": 0,
            "threats_updated": 0,
            "relationships_created": 0,
            "errors": 0,
        }

    def load_evidence_envelopes(self, envelopes: list[dict[str, Any]]) -> dict[str, int]:
        """
        Load multiple evidence envelopes

        Args:
            envelopes: List of evidence envelope dicts

        Returns:
            Statistics dict (findings_created, controls_created, etc.)
        """
        with self.driver.session() as session:
            for envelope in envelopes:
                try:
                    source_type = envelope.get("source_type")

                    if source_type == "sarif":
                        self._load_sarif_evidence(session, envelope)
                    elif source_type == "control":
                        self._load_control_framework(session, envelope)
                    elif source_type == "threat_model":
                        self._load_threat_model(session, envelope)
                    else:
                        logger.warning(f"Unknown source type: {source_type}")

                except Exception:
                    logger.exception("Failed to load envelope %s", envelope.get("evidence_id"))
                    self.stats["errors"] += 1

        return self.stats

    def _load_sarif_evidence(self, session: Session, envelope: dict[str, Any]) -> None:
        """
        Convert SARIF finding to Finding node

        Operations:
        1. Create/merge Finding node
        2. Create/merge CWE node (if referenced)
        3. Create FINDING_HAS_CWE relationship
        4. Create/merge CVE node (if referenced via enrichment)
        5. Create FINDING_LINKS_CVE relationship (if CVE exists)
        """
        data = envelope.get("structured_data", {})

        finding_id = data.get("ruleId", envelope.get("evidence_id"))
        cwe_id = data.get("cwe_id")
        cve_id = data.get("cve_id")

        # 1. Create Finding node
        finding_query = """
        MERGE (f:Finding {finding_id: $finding_id})
        SET f.cwe_id = $cwe_id,
            f.severity = $severity,
            f.cvss_score = $cvss_score,
            f.epss_score = $epss_score,
            f.title = $title,
            f.description = $description,
            f.first_seen = $first_seen,
            f.status = 'open'
        RETURN f
        """

        try:
            session.run(
                finding_query,
                {
                    "finding_id": finding_id,
                    "cwe_id": cwe_id,
                    "severity": data.get("severity", "medium"),
                    "cvss_score": data.get("cvss_score", 0.0),
                    "epss_score": data.get("epss_score", 0.0),
                    "title": data.get("title", ""),
                    "description": data.get("description", ""),
                    "first_seen": envelope.get("timestamp", datetime.now().isoformat()),
                },
            )
            self.stats["findings_created"] += 1
        except Neo4jError:
            logger.exception("Failed to create Finding node")
            raise

        # 2. Ensure CWE node exists
        if cwe_id:
            cwe_query = """
            MERGE (c:CWE {cwe_id: $cwe_id})
            SET c.title = $title,
                c.description = $description
            RETURN c
            """
            try:
                session.run(
                    cwe_query,
                    {
                        "cwe_id": cwe_id,
                        "title": f"CWE {cwe_id}",
                        "description": data.get("description", ""),
                    },
                )
            except Neo4jError:
                logger.exception("Failed to create CWE node")

            # 3. Create FINDING_HAS_CWE relationship
            rel_query = """
            MATCH (f:Finding {finding_id: $finding_id})
            MATCH (c:CWE {cwe_id: $cwe_id})
            MERGE (f)-[r:FINDING_HAS_CWE {confidence: 1.0}]->(c)
            RETURN r
            """
            try:
                session.run(
                    rel_query,
                    {
                        "finding_id": finding_id,
                        "cwe_id": cwe_id,
                    },
                )
                self.stats["relationships_created"] += 1
            except Neo4jError:
                logger.exception("Failed to create FINDING_HAS_CWE relationship")

        # 4. Link to CVE (if enriched)
        if cve_id:
            cve_query = """
            MERGE (v:CVE {cve_id: $cve_id})
            SET v.cwe_id = $cwe_id
            RETURN v
            """
            try:
                session.run(
                    cve_query,
                    {
                        "cve_id": cve_id,
                        "cwe_id": cwe_id,
                    },
                )
            except Neo4jError:
                logger.exception("Failed to create CVE node")

            # 5. Create FINDING_LINKS_CVE relationship
            cve_rel_query = """
            MATCH (f:Finding {finding_id: $finding_id})
            MATCH (v:CVE {cve_id: $cve_id})
            MERGE (f)-[r:FINDING_LINKS_CVE {detected_by: $detected_by}]->(v)
            RETURN r
            """
            try:
                session.run(
                    cve_rel_query,
                    {
                        "finding_id": finding_id,
                        "cve_id": cve_id,
                        "detected_by": data.get("tool", "unknown"),
                    },
                )
                self.stats["relationships_created"] += 1
            except Neo4jError:
                logger.exception("Failed to create FINDING_LINKS_CVE relationship")

    def _load_control_framework(self, session: Session, envelope: dict[str, Any]) -> None:
        """
        Convert control framework to Control nodes

        Operations:
        1. Create/merge Control nodes (per framework)
        2. Create CWE_VIOLATES_CONTROL relationships
        3. Set implementation status
        """
        data = envelope.get("structured_data", {})
        controls = data.get("controls", [])

        for control in controls:
            control_id = control.get("id")
            framework = control.get("framework", "unknown")

            # 1. Create Control node
            ctrl_query = """
            MERGE (c:Control {control_id: $control_id})
            SET c.framework = $framework,
                c.title = $title,
                c.description = $description,
                c.status = $status
            RETURN c
            """

            try:
                session.run(
                    ctrl_query,
                    {
                        "control_id": control_id,
                        "framework": framework,
                        "title": control.get("title", ""),
                        "description": control.get("description", ""),
                        "status": control.get("status", "missing"),
                    },
                )
                self.stats["controls_created"] += 1
            except Neo4jError:
                logger.exception("Failed to create Control node %s", control_id)

    def _load_threat_model(self, session: Session, envelope: dict[str, Any]) -> None:
        """
        Convert threat model to Threat nodes + relationships

        Operations:
        1. Create/merge Threat nodes (STRIDE categories)
        2. Create CONTROL_MITIGATES_THREAT relationships
        3. Create THREAT_AFFECTS_SERVICE relationships
        """
        data = envelope.get("structured_data", {})
        threats = data.get("threats", []) if isinstance(data, dict) else [data]

        # Handle single threat object
        if not isinstance(threats, list):
            threats = [data]

        for threat in threats:
            threat_id = threat.get("threat_id")
            stride_category = threat.get("stride_category", "U")  # U = Unknown

            # 1. Create Threat node
            threat_query = """
            MERGE (t:Threat {threat_id: $threat_id})
            SET t.stride_category = $stride_category,
                t.title = $title,
                t.description = $description,
                t.likelihood = $likelihood,
                t.impact = $impact
            RETURN t
            """

            try:
                session.run(
                    threat_query,
                    {
                        "threat_id": threat_id,
                        "stride_category": stride_category,
                        "title": threat.get("title", ""),
                        "description": threat.get("description", ""),
                        "likelihood": threat.get("likelihood", "medium"),
                        "impact": threat.get("impact", "medium"),
                    },
                )
                self.stats["threats_created"] += 1
            except Neo4jError:
                logger.exception("Failed to create Threat node %s", threat_id)

            # 2. Create CONTROL_MITIGATES_THREAT relationships
            mitigating_controls = threat.get("mitigating_controls", [])
            for control_id in mitigating_controls:
                rel_query = """
                MATCH (c:Control {control_id: $control_id})
                MATCH (t:Threat {threat_id: $threat_id})
                MERGE (c)-[r:CONTROL_MITIGATES_THREAT {coverage: 'partial', confidence: 0.8}]->(t)
                RETURN r
                """
                try:
                    session.run(
                        rel_query,
                        {
                            "control_id": control_id,
                            "threat_id": threat_id,
                        },
                    )
                    self.stats["relationships_created"] += 1
                except Neo4jError:
                    logger.exception("Failed to create CONTROL_MITIGATES_THREAT relationship")

            # 3. Create THREAT_AFFECTS_SERVICE relationships
            affected_services = threat.get("affected_services", [])
            for service_id in affected_services:
                svc_rel_query = """
                MATCH (t:Threat {threat_id: $threat_id})
                MATCH (s:Service {service_id: $service_id})
                MERGE (t)-[r:THREAT_AFFECTS_SERVICE {likelihood: $likelihood}]->(s)
                RETURN r
                """
                try:
                    session.run(
                        svc_rel_query,
                        {
                            "threat_id": threat_id,
                            "service_id": service_id,
                            "likelihood": threat.get("likelihood", "medium"),
                        },
                    )
                    self.stats["relationships_created"] += 1
                except Neo4jError:
                    logger.exception("Failed to create THREAT_AFFECTS_SERVICE relationship")

    def get_graph_statistics(self, session: Session) -> dict[str, int]:
        """
        Get summary statistics for loaded graph

        Returns:
            Dict with counts of nodes and relationships by type
        """
        stats_query = """
        MATCH (n)
        WITH labels(n) as labels, count(*) as node_count
        UNWIND labels as label
        RETURN label, node_count
        """

        node_stats = {}
        try:
            result = session.run(stats_query)
            for record in result:
                label = record["label"]
                count = record["node_count"]
                node_stats[label] = count
        except Neo4jError:
            logger.exception("Failed to get graph statistics")

        return {
            "nodes": node_stats,
        }
