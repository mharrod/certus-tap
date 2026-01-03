"""OpenSearch document store factory functions.

Provides backward-compatible functions that delegate to OpenSearchClient.
"""

from functools import lru_cache

try:
    from opensearch_haystack.document_stores import OpenSearchDocumentStore  # type: ignore[import]
except ModuleNotFoundError:  # pragma: no cover - compatibility fallback
    from haystack_integrations.document_stores.opensearch import OpenSearchDocumentStore  # type: ignore[import]

from certus_ask.core.config import settings
from certus_ask.services.storage import OpenSearchClient


@lru_cache(maxsize=1)
def _get_opensearch_client() -> OpenSearchClient:
    """Get cached OpenSearchClient instance."""
    return OpenSearchClient(
        hosts=settings.opensearch_host,
        http_auth_user=settings.opensearch_http_auth_user,
        http_auth_password=settings.opensearch_http_auth_password,
        embedding_dim=384,
    )


@lru_cache(maxsize=1)
def get_document_store() -> OpenSearchDocumentStore:
    """Get default document store instance.

    This function maintains backward compatibility while delegating to OpenSearchClient.
    """
    client = _get_opensearch_client()
    return client.get_default_document_store()


def get_document_store_for_workspace(workspace_id: str) -> OpenSearchDocumentStore:
    """Get or create a document store for a specific workspace.

    This function maintains backward compatibility while delegating to OpenSearchClient.

    Args:
        workspace_id: Workspace identifier

    Returns:
        OpenSearchDocumentStore configured for workspace-specific index
    """
    client = _get_opensearch_client()
    return client.get_workspace_document_store(workspace_id)
