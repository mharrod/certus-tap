import time
from typing import Any

import structlog
from haystack import Document, Pipeline, component
from haystack.components.converters import (
    CSVToDocument,
    DOCXToDocument,
    HTMLToDocument,
    MarkdownToDocument,
    PPTXToDocument,
    PyPDFToDocument,
    TextFileToDocument,
)
from haystack.components.embedders import SentenceTransformersDocumentEmbedder as HaystackDocumentEmbedder
from haystack.components.joiners import DocumentJoiner
from haystack.components.preprocessors import DocumentCleaner as HaystackDocumentCleaner
from haystack.components.preprocessors import DocumentSplitter as HaystackDocumentSplitter
from haystack.components.routers import FileTypeRouter
from haystack.components.writers import DocumentWriter
from haystack.document_stores.types import DuplicatePolicy

try:
    from opensearch_haystack.document_stores import OpenSearchDocumentStore  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - compatibility fallback
    from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore  # type: ignore[import]

from certus_ask.core.config import settings
from certus_ask.pipelines.metadata import enrich_documents_with_metadata
from certus_ask.services.privacy_logger import PrivacyLogger
from certus_integrity.services import get_analyzer, get_anonymizer

logger = structlog.get_logger(__name__)


@component
class PresidioAnonymizer:
    """
    Haystack component for PII detection and anonymization with structured logging.

    This component:
    - Detects PII using Presidio analyzer
    - Logs detailed PII entities with type, confidence, and location
    - Supports strict mode (reject) or lenient mode (anonymize)
    - Tracks privacy incidents for monitoring and alerts
    """

    def __init__(self, strict_mode: bool = False, high_confidence_threshold: float = 0.9):
        """
        Initialize the anonymizer component.

        Args:
            strict_mode: If True, documents with PII are excluded from pipeline
            high_confidence_threshold: Confidence threshold for high-confidence PII
        """
        self.strict_mode = strict_mode
        self.privacy_logger = PrivacyLogger(
            strict_mode=strict_mode,
            high_confidence_threshold=high_confidence_threshold,
        )

    @component.output_types(documents=list[Document], quarantined=list[Document])
    def run(self, documents: list[Document]) -> dict[str, list[Document]]:
        """Process documents for PII: detect, anonymize, or quarantine.

        Analyzes each document for Personally Identifiable Information (PII) using
        Presidio analyzer and either anonymizes sensitive data or quarantines
        documents based on strict_mode setting.

        **Behavior:**
        - Strict mode (True): Documents with PII are quarantined, not processed
        - Lenient mode (False): PII is detected and masked with placeholders
        - Clean documents: Passed through unchanged

        **Privacy Logging:**
        - Each PII entity (name, email, phone, etc.) is logged separately
        - Confidence scores included for each entity
        - Quarantine/anonymization events tracked for audit

        Args:
            documents: List of Haystack Document objects to process.
                Each document should have content and optional metadata.

        Returns:
            Dict with two keys:
            - 'documents': List of clean or anonymized documents (ready for embedding)
            - 'quarantined': List of documents quarantined due to PII (if strict_mode=True)

        Raises:
            Exception: If Presidio analyzer fails (connection error, invalid config)

        Examples:
            >>> from haystack import Document
            >>> anonymizer = PresidioAnonymizer(strict_mode=False)
            >>> docs = [
            ...     Document(content="My email is john@example.com", meta={"id": "doc1"}),
            ...     Document(content="The capital of France is Paris", meta={"id": "doc2"})
            ... ]
            >>> result = anonymizer.run(docs)
            >>> result["documents"][0].content
            'My email is <EMAIL>, meta={"pii_anonymized": True, "pii_count": 1}'
            >>> result["documents"][1].content
            'The capital of France is Paris'
            >>> result["quarantined"]
            []

            >>> # Strict mode example
            >>> strict_anonymizer = PresidioAnonymizer(strict_mode=True)
            >>> result = strict_anonymizer.run(docs)
            >>> len(result["documents"])  # Only clean doc
            1
            >>> len(result["quarantined"])  # PII doc quarantined
            1
        """
        analyzer = get_analyzer()
        anonymizer = get_anonymizer()

        anonymized_documents = []
        quarantined_documents = []

        for doc in documents:
            doc_id = doc.meta.get("id", "unknown")
            doc_name = doc.meta.get("file_path", doc.meta.get("name", "unknown"))

            logger.info(
                event="document.privacy_scan_start",
                doc_id=doc_id,
                doc_name=doc_name,
                content_length=len(doc.content),
            )

            try:
                # Analyze document for PII
                analysis_results = analyzer.analyze(text=doc.content, entities=[], language="en")

                if analysis_results:
                    # PII detected - log incident
                    if self.strict_mode:
                        self.privacy_logger.log_quarantine(
                            document_id=doc_id,
                            document_name=doc_name,
                            analysis_results=analysis_results,
                            reason="Strict mode: PII detected",
                        )
                        logger.warning(
                            event="document.privacy_quarantined",
                            doc_id=doc_id,
                            doc_name=doc_name,
                            pii_count=len(analysis_results),
                        )
                        quarantined_documents.append(doc)
                    else:
                        # Anonymize document
                        self.privacy_logger.log_anonymization(
                            document_id=doc_id,
                            document_name=doc_name,
                            analysis_results=analysis_results,
                        )

                        anonymized_text = anonymizer.anonymize(
                            text=doc.content,
                            analyzer_results=analysis_results,
                        )

                        logger.info(
                            event="document.privacy_anonymized",
                            doc_id=doc_id,
                            doc_name=doc_name,
                            pii_count=len(analysis_results),
                            original_size=len(doc.content),
                            anonymized_size=len(anonymized_text.text),
                        )

                        # Create anonymized document
                        anonymized_doc = Document(
                            content=anonymized_text.text,
                            meta={**doc.meta, "pii_anonymized": True, "pii_count": len(analysis_results)},
                        )
                        anonymized_documents.append(anonymized_doc)
                else:
                    # No PII detected
                    logger.info(
                        event="document.privacy_clean",
                        doc_id=doc_id,
                        doc_name=doc_name,
                    )
                    anonymized_documents.append(doc)

            except Exception as exc:
                logger.error(
                    event="document.privacy_scan_failed",
                    doc_id=doc_id,
                    doc_name=doc_name,
                    error=str(exc),
                    exc_info=True,
                )
                raise

        logger.info(
            event="privacy_scan.complete",
            total_documents=len(documents),
            clean_documents=len(anonymized_documents),
            quarantined_documents=len(quarantined_documents),
        )

        return {"documents": anonymized_documents, "quarantined": quarantined_documents}


