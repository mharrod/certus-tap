# OpenSearch Explorer

## Purpose
Show how to inspect stored document chunks and metadata in OpenSearch—either via the Dashboards GUI or REST API—so you can validate ingestion, troubleshoot RAG retrieval, or audit provenance.

## Audience & Prerequisites
- Engineers verifying chunking/splitting behavior.
- Analysts auditing metadata (`metadata_envelope`, `meta.source`, etc.).
- Requires the stack to be up (`just up`) with OpenSearch reachable at `http://localhost:9200` and Dashboards at `http://localhost:5601`.

## Overview
- Every chunk from the preprocessing pipeline lands in an index named `ask_certus_<workspace>` (or `security-findings`, `sbom-packages` aliases).
- Dashboards provides an interactive UI (Discover, Dev Tools).
- REST queries (`curl` or Dashboards Console) expose the same data for automation.

## Key Concepts

### Dashboards Workflow
1. Visit `http://localhost:5601`.
2. Create a **Data View** (e.g., `ask_certus*`).
3. Use **Discover** to search/filter columns such as:
   - `content`
   - `meta.source`
   - `meta.file_path`
   - `metadata_envelope.ingestion_id`
4. Adjust the time picker to focus on recent ingestions.

Useful filters:
- `meta.file_path.keyword: "docs/index.md"`
- `meta.source.keyword: "web"`
- `metadata_envelope.source.keyword: "github"`

### REST Queries

**Top 5 chunks mentioning “TAP”:**
```bash
curl http://localhost:9200/ask_certus/_search?pretty \
  -H "Content-Type: application/json" \
  -d '{
    "size": 5,
    "_source": ["content", "meta"],
    "query": { "match": { "content": "TAP" } }
  }'
```

**Dump entire index (careful with size):**
```bash
curl http://localhost:9200/ask_certus/_search?pretty \
  -H "Content-Type: application/json" \
  -d '{ "query": { "match_all": {} }, "size": 10 }'
```

### Dev Tools Console
Inside Dashboards, open **Dev Tools → Console** and run the same queries:
```http
GET ask_certus/_search
{
  "query": {
    "match": {
      "content": "pipeline"
    }
  }
}
```
Console provides syntax highlighting, history, and saved queries.

## Workflows / Operations
- **Validate ingestion** – Immediately after running `/v1/{workspace}/index/*`, search for the source file/path to confirm segments exist.
- **Investigate RAG misses** – Search for keywords you expected to retrieve; ensure they were chunked and indexed correctly.
- **Audit metadata** – Filter on `metadata_envelope.*` or `meta.source` to ensure provenance fields are populated.
- **Monitoring** – Use Discover to watch ingestion volume by timeframe or source.

## Configuration / Interfaces
- Indices: `ask_certus_<workspace>` for knowledge chunks, `security-findings` and `sbom-packages` aliases for SARIF/SPDX pipelines, `logs-certus-tap` for structured logs.
- Access: `http://localhost:9200` (REST), `http://localhost:5601` (GUI). No authentication in local stack; add security if deploying remotely.
- Tooling: `curl`, Dashboards Dev Tools, or any OpenSearch-compatible client.

## Troubleshooting / Gotchas
- **No data view results:** Confirm `ask_certus_*` index exists (`curl http://localhost:9200/_cat/indices?v`). If empty, ingestion didn’t run or used a different workspace.
- **Query mismatch:** Use `.keyword` fields for exact matches (e.g., `meta.source.keyword`); plain fields are analyzed and may tokenize.
- **Large responses:** Always limit `size` when using `match_all` to avoid fetching thousands of chunks.
- **Dashboards port blocked:** Ensure `docker compose ps` shows `dashboards` running and no other process occupies port 5601.

## Related Documents
- [Metadata Envelopes (Component)](metadata-envelopes.md)
- [Logging – Usage](../logging/usage.md)
- [Neo4j Guide](neo4j-guide.md) – Complementary structured reasoning rail
- [Streamlit Console](streamlit-console.md) – Has built-in OpenSearch query panel
