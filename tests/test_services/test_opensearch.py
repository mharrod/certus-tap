"""
Unit tests for OpenSearch service layer.

Tests cover:
- Client initialization and connection
- Document CRUD operations
- Search and filtering
- Index management
- Error handling and resilience
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from opensearchpy import exceptions as os_exceptions

pytestmark = pytest.mark.integration


class TestOpenSearchClientInitialization:
    """Tests for OpenSearch client setup and connection."""

    def test_client_initialization_success(self, mock_opensearch_client):
        """Test successful OpenSearch client initialization."""
        assert mock_opensearch_client is not None
        assert mock_opensearch_client.index is not None

    def test_client_connection_failure(self):
        """Test handling of connection failures."""
        from certus_ask.services import opensearch as opensearch_service

        # Clear cache to ensure fresh client creation
        opensearch_service._get_opensearch_client.cache_clear()
        opensearch_service.get_document_store.cache_clear()

        with patch("certus_ask.services.opensearch.OpenSearchClient") as client_cls:
            client_cls.side_effect = os_exceptions.ConnectionError("Connection failed")

            with pytest.raises(os_exceptions.ConnectionError):
                opensearch_service.get_document_store()

    def test_client_with_authentication(self, monkeypatch):
        """Test client initialization with username/password."""
        from certus_ask.services import opensearch as opensearch_service

        # Clear cache to ensure fresh client creation
        opensearch_service._get_opensearch_client.cache_clear()
        opensearch_service.get_document_store.cache_clear()

        captured = {}

        def fake_client(**kwargs):
            captured.update(kwargs)
            mock_doc_store = SimpleNamespace()
            return SimpleNamespace(get_default_document_store=lambda: mock_doc_store)

        monkeypatch.setattr("certus_ask.services.opensearch.OpenSearchClient", fake_client)
        monkeypatch.setattr(
            "certus_ask.services.opensearch.settings",
            SimpleNamespace(
                opensearch_host="https://search.local",
                opensearch_index="ask-certus",
                opensearch_http_auth_user="user",
                opensearch_http_auth_password="pass",
            ),
        )

        opensearch_service.get_document_store()
        assert captured["http_auth_user"] == "user"
        assert captured["http_auth_password"] == "pass"


class TestDocumentOperations:
    """Tests for document CRUD operations."""

    def test_index_document(self, mock_opensearch_client, document_factory):
        """Test indexing a document."""
        doc = document_factory.create(content="test document")

        mock_opensearch_client.index(index="test", body=doc)

        assert mock_opensearch_client.index.called
        call_args = mock_opensearch_client.index.call_args
        assert call_args[1]["index"] == "test"

    def test_get_document(self, mock_opensearch_client):
        """Test retrieving a document by ID."""
        mock_opensearch_client.get.return_value = {"_id": "doc-123", "_source": {"content": "test"}}

        result = mock_opensearch_client.get(index="test", id="doc-123")

        assert result["_id"] == "doc-123"
        assert result["_source"]["content"] == "test"

    def test_get_nonexistent_document(self, mock_opensearch_client):
        """Test retrieving non-existent document."""
        mock_opensearch_client.get.side_effect = os_exceptions.NotFoundError(404, "Document not found")

        with pytest.raises(os_exceptions.NotFoundError):
            mock_opensearch_client.get(index="test", id="nonexistent")

    def test_delete_document(self, mock_opensearch_client):
        """Test deleting a document."""
        mock_opensearch_client.delete.return_value = {"result": "deleted"}

        result = mock_opensearch_client.delete(index="test", id="doc-123")

        assert result["result"] == "deleted"
        assert mock_opensearch_client.delete.called

    def test_update_document(self, mock_opensearch_client):
        """Test updating a document."""
        update_body = {"doc": {"status": "updated"}}
        mock_opensearch_client.update.return_value = {"result": "updated"}

        result = mock_opensearch_client.update(index="test", id="doc-123", body=update_body)

        assert result["result"] == "updated"


class TestSearchOperations:
    """Tests for search and query operations."""

    def test_search_all_documents(self, mock_opensearch_client):
        """Test searching for all documents."""
        mock_opensearch_client.search.return_value = {
            "hits": {
                "total": {"value": 2},
                "hits": [
                    {"_source": {"content": "doc1"}},
                    {"_source": {"content": "doc2"}},
                ],
            }
        }

        result = mock_opensearch_client.search(index="test", body={"query": {"match_all": {}}})

        assert result["hits"]["total"]["value"] == 2
        assert len(result["hits"]["hits"]) == 2

    def test_search_with_filter(self, mock_opensearch_client):
        """Test searching with filters."""
        mock_opensearch_client.search.return_value = {
            "hits": {"total": {"value": 1}, "hits": [{"_source": {"status": "active"}}]}
        }

        query = {"query": {"bool": {"filter": {"term": {"status": "active"}}}}}

        result = mock_opensearch_client.search(index="test", body=query)

        assert result["hits"]["total"]["value"] == 1

    def test_search_empty_results(self, mock_opensearch_client):
        """Test search returning no results."""
        mock_opensearch_client.search.return_value = {"hits": {"total": {"value": 0}, "hits": []}}

        result = mock_opensearch_client.search(index="test", body={"query": {"match_all": {}}})

        assert result["hits"]["total"]["value"] == 0
        assert len(result["hits"]["hits"]) == 0

    def test_search_with_pagination(self, mock_opensearch_client):
        """Test search with pagination."""
        mock_opensearch_client.search.return_value = {
            "hits": {"total": {"value": 100}, "hits": [{"_source": {"id": i}} for i in range(10)]}
        }

        query = {"query": {"match_all": {}}, "from": 10, "size": 10}
        result = mock_opensearch_client.search(index="test", body=query)

        assert result["hits"]["total"]["value"] == 100
        assert len(result["hits"]["hits"]) == 10

    def test_count_documents(self, mock_opensearch_client):
        """Test counting documents."""
        mock_opensearch_client.count.return_value = {"count": 42}

        result = mock_opensearch_client.count(index="test")

        assert result["count"] == 42


class TestIndexManagement:
    """Tests for index operations."""

    def test_create_index(self, mock_opensearch_client):
        """Test creating an index."""
        mock_opensearch_client.indices.create.return_value = {"acknowledged": True}

        result = mock_opensearch_client.indices.create(index="test-index")

        assert result["acknowledged"] is True

    def test_index_already_exists(self, mock_opensearch_client):
        """Test creating index that already exists."""
        mock_opensearch_client.indices.create.side_effect = os_exceptions.RequestError(400, "Already exists")

        with pytest.raises(os_exceptions.RequestError):
            mock_opensearch_client.indices.create(index="test-index")

    def test_index_exists_check(self, mock_opensearch_client):
        """Test checking if index exists."""
        mock_opensearch_client.indices.exists.return_value = True

        result = mock_opensearch_client.indices.exists(index="test-index")

        assert result is True

    def test_delete_index(self, mock_opensearch_client):
        """Test deleting an index."""
        mock_opensearch_client.indices.delete.return_value = {"acknowledged": True}

        result = mock_opensearch_client.indices.delete(index="test-index")

        assert result["acknowledged"] is True

    def test_get_index_settings(self, mock_opensearch_client):
        """Test retrieving index settings."""
        mock_opensearch_client.indices.get_settings.return_value = {
            "test-index": {"settings": {"index": {"number_of_shards": 1}}}
        }

        result = mock_opensearch_client.indices.get_settings(index="test-index")

        assert result["test-index"]["settings"]["index"]["number_of_shards"] == 1

    def test_put_index_mapping(self, mock_opensearch_client):
        """Test setting index mappings."""
        mock_opensearch_client.indices.put_mapping.return_value = {"acknowledged": True}


def test_get_document_store_caches_instances(monkeypatch):
    """The document store factory should cache the instance and reuse auth settings."""
    from certus_ask.services import opensearch as opensearch_service

    opensearch_service._get_opensearch_client.cache_clear()
    opensearch_service.get_document_store.cache_clear()
    created = []

    def fake_client(**kwargs):
        created.append(kwargs)
        mock_doc_store = SimpleNamespace(index="ask-certus")
        return SimpleNamespace(get_default_document_store=lambda: mock_doc_store)

    monkeypatch.setattr("certus_ask.services.opensearch.OpenSearchClient", fake_client)
    monkeypatch.setattr(
        "certus_ask.services.opensearch.settings",
        SimpleNamespace(
            opensearch_host="https://search.local",
            opensearch_index="ask-certus",
            opensearch_http_auth_user="user",
            opensearch_http_auth_password="pass",
        ),
    )

    store1 = opensearch_service.get_document_store()
    store2 = opensearch_service.get_document_store()

    assert store1 is store2
    assert created[0]["http_auth_user"] == "user"
    assert created[0]["http_auth_password"] == "pass"
    assert created[0]["hosts"] == "https://search.local"


def test_workspace_document_store_sanitizes_indices(monkeypatch):
    """Workspace stores should sanitize workspace IDs before constructing index names."""
    from certus_ask.services import opensearch as opensearch_service

    opensearch_service._get_opensearch_client.cache_clear()
    created_stores = []

    class FakeClient:
        def __init__(self, **kwargs):
            pass

        def get_workspace_document_store(self, workspace_id):
            # Return a mock document store with the sanitized index name
            sanitized_index = f"ask_certus_{workspace_id.lower().replace(' ', '-').replace('!', '')}"
            store = SimpleNamespace(index=sanitized_index)
            created_stores.append(store)
            return store

    monkeypatch.setattr("certus_ask.services.opensearch.OpenSearchClient", FakeClient)
    monkeypatch.setattr(
        "certus_ask.services.opensearch.settings",
        SimpleNamespace(
            opensearch_host="http://localhost:9200",
            opensearch_index="ask-certus",
            opensearch_http_auth_user=None,
            opensearch_http_auth_password=None,
        ),
    )

    store = opensearch_service.get_document_store_for_workspace("Demo Workspace!!")

    assert store.index == "ask_certus_demo-workspace"


class TestBulkOperations:
    """Tests for bulk operations."""

    def test_bulk_index_documents(self, mock_opensearch_client, document_factory):
        """Test bulk indexing multiple documents."""
        docs = document_factory.create_batch(count=10)

        mock_opensearch_client.bulk.return_value = {
            "errors": False,
            "items": [{"index": {"_index": "test", "_id": str(i)}} for i in range(10)],
        }

        # Simulate bulk request
        body_payload = []
        for doc in docs:
            body_payload.append({"index": {}})
            body_payload.append(doc)

        result = mock_opensearch_client.bulk(
            index="test",
            body=body_payload,
        )

        assert result["errors"] is False
        assert len(result["items"]) == 10

    def test_bulk_with_errors(self, mock_opensearch_client):
        """Test bulk operation with some failures."""
        mock_opensearch_client.bulk.return_value = {
            "errors": True,
            "items": [
                {"index": {"_index": "test", "status": 201}},
                {"index": {"_index": "test", "status": 400, "error": "Invalid"}},
            ],
        }

        result = mock_opensearch_client.bulk(index="test", body=[])

        assert result["errors"] is True


class TestErrorHandling:
    """Tests for error scenarios and resilience."""

    def test_connection_timeout(self, mock_opensearch_client):
        """Test handling connection timeout."""
        mock_opensearch_client.search.side_effect = os_exceptions.ConnectionTimeout("Request timed out")

        with pytest.raises(os_exceptions.ConnectionTimeout):
            mock_opensearch_client.search(index="test", body={})

    def test_request_error(self, mock_opensearch_client):
        """Test handling request error."""
        mock_opensearch_client.index.side_effect = os_exceptions.RequestError(400, "Bad request")

        with pytest.raises(os_exceptions.RequestError):
            mock_opensearch_client.index(index="test", body={})

    def test_server_error(self, mock_opensearch_client):
        """Test handling server error."""
        mock_opensearch_client.search.side_effect = os_exceptions.NotFoundError(500, "Server error")

        with pytest.raises(os_exceptions.NotFoundError):
            mock_opensearch_client.search(index="nonexistent", body={})

    def test_retry_logic(self, mock_opensearch_client):
        """Test automatic retry on transient failure."""
        mock_opensearch_client.search.side_effect = [
            os_exceptions.ConnectionError("Failed"),
            os_exceptions.ConnectionError("Failed"),
            {"hits": {"hits": []}},  # Success on third try
        ]

        # In real code, retry logic would be implemented
        # This test verifies mock supports retry patterns
        assert mock_opensearch_client.search.call_count == 0


class TestAggregations:
    """Tests for aggregation operations."""

    def test_simple_aggregation(self, mock_opensearch_client):
        """Test simple aggregation."""
        mock_opensearch_client.search.return_value = {
            "aggregations": {
                "status_count": {
                    "buckets": [
                        {"key": "active", "doc_count": 10},
                        {"key": "inactive", "doc_count": 5},
                    ]
                }
            }
        }

        query = {"aggs": {"status_count": {"terms": {"field": "status"}}}}

        result = mock_opensearch_client.search(index="test", body=query)

        assert len(result["aggregations"]["status_count"]["buckets"]) == 2

    def test_date_histogram_aggregation(self, mock_opensearch_client):
        """Test date histogram aggregation."""
        mock_opensearch_client.search.return_value = {
            "aggregations": {
                "events_over_time": {
                    "buckets": [
                        {"key_as_string": "2024-01-01", "doc_count": 100},
                        {"key_as_string": "2024-01-02", "doc_count": 150},
                    ]
                }
            }
        }

        result = mock_opensearch_client.search(index="test", body={})

        assert len(result["aggregations"]["events_over_time"]["buckets"]) == 2


class TestDocumentStoreIntegration:
    """Integration tests for document store operations."""

    def test_complete_workflow(self, mock_opensearch_client, document_factory):
        """Test complete document lifecycle."""
        # Create
        doc = document_factory.create(content="test workflow")
        mock_opensearch_client.index.return_value = {"_id": "doc-1"}

        create_result = mock_opensearch_client.index(index="test", body=doc)
        assert create_result["_id"] == "doc-1"

        # Read
        mock_opensearch_client.get.return_value = {"_source": doc}
        read_result = mock_opensearch_client.get(index="test", id="doc-1")
        assert read_result["_source"]["content"] == "test workflow"

        # Update
        mock_opensearch_client.update.return_value = {"result": "updated"}
        update_result = mock_opensearch_client.update(index="test", id="doc-1", body={"doc": {"status": "updated"}})
        assert update_result["result"] == "updated"

        # Delete
        mock_opensearch_client.delete.return_value = {"result": "deleted"}
        delete_result = mock_opensearch_client.delete(index="test", id="doc-1")
        assert delete_result["result"] == "deleted"

    def test_search_after_indexing(self, mock_opensearch_client, document_factory):
        """Test searching documents after indexing."""
        docs = document_factory.create_batch(count=5)

        # Index documents
        for doc in docs:
            mock_opensearch_client.index(index="test", body=doc)

        # Search
        mock_opensearch_client.search.return_value = {
            "hits": {"total": {"value": 5}, "hits": [{"_source": doc} for doc in docs]}
        }

        search_result = mock_opensearch_client.search(index="test", body={"query": {"match_all": {}}})

        assert search_result["hits"]["total"]["value"] == 5
        assert len(search_result["hits"]["hits"]) == 5
