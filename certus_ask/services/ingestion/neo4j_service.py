"""Neo4j graph database service.

Handles all Neo4j operations for security scan data including
SARIF and SPDX loading, querying, and relationship management.
"""

from typing import Any, Optional

import structlog

logger = structlog.get_logger(__name__)


class Neo4jService:
    """Service for Neo4j graph database operations.

    This service encapsulates:
    - Neo4j driver connection management
    - SARIF data loading (vulnerabilities, tools, runs)
    - SPDX data loading (packages, relationships, licenses)
    - Markdown generation from graph data
    - Graph queries and traversals
    - Transaction management

    Dependencies are injected via constructor to enable testing and reuse.
    """

    def __init__(
        self,
        uri: str,
        user: str,
        password: str,
    ):
        """Initialize the Neo4j service.

        Args:
            uri: Neo4j connection URI (e.g., "bolt://localhost:7687")
            user: Neo4j username
            password: Neo4j password
        """
        self.uri = uri
        self.user = user
        self.password = password
        logger.info("Neo4jService initialized", uri=uri, user=user)

    def load_sarif(
        self,
        sarif_data: dict[str, Any],
        scan_id: str,
        verification_proof: Optional[dict[str, Any]] = None,
        assessment_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Load SARIF data into Neo4j graph.

        Args:
            sarif_data: Parsed SARIF JSON data
            scan_id: Unique identifier for this scan (becomes Neo4j node ID)
            verification_proof: Optional trust verification proof for premium tier
            assessment_id: Optional assessment ID for premium tier

        Returns:
            Loading result with node/relationship counts

        Raises:
            Exception: If Neo4j loading fails (caller should handle gracefully)
        """
        from certus_ask.pipelines.neo4j_loaders.sarif_loader import SarifToNeo4j

        logger.info("load_sarif called", scan_id=scan_id, assessment_id=assessment_id)

        neo4j_loader = SarifToNeo4j(self.uri, self.user, self.password)
        try:
            graph_result = neo4j_loader.load(
                sarif_data,
                scan_id,
                verification_proof=verification_proof,
                assessment_id=assessment_id,
            )
            logger.info(
                "load_sarif completed",
                scan_id=scan_id,
                nodes_created=graph_result.get("nodes_created", 0),
            )
            return graph_result
        finally:
            neo4j_loader.close()

    def load_spdx(
        self,
        spdx_data: dict[str, Any],
        sbom_id: str,
    ) -> dict[str, Any]:
        """Load SPDX data into Neo4j graph.

        Args:
            spdx_data: Parsed SPDX JSON data
            sbom_id: Unique identifier for this SBOM (becomes Neo4j node ID)

        Returns:
            Loading result with package_count and other metrics

        Raises:
            Exception: If Neo4j loading fails (caller should handle gracefully)
        """
        from certus_ask.pipelines.neo4j_loaders.spdx_loader import SpdxToNeo4j

        logger.info("load_spdx called", sbom_id=sbom_id)

        neo4j_loader = SpdxToNeo4j(self.uri, self.user, self.password)
        try:
            graph_result = neo4j_loader.load(spdx_data, sbom_id)
            logger.info(
                "load_spdx completed",
                sbom_id=sbom_id,
                package_count=graph_result.get("package_count", 0),
            )
            return graph_result
        finally:
            neo4j_loader.close()

    def generate_sarif_markdown(
        self,
        scan_id: str,
    ) -> str:
        """Generate markdown documentation from SARIF data in Neo4j.

        Args:
            scan_id: Scan ID to generate markdown for (must exist in Neo4j)

        Returns:
            Markdown string with findings summary and details

        Raises:
            Exception: If Neo4j query fails (caller should handle gracefully)
        """
        from certus_ask.pipelines.markdown_generators.sarif_markdown import SarifToMarkdown

        logger.info("generate_sarif_markdown called", scan_id=scan_id)

        markdown_gen = SarifToMarkdown(self.uri, self.user, self.password)
        try:
            markdown_content = markdown_gen.generate(scan_id)
            logger.info(
                "generate_sarif_markdown completed",
                scan_id=scan_id,
                markdown_length=len(markdown_content),
            )
            return markdown_content
        finally:
            markdown_gen.close()

    def generate_spdx_markdown(
        self,
        sbom_id: str,
    ) -> str:
        """Generate markdown documentation from SPDX data in Neo4j.

        Args:
            sbom_id: SBOM ID to generate markdown for (must exist in Neo4j)

        Returns:
            Markdown string with package list and details

        Raises:
            Exception: If Neo4j query fails (caller should handle gracefully)
        """
        from certus_ask.pipelines.markdown_generators.spdx_markdown import SpdxToMarkdown

        logger.info("generate_spdx_markdown called", sbom_id=sbom_id)

        markdown_gen = SpdxToMarkdown(self.uri, self.user, self.password)
        try:
            markdown_content = markdown_gen.generate(sbom_id)
            logger.info(
                "generate_spdx_markdown completed",
                sbom_id=sbom_id,
                markdown_length=len(markdown_content),
            )
            return markdown_content
        finally:
            markdown_gen.close()
