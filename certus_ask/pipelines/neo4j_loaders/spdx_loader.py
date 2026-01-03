"""Load SPDX software bill of materials into Neo4j knowledge graph."""

from __future__ import annotations

from typing import Any

import structlog
from neo4j import GraphDatabase
from neo4j.exceptions import DriverError

logger = structlog.get_logger(__name__)


class SpdxToNeo4j:
    """Load SPDX packages into Neo4j knowledge graph.

    Creates nodes for:
    - SBOM: represents the software bill of materials
    - Package: software packages/components
    - License: licenses used
    - ExternalRef: external references (CPE, purl)

    And creates relationships:
    - (SBOM)-[:CONTAINS]->(Package)
    - (Package)-[:DEPENDS_ON]->(Package)
    - (Package)-[:USES_LICENSE]->(License)
    - (Package)-[:HAS_REFERENCE]->(ExternalRef)
    """

    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        """Initialize Neo4j connection.

        Args:
            neo4j_uri: Neo4j connection URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.neo4j_uri = neo4j_uri

    def close(self):
        """Close Neo4j driver connection."""
        if self.driver:
            self.driver.close()

    def load(self, spdx_data: dict, sbom_id: str) -> dict[str, Any]:
        """Load SPDX data into Neo4j.

        Args:
            spdx_data: Parsed SPDX JSON data
            sbom_id: Unique ID for this SBOM (e.g., ingestion_id)

        Returns:
            Dict containing:
            - sbom_node_id: ID of created SBOM node
            - package_ids: List of Package node IDs
            - license_ids: List of License node IDs
            - package_count: Total packages indexed
        """
        try:
            with self.driver.session() as session:
                session.execute_write(self._cleanup_existing_sbom, sbom_id)
                # Create SBOM node
                sbom_node_id = session.execute_write(
                    self._create_sbom_node,
                    sbom_id,
                    spdx_data.get("name", "Unknown"),
                    spdx_data.get("spdxVersion", "SPDX-2.3"),
                )

                logger.info(event="spdx.neo4j.sbom_created", sbom_id=sbom_id, sbom_node_id=sbom_node_id)

                package_ids = []
                license_ids = []
                package_map = {}  # Map SPDX ID to node ID

                # Create package nodes
                for package in spdx_data.get("packages", []):
                    package_name = package.get("name", "unknown")
                    package_version = package.get("versionInfo", "unknown")
                    spdx_id = package.get("SPDXID", "")
                    supplier = package.get("supplier", "")
                    download_location = package.get("downloadLocation", "")

                    # Create package node
                    package_node_id = session.execute_write(
                        self._create_package_node, package_name, package_version, spdx_id, supplier, download_location
                    )
                    package_ids.append(package_node_id)
                    package_map[spdx_id] = package_node_id

                    # Link SBOM to package
                    session.execute_write(self._link_sbom_to_package, sbom_node_id, package_node_id)

                    # Create and link licenses
                    licenses = [package.get("licenseDeclared", ""), package.get("licenseConcluded", "")]
                    licenses = [l for l in licenses if l]  # Filter empty

                    for license_str in licenses:
                        license_id = session.execute_write(self._create_or_get_license_node, license_str)
                        license_ids.append(license_id)

                        session.execute_write(self._link_package_to_license, package_node_id, license_id)

                    # Create external references
                    for ext_ref in package.get("externalRefs", []):
                        ref_type = ext_ref.get("referenceType", "")
                        ref_locator = ext_ref.get("referenceLocator", "")

                        if ref_type and ref_locator:
                            session.execute_write(self._create_external_ref, package_node_id, ref_type, ref_locator)

                # Create relationships between packages
                for rel in spdx_data.get("relationships", []):
                    element_id = rel.get("spdxElementId", "")
                    rel_type = rel.get("relationshipType", "")
                    related_id = rel.get("relatedSpdxElement", "")

                    # Handle DEPENDS_ON relationships
                    if rel_type == "DEPENDS_ON" and element_id in package_map and related_id in package_map:
                        session.execute_write(
                            self._link_package_dependency, package_map[element_id], package_map[related_id]
                        )

                logger.info(
                    event="spdx.neo4j.load_complete",
                    sbom_id=sbom_id,
                    package_count=len(package_ids),
                    license_count=len(license_ids),
                )

                return {
                    "sbom_node_id": sbom_node_id,
                    "package_ids": package_ids,
                    "license_ids": license_ids,
                    "package_count": len(package_ids),
                }

        except DriverError as exc:
            logger.error(event="spdx.neo4j.load_failed", sbom_id=sbom_id, error=str(exc), exc_info=True)
            raise

    @staticmethod
    def _create_sbom_node(tx, sbom_id: str, name: str, version: str) -> str:
        """Create an SBOM node."""
        result = tx.run(
            """
            MERGE (s:SBOM {
                id: $sbom_id,
                name: $name,
                version: $version,
                created_at: datetime()
            })
            RETURN s.id as id
            """,
            sbom_id=sbom_id,
            name=name,
            version=version,
        )
        return result.single()["id"]

    @staticmethod
    def _cleanup_existing_sbom(tx, sbom_id: str):
        """Remove an existing SBOM graph before reloading."""
        tx.run(
            """
            MATCH (sbom:SBOM {id: $sbom_id})
            OPTIONAL MATCH (sbom)-[:CONTAINS]->(pkg:Package)
            OPTIONAL MATCH (pkg)-[:HAS_REFERENCE]->(ref:ExternalRef)
            DETACH DELETE sbom, pkg, ref
            """,
            sbom_id=sbom_id,
        )

    @staticmethod
    def _create_package_node(tx, name: str, version: str, spdx_id: str, supplier: str, download_location: str) -> str:
        """Create a Package node."""
        result = tx.run(
            """
            CREATE (p:Package {
                name: $name,
                version: $version,
                spdx_id: $spdx_id,
                supplier: $supplier,
                download_location: $download_location
            })
            RETURN p.name + '@' + p.version as id
            """,
            name=name,
            version=version,
            spdx_id=spdx_id,
            supplier=supplier,
            download_location=download_location,
        )
        return result.single()["id"]

    @staticmethod
    def _create_or_get_license_node(tx, license_str: str) -> str:
        """Create or get a License node."""
        result = tx.run(
            """
            MERGE (l:License {name: $name})
            RETURN l.name as id
            """,
            name=license_str,
        )
        return result.single()["id"]

    @staticmethod
    def _link_sbom_to_package(tx, sbom_id: str, package_id: str):
        """Link SBOM to Package."""
        tx.run(
            """
            MATCH (s:SBOM {id: $sbom_id})
            MATCH (p:Package {name: $pkg_name, version: $pkg_version})
            MERGE (s)-[:CONTAINS]->(p)
            """,
            sbom_id=sbom_id,
            pkg_name=package_id.split("@")[0],
            pkg_version=package_id.split("@")[1],
        )

    @staticmethod
    def _link_package_to_license(tx, package_id: str, license_id: str):
        """Link Package to License."""
        tx.run(
            """
            MATCH (p:Package {name: $pkg_name, version: $pkg_version})
            MATCH (l:License {name: $license})
            MERGE (p)-[:USES_LICENSE]->(l)
            """,
            pkg_name=package_id.split("@")[0],
            pkg_version=package_id.split("@")[1],
            license=license_id,
        )

    @staticmethod
    def _link_package_dependency(tx, from_pkg_id: str, to_pkg_id: str):
        """Link Package dependency."""
        tx.run(
            """
            MATCH (p1:Package {name: $pkg1_name, version: $pkg1_version})
            MATCH (p2:Package {name: $pkg2_name, version: $pkg2_version})
            MERGE (p1)-[:DEPENDS_ON]->(p2)
            """,
            pkg1_name=from_pkg_id.split("@")[0],
            pkg1_version=from_pkg_id.split("@")[1],
            pkg2_name=to_pkg_id.split("@")[0],
            pkg2_version=to_pkg_id.split("@")[1],
        )

    @staticmethod
    def _create_external_ref(tx, package_id: str, ref_type: str, ref_locator: str):
        """Create external reference for a package."""
        tx.run(
            """
            MATCH (p:Package {name: $pkg_name, version: $pkg_version})
            MERGE (ref:ExternalRef {type: $ref_type, locator: $ref_locator})
            MERGE (p)-[:HAS_REFERENCE]->(ref)
            """,
            pkg_name=package_id.split("@")[0],
            pkg_version=package_id.split("@")[1],
            ref_type=ref_type,
            ref_locator=ref_locator,
        )
