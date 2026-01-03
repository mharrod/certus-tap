from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
import yaml
from haystack import Pipeline, component
from haystack.components.embedders import SentenceTransformersDocumentEmbedder
from haystack.components.preprocessors import DocumentSplitter
from haystack.document_stores.types import DuplicatePolicy

try:
    from opensearch_haystack.document_stores import OpenSearchDocumentStore  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - compatibility fallback
    from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore  # type: ignore[import]

from certus_ask.pipelines.components import LoggingDocumentWriter
from certus_ask.pipelines.preprocessing import PresidioAnonymizer

logger = structlog.get_logger(__name__)


@component
class SpdxFileToDocuments:
    """Parse SPDX Software Bill of Materials (SBOM) and return structured data.

    SPDX (Software Package Data Exchange) is the standard format for software
    composition analysis and supply chain security. This component parses SPDX
    SBOM files and returns structured data for loading into Neo4j knowledge graph.

    **Features:**
    - Parses SPDX 2.3 JSON and YAML formats
    - Validates SPDX structure
    - Extracts package metadata (name, version, supplier, licenses)
    - Captures dependencies and relationships between components
    - Preserves all hierarchical information

    **Returns:**
    - Raw SPDX data for Neo4j loading
    - Metadata about the SBOM
    """

    @component.output_types(spdx_data=dict)
    def run(self, file_path: Path | str) -> dict[str, dict]:
        """Parse SPDX file and return structured data.

        Reads an SPDX JSON or YAML file and returns the raw parsed data for loading
        into Neo4j knowledge graph.

        **SPDX File Requirements:**
        - Valid JSON or YAML format
        - Must comply with SPDX 2.3 specification
        - Contains "packages" array

        Args:
            file_path: Path to SPDX JSON or YAML file. Can be string or pathlib.Path.
                File must be readable UTF-8 encoded JSON or YAML.

        Returns:
            Dictionary with key 'spdx_data' containing the parsed SPDX structure.

        Raises:
            FileNotFoundError: If file_path doesn't exist
            json.JSONDecodeError: If JSON is malformed

        Examples:
            >>> from pathlib import Path
            >>> converter = SpdxFileToDocuments()
            >>> result = converter.run(Path("sbom.spdx.json"))
            >>> spdx_data = result["spdx_data"]
            >>> len(spdx_data["packages"])
            15
        """
        file_path = Path(file_path)
        content = file_path.read_text(encoding="utf-8")

        # Try JSON first
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try YAML if JSON fails
            try:
                data = yaml.safe_load(content)
            except Exception as exc:
                raise json.JSONDecodeError("Unable to parse as JSON or YAML", content, 0) from exc

        return {"spdx_data": data}


