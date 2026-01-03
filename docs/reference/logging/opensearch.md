# OpenSearch Logging Guide

## Purpose
Explain how structured logs are stored, queried, and retained in OpenSearch, including schema details, lifecycle policies, and common Kibana/OpenSearch Dashboards workflows.

## Audience & Prerequisites
- Operators managing retention and index health.
- Developers or analysts querying logs via OpenSearch/KQL.
- Requires access to the OpenSearch cluster and Dashboards (`http://localhost:5601` locally).

## Overview
- Logs land in daily indices named `logs-certus-tap-YYYY-MM-DD`.
- A lifecycle policy (`logs-policy`) rolls indices every day and deletes data after 30 days.
- Dashboards uses the `logs-*` data view for search/visualization.
- Each document contains timestamp, level, logger, message, `trace_id`, HTTP context, and domain-specific fields (e.g., `doc_id`, `duration_ms`, `pii_score`).

## Key Concepts

### Index Properties
| Property | Value |
| -------- | ----- |
| Name pattern | `logs-certus-tap-*` |
| Type | Time-series (daily) |
| Retention | 30 days (configurable) |
| Shards | 1 (default) |
| Replicas | 0 (adjust per environment) |
| Policy | `logs-policy` (ISM/ILM) |

### Field Highlights
| Field | Type | Notes |
| ----- | ---- | ----- |
| `timestamp` | `date` | Primary time filter. |
| `level` | `keyword` | INFO/DEBUG/WARNING/ERROR/CRITICAL. |
| `logger` | `keyword` | Python module path. |
| `message` | `text` | Free-form event name (e.g., `operation.failed`). |
| `trace_id` | `keyword` | Correlates entire request. |
| `path`, `method`, `status_code` | Request metadata logged by middleware. |
| `doc_id`, `duration_ms`, `error`, `error_type` | Domain-specific context used by ingestion pipelines. |

### Lifecycle Policy Setup
```bash
# Create policy (daily rollover, delete after 30d)
curl -u admin:admin -X PUT http://localhost:9200/_plugins/_ism/policies/logs-policy \
  -H "Content-Type: application/json" -d '{
    "policy": {
      "description": "Daily rollover, 30-day retention",
      "default_state": "hot",
      "states": [
        {"name": "hot","actions":[{"rollover":{"min_index_age":"1d"}}],
         "transitions":[{"state_name":"delete","conditions":{"min_index_age":"30d"}}]},
        {"name": "delete","actions":[{"delete":{}}]}
      ]
    }
  }'

# Attach template to indices
curl -u admin:admin -X PUT http://localhost:9200/_index_template/logs-certus-tap \
  -H "Content-Type: application/json" -d '{
    "index_patterns": ["logs-certus-tap-*"],
    "template": {
      "settings": {
        "index.number_of_shards": 1,
        "index.number_of_replicas": 0,
        "index.plugins.index_state_management.policy_id": "logs-policy"
      }
    }
  }'
```

## Workflows / Operations

### Query Examples (KQL)
- All errors in last hour: `level: ERROR AND timestamp >= now-1h`
- Trace a request: `trace_id: "550e8400-e29b-41d4-a716-446655440000"`
- Slow operations: `duration_ms >= 5000`
- Document-specific failures: `doc_id: "doc-123" AND level: (ERROR OR WARNING)`

### Dashboards Setup
1. Visit `http://localhost:5601`.
2. Create data view `logs-*` with time field `timestamp`.
3. Use **Discover** for ad-hoc queries; save searches for dashboards.
4. Build panels:
   - Log volume over time (`count` by timestamp).
   - Error rate (filter `level: ERROR`).
   - Slow operations (`avg duration_ms` grouped by `path`).
   - Module contribution (`top values of logger`).

### Manual Index Ops
```bash
curl http://localhost:9200/_cat/indices?v | grep logs
curl -X DELETE http://localhost:9200/logs-certus-tap-2025-11-01   # delete specific day
```

## Configuration / Interfaces
- Handler settings come from [Configuration](configuration.md); ensure `SEND_LOGS_TO_OPENSEARCH=true`.
- To secure the pipeline: enable TLS/auth in OpenSearch, create a dedicated logging user, and map its credentials to `OPENSEARCH_LOG_USERNAME`/`PASSWORD`.
- Approximate storage: 50–100 MB/day (JSON logs). Adjust ILM policy if you need longer retention or additional shards.

## Troubleshooting / Gotchas
- **No indices appearing** – confirm the backend is running with streaming enabled and that OpenSearch is reachable (`curl http://localhost:9200`).
- **Dashboards missing data** – verify the index pattern includes the day’s index (wildcard `logs-*`) and the time picker covers the desired period.
- **Retention not applying** – make sure the ILM/ISM policy is attached to the template and the backend writes to `logs-certus-tap-YYYY-MM-DD`.
- **Performance issues** – filter by `timestamp` range and avoid full-text searches on `message` when possible; prefer keyword fields (trace_id, level, logger).

## Related Documents
- [Configuration](configuration.md)
- [Usage](usage.md)
- [Logging Stack Component](../components/logging-stack.md)
- [Troubleshooting](troubleshooting.md)
