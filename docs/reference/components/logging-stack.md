# Logging Stack & Dashboards

## Purpose
Summarize how Certus TAP emits structured logs, where those logs live (OpenSearch `logs-certus-tap` index), and how to explore them in OpenSearch Dashboards for troubleshooting or auditing.

## Audience & Prerequisites
- Operators monitoring ingestion health, privacy events, or API errors.
- Developers debugging backend issues.
- Requires the stack running with OpenSearch and Dashboards available.

## Overview
- All backend services use `structlog` to emit JSON logs enriched with `trace_id`, workspace, ingestion IDs, and error metadata.
- Logs flow to `logs-certus-tap` via the OpenSearch handler configured in `certus_ask/core/logging.py`.
- Dashboards (`http://localhost:5601`) provides canned views plus Dev Tools for raw queries.

## Key Concepts

### Structured Log Schema

| Field | Description |
| ----- | ----------- |
| `timestamp` | ISO8601 UTC when the event occurred. |
| `level` | `info`, `warning`, `error`. |
| `logger` | Module/logger name (e.g., `certus_ask.main`). |
| `event` | Event key (e.g., `ingestion.start`, `privacy.quarantine`). |
| `trace_id` | Correlates with API responses. |
| `workspace_id` | Present when request-scoped. |
| `ingestion_id` | For ingestion workflows. |
| `meta.*` | Additional context (connector, file, request path, etc.). |

### Indexes
- `logs-certus-tap` – Structured backend logs.
- `security-findings` / `sbom-packages` – Not logs but often cross-referenced for security analytics.
- Kibana index pattern example: `logs-certus-*`.

### Log Producers
- FastAPI middleware (`certus_ask/main.py`) logs request start/end, status codes, and trace IDs.
- Privacy logger (`certus_ask/services/privacy_logger.py`) emits PII detections, quarantines, and manual reviews.
- Pipelines/logging components log major lifecycle events (`ingestion.start`, `document_writer.complete`, `sarif.neo4j.*`).

## Workflows / Operations

1. **Create Data View in Dashboards**
   - Navigate to Stack Management → Data Views → Create (`logs-certus-*`).
   - Use Discover to search events by `trace_id`, `workspace_id`, or `event`.

2. **Search for Errors**
   ```bash
   curl -s "http://localhost:9200/logs-certus-tap/_search" \
     -H "Content-Type: application/json" \
     -d '{"query":{"term":{"level.keyword":"error"}},"size":5}'
   ```

3. **Trace a Request**
   - Grab `trace_id` from API response.
   - Query:
     ```bash
     curl -s "http://localhost:9200/logs-certus-tap/_search" \
       -H "Content-Type: application/json" \
       -d "{\"query\":{\"term\":{\"trace_id.keyword\":\"${TRACE_ID}\"}},\"size\":50}"
     ```

4. **Monitor Privacy Events**
   ```bash
   curl -s "http://localhost:9200/logs-certus-tap/_search" \
     -H "Content-Type: application/json" \
     -d '{"query":{"match":{"event":"privacy"}},"size":20}'
   ```

5. **Dashboards Visuals**
   - Save Discover searches (e.g., `level:error`).
   - Build visualizations (pie charts by workspace, bar charts by event).

## Configuration / Interfaces
- Logging config: `certus_ask/core/logging.py` (structlog processors, OpenSearch handler).
- Environment variables: `LOG_LEVEL`, `OPENSEARCH_URL`, `ENABLE_OPENSEARCH_LOGGING`.
- Dashboards service configured in `docker-compose.yml` (ports 5601/9200).
- Privacy logger toggles: `ENABLE_PRIVACY_LOGGING` (if you want to suppress certain events in dev).

## Troubleshooting / Gotchas
- **Empty logs:** Ensure OpenSearch handler is enabled (`ENABLE_OPENSEARCH_LOGGING=true`) and the backend can reach OpenSearch (check container networking).
- **Trace ID missing:** Confirm the tracing middleware runs before request handling; upgrades to FastAPI can reorder middleware if not careful.
- **High volume:** Use ILM (Index Lifecycle Management) or manual cleanup (`curl -X DELETE logs-certus-tap-YYYY.MM.DD`) if index grows too large in dev.
- **Timezone confusion:** All timestamps are UTC; configure Dashboards to display local time if desired.

## Related Documents
- [Standardized Response Format](../api/api-response.md) – Shares trace IDs.
- [Logging – Usage & Privacy](../logging/usage.md)
- [Streamlit Console](streamlit-console.md) – Health tab surfaces recent log snippets.
- [Metadata Envelopes](metadata-envelopes.md) – Frequently referenced alongside log events.