@component
class LoggingDocumentCleaner:
    """DocumentCleaner wrapper that logs cleaning events."""

    def __init__(self):
        self.cleaner = HaystackDocumentCleaner()

    @component.output_types(documents=list[Document])
    def run(self, documents: list[Document]) -> dict[str, list[Document]]:
        """Clean documents with logging."""
        raw_size = sum(len(doc.content) for doc in documents)

        logger.info(
            event="document.cleaning_start",
            document_count=len(documents),
            total_size_bytes=raw_size,
            step="cleaning",
        )

        start_time = time.time()
        try:
            result = self.cleaner.run(documents=documents)
        except Exception as exc:
            logger.error(
                event="document.cleaning_failed",
                document_count=len(documents),
                error=str(exc),
                exc_info=True,
            )
            raise
        else:
            cleaned_docs = result.get("documents", [])

            clean_size = sum(len(doc.content) for doc in cleaned_docs)
            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                event="document.cleaning_complete",
                document_count=len(cleaned_docs),
                raw_size_bytes=raw_size,
                clean_size_bytes=clean_size,
                duration_ms=duration_ms,
                step="cleaning",
            )

            return result


@component
class LoggingDocumentSplitter:
    """DocumentSplitter wrapper that logs chunking events."""

    def __init__(self, split_by: str = "word", split_length: int = 150, split_overlap: int = 50):
        self.splitter = HaystackDocumentSplitter(
            split_by=split_by,
            split_length=split_length,
            split_overlap=split_overlap,
        )
        self.split_length = split_length
        self.split_overlap = split_overlap

    @component.output_types(documents=list[Document])
    def run(self, documents: list[Document]) -> dict[str, list[Document]]:
        """Split documents with logging."""
        total_size = sum(len(doc.content) for doc in documents)

        logger.info(
            event="document.chunking_start",
            document_count=len(documents),
            total_size_bytes=total_size,
            chunk_size=self.split_length,
            overlap=self.split_overlap,
        )

        start_time = time.time()

        try:
            result = self.splitter.run(documents=documents)
        except Exception as exc:
            logger.error(
                event="document.chunking_failed",
                document_count=len(documents),
                error=str(exc),
                exc_info=True,
            )
            raise
        else:
            chunks = result.get("documents", [])

            duration_ms = int((time.time() - start_time) * 1000)
            avg_chunk_size = sum(len(doc.content) for doc in chunks) // len(chunks) if chunks else 0

            logger.info(
                event="document.chunking_complete",
                chunk_count=len(chunks),
                avg_chunk_size=avg_chunk_size,
                duration_ms=duration_ms,
            )

            return result


