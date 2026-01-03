# Logging Troubleshooting

## Purpose
Help operators diagnose common logging issues—from OpenSearch connectivity to missing events or excessive resource usage.

## Audience & Prerequisites
- Engineers running Certus TAP locally or in production.
- Requires shell access to the backend container and OpenSearch.

## Overview
Most failures fall into four buckets:
1. **Connection/auth problems** – handler can’t reach OpenSearch.
2. **No data** – streaming disabled or no events generated.
3. **Performance/storage** – queue backpressure, slow Dashboards, disk full.
4. **Data quality** – missing fields, inconsistent trace IDs.

The troubleshooting steps below address each category.

## Key Concepts

### Connectivity
| Symptom | Checks | Fixes |
| ------- | ------ | ----- |
| `Connection refused` on startup | `curl http://localhost:9200` | `docker compose up -d opensearch` |
| `401 Unauthorized` | `curl -u $OPENSEARCH_LOG_USERNAME:$OPENSEARCH_LOG_PASSWORD http://host:port` | Update credentials or disable auth in `.env`. |
| Wrong host/port | `echo $OPENSEARCH_LOG_HOST:$OPENSEARCH_LOG_PORT` | Match Docker service name (`opensearch`) and port `9200`. |

### Missing Logs
- Confirm streaming enabled: `echo $SEND_LOGS_TO_OPENSEARCH` should be `true`.
- Check handler status in backend logs:
  ```
  docker logs ask-certus-backend | grep "OpenSearch logging handler"
  ```
- Generate traffic:
  ```bash
  curl http://localhost:8000/v1/health/
  curl http://localhost:9200/logs-*/_count
  ```

### Dashboards
- Ensure data view `logs-*` exists and time range is reasonable (Last 15 minutes vs 30 days).
- Query via REST if UI is empty:
  ```bash
  curl http://localhost:9200/_cat/indices | grep logs
  ```

## Workflows / Operations

### Connection Failure Playbook
1. `curl http://localhost:9200` – verify cluster up.
2. `ping opensearch` / `telnet opensearch 9200` – confirm Docker networking.
3. Check `.env` for host/port/user/pass.
4. Restart backend after config changes.

### No Logs Appearing
1. Ensure `SEND_LOGS_TO_OPENSEARCH=true`.
2. Trigger `curl http://localhost:8000/v1/health/`.
3. Recheck `_count`.
4. If still zero, inspect backend logs for errors (queue full, auth failures). Fall back to console logs while fixing root cause.

### Queue Full / High Memory
- Warning:
  ```
  WARNING OpenSearch log queue full, dropping logs
  ```
- Actions:
  - Reduce verbosity (`LOG_LEVEL=INFO` instead of `DEBUG`).
  - Increase OpenSearch capacity (CPU/memory) or investigate cluster latency.
  - Ensure batch size/queue size remain default (don’t shrink).

### Disk Pressure
```bash
curl http://localhost:9200/_cat/indices | grep logs
```
- Delete stale indices: `curl -X DELETE http://localhost:9200/logs-certus-tap-2025-11-01`.
- Shorten retention in ILM policy (`min_index_age`: `"14d"`).

## Configuration / Interfaces
- Environment debug:
  ```bash
  env | grep LOG_
  env | grep OPENSEARCH_LOG_
  ```
- Handler health (Python REPL):
  ```python
  from certus_ask.core.async_opensearch_handler import handler_instance
  handler_instance.queue.qsize()
  ```
  (Instrument as needed in debugging builds.)

## Troubleshooting / Gotchas
- **Console logs only** – expected when streaming disabled. Re-enable and restart.
- **Missing trace IDs** – ensure logging happens inside HTTP request context or manually bind `trace_id`.
- **Slow Dashboards** – reduce time window, filter by `level` or `module`, avoid wildcard searches across 30 days.
- **Auth mismatch** – leaving `OPENSEARCH_LOG_USERNAME`/`PASSWORD` set when the cluster has no auth causes 401s; unset both variables.

## Related Documents
- [Configuration](configuration.md)
- [OpenSearch Logging Guide](opensearch.md)
- [Logging Stack Component](../components/logging-stack.md)
