"""Ingestion service layer for document processing.

This package contains service classes that encapsulate business logic
for ingesting documents from various sources. Services are designed to be:
- Testable in isolation
- Reusable across routers, CLI tools, and background jobs
- Decoupled from HTTP/presentation concerns

Service modules:
- security_processor: Handles SARIF/SPDX security scan ingestion
- file_processor: Handles general file and document ingestion
- neo4j_service: Manages Neo4j graph database operations
- storage_service: Handles S3 and file storage operations
"""

from certus_ask.services.ingestion.file_processor import FileProcessor
from certus_ask.services.ingestion.neo4j_service import Neo4jService
from certus_ask.services.ingestion.security_processor import SecurityProcessor
from certus_ask.services.ingestion.storage_service import StorageService
from certus_ask.services.ingestion.utils import (
    compute_sha256_digest,
    enforce_verified_digest,
    extract_filename_from_source,
    extract_metadata_preview,
    get_upload_file_size,
    match_expected_digest,
)

__all__ = [
    "FileProcessor",
    "Neo4jService",
    "SecurityProcessor",
    "StorageService",
    "compute_sha256_digest",
    "enforce_verified_digest",
    "extract_filename_from_source",
    # Utility functions
    "extract_metadata_preview",
    "get_upload_file_size",
    "match_expected_digest",
]