@component
class LoggingDocumentEmbedder:
    """DocumentEmbedder wrapper that logs embedding events."""

    def __init__(self, model: str):
        self.embedder = HaystackDocumentEmbedder(model=model)
        self.model = model
        self._is_warm = False

    def _ensure_model_ready(self) -> None:
        """Load embedding model once before processing documents."""
        if self._is_warm:
            return

        logger.info(
            event="document.embedding_model_warm_up",
            model=self.model,
        )
        try:
            self.embedder.warm_up()
        except Exception as exc:  # pragma: no cover - external dependency init
            logger.error(
                event="document.embedding_model_warm_up_failed",
                model=self.model,
                error=str(exc),
                exc_info=True,
            )
            raise
        else:
            self._is_warm = True
            logger.info(
                event="document.embedding_model_ready",
                model=self.model,
            )

    @component.output_types(documents=list[Document])
    def run(self, documents: list[Document]) -> dict[str, list[Document]]:
        """Embed documents with logging."""
        self._ensure_model_ready()

        logger.info(
            event="document.embedding_start",
            document_count=len(documents),
            model=self.model,
        )

        start_time = time.time()

        try:
            result = self.embedder.run(documents=documents)
        except Exception as exc:
            logger.error(
                event="document.embedding_failed",
                document_count=len(documents),
                error=str(exc),
                exc_info=True,
            )
            raise
        else:
            embedded_docs = result.get("documents", [])

            duration_ms = int((time.time() - start_time) * 1000)

            logger.info(
                event="document.embedding_complete",
                embedding_count=len(embedded_docs),
                duration_ms=duration_ms,
                model=self.model,
            )

            return result


@component
class LoggingDocumentWriter:
    """DocumentWriter wrapper that logs indexing events."""

    def __init__(self, document_store, policy=DuplicatePolicy.SKIP):
        self.writer = DocumentWriter(document_store, policy=policy)
        self.document_store = document_store
        self.policy = policy

    @component.output_types(documents_written=int, documents=list[Document], metadata_preview=list[dict[str, Any]])
    def run(self, documents: list[Document], metadata_context: dict[str, Any] | None = None) -> dict[str, object]:
        """Write documents to store with logging."""
        if not documents:
            return {"documents_written": 0, "documents": [], "metadata_preview": []}

        metadata_preview: list[dict[str, Any]] = []
        if metadata_context:
            try:
                metadata_preview = enrich_documents_with_metadata(documents, **metadata_context)
            except TypeError:
                metadata_preview = enrich_documents_with_metadata(
                    documents, **{k: v for k, v in metadata_context.items() if v is not None}
                )

        logger.info(
            event="document.indexing_start",
            document_count=len(documents),
        )

        start_time = time.time()

        try:
            result = self.writer.run(documents=documents)
        except Exception as exc:
            logger.error(
                event="document.indexing_failed",
                document_count=len(documents),
                error=str(exc),
                exc_info=True,
            )
            raise
        else:
            written_count = result.get("documents_written", 0)

            duration_ms = int((time.time() - start_time) * 1000)

            workspace_id = metadata_context.get("workspace_id", "default") if metadata_context else "default"
            index_name = f"ask_certus_{workspace_id}"
            logger.info(
                event="document.indexed",
                index=index_name,
                chunks_indexed=written_count,
                duration_ms=duration_ms,
            )

            return {
                "documents_written": written_count,
                "documents": documents,
                "metadata_preview": metadata_preview,
            }


