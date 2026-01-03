# Logging Configuration

## Purpose
Document the environment variables and recommended presets that control Certus TAP’ structured logging stack (log levels, JSON output, OpenSearch streaming, credentials, and tuning).

## Audience & Prerequisites
- Developers editing `.env` files or Docker Compose overrides.
- Operators deploying Certus TAP to staging/production and hooking into centralized logging.
- Familiarity with standard env var management (`uv`, Docker Compose).

## Overview
All logging behavior is driven by environment variables. There are three main categories:
1. **Core logging settings** – level, JSON vs. text, and whether to ship to OpenSearch.
2. **OpenSearch connection** – host, port, optional credentials.
3. **Tuning** – choose presets for dev, local testing, staging, or production.

## Key Concepts

### Core Settings
| Variable | Default | Description |
|----------|---------|-------------|
| `LOG_LEVEL` | `INFO` | One of `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`. |
| `LOG_JSON_OUTPUT` | `true` | Emit structured JSON (`true`) or human-readable text (`false`). |
| `SEND_LOGS_TO_OPENSEARCH` | `true` | Stream logs to OpenSearch when `true`; console-only when `false`. |

**Log level guidance**
- `DEBUG` – heavy detail for development/troubleshooting.
- `INFO` – recommended for production (tracks operations without noise).
- `WARNING`/`ERROR` – minimal logging for high-security environments.

### OpenSearch Connection
| Variable | Default | Description |
|----------|---------|-------------|
| `OPENSEARCH_LOG_HOST` | `localhost` | Hostname (use service name `opensearch` inside Docker). |
| `OPENSEARCH_LOG_PORT` | `9200` | Port exposed by OpenSearch. |
| `OPENSEARCH_LOG_USERNAME` | _(empty)_ | Optional basic-auth username. |
| `OPENSEARCH_LOG_PASSWORD` | _(empty)_ | Optional basic-auth password. |

Example (auth-enabled cluster):
```bash
OPENSEARCH_LOG_HOST=opensearch.example.com
OPENSEARCH_LOG_PORT=9200
OPENSEARCH_LOG_USERNAME=loguser
OPENSEARCH_LOG_PASSWORD=strong-password
```

### Output Formats
- `LOG_JSON_OUTPUT=false` → console-friendly text (ideal for local dev).
  ```
  2025-11-14 10:30:45 - certus_ask.services.datalake - INFO - bucket.created bucket_name=raw
  ```
- `LOG_JSON_OUTPUT=true` → machine-readable JSON with timestamp, logger, message, and structured context (required for OpenSearch ingestion).

## Workflows / Operations

### Development (console only)
```bash
LOG_LEVEL=DEBUG
LOG_JSON_OUTPUT=false
SEND_LOGS_TO_OPENSEARCH=false
```

### Local testing with OpenSearch
```bash
LOG_LEVEL=DEBUG
LOG_JSON_OUTPUT=true
SEND_LOGS_TO_OPENSEARCH=true
OPENSEARCH_LOG_HOST=opensearch
OPENSEARCH_LOG_PORT=9200
```

### Staging
```bash
LOG_LEVEL=INFO
LOG_JSON_OUTPUT=true
SEND_LOGS_TO_OPENSEARCH=true
OPENSEARCH_LOG_HOST=opensearch-staging
OPENSEARCH_LOG_PORT=9200
OPENSEARCH_LOG_USERNAME=stage_user
OPENSEARCH_LOG_PASSWORD=stage_pass
```

### Production
```bash
LOG_LEVEL=INFO
LOG_JSON_OUTPUT=true
SEND_LOGS_TO_OPENSEARCH=true
OPENSEARCH_LOG_HOST=opensearch.example.com
OPENSEARCH_LOG_PORT=9200
OPENSEARCH_LOG_USERNAME=loguser
OPENSEARCH_LOG_PASSWORD=securepassword
```

## Configuration / Interfaces
- Add variables to `.env` or inject them via Docker Compose (`environment:` block already includes safe defaults for `ask-certus-backend`).
- To override per environment: `docker compose --env-file .env.production up`.
- Verification commands:
  ```bash
  env | grep LOG_
  env | grep OPENSEARCH_LOG_
  curl -u $OPENSEARCH_LOG_USERNAME:$OPENSEARCH_LOG_PASSWORD \
    http://$OPENSEARCH_LOG_HOST:$OPENSEARCH_LOG_PORT/
  ```

## Troubleshooting / Gotchas
- **Console logs but nothing in OpenSearch** – likely `SEND_LOGS_TO_OPENSEARCH=false` or wrong host/credentials. Enable streaming and restart the backend.
*- **Authentication errors** – ensure username/password pair has `write` permissions on the `logs-certus-tap` index; check OpenSearch logs for `security_exception`.
- **Unparsable console output in production** – set `LOG_JSON_OUTPUT=true`; structured logs are required for dashboards and retention policies.

## Related Documents
- [Getting Started](getting-started.md) – full bootstrap instructions.
- [Usage](usage.md) – best practices for emitting log events.
- [OpenSearch Logging Guide](opensearch.md) – index policies, sample queries.
- [Logging Stack Component](../components/logging-stack.md).
