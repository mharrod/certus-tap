"""Generate markdown from SPDX data stored in Neo4j."""

from __future__ import annotations

import structlog
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError

logger = structlog.get_logger(__name__)


class SpdxToMarkdown:
    """Generate readable markdown from SPDX packages in Neo4j."""

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

    def generate(self, sbom_id: str) -> str:
        """Generate markdown from SPDX SBOM in Neo4j.

        Args:
            sbom_id: The SBOM ID to generate markdown for

        Returns:
            Markdown-formatted string with all packages and dependencies
        """
        try:
            with self.driver.session() as session:
                # Get SBOM info
                sbom_result = session.run(
                    """
                    MATCH (sbom:SBOM {id: $sbom_id})
                    RETURN sbom.name as name, sbom.version as version, sbom.created_at as created_at
                    """,
                    sbom_id=sbom_id,
                )

                sbom_record = sbom_result.single()
                if not sbom_record:
                    logger.warning(event="spdx.markdown.sbom_not_found", sbom_id=sbom_id)
                    return ""

                sbom_name = sbom_record["name"]
                sbom_version = sbom_record["version"]
                created_at = sbom_record["created_at"]

                # Get all packages with their licenses and dependencies
                packages_result = session.run(
                    """
                    MATCH (sbom:SBOM {id: $sbom_id})-[:CONTAINS]->(p:Package)
                    OPTIONAL MATCH (p)-[:USES_LICENSE]->(l:License)
                    OPTIONAL MATCH (p)-[:DEPENDS_ON]->(dep:Package)
                    OPTIONAL MATCH (p)-[:HAS_REFERENCE]->(ref:ExternalRef)
                    RETURN
                        p.name as name,
                        p.version as version,
                        p.supplier as supplier,
                        p.download_location as download_location,
                        collect(distinct l.name) as licenses,
                        collect(distinct {name: dep.name, version: dep.version}) as dependencies,
                        collect({type: ref.type, locator: ref.locator}) as external_refs
                    ORDER BY p.name ASC
                    """,
                    sbom_id=sbom_id,
                )

                packages = packages_result.data()

                # Build markdown
                md = "# Software Bill of Materials (SBOM)\n\n"
                md += f"**SBOM Name:** {sbom_name}\n"
                md += f"**SBOM Version:** {sbom_version}\n"
                md += f"**Created:** {created_at}\n"
                md += f"**SBOM ID:** {sbom_id}\n\n"
                md += "## Summary\n\n"
                md += f"**Total Packages:** {len(packages)}\n\n"

                # Count licenses
                all_licenses = set()
                for pkg in packages:
                    all_licenses.update(pkg["licenses"] or [])
                md += f"**Unique Licenses:** {len(all_licenses)}\n\n"

                if all_licenses:
                    md += "**Licenses Used:**\n\n"
                    for lic in sorted(all_licenses):
                        md += f"- {lic}\n"
                    md += "\n"

                md += "---\n\n"

                # List packages
                md += "## Packages\n\n"

                for i, pkg in enumerate(packages, 1):
                    name = pkg["name"]
                    version = pkg["version"]
                    supplier = pkg["supplier"] or "Unknown"
                    download_location = pkg["download_location"] or "Unknown"
                    licenses = pkg["licenses"] or []
                    dependencies = pkg["dependencies"] or []
                    external_refs = pkg["external_refs"] or []

                    md += f"### {i}. {name} ({version})\n\n"
                    md += f"**Supplier:** {supplier}\n\n"
                    md += f"**Download Location:** {download_location}\n\n"

                    if licenses:
                        md += "**Licenses:**\n\n"
                        for lic in licenses:
                            md += f"- {lic}\n"
                        md += "\n"

                    if dependencies:
                        md += "**Dependencies:**\n\n"
                        for dep in dependencies:
                            dep_name = dep.get("name", "unknown")
                            dep_version = dep.get("version", "unknown")
                            md += f"- {dep_name} ({dep_version})\n"
                        md += "\n"

                    if external_refs:
                        md += "**External References:**\n\n"
                        for ref in external_refs:
                            ref_type = ref.get("type", "unknown")
                            ref_locator = ref.get("locator", "unknown")
                            md += f"- **{ref_type}:** `{ref_locator}`\n"
                        md += "\n"

                    md += "---\n\n"

                logger.info(event="spdx.markdown.generated", sbom_id=sbom_id, package_count=len(packages))

                return md

        except DriverError as exc:
            logger.error(event="spdx.markdown.generation_failed", sbom_id=sbom_id, error=str(exc), exc_info=True)
            return ""