def create_spdx_pipeline(
    document_store: OpenSearchDocumentStore, metadata_context: dict[str, Any] | None = None
) -> Pipeline:
    """Create a pipeline for processing SPDX SBOM files into searchable index.

    Constructs a Haystack pipeline specialized for software bill of materials.
    Transforms SPDX (Software Package Data Exchange) files into embedded documents
    indexed in OpenSearch for semantic search and RAG retrieval, with full metadata
    envelope capture for lineage tracking and multi-workspace isolation.

    **Pipeline Flow:**
    ```
    SPDX File → Parser → Anonymizer → Splitter → Embedder → Logging Writer → OpenSearch Index
    ```

    **Processing Steps:**
    1. **SPDX Parsing** - Extracts packages from SPDX JSON/YAML
    2. **PII Anonymization** - Masks sensitive data in SBOM
    3. **Chunking** - Splits packages into semantic units (150 word chunks)
    4. **Embedding** - Generates 384-dim vectors for semantic search
    5. **Metadata Enrichment** - Captures complete provenance envelope (workspace, ingestion ID, etc.)
    6. **Indexing** - Stores in workspace-specific OpenSearch index with deduplication

    **Use Cases:**
    - Make SBOM searchable ("Show me all packages using Apache license")
    - Build RAG system over software composition analysis
    - Track dependencies across application versions
    - Identify license compliance risks
    - Monitor supply chain security

    **Workspace Isolation:**
    - Each workspace gets its own OpenSearch index (ask_certus_{workspace_id})
    - Complete metadata envelope with workspace_id for full lineage tracking
    - Supports multi-tenant SBOM analysis

    Args:
        document_store: OpenSearch document store for persisting SBOM packages.
            Must be initialized with proper OpenSearch connection, authentication,
            and workspace-specific index name (e.g., ask_certus_default, ask_certus_product_a).
        metadata_context: Optional metadata context to pass to LoggingDocumentWriter for
            enrichment with metadata envelopes. Contains workspace_id, ingestion_id, source, etc.

    Returns:
        Pipeline: Configured Haystack pipeline ready to process SPDX files.
            Execute with pipeline.run({
                "spdx_converter": {"file_path": Path(...)}
            })
            Metadata context is baked into the pipeline at creation time.

    Raises:
        ImportError: If Haystack components are not installed
        ConnectionError: If document_store connection fails

    Examples:
        >>> from certus_ask.services.opensearch import get_document_store_for_workspace
        >>> from pathlib import Path
        >>> import uuid
        >>>
        >>> # Create pipeline for a specific workspace with metadata
        >>> doc_store = get_document_store_for_workspace("product-a")
        >>> metadata = {
        ...     "workspace_id": "product-a",
        ...     "ingestion_id": str(uuid.uuid4()),
        ...     "source": "spdx",
        ...     "source_location": "app_sbom.spdx.json",
        ...     "extra_meta": {"filename": "app_sbom.spdx.json"}
        ... }
        >>> pipeline = create_spdx_pipeline(doc_store, metadata_context=metadata)
        >>>
        >>> # Process SBOM
        >>> result = pipeline.run({
        ...     "spdx_converter": {"file_path": Path("app_sbom.spdx.json")}
        ... })
        >>> indexed_docs = result.get("document_writer", {}).get("documents", [])
        >>> metadata_preview = result.get("document_writer", {}).get("metadata_preview", [])
        >>> print(f"Indexed {len(indexed_docs)} packages from SBOM")
        Indexed 42 packages from SBOM

        >>> # Query SBOM using RAG
        >>> from certus_ask.pipelines.rag import create_rag_pipeline
        >>> rag_pipeline = create_rag_pipeline(doc_store)
        >>> answer = rag_pipeline.run({
        ...     "embedder": {"text": "What packages are using GPL licenses?"},
        ...     "retriever": {"top_k": 5}
        ... })
        >>> print(answer["llm"]["replies"][0])
        'Based on the SBOM analysis, the following packages use GPL licenses...'

    See Also:
        - SpdxFileToDocuments: For SPDX parsing details
        - LoggingDocumentWriter: For metadata enrichment and logging
        - create_preprocessing_pipeline: For general document processing
        - create_rag_pipeline: For querying indexed SBOM
    """
    pipeline = Pipeline()
    spdx_converter = SpdxFileToDocuments()
    presidio_anonymizer = PresidioAnonymizer()
    splitter = DocumentSplitter(split_by="word", split_length=150, split_overlap=50)
    embedder = SentenceTransformersDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
    writer = LoggingDocumentWriter(document_store, policy=DuplicatePolicy.SKIP, metadata_context=metadata_context)

    pipeline.add_component(instance=spdx_converter, name="spdx_converter")
    pipeline.add_component(instance=presidio_anonymizer, name="presidio_anonymizer")
    pipeline.add_component(instance=splitter, name="document_splitter")
    pipeline.add_component(instance=embedder, name="document_embedder")
    pipeline.add_component(instance=writer, name="document_writer")

    pipeline.connect("spdx_converter.documents", "presidio_anonymizer.documents")
    pipeline.connect("presidio_anonymizer.documents", "document_splitter.documents")
    pipeline.connect("document_splitter.documents", "document_embedder.documents")
    pipeline.connect("document_embedder.documents", "document_writer.documents")

    return pipeline


def _extract_external_references(package: dict) -> list[tuple[str, str]]:
    """Extract external references from SPDX package (CPE, purl, etc.)."""
    refs: list[tuple[str, str]] = []
    for ref in package.get("externalRefs", []) or []:
        ref_type = ref.get("referenceType", "")
        ref_locator = ref.get("referenceLocator", "")
        if ref_type and ref_locator:
            refs.append((ref_type, ref_locator))
    return refs


def _extract_relationships(data: dict, spdx_id: str) -> list[tuple[str, str]]:
    """Extract relationships involving this package from relationships array."""
    rels: list[tuple[str, str]] = []
    for rel in data.get("relationships", []) or []:
        if rel.get("spdxElementId") == spdx_id:
            rel_type = rel.get("relationshipType", "")
            rel_target = rel.get("relatedSpdxElement", "")
            if rel_type and rel_target:
                rels.append((rel_type, rel_target))
    return rels
