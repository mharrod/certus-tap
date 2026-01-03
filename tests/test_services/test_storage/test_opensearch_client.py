"""Unit tests for OpenSearchClient wrapper."""

from unittest.mock import MagicMock, patch

import pytest

from certus_ask.services.storage import OpenSearchClient


@pytest.fixture
def opensearch_client():
    """Create OpenSearchClient instance for testing."""
    return OpenSearchClient(
        hosts="http://localhost:9200",
        http_auth_user="admin",
        http_auth_password="password",
        embedding_dim=384,
    )


class TestOpenSearchClientInitialization:
    """Tests for OpenSearchClient initialization."""

    def test_initialization_with_auth(self):
        """Should initialize with authentication."""
        # Act
        client = OpenSearchClient(
            hosts="https://opensearch.example.com",
            http_auth_user="user",
            http_auth_password="pass",
            embedding_dim=512,
        )

        # Assert
        assert client.hosts == "https://opensearch.example.com"
        assert client.http_auth_user == "user"
        assert client.http_auth_password == "pass"
        assert client.embedding_dim == 512

    def test_initialization_without_auth(self):
        """Should initialize without authentication."""
        # Act
        client = OpenSearchClient(
            hosts="http://localhost:9200",
        )

        # Assert
        assert client.hosts == "http://localhost:9200"
        assert client.http_auth_user is None
        assert client.http_auth_password is None
        assert client.embedding_dim == 384  # default


class TestGetDefaultDocumentStore:
    """Tests for get_default_document_store method."""

    @patch("certus_ask.services.storage.opensearch_client.OpenSearchDocumentStore")
    def test_get_default_store_with_auth(self, mock_store_class, opensearch_client):
        """Should create default store with authentication."""
        # Arrange
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # Act
        result = opensearch_client.get_default_document_store()

        # Assert
        assert result == mock_store
        mock_store_class.assert_called_once_with(
            hosts="http://localhost:9200",
            index="ask_certus",
            use_ssl=False,
            verify_certs=False,
            http_auth=("admin", "password"),
            embedding_dim=384,
        )

    @patch("certus_ask.services.storage.opensearch_client.OpenSearchDocumentStore")
    def test_get_default_store_without_auth(self, mock_store_class):
        """Should create default store without authentication."""
        # Arrange
        client = OpenSearchClient(hosts="http://localhost:9200")
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # Act
        result = client.get_default_document_store()

        # Assert
        assert result == mock_store
        mock_store_class.assert_called_once_with(
            hosts="http://localhost:9200",
            index="ask_certus",
            use_ssl=False,
            verify_certs=False,
            http_auth=None,
            embedding_dim=384,
        )

    @patch("certus_ask.services.storage.opensearch_client.OpenSearchDocumentStore")
    def test_get_default_store_https(self, mock_store_class):
        """Should use SSL for https hosts."""
        # Arrange
        client = OpenSearchClient(hosts="https://opensearch.example.com")
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # Act
        client.get_default_document_store()

        # Assert
        call_kwargs = mock_store_class.call_args[1]
        assert call_kwargs["use_ssl"] is True
        assert call_kwargs["hosts"] == "https://opensearch.example.com"


class TestGetWorkspaceDocumentStore:
    """Tests for get_workspace_document_store method."""

    @patch("certus_ask.services.storage.opensearch_client.OpenSearchDocumentStore")
    def test_get_workspace_store_basic(self, mock_store_class, opensearch_client):
        """Should create workspace-specific store."""
        # Arrange
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # Act
        result = opensearch_client.get_workspace_document_store("workspace-123")

        # Assert
        assert result == mock_store
        mock_store_class.assert_called_once_with(
            hosts="http://localhost:9200",
            index="ask_certus_workspace-123",
            use_ssl=False,
            verify_certs=False,
            http_auth=("admin", "password"),
            embedding_dim=384,
        )

    @patch("certus_ask.services.storage.opensearch_client.OpenSearchDocumentStore")
    def test_get_workspace_store_sanitized_name(self, mock_store_class, opensearch_client):
        """Should sanitize workspace ID for index name."""
        # Arrange
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # Act - workspace ID with special characters
        opensearch_client.get_workspace_document_store("My Workspace! @123")

        # Assert
        call_kwargs = mock_store_class.call_args[1]
        # Should be sanitized to lowercase, alphanumeric + hyphens/underscores only
        assert call_kwargs["index"] == "ask_certus_my-workspace-123"

    @patch("certus_ask.services.storage.opensearch_client.OpenSearchDocumentStore")
    def test_get_workspace_store_empty_workspace_id(self, mock_store_class, opensearch_client):
        """Should use default for empty workspace ID."""
        # Arrange
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # Act
        opensearch_client.get_workspace_document_store("")

        # Assert
        call_kwargs = mock_store_class.call_args[1]
        assert call_kwargs["index"] == "ask_certus_default"

    @patch("certus_ask.services.storage.opensearch_client.OpenSearchDocumentStore")
    def test_get_workspace_store_special_chars_only(self, mock_store_class, opensearch_client):
        """Should use default for workspace ID with only special characters."""
        # Arrange
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # Act
        opensearch_client.get_workspace_document_store("!@#$%")

        # Assert
        call_kwargs = mock_store_class.call_args[1]
        assert call_kwargs["index"] == "ask_certus_default"

    @patch("certus_ask.services.storage.opensearch_client.OpenSearchDocumentStore")
    def test_get_workspace_store_uppercase(self, mock_store_class, opensearch_client):
        """Should convert workspace ID to lowercase."""
        # Arrange
        mock_store = MagicMock()
        mock_store_class.return_value = mock_store

        # Act
        opensearch_client.get_workspace_document_store("PRODUCTION")

        # Assert
        call_kwargs = mock_store_class.call_args[1]
        assert call_kwargs["index"] == "ask_certus_production"


class TestOpenSearchClientUtility:
    """Tests for utility methods."""

    def test_create_index(self, opensearch_client):
        """Should log index creation (placeholder method)."""
        # Act - should not raise
        opensearch_client.create_index("test-index")

    def test_delete_index(self, opensearch_client):
        """Should log index deletion (placeholder method)."""
        # Act - should not raise
        opensearch_client.delete_index("test-index")

    def test_index_exists(self, opensearch_client):
        """Should return False (placeholder method)."""
        # Act
        result = opensearch_client.index_exists("test-index")

        # Assert
        assert result is False