def create_preprocessing_pipeline(document_store: OpenSearchDocumentStore) -> Pipeline:
    """Create a complete document preprocessing pipeline for ingestion and indexing.

    Constructs a Haystack pipeline that transforms raw documents into embedded,
    indexed records ready for RAG queries. The pipeline handles:

    1. **File Type Detection** - Routes documents by MIME type
    2. **Format Conversion** - Converts PDF, DOCX, PPTX, CSV, Markdown, TXT to text
    3. **Text Cleaning** - Removes artifacts and normalizes whitespace
    4. **Metadata Capture** - Generates an evidence envelope for lineage tracking
    5. **PII Detection** - Finds and anonymizes sensitive information
    6. **Chunking** - Splits documents into semantic chunks for embedding
    7. **Embedding** - Generates vector embeddings using sentence transformers
    8. **Indexing** - Stores documents in OpenSearch with deduplication

    **Pipeline Flow:**
    ```
    File → Type Router → Format Converter → Joiner → Cleaner →
    Metadata → Anonymizer → Splitter → Embedder → Document Writer → OpenSearch
    ```

    **Supported Formats:**
    - Text files (.txt)
    - PDF documents (.pdf)
    - Markdown (.md)
    - Microsoft Word (.docx)
    - PowerPoint (.pptx)
    - CSV files (.csv)

    **Processing Parameters:**
    - Chunk size: 150 words
    - Chunk overlap: 50 words
    - Embedding model: sentence-transformers/all-MiniLM-L6-v2 (384 dimensions)
    - Duplicate policy: SKIP (prevents re-indexing)

    Args:
        document_store: OpenSearch document store for persisting indexed documents.
            Should be initialized with proper connection settings and authentication.

    Returns:
        Pipeline: Configured Haystack pipeline ready to process documents.
            Can be executed with pipeline.run({"file_type_router": {"sources": [file_paths]}})

    Raises:
        ImportError: If required Haystack components are not installed
        ConnectionError: If document_store is not properly initialized

    Examples:
        >>> from certus_ask.services.opensearch import get_document_store
        >>>
        >>> # Create pipeline
        >>> doc_store = get_document_store()
        >>> pipeline = create_preprocessing_pipeline(doc_store)
        >>>
        >>> # Process a single file
        >>> from pathlib import Path
        >>> result = pipeline.run({
        ...     "file_type_router": {
        ...         "sources": [Path("document.pdf")]
        ...     }
        ... })
        >>> print(f"Indexed {len(result.get('document_writer', {}).get('documents', []))} documents")

        >>> # Process multiple files
        >>> from pathlib import Path
        >>> files = list(Path("documents/").glob("**/*.pdf"))
        >>> result = pipeline.run({
        ...     "file_type_router": {
        ...         "sources": files
        ...     }
        ... })
        >>> documents_indexed = result.get("document_writer", {}).get("documents", [])
        >>> print(f"Successfully indexed {len(documents_indexed)} documents")
        >>> print(f"Quarantined documents: {result.get('presidio_anonymizer', {}).get('quarantined', [])}")

        >>> # Check for PII-anonymized documents
        >>> for doc in documents_indexed:
        ...     if doc.meta.get("pii_anonymized"):
        ...         print(f"Document {doc.id} had {doc.meta['pii_count']} PII entities masked")

    See Also:
        - create_rag_pipeline: For creating the query/retrieval pipeline
        - PresidioAnonymizer: For detailed PII handling behavior
        - OpenSearchDocumentStore: For persistence layer configuration
    """
    file_type_router = FileTypeRouter(
        mime_types=[
            "text/plain",
            "application/pdf",
            "text/markdown",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "text/csv",
            "text/html",
        ]
    )

    document_converters = {
        "text_file_converter": TextFileToDocument(),
        "markdown_converter": MarkdownToDocument(),
        "pdf_converter": PyPDFToDocument(),
        "docx_converter": DOCXToDocument(),
        "pptx_converter": PPTXToDocument(),
        "csv_converter": CSVToDocument(),
        "html_converter": HTMLToDocument(),
    }

    document_joiner = DocumentJoiner()
    document_cleaner = LoggingDocumentCleaner()
    document_splitter = LoggingDocumentSplitter(split_by="word", split_length=150, split_overlap=50)
    document_embedder = LoggingDocumentEmbedder(model="sentence-transformers/all-MiniLM-L6-v2")
    document_writer = LoggingDocumentWriter(document_store, policy=DuplicatePolicy.SKIP)
    presidio_anonymizer = PresidioAnonymizer()

    pipeline = Pipeline()
    pipeline.add_component(instance=file_type_router, name="file_type_router")

    for converter_name, converter in document_converters.items():
        pipeline.add_component(instance=converter, name=converter_name)

    pipeline.add_component(instance=document_joiner, name="document_joiner")
    pipeline.add_component(instance=document_cleaner, name="document_cleaner")
    if settings.anonymizer_enabled:
        pipeline.add_component(instance=presidio_anonymizer, name="presidio_anonymizer")
    pipeline.add_component(instance=document_splitter, name="document_splitter")
    pipeline.add_component(instance=document_embedder, name="document_embedder")
    pipeline.add_component(instance=document_writer, name="document_writer")

    pipeline.connect("file_type_router.text/plain", "text_file_converter.sources")
    pipeline.connect("file_type_router.application/pdf", "pdf_converter.sources")
    pipeline.connect("file_type_router.text/markdown", "markdown_converter.sources")
    pipeline.connect(
        "file_type_router.application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "docx_converter.sources",
    )
    pipeline.connect(
        "file_type_router.application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "pptx_converter.sources",
    )
    pipeline.connect("file_type_router.text/csv", "csv_converter.sources")
    pipeline.connect("file_type_router.text/html", "html_converter.sources")

    for converter_name in document_converters:
        pipeline.connect(converter_name, "document_joiner")

    pipeline.connect("document_joiner", "document_cleaner.documents")
    if settings.anonymizer_enabled:
        pipeline.connect("document_cleaner", "presidio_anonymizer.documents")
        pipeline.connect("presidio_anonymizer", "document_splitter")
    else:
        logger.info("anonymizer.disabled", reason="ANONYMIZER_ENABLED=false")
        pipeline.connect("document_cleaner", "document_splitter.documents")
    pipeline.connect("document_splitter", "document_embedder")
    pipeline.connect("document_embedder", "document_writer")

    return pipeline
