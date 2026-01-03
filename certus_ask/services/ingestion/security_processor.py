"""Security scan processing service.

Handles ingestion and processing of security scan results (SARIF, SPDX).
Orchestrates parsing, trust verification, Neo4j loading, and document generation.
"""

import json
from pathlib import Path
from typing import Any, Optional

import structlog
from haystack import Document

logger = structlog.get_logger(__name__)


class SecurityProcessor:
    """Service for processing security scan files (SARIF, SPDX).

    This service encapsulates the business logic for:
    - Format detection (SARIF, SPDX, JSONPath, pre-registered tools)
    - Parsing SARIF and SPDX formats
    - Parsing custom JSONPath schemas
    - Verifying trust/provenance
    - Loading data into Neo4j
    - Generating markdown documentation
    - Preparing documents for indexing

    Dependencies are injected via constructor to enable testing and reuse.
    """

    def __init__(
        self,
        trust_client: Optional[Any] = None,
        neo4j_service: Optional[Any] = None,
        storage_service: Optional[Any] = None,
    ):
        """Initialize the security processor.

        Args:
            trust_client: Client for trust/provenance verification
            neo4j_service: Service for Neo4j graph operations
            storage_service: Service for S3/file storage operations
        """
        self.trust_client = trust_client
        self.neo4j_service = neo4j_service
        self.storage_service = storage_service
        logger.info("SecurityProcessor initialized")

    @staticmethod
    def extract_filename(source_name: str) -> str:
        """Extract the filename component from a source identifier.

        Args:
            source_name: Source name (may include path like "s3://bucket/key")

        Returns:
            Filename portion (e.g., "scan.sarif" from "s3://bucket/scans/scan.sarif")
        """
        if "/" in source_name:
            return source_name.rsplit("/", 1)[-1] or source_name
        return source_name

    def detect_format(
        self,
        filename: str,
        requested_format: str,
        tool_hint: Optional[str] = None,
    ) -> str:
        """Detect the security file format based on request parameters and filename.

        Args:
            filename: Filename to analyze
            requested_format: Format specified by user ("auto", "sarif", "spdx", etc.)
            tool_hint: Optional tool name hint for auto-detection

        Returns:
            Detected format: "sarif", "spdx", "jsonpath", or tool name

        Raises:
            DocumentParseError: If format cannot be detected
        """
        from certus_ask.core.exceptions import DocumentParseError

        fmt = (requested_format or "auto").lower()
        if fmt != "auto":
            return fmt

        lowered = filename.lower()
        if lowered.endswith(".sarif") or ".sarif." in lowered:
            return "sarif"
        if lowered.endswith((".spdx.json", ".spdx.yaml", ".spdx.yml")):
            return "spdx"
        if tool_hint:
            return tool_hint

        raise DocumentParseError(
            message="Could not detect file format",
            error_code="unknown_format",
            details={"filename": filename},
        )

    def parse_sarif(
        self,
        file_path: Path,
        ingestion_id: str,
        workspace_id: str,
    ) -> tuple[Any, list[Document], int]:
        """Parse SARIF file and generate initial documents.

        Args:
            file_path: Path to SARIF file
            ingestion_id: Unique ingestion identifier
            workspace_id: Workspace identifier

        Returns:
            Tuple of (unified_scan, base_documents, findings_count)
            - unified_scan: Parsed scan data
            - base_documents: Empty list (documents created later with Neo4j data)
            - findings_count: Number of findings found

        Raises:
            DocumentParseError: If SARIF parsing fails
        """
        from certus_ask.pipelines.security_scan_parsers import parse_security_scan

        logger.info("parse_sarif called", file_path=str(file_path), ingestion_id=ingestion_id)

        raw_json = json.loads(file_path.read_text(encoding="utf-8"))
        unified_scan = parse_security_scan(raw_json, tool_hint="sarif")

        findings_indexed = len(unified_scan.findings)

        logger.info(
            "parse_sarif completed",
            findings_count=findings_indexed,
            tool=unified_scan.metadata.tool_version or "unknown",
        )

        # Return parsed data; documents will be created after Neo4j processing
        return unified_scan, [], findings_indexed

    def parse_spdx(
        self,
        file_path: Path,
        ingestion_id: str,
        workspace_id: str,
    ) -> tuple[dict[str, Any], list[Document], int]:
        """Parse SPDX file and generate initial documents.

        Args:
            file_path: Path to SPDX file
            ingestion_id: Unique ingestion identifier
            workspace_id: Workspace identifier

        Returns:
            Tuple of (spdx_data, base_documents, package_count)
            - spdx_data: Parsed SPDX JSON
            - base_documents: Empty list (documents created later with Neo4j data)
            - package_count: Number of packages found

        Raises:
            DocumentParseError: If SPDX parsing fails
        """
        from certus_ask.pipelines.spdx import SpdxFileToDocuments

        logger.info("parse_spdx called", file_path=str(file_path), ingestion_id=ingestion_id)

        parser = SpdxFileToDocuments()
        parse_result = parser.run(file_path)
        spdx_data = parse_result["spdx_data"]

        package_count = len(spdx_data.get("packages", []))

        logger.info(
            "parse_spdx completed",
            package_count=package_count,
            sbom_name=spdx_data.get("name", "unknown"),
        )

        # Return parsed data; documents will be created after Neo4j processing
        return spdx_data, [], package_count

    def parse_jsonpath(
        self,
        file_path: Path,
        schema: dict[str, Any],
        ingestion_id: str,
        workspace_id: str,
    ) -> tuple[Any, list[Document], int]:
        """Parse file using custom JSONPath schema.

        Args:
            file_path: Path to file
            schema: JSONPath schema definition
            ingestion_id: Unique ingestion identifier
            workspace_id: Workspace identifier

        Returns:
            Tuple of (unified_scan, documents, findings_count)
            - unified_scan: Parsed scan data
            - documents: Generated documents
            - findings_count: Number of findings found

        Raises:
            ValidationError: If schema is invalid
            DocumentParseError: If parsing fails
        """
        from certus_ask.pipelines.security_scan_parsers import (
            JSONPathParser,
            SchemaLoader,
            get_parser_registry,
        )

        logger.info("parse_jsonpath called", file_path=str(file_path), ingestion_id=ingestion_id)

        schema_loader = SchemaLoader()
        schema_loader.validate_schema(schema)
        jsonpath_parser = JSONPathParser(schema)

        raw_json = json.loads(file_path.read_text(encoding="utf-8"))
        unified_scan = jsonpath_parser.parse(raw_json)

        # Register parser for future use
        registry = get_parser_registry()
        registry.register(jsonpath_parser)

        findings_indexed = len(unified_scan.findings)
        tool_name = unified_scan.metadata.tool_name

        # Generate markdown document
        markdown_content = f"# {tool_name} Findings\n\n"
        markdown_content += f"Tool Version: {unified_scan.metadata.tool_version or 'Unknown'}\n"
        markdown_content += f"Findings: {findings_indexed}\n\n"

        for finding in unified_scan.findings:
            markdown_content += f"## {finding.title}\n"
            markdown_content += f"**Severity:** {finding.severity}\n"
            markdown_content += f"**ID:** {finding.id}\n"
            if finding.location:
                markdown_content += f"**Location:** {finding.location.file_path}:{finding.location.line_start}\n"
            markdown_content += f"\n{finding.description}\n\n"

        document = Document(
            content=markdown_content,
            meta={
                "source": "jsonpath",
                "ingestion_id": ingestion_id,
                "workspace_id": workspace_id,
                "neo4j_available": False,
                "tool": tool_name,
                "tool_version": unified_scan.metadata.tool_version or "unknown",
                "findings_indexed": findings_indexed,
            },
        )

        logger.info("parse_jsonpath completed", findings_count=findings_indexed, tool=tool_name)

        return unified_scan, [document], findings_indexed

    def parse_preregistered_tool(
        self,
        file_path: Path,
        tool_name: str,
        ingestion_id: str,
        workspace_id: str,
    ) -> tuple[Any, list[Document], int]:
        """Parse file using pre-registered tool schema (Bandit, Trivy, OpenGrep, etc.).

        Args:
            file_path: Path to file
            tool_name: Name of pre-registered tool ("bandit", "trivy", "opengrep", etc.)
            ingestion_id: Unique ingestion identifier
            workspace_id: Workspace identifier

        Returns:
            Tuple of (unified_scan, documents, findings_count)
            - unified_scan: Parsed scan data
            - documents: Generated documents
            - findings_count: Number of findings found

        Raises:
            FileUploadError: If parsing fails
        """
        from certus_ask.core.exceptions import FileUploadError
        from certus_ask.pipelines.security_scan_parsers import JSONPathParser, SchemaLoader

        logger.info(
            "parse_preregistered_tool called",
            tool=tool_name,
            file_path=str(file_path),
            ingestion_id=ingestion_id,
        )

        try:
            schema_loader = SchemaLoader()
            schema = schema_loader.load_schema_by_name(tool_name)
            jsonpath_parser = JSONPathParser(schema)

            raw_json = json.loads(file_path.read_text(encoding="utf-8"))
            unified_scan = jsonpath_parser.parse(raw_json)

            findings_indexed = len(unified_scan.findings)
            tool_display_name = unified_scan.metadata.tool_name

            # Generate markdown document
            markdown_content = f"# {tool_display_name} Findings\n\n"
            markdown_content += f"Tool Version: {unified_scan.metadata.tool_version or 'Unknown'}\n"
            markdown_content += f"Findings: {findings_indexed}\n\n"

            for finding in unified_scan.findings:
                markdown_content += f"## {finding.title}\n"
                markdown_content += f"**Severity:** {finding.severity}\n"
                markdown_content += f"**ID:** {finding.id}\n"
                if finding.location:
                    markdown_content += f"**Location:** {finding.location.file_path}:{finding.location.line_start}\n"
                markdown_content += f"\n{finding.description}\n\n"

            document = Document(
                content=markdown_content,
                meta={
                    "source": tool_name,
                    "ingestion_id": ingestion_id,
                    "workspace_id": workspace_id,
                    "neo4j_available": False,
                    "tool": tool_display_name,
                    "tool_version": unified_scan.metadata.tool_version or "unknown",
                    "findings_indexed": findings_indexed,
                },
            )

            logger.info(
                "parse_preregistered_tool completed",
                tool=tool_name,
                findings_count=findings_indexed,
            )

            return unified_scan, [document], findings_indexed

        except Exception as exc:
            logger.error(
                event="parse_preregistered_tool_failed",
                ingestion_id=ingestion_id,
                tool=tool_name,
                error=str(exc),
                exc_info=True,
            )
            raise FileUploadError(
                message=f"Failed to process {tool_name.upper()} file",
                error_code=f"{tool_name}_processing_failed",
                details={"filename": str(file_path)},
            ) from exc

    async def verify_trust_chain(
        self,
        signatures: dict[str, Any],
        artifact_locations: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify trust chain for premium tier ingestion.

        Args:
            signatures: Signature data from client
            artifact_locations: Expected artifact locations/digests

        Returns:
            Verification proof dictionary with chain_verified, signer_outer, etc.

        Raises:
            ValidationError: If verification fails or trust client not configured
        """
        from certus_ask.core.exceptions import ValidationError

        if not self.trust_client:
            raise ValidationError(
                message="Trust client not configured for premium tier",
                error_code="trust_client_missing",
            )

        logger.info("verify_trust_chain called")

        verification = await self.trust_client.verify_chain(
            artifact_locations=artifact_locations,
            signatures=signatures,
        )

        if not verification.chain_verified:
            raise ValidationError(
                message="Non-repudiation chain verification failed",
                error_code="verification_failed",
                details=verification.raw,
            )

        logger.info(
            "verify_trust_chain completed",
            chain_verified=True,
            signer=verification.signer_outer,
        )

        return verification.verification_proof

    def verify_digest(
        self,
        file_bytes: bytes,
        artifact_locations: dict[str, Any],
        s3_bucket: Optional[str] = None,
        s3_key: Optional[str] = None,
    ) -> Optional[str]:
        """Verify file digest matches expected value from artifact_locations.

        Args:
            file_bytes: Raw file bytes to verify
            artifact_locations: Expected artifact locations/digests
            s3_bucket: Optional S3 bucket name
            s3_key: Optional S3 key

        Returns:
            Actual digest or None if no expected digest found

        Raises:
            ValidationError: If digest verification fails
        """

        logger.info("verify_digest called", s3_bucket=s3_bucket, s3_key=s3_key)

        # Import helper function from router (will be moved to service layer eventually)
        from certus_ask.routers.ingestion import _enforce_verified_digest

        digest_result = _enforce_verified_digest(
            file_bytes,
            artifact_locations,
            s3_bucket,
            s3_key,
        )

        if digest_result is None and s3_bucket and s3_key:
            logger.warning(
                "verify_digest.digest_missing",
                bucket=s3_bucket,
                key=s3_key,
            )

        logger.info("verify_digest completed", digest=digest_result)
        return digest_result

    def create_sarif_documents(
        self,
        unified_scan: Any,
        metadata: dict[str, Any],
        neo4j_scan_id: Optional[str],
        markdown_content: str,
        verification_proof: Optional[dict[str, Any]] = None,
    ) -> list[Document]:
        """Create documents from SARIF scan results.

        Args:
            unified_scan: Parsed SARIF scan data
            metadata: Base metadata (workspace_id, ingestion_id, etc.)
            neo4j_scan_id: Neo4j scan identifier if available
            markdown_content: Markdown summary content
            verification_proof: Optional verification proof for premium tier

        Returns:
            List of Document objects ready for embedding/indexing
        """
        logger.info(
            "create_sarif_documents called",
            findings_count=len(unified_scan.findings),
            neo4j_scan_id=neo4j_scan_id,
        )

        documents = []

        # Create summary document
        doc_meta = {
            "source": "sarif",
            "record_type": "scan_report",
            "ingestion_id": metadata["ingestion_id"],
            "workspace_id": metadata["workspace_id"],
            "neo4j_scan_id": neo4j_scan_id,
            "neo4j_available": neo4j_scan_id is not None,
            "tool": unified_scan.metadata.tool_version or "unknown",
            "findings_indexed": len(unified_scan.findings),
            "tier": metadata.get("tier", "free"),
        }

        # Add verification proof for premium tier
        if verification_proof:
            doc_meta["chain_verified"] = verification_proof.get("chain_verified")
            doc_meta["signer_outer"] = verification_proof.get("signer_outer")
            doc_meta["sigstore_timestamp"] = verification_proof.get("sigstore_timestamp")

        summary_doc = Document(content=markdown_content, meta=doc_meta)
        documents.append(summary_doc)

        # Create individual finding documents
        for finding in unified_scan.findings:
            location = finding.location
            location_label = None
            if location and location.file_path:
                line_value = location.line_start or 0
                location_label = f"{location.file_path}:{line_value}"

            finding_content = f"## {finding.title}\n\n"
            finding_content += f"- Rule: {finding.id}\n"
            finding_content += f"- Severity: {finding.severity}\n"
            if location_label:
                finding_content += f"- Location: {location_label}\n"
            if finding.description:
                finding_content += f"\n{finding.description}\n"

            finding_doc = Document(
                content=finding_content,
                meta={
                    "source": "sarif",
                    "record_type": "finding",
                    "ingestion_id": metadata["ingestion_id"],
                    "workspace_id": metadata["workspace_id"],
                    "rule_id": finding.id,
                    "severity": finding.severity,
                    "source_location": location_label,
                    "neo4j_scan_id": neo4j_scan_id,
                    "tool": unified_scan.metadata.tool_version or "unknown",
                    "finding_title": finding.title,
                },
            )
            documents.append(finding_doc)

        logger.info("create_sarif_documents completed", document_count=len(documents))
        return documents

    def create_spdx_documents(
        self,
        spdx_data: dict[str, Any],
        metadata: dict[str, Any],
        neo4j_sbom_id: Optional[str],
        markdown_content: str,
    ) -> list[Document]:
        """Create documents from SPDX SBOM data.

        Args:
            spdx_data: Parsed SPDX JSON data
            metadata: Base metadata (workspace_id, ingestion_id, etc.)
            neo4j_sbom_id: Neo4j SBOM identifier if available
            markdown_content: Markdown summary content

        Returns:
            List of Document objects ready for embedding/indexing
        """
        logger.info(
            "create_spdx_documents called",
            package_count=len(spdx_data.get("packages", [])),
            neo4j_sbom_id=neo4j_sbom_id,
        )

        documents = []

        # Create summary document
        summary_doc = Document(
            content=markdown_content,
            meta={
                "source": "spdx",
                "record_type": "sbom_report",
                "ingestion_id": metadata["ingestion_id"],
                "workspace_id": metadata["workspace_id"],
                "neo4j_sbom_id": neo4j_sbom_id,
                "neo4j_available": neo4j_sbom_id is not None,
                "sbom_name": spdx_data.get("name", "unknown"),
            },
        )
        documents.append(summary_doc)

        # Create individual package documents
        for package in spdx_data.get("packages", []):
            package_name = package.get("name", "unknown")
            package_version = package.get("versionInfo", "unknown")
            licenses = [package.get("licenseDeclared"), package.get("licenseConcluded")]
            licenses = [lic for lic in licenses if lic]
            supplier = package.get("supplier")
            location = package.get("downloadLocation")
            external_refs = [
                f"{ref.get('referenceType')}:{ref.get('referenceLocator')}"
                for ref in package.get("externalRefs", [])
                if ref.get("referenceType") and ref.get("referenceLocator")
            ]

            package_content = f"### Package {package_name} ({package_version})\n"
            if supplier:
                package_content += f"Supplier: {supplier}\n"
            if location:
                package_content += f"Download: {location}\n"
            if licenses:
                package_content += "Licenses:\n"
                for lic in licenses:
                    package_content += f"- {lic}\n"
            if external_refs:
                package_content += "External References:\n"
                for ref in external_refs:
                    package_content += f"- {ref}\n"

            package_doc = Document(
                content=package_content,
                meta={
                    "source": "spdx",
                    "record_type": "package",
                    "ingestion_id": metadata["ingestion_id"],
                    "workspace_id": metadata["workspace_id"],
                    "package_name": package_name,
                    "package_version": package_version,
                    "licenses": licenses,
                    "supplier": supplier,
                    "external_refs": external_refs,
                    "neo4j_sbom_id": neo4j_sbom_id,
                },
            )
            documents.append(package_doc)

        logger.info("create_spdx_documents completed", document_count=len(documents))
        return documents

    async def embed_documents(self, documents: list[Document]) -> list[Document]:
        """Embed documents using configured embedding model.

        Args:
            documents: List of documents to embed

        Returns:
            List of documents with embeddings attached
        """
        from certus_ask.pipelines.preprocessing import LoggingDocumentEmbedder

        logger.info("embed_documents called", document_count=len(documents))

        document_embedder = LoggingDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
        embed_result = document_embedder.run(documents=documents)
        embedded_documents = embed_result.get("documents", [])

        if not embedded_documents:
            logger.warning("embed_documents.embedding_empty")
        else:
            logger.info(
                "embed_documents completed",
                embedded_count=len(embedded_documents),
                sample_has_embedding=embedded_documents[0].embedding is not None,
            )

        return embedded_documents

    async def process(
        self,
        workspace_id: str,
        file_bytes: bytes,
        source_name: str,
        requested_format: str,
        tool_hint: Optional[str] = None,
        schema_dict: Optional[dict[str, Any]] = None,
        ingestion_id: str = "",
        tier: str = "free",
        assessment_id: Optional[str] = None,
        signatures: Optional[dict[str, Any]] = None,
        artifact_locations: Optional[dict[str, Any]] = None,
        s3_bucket: Optional[str] = None,
        s3_key: Optional[str] = None,
        document_store: Optional[Any] = None,
        settings: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Master orchestration method for security file processing.

        This method coordinates all phases of security scan ingestion:
        1. Format detection
        2. Trust verification (premium tier)
        3. Parsing (format-specific)
        4. Neo4j loading (if enabled)
        5. Document creation
        6. Embedding
        7. Writing to document store

        Args:
            workspace_id: Workspace identifier
            file_bytes: Raw file bytes
            source_name: Source filename or identifier
            requested_format: Requested format ("auto", "sarif", "spdx", etc.)
            tool_hint: Optional tool name hint for detection
            schema_dict: Optional JSONPath schema for custom parsing
            ingestion_id: Unique ingestion identifier
            tier: Service tier ("free" or "premium")
            assessment_id: Optional assessment identifier (premium tier)
            signatures: Optional signature data (premium tier)
            artifact_locations: Optional artifact locations (premium tier)
            s3_bucket: Optional S3 bucket name
            s3_key: Optional S3 key
            document_store: Document store instance
            settings: Settings instance

        Returns:
            Dictionary with processing results:
            - ingestion_id: Unique identifier
            - findings_indexed: Number of findings/packages indexed
            - document_count: Total documents in store
            - neo4j_scan_id: Neo4j scan ID (if applicable)
            - neo4j_sbom_id: Neo4j SBOM ID (if applicable)
            - format: Detected format

        Raises:
            ValidationError: If validation fails (premium tier requirements, etc.)
            DocumentParseError: If parsing fails
            FileUploadError: If processing fails
        """
        from certus_ask.core.exceptions import DocumentParseError, ValidationError
        from certus_ask.pipelines.components import LoggingDocumentWriter
        from certus_ask.services.ingestion import FileProcessor

        logger.info(
            "process called",
            workspace_id=workspace_id,
            source_name=source_name,
            requested_format=requested_format,
            tier=tier,
            ingestion_id=ingestion_id,
        )

        # 1. Detect format
        filename_hint = self.extract_filename(source_name)
        detected_format = self.detect_format(filename_hint, requested_format, tool_hint)

        neo4j_scan_id: Optional[str] = None
        neo4j_sbom_id: Optional[str] = None
        verification_proof: Optional[dict[str, Any]] = None

        # 2. Verify trust (if premium tier)
        if tier == "premium":
            if not assessment_id:
                raise ValidationError(
                    message="assessment_id is required for premium tier",
                    error_code="missing_assessment_id",
                )
            if not signatures:
                raise ValidationError(
                    message="signatures are required for premium tier",
                    error_code="missing_signatures",
                )
            if not artifact_locations:
                raise ValidationError(
                    message="artifact_locations are required for premium tier",
                    error_code="missing_artifact_locations",
                )

            try:
                verification_proof = await self.verify_trust_chain(signatures, artifact_locations)
                self.verify_digest(file_bytes, artifact_locations, s3_bucket, s3_key)

                logger.info(
                    event="process.trust_verification_passed",
                    ingestion_id=ingestion_id,
                    assessment_id=assessment_id,
                    signer=verification_proof.get("signer_outer"),
                )
            except Exception as exc:
                logger.error(
                    event="process.trust_verification_failed",
                    ingestion_id=ingestion_id,
                    assessment_id=assessment_id,
                    error=str(exc),
                    exc_info=True,
                )
                raise

        # Determine file suffix for temp file
        suffix = Path(filename_hint).suffix or ""
        if detected_format in {"sarif", "spdx"}:
            suffix = f".{detected_format}"
        elif detected_format == "jsonpath" and not suffix:
            suffix = ".json"
        elif not suffix:
            suffix = ".tmp"

        # Save bytes to temp file
        file_processor = FileProcessor()
        file_path = file_processor.save_to_temp(file_bytes, suffix=suffix)

        try:
            findings_indexed = 0
            documents_to_write: list[Document] = []

            # 3. Parse based on format
            if detected_format == "sarif":
                unified_scan, _, findings_indexed = self.parse_sarif(file_path, ingestion_id, workspace_id)

                # Generate initial markdown
                markdown_content = f"# {unified_scan.metadata.tool_version or 'SARIF'} Findings\n\n"
                markdown_content += f"Scan Target: {unified_scan.metadata.scan_target or 'Unknown'}\n"
                markdown_content += f"Findings: {findings_indexed}\n\n"

                for finding in unified_scan.findings:
                    markdown_content += f"## {finding.title}\n"
                    markdown_content += f"**Severity:** {finding.severity}\n"
                    markdown_content += f"**ID:** {finding.id}\n"
                    if finding.location:
                        markdown_content += (
                            f"**Location:** {finding.location.file_path}:{finding.location.line_start}\n"
                        )
                    markdown_content += f"\n{finding.description}\n\n"

                # Load into Neo4j if enabled
                if settings and settings.neo4j_enabled and self.neo4j_service:
                    neo4j_scan_id = assessment_id if assessment_id else f"neo4j-{workspace_id}-scan"
                    try:
                        raw_json = json.loads(file_path.read_text(encoding="utf-8"))
                        graph_result = self.neo4j_service.load_sarif(
                            raw_json,
                            neo4j_scan_id,
                            verification_proof=verification_proof,
                            assessment_id=assessment_id,
                        )
                        markdown_content = self.neo4j_service.generate_sarif_markdown(neo4j_scan_id)
                    except Exception as neo4j_error:
                        logger.warning(
                            event="process.neo4j_failed",
                            ingestion_id=ingestion_id,
                            format="sarif",
                            error=str(neo4j_error),
                        )
                        neo4j_scan_id = None

                # Create documents
                metadata = {
                    "workspace_id": workspace_id,
                    "ingestion_id": ingestion_id,
                    "tier": tier,
                }
                documents_to_write = self.create_sarif_documents(
                    unified_scan,
                    metadata,
                    neo4j_scan_id,
                    markdown_content,
                    verification_proof,
                )

            elif detected_format == "spdx":
                spdx_data, _, package_count = self.parse_spdx(file_path, ingestion_id, workspace_id)
                findings_indexed = package_count

                markdown_content = ""

                # Load into Neo4j if enabled
                if settings and settings.neo4j_enabled and self.neo4j_service:
                    neo4j_sbom_id = f"neo4j-{workspace_id}-sbom"
                    try:
                        graph_result = self.neo4j_service.load_spdx(spdx_data, neo4j_sbom_id)
                        findings_indexed = graph_result["package_count"]
                        markdown_content = self.neo4j_service.generate_spdx_markdown(neo4j_sbom_id)
                    except Exception as neo4j_error:
                        logger.warning(
                            event="process.neo4j_failed",
                            ingestion_id=ingestion_id,
                            format="spdx",
                            error=str(neo4j_error),
                        )
                        findings_indexed = len(spdx_data.get("packages", []))
                        markdown_content = (
                            f"# SPDX SBOM\n\n{findings_indexed} packages found (Neo4j unavailable, basic text only)."
                        )
                        neo4j_sbom_id = None

                if not markdown_content:
                    findings_indexed = len(spdx_data.get("packages", []))
                    markdown_content = f"# SPDX SBOM\n\n{findings_indexed} packages found."

                # Create documents
                metadata = {
                    "workspace_id": workspace_id,
                    "ingestion_id": ingestion_id,
                }
                documents_to_write = self.create_spdx_documents(
                    spdx_data,
                    metadata,
                    neo4j_sbom_id,
                    markdown_content,
                )

            elif detected_format in {"bandit", "opengrep", "trivy"}:
                _, documents_to_write, findings_indexed = self.parse_preregistered_tool(
                    file_path,
                    detected_format,
                    ingestion_id,
                    workspace_id,
                )

            elif detected_format == "jsonpath" or (requested_format == "auto" and schema_dict):
                if schema_dict is None:
                    raise ValidationError(
                        message="schema_dict is required for JSONPath parsing",
                        error_code="missing_schema",
                        details={"format": detected_format},
                    )

                _, documents_to_write, findings_indexed = self.parse_jsonpath(
                    file_path,
                    schema_dict,
                    ingestion_id,
                    workspace_id,
                )

            else:
                raise DocumentParseError(
                    message=f"Unsupported format: {detected_format}",
                    error_code="unsupported_format",
                    details={
                        "format": detected_format,
                        "supported_formats": ["sarif", "spdx", "jsonpath"],
                        "filename": filename_hint,
                    },
                )

            # 4. Embed documents
            embedded_documents = await self.embed_documents(documents_to_write)

            # 5. Write to document store
            if document_store:
                metadata_context = {
                    "workspace_id": workspace_id,
                    "ingestion_id": ingestion_id,
                    "source": detected_format,
                    "source_location": source_name,
                    "extra_meta": {
                        "filename": filename_hint,
                        "dual_indexed": settings and settings.neo4j_enabled,
                    },
                }

                writer = LoggingDocumentWriter(document_store, metadata_context=metadata_context)
                writer.run(embedded_documents)

                logger.info(
                    event="process.security_indexed",
                    ingestion_id=ingestion_id,
                    filename=source_name,
                    format=detected_format,
                    items_indexed=findings_indexed,
                    total_documents=document_store.count_documents(),
                    neo4j_enabled=settings and settings.neo4j_enabled,
                )

            # 6. Return results
            return {
                "ingestion_id": ingestion_id,
                "findings_indexed": findings_indexed,
                "document_count": document_store.count_documents() if document_store else len(embedded_documents),
                "neo4j_scan_id": neo4j_scan_id,
                "neo4j_sbom_id": neo4j_sbom_id,
                "format": detected_format,
            }

        finally:
            # Cleanup temp file
            file_path.unlink(missing_ok=True)
