"""OpenSearch client wrapper for document store operations.

Centralizes OpenSearch/document store interactions with workspace management.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import structlog

try:
    from opensearch_haystack.document_stores import OpenSearchDocumentStore  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - compatibility fallback
    from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore  # type: ignore[import]

logger = structlog.get_logger(__name__)


class OpenSearchClient:
    """Wrapper for OpenSearch document store operations."""

    def __init__(
        self,
        hosts: str,
        http_auth_user: str | None = None,
        http_auth_password: str | None = None,
        embedding_dim: int = 384,
    ):
        """Initialize OpenSearch client with configuration.

        Args:
            hosts: OpenSearch host URL
            http_auth_user: Optional HTTP auth username
            http_auth_password: Optional HTTP auth password
            embedding_dim: Vector embedding dimension (default: 384)
        """
        self.hosts = hosts
        self.http_auth_user = http_auth_user
        self.http_auth_password = http_auth_password
        self.embedding_dim = embedding_dim

    @lru_cache(maxsize=1)
    def get_default_document_store(self) -> OpenSearchDocumentStore:
        """Get cached default document store instance.

        Returns:
            OpenSearchDocumentStore configured for default index
        """
        auth = None
        if self.http_auth_user and self.http_auth_password:
            auth = (self.http_auth_user, self.http_auth_password)

        logger.info(
            event="opensearch.get_default_store",
            hosts=self.hosts,
        )

        return OpenSearchDocumentStore(
            hosts=self.hosts,
            index="ask_certus",
            use_ssl=self.hosts.startswith("https"),
            verify_certs=False,
            http_auth=auth,
            embedding_dim=self.embedding_dim,
        )

    def get_workspace_document_store(
        self,
        workspace_id: str,
    ) -> OpenSearchDocumentStore:
        """Get document store for specific workspace.

        Creates workspace-specific index name by sanitizing workspace ID.

        Args:
            workspace_id: Workspace identifier

        Returns:
            OpenSearchDocumentStore configured for workspace index
        """
        auth = None
        if self.http_auth_user and self.http_auth_password:
            auth = (self.http_auth_user, self.http_auth_password)

        # Sanitize workspace ID for index name
        sanitized_workspace = re.sub(r"[^a-z0-9_-]+", "-", workspace_id.lower()).strip("-")
        if not sanitized_workspace:
            sanitized_workspace = "default"

        # Construct workspace-specific index name
        index_name = f"ask_certus_{sanitized_workspace}"

        logger.info(
            event="opensearch.get_workspace_store",
            workspace_id=workspace_id,
            index_name=index_name,
            hosts=self.hosts,
        )

        return OpenSearchDocumentStore(
            hosts=self.hosts,
            index=index_name,
            use_ssl=self.hosts.startswith("https"),
            verify_certs=False,
            http_auth=auth,
            embedding_dim=self.embedding_dim,
        )

    def create_index(
        self,
        index_name: str,
        settings: dict[str, Any] | None = None,
        mappings: dict[str, Any] | None = None,
    ) -> None:
        """Create new index with optional settings and mappings.

        Args:
            index_name: Name of index to create
            settings: Optional index settings
            mappings: Optional index mappings

        Note:
            This is a placeholder for future expansion.
            Current implementation uses OpenSearchDocumentStore which
            handles index creation automatically.
        """
        logger.info(
            event="opensearch.create_index",
            index_name=index_name,
        )
        # OpenSearchDocumentStore handles index creation automatically
        # This method exists for future expansion if manual index
        # creation is needed

    def delete_index(self, index_name: str) -> None:
        """Delete index.

        Args:
            index_name: Name of index to delete

        Note:
            This is a placeholder for future expansion.
        """
        logger.info(
            event="opensearch.delete_index",
            index_name=index_name,
        )
        # Placeholder for future expansion

    def index_exists(self, index_name: str) -> bool:
        """Check if index exists.

        Args:
            index_name: Name of index to check

        Returns:
            True if index exists, False otherwise

        Note:
            This is a placeholder for future expansion.
        """
        logger.info(
            event="opensearch.index_exists_check",
            index_name=index_name,
        )
        # Placeholder for future expansion
        return False
