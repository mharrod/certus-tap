# Getting Started with Structured Logging

## Purpose

Walk through the minimum steps to enable Certus TAP’ structured logging stack: install dependencies, start infrastructure, verify traffic, and confirm events appear in OpenSearch Dashboards.

## Audience & Prerequisites

- Developers running the backend locally or in CI.
- Operators bootstrapping new environments.
- Requires Docker (for OpenSearch/Dashboards) and Python with `uv`.

## Overview

The logging stack is pre-integrated with the backend. Getting started consists of syncing dependencies, starting OpenSearch/Dashboards, launching the app, sending a test request, and verifying logs in OpenSearch. Two configurations are typical:

- **Development** – console-friendly (no OpenSearch shipping).
- **Production** – JSON logs + OpenSearch streaming.

## Key Concepts

| Step           | Description                                                                                                  |
| -------------- | ------------------------------------------------------------------------------------------------------------ |
| Dependencies   | `uv sync` installs structlog + json logger (already in `pyproject.toml`).                                    |
| Infrastructure | `docker compose up -d opensearch opensearch-dashboards` ensures the cluster/UI is running.                   |
| Backend start  | `uvicorn certus_ask.main:app --reload` should log “✓ OpenSearch logging handler connected…” when configured. |
| Verification   | `curl http://localhost:8000/v1/health/` triggers `http.request.*` events.                                    |
| Observability  | Query `http://localhost:9200/logs-*/_count` or use Dashboards (`logs-*` data view).                          |

## Workflows / Operations

1. **Install deps**
   ```bash
   uv sync
   ```
2. **Start OpenSearch + Dashboards**
   ```bash
   docker compose up -d opensearch opensearch-dashboards
   curl http://localhost:9200   # sanity check
   ```
3. **Run backend**
   ```bash
   uvicorn certus_ask.main:app --reload
   ```
   Confirm logs show `✓ OpenSearch logging handler connected to opensearch:9200`.
4. **Send a test request**
   ```bash
   curl http://localhost:8000/v1/health/
   ```
5. **Verify ingestion**
   ```bash
   curl http://localhost:9200/logs-*/_count
   ```
   or open `http://localhost:5601`, create data view `logs-*`, and inspect events in Discover.

## Configuration / Interfaces

Add the following to `.env` (production defaults):

```bash
LOG_LEVEL=INFO
LOG_JSON_OUTPUT=true
SEND_LOGS_TO_OPENSEARCH=true
OPENSEARCH_LOG_HOST=opensearch
OPENSEARCH_LOG_PORT=9200
# Optional auth:
# OPENSEARCH_LOG_USERNAME=...
# OPENSEARCH_LOG_PASSWORD=...
```

Docker Compose already injects sane defaults for `ask-certus-backend`. For local dev, set:

```bash
LOG_LEVEL=DEBUG
LOG_JSON_OUTPUT=false
SEND_LOGS_TO_OPENSEARCH=false
```

## Troubleshooting / Gotchas

- **“Connection refused” on startup:** Ensure OpenSearch is up (`docker compose up -d opensearch` and `curl http://localhost:9200`).
- **No documents in index:** Verify the backend is running, send a request, and check `SEND_LOGS_TO_OPENSEARCH=true`. Credentials or host mismatches are the most common root cause.
- **Only console logs:** Expected when `SEND_LOGS_TO_OPENSEARCH=false`. Flip the flag and restart to stream to OpenSearch.

## Related Documents

- [Usage](usage.md) – Emitting domain-specific events.
- [Configuration](configuration.md) – Full list of environment variables.
- [OpenSearch](opensearch.md) – Index management and queries.
- [Logging Stack Component](../components/logging-stack.md).
  **Installation Time**: ~5 minutes
  **Verification Time**: ~2 minutes
