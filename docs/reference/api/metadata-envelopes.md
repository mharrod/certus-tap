# Metadata Envelope Reference

## Purpose
Describe the provenance metadata recorded for every document chunk that flows through Certus TAP so analysts can trace origin, verify integrity, and debug ingestion pipelines.

## Audience & Prerequisites
- Engineers extending ingestion connectors or document writers.
- Analysts validating provenance previews returned by the API.
- Familiarity with Haystack documents, OpenSearch indices, and [Multi-Workspace Isolation](../general/multi-workspace-isolation.md).

## Overview
- Each document carries a `metadata_envelope` injected by `LoggingDocumentWriter`.
- API responses expose a lightweight `metadata_preview` (first three envelopes) for quick inspection.
- Full envelopes are stored inside workspace-specific OpenSearch indices (`ask_certus_<workspace>`).

## Key Concepts

### Envelope Schema

| Field             | Description                                                                     |
| ----------------- | ------------------------------------------------------------------------------- |
| `version`         | Schema version (currently `1.0`).                                               |
| `workspace_id`    | Workspace slug for multi-tenant isolation.                                      |
| `ingestion_id`    | Unique ID assigned to the ingestion run.                                        |
| `document_id`     | Haystack document/chunk identifier.                                             |
| `source`          | Connector name (`upload`, `folder`, `github`, `web`, `web_crawl`, `security`).  |
| `source_location` | Canonical path/URL identifying the source artifact.                             |
| `content_hash`    | SHA-256 hash of chunk content for dedup/integrity checks.                       |
| `captured_at`     | UTC timestamp when metadata was generated.                                      |
| `extra`           | Connector-specific fields (branch, crawl limits, filenames, render flags, etc.) |

### Preview in API Responses
Every ingestion endpoint returns a `metadata_preview` array so you can audit provenance without querying OpenSearch:

```bash
curl -s -X POST "http://localhost:8000/v1/default/index/" \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@docs/index.md" | jq '.metadata_preview'
```

```json
[
  {
    "version": "1.0",
    "workspace_id": "default",
    "ingestion_id": "96435e86-4f90-45a8-872e-63f7cf5b49c4",
    "document_id": "1de4f6a1f61b49a08868b11d24db517d",
    "source": "upload",
    "source_location": "uploads/index.md",
    "content_hash": "71ff75...",
    "captured_at": "2024-06-03T22:19:05.104163+00:00",
    "extra": {
      "filename": "index.md"
    }
  }
]
```

### Connector Field Reference

| Endpoint                                  | `source` value | Common `extra` fields                          |
| ----------------------------------------- | -------------- | ---------------------------------------------- |
| `POST /v1/{workspace}/index/`             | `upload`       | `filename`                                     |
| `POST /v1/{workspace}/index_folder/`      | `folder`       | `root_directory`                               |
| `POST /v1/{workspace}/index/github`       | `github`       | `owner`, `repo`, `branch`                      |
| `POST /v1/{workspace}/index/web`          | `web`          | `render`, `url_count`                          |
| `POST /v1/{workspace}/index/web/crawl`    | `web_crawl`    | `allowed_domains`, `max_pages`, `max_depth`    |
| `POST /v1/{workspace}/index/security/s3`  | `security`     | `tool_name`, `schema`, `bucket`, `key`         |

SARIF/datastore connectors inherit the same envelope mechanics when routed through `LoggingDocumentWriter`.

### Querying OpenSearch

Documents live in workspace indices such as `ask_certus_default`. The full envelope remains on each chunk.

Filter by source:

```bash
curl -s "http://localhost:9200/ask_certus_default/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "_source": ["content", "metadata_envelope"],
    "query": { "term": { "metadata_envelope.source.keyword": "github" } },
    "size": 3
  }' | jq '.hits.hits[].\_source.metadata_envelope'
```

Filter by ingestion ID:

```bash
curl -s "http://localhost:9200/${INDEX}/_search" \
  -H 'Content-Type: application/json' \
  -d "{\"query\":{\"term\":{\"metadata_envelope.ingestion_id.keyword\":\"${INGESTION_ID}\"}},\"size\":3}" \
  | jq '.hits.hits[].\_source.metadata_envelope'
```

Aggregate unique ingestions:

```bash
curl -s "http://localhost:9200/ask_certus_default/_search" \
  -H "Content-Type: application/json" \
  -d '{"aggs":{"unique_ingestions":{"terms":{"field":"metadata_envelope.ingestion_id","size":100}}},"size":0}'
```

### Kibana / OpenSearch Dashboards
1. Navigate to `http://localhost:5601`.
2. Open **Discover** and select your index (e.g., `ask_certus_default`).
3. Add `metadata_envelope.source`, `metadata_envelope.source_location`, or `metadata_envelope.extra.*` to visualize provenance.

## Workflows / Operations
1. **During ingestion** – `LoggingDocumentWriter` enriches documents via `enrich_documents_with_metadata()` before writing.
2. **Preview validation** – Examine `metadata_preview` in API responses to ensure connectors populate expected fields.
3. **Audit** – Query OpenSearch by `ingestion_id`, `source`, or `extra` attributes for compliance or debugging.
4. **Analytics** – Use aggregations to track source diversity, deduplication hits, or quarantine events.

## Configuration / Interfaces
- Metadata enrichment lives in `certus_ask/pipelines/preprocessing.py` and `certus_ask/pipelines/components/document_writer.py`.
- `metadata_context` includes workspace ID, ingestion ID, source name, source location, and connector extras.
- The envelope schema version is controlled in `certus_ask/core/metadata.py` (bump when fields change).

## Troubleshooting / Gotchas
- **Missing preview entries:** Ensure the connector populates `metadata_context` before invoking the writer.
- **Inconsistent workspace IDs:** Always pass the authenticated workspace to `metadata_context` (avoid defaults).
- **Hash mismatches:** Recompute `content_hash` only from normalized chunk text; newline/encoding differences can cause false positives.
- **Query typos:** Use `.keyword` fields (`metadata_envelope.source.keyword`) for exact matches in OpenSearch.

## Related Documents
- [Multi-Workspace Isolation](../general/multi-workspace-isolation.md)
- [API Documentation Standard](api-doc-standard.md)
- [Standardized Response Format](api-response.md)
- [Logging – Usage](../logging/usage.md)
