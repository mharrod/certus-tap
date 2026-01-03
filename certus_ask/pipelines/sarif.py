from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import structlog
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
class SarifFileToDocuments:
    """Parse SARIF security scan results and return structured data.

    SARIF (Static Analysis Results Interchange Format) is the standard format for
    security and code analysis tools. This component parses SARIF files and returns
    structured data for loading into Neo4j knowledge graph.

    **Features:**
    - Parses SARIF 2.1.0 compliant JSON files
    - Validates SARIF structure
    - Extracts vulnerability findings with severity levels
    - Captures source code locations (file:line)
    - Preserves relationships and hierarchies

    **Returns:**
    - Raw SARIF data for Neo4j loading
    - Metadata about the scan
    """

    @component.output_types(sarif_data=dict)
    def run(self, file_path: Path | str) -> dict[str, dict]:
        """Parse SARIF file and return structured data.

        Reads a SARIF JSON file and returns the raw parsed data for loading
        into Neo4j knowledge graph.

        **SARIF File Requirements:**
        - Valid JSON format
        - Must comply with SARIF 2.1.0 specification
        - Contains "runs" array with "results"

        Args:
            file_path: Path to SARIF JSON file. Can be string or pathlib.Path.
                File must be readable UTF-8 encoded JSON.

        Returns:
            Dictionary with key 'sarif_data' containing the parsed SARIF structure.

        Raises:
            FileNotFoundError: If file_path doesn't exist
            json.JSONDecodeError: If file is not valid JSON

        Examples:
            >>> from pathlib import Path
            >>> converter = SarifFileToDocuments()
            >>> result = converter.run(Path("scan_results.sarif"))
            >>> sarif_data = result["sarif_data"]
            >>> len(sarif_data["runs"])
            1
        """
        data = json.loads(Path(file_path).read_text(encoding="utf-8"))
        return {"sarif_data": data}


def create_sarif_pipeline(
    document_store: OpenSearchDocumentStore, metadata_context: dict[str, Any] | None = None
) -> Pipeline:
    """Create a pipeline for processing SARIF security scan files into searchable index.

    Constructs a Haystack pipeline specialized for security findings. Transforms
    SARIF (Static Analysis Results Interchange Format) files into embedded documents
    indexed in OpenSearch for semantic search and RAG retrieval, with full metadata
    envelope capture for lineage tracking and multi-workspace isolation.

    **Pipeline Flow:**
    ```
    SARIF File → Parser → Anonymizer → Splitter → Embedder → Logging Writer → OpenSearch Index
    ```

    **Processing Steps:**
    1. **SARIF Parsing** - Extracts findings from SARIF JSON
    2. **PII Anonymization** - Masks sensitive data in findings
    3. **Chunking** - Splits findings into semantic units (150 word chunks)
    4. **Embedding** - Generates 384-dim vectors for semantic search
    5. **Metadata Enrichment** - Captures complete provenance envelope (workspace, ingestion ID, etc.)
    6. **Indexing** - Stores in workspace-specific OpenSearch index with deduplication

    **Use Cases:**
    - Make security findings searchable ("Show me all SQL injection risks")
    - Build RAG system over security scan history
    - Correlate findings across multiple scans
    - Track remediation progress
    - Audit which workspace/scan produced which findings

    **Workspace Isolation:**
    - Each workspace gets its own OpenSearch index (ask_certus_{workspace_id})
    - Complete metadata envelope with workspace_id for full lineage tracking
    - Supports multi-tenant scanning scenarios

    Args:
        document_store: OpenSearch document store for persisting findings.
            Must be initialized with proper OpenSearch connection, authentication,
            and workspace-specific index name (e.g., ask_certus_default, ask_certus_product_a).
        metadata_context: Optional metadata context to pass to LoggingDocumentWriter for
            enrichment with metadata envelopes. Contains workspace_id, ingestion_id, source, etc.

    Returns:
        Pipeline: Configured Haystack pipeline ready to process SARIF files.
            Execute with pipeline.run({
                "sarif_converter": {"file_path": Path(...)}
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
        ...     "source": "sarif",
        ...     "source_location": "bandit_scan.sarif",
        ...     "extra_meta": {"filename": "bandit_scan.sarif"}
        ... }
        >>> pipeline = create_sarif_pipeline(doc_store, metadata_context=metadata)
        >>>
        >>> # Process security scan results
        >>> result = pipeline.run({
        ...     "sarif_converter": {"file_path": Path("bandit_scan.sarif")}
        ... })
        >>> indexed_docs = result.get("document_writer", {}).get("documents", [])
        >>> metadata_preview = result.get("document_writer", {}).get("metadata_preview", [])
        >>> print(f"Indexed {len(indexed_docs)} security findings")
        Indexed 12 security findings

        >>> # Query findings using RAG
        >>> from certus_ask.pipelines.rag import create_rag_pipeline
        >>> rag_pipeline = create_rag_pipeline(doc_store)
        >>> answer = rag_pipeline.run({
        ...     "embedder": {"text": "What SQL injection vulnerabilities were found?"},
        ...     "retriever": {"top_k": 5}
        ... })
        >>> print(answer["llm"]["replies"][0])
        'Based on the security scans, the following SQL injection issues were found...'

    See Also:
        - SarifFileToDocuments: For SARIF parsing details
        - LoggingDocumentWriter: For metadata enrichment and logging
        - create_preprocessing_pipeline: For general document processing
        - create_rag_pipeline: For querying indexed findings
    """
    pipeline = Pipeline()
    sarif_converter = SarifFileToDocuments()
    presidio_anonymizer = PresidioAnonymizer()
    splitter = DocumentSplitter(split_by="word", split_length=150, split_overlap=50)
    embedder = SentenceTransformersDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
    writer = LoggingDocumentWriter(document_store, policy=DuplicatePolicy.SKIP, metadata_context=metadata_context)

    pipeline.add_component(instance=sarif_converter, name="sarif_converter")
    pipeline.add_component(instance=presidio_anonymizer, name="presidio_anonymizer")
    pipeline.add_component(instance=splitter, name="document_splitter")
    pipeline.add_component(instance=embedder, name="document_embedder")
    pipeline.add_component(instance=writer, name="document_writer")

    pipeline.connect("sarif_converter.documents", "presidio_anonymizer.documents")
    pipeline.connect("presidio_anonymizer.documents", "document_splitter.documents")
    pipeline.connect("document_splitter.documents", "document_embedder.documents")
    pipeline.connect("document_embedder.documents", "document_writer.documents")

    return pipeline


def _extract_locations(result: dict) -> list[str]:
    locations: list[str] = []
    for loc in result.get("locations", []) or []:
        physical = loc.get("physicalLocation", {}) or {}
        artifact = physical.get("artifactLocation", {}) or {}
        uri = artifact.get("uri")
        region = physical.get("region", {}) or {}
        start_line = region.get("startLine")
        if uri and start_line is not None:
            locations.append(f"{uri}:{start_line}")
        elif uri:
            locations.append(uri)
    return locations


def _extract_remediation(result: dict) -> str | None:
    fixes = result.get("fixes") or []
    if not fixes:
        return None
    first_fix = fixes[0]
    description = (first_fix.get("description", {}) or {}).get("text")
    return description
