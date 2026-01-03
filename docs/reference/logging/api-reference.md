# Logging API Reference

## Purpose

Serve as the canonical reference for structured logging primitives (`get_logger`, async OpenSearch handler, request middleware, and settings model) used throughout Certus TAP.

## Audience & Prerequisites

- Developers extending logging infrastructure or integrating new services.
- Requires familiarity with Python logging, structlog, and OpenSearch clients.

## Overview

The logging API consists of:

- `certus_ask.core.logging` – entry point for configuring structlog and retrieving bound loggers.
- `certus_ask.core.async_opensearch_handler` – async transport layer that sends logs to OpenSearch.
- `certus_ask.core.opensearch_indices` – utilities for creating indices and lifecycle policies.
- `certus_ask.middleware.logging` – FastAPI middleware for tracing requests.
- `certus_ask.core.config.Settings` – strongly typed settings (env-driven).

## Key Concepts

### Core Modules

### `certus_ask.core.logging`

Main logging configuration module.

#### Functions

##### `configure_logging()`

```python
def configure_logging(
    level: str = "INFO",
    json_output: bool = True,
    opensearch_handler: Optional[logging.Handler] = None,
) -> None:
```

Configure structured logging for the application.

**Parameters:**

- `level` (str): Logging level - DEBUG, INFO, WARNING, ERROR, CRITICAL
- `json_output` (bool): True for JSON format, False for human-readable
- `opensearch_handler` (Handler|None): Optional OpenSearch handler for remote logging

**Example:**

```python
from certus_ask.core.logging import configure_logging

configure_logging(
    level="INFO",
    json_output=True,
    opensearch_handler=handler
)
```

##### `get_logger()`

```python
def get_logger(name: str) -> structlog.BoundLogger:
```

Get a structured logger instance.

**Parameters:**

- `name` (str): Logger name, typically `__name__`

**Returns:**

- `structlog.BoundLogger`: Configured structured logger

**Example:**

```python
from certus_ask.core.logging import get_logger

logger = get_logger(__name__)
logger.info("event.name", field="value")
```

---

### `certus_ask.core.async_opensearch_handler`

Non-blocking async handler for OpenSearch logging.

#### Classes

##### `AsyncOpenSearchHandler`

Non-blocking logging handler with automatic reconnection.

```python
class AsyncOpenSearchHandler(logging.Handler):
    def __init__(
        self,
        hosts: list[dict],
        index_name: str = "logs-certus-tap",
        batch_size: int = 100,
        queue_size: int = 1000,
        timeout: int = 5,
        username: Optional[str] = None,
        password: Optional[str] = None,
    ):
```

**Parameters:**

- `hosts` (list): List of OpenSearch host dicts, e.g., `[{"host": "localhost", "port": 9200}]`
- `index_name` (str): OpenSearch index name
- `batch_size` (int): Number of logs to batch before sending
- `queue_size` (int): Maximum size of log queue
- `timeout` (int): Connection timeout in seconds
- `username` (str|None): OpenSearch username if auth required
- `password` (str|None): OpenSearch password if auth required

**Features:**

- Non-blocking async log shipping
- Queue-based batching for efficiency
- Graceful degradation when OpenSearch unavailable
- Automatic reconnection with exponential backoff
- Circuit breaker pattern for resilience

**Example:**

```python
from certus_ask.core.async_opensearch_handler import AsyncOpenSearchHandler

handler = AsyncOpenSearchHandler(
    hosts=[{"host": "opensearch", "port": 9200}],
    index_name="logs-certus-tap",
    batch_size=100,
    username="admin",
    password="password"
)
```

**Methods:**

###### `emit()`

```python
def emit(self, record: logging.LogRecord) -> None:
```

Queue a log record for sending to OpenSearch. Non-blocking.

###### `close()`

```python
def close(self) -> None:
```

Close the handler and stop the background worker thread.

---

### `certus_ask.core.opensearch_indices`

Index setup and management utilities.

#### Functions

##### `create_logs_index()`

```python
def create_logs_index(
    client: OpenSearch,
    index_name: str = "logs-certus-tap"
) -> None:
```

Create the logs index with proper mappings and settings.

**Parameters:**

- `client` (OpenSearch): OpenSearch client instance
- `index_name` (str): Name of index to create

**Example:**

```python
from opensearchpy import OpenSearch
from certus_ask.core.opensearch_indices import create_logs_index

client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}])
create_logs_index(client, "logs-certus-tap")
```

##### `create_ilm_policy()`

```python
def create_ilm_policy(client: OpenSearch) -> None:
```

Create Index Lifecycle Management policy for automatic log cleanup.

**Parameters:**

- `client` (OpenSearch): OpenSearch client instance

**Behavior:**

- Creates daily index rollover
- Deletes indices older than 30 days
- Prevents unbounded disk growth

##### `setup_logs_infrastructure()`

```python
def setup_logs_infrastructure(
    client: OpenSearch,
    index_name: str = "logs-certus-tap"
) -> None:
```

Complete setup of logging infrastructure.

**Parameters:**

- `client` (OpenSearch): OpenSearch client instance
- `index_name` (str): Name of logs index

**Does:**

1. Creates logs index
2. Creates ILM policy
3. Sets up field mappings

**Example:**

```python
from opensearchpy import OpenSearch
from certus_ask.core.opensearch_indices import setup_logs_infrastructure

client = OpenSearch(hosts=[{"host": "localhost", "port": 9200}])
setup_logs_infrastructure(client)
```

---

### `certus_ask.middleware.logging`

FastAPI request/response logging middleware.

#### Classes

##### `RequestLoggingMiddleware`

Logs all HTTP requests and responses with timing.

```python
class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable
    ) -> Response:
```

**Features:**

- Generates unique request ID
- Logs HTTP method, path, query params
- Logs response status and duration
- Binds request context to all logs
- Captures and logs errors

**Automatic Fields:**

- `request_id` - Unique ID for tracing
- `method` - HTTP method
- `path` - Request path
- `client_ip` - Client IP address
- `status_code` - Response status (in response log)
- `duration_ms` - Request duration (in response log)

**Example Usage:**

```python
# In main.py
from certus_ask.middleware.logging import RequestLoggingMiddleware

app.add_middleware(RequestLoggingMiddleware)

# Now all requests are logged automatically
```

---

## Structured Logger API

### Logger Methods

#### `logger.info()`

```python
logger.info(event: str, **fields) -> None:
```

Log an informational message.

**Parameters:**

- `event` (str): Event name (format: `context.action`)
- `**fields`: Structured fields as keyword arguments

**Example:**

```python
logger.info("document.indexed", doc_id="123", duration_ms=250)
```

#### `logger.debug()`

```python
logger.debug(event: str, **fields) -> None:
```

Log detailed debugging information.

**Example:**

```python
logger.debug("processing.step", step="validation", took_ms=45)
```

#### `logger.warning()`

```python
logger.warning(event: str, **fields) -> None:
```

Log a warning for recoverable issues.

**Example:**

```python
logger.warning("operation.slow", operation="indexing", duration_ms=5000)
```

#### `logger.error()`

```python
logger.error(event: str, **fields) -> None:
```

Log an error for failed operations.

**Example:**

```python
logger.error("operation.failed", doc_id="123", error=str(exc))
```

#### `logger.critical()`

```python
logger.critical(event: str, **fields) -> None:
```

Log a critical error when service cannot continue.

**Example:**

```python
logger.critical("service.down", service="opensearch")
```

#### `logger.bind()`

```python
logger.bind(**context) -> BoundLogger:
```

Create a new logger with additional context fields.

**Parameters:**

- `**context`: Context fields to include in all subsequent logs

**Returns:**

- New `BoundLogger` with bound context

**Example:**

```python
user_logger = logger.bind(user_id="user-123", tenant_id="acme")
user_logger.info("query.executed")  # Includes user_id and tenant_id
```

---

## Configuration Module

### `certus_ask.core.config.Settings`

Pydantic Settings model for application configuration.

```python
class Settings(BaseSettings):
    # Logging configuration
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_json_output: bool = Field(default=True, env="LOG_JSON_OUTPUT")
    send_logs_to_opensearch: bool = Field(default=True, env="SEND_LOGS_TO_OPENSEARCH")
    disable_opensearch_logging: bool = Field(
        default=False,
        env="DISABLE_OPENSEARCH_LOGGING",
        description="Force-disable the async OpenSearch log handler regardless of SEND_LOGS_TO_OPENSEARCH."
    )

    # OpenSearch logging
    opensearch_log_host: str = Field(default="localhost", env="OPENSEARCH_LOG_HOST")
    opensearch_log_port: int = Field(default=9200, env="OPENSEARCH_LOG_PORT")
    opensearch_log_username: str | None = Field(None, env="OPENSEARCH_LOG_USERNAME")
    opensearch_log_password: str | None = Field(None, env="OPENSEARCH_LOG_PASSWORD")
```

**Usage:**

```python
from certus_ask.core.config import get_settings

settings = get_settings()
print(f"Log level: {settings.log_level}")
print(f"OpenSearch host: {settings.opensearch_log_host}")
```

---

## Environment Variables

Complete reference of logging-related environment variables.

| Variable                     | Type | Default   | Description                                      |
| ---------------------------- | ---- | --------- | ------------------------------------------------ |
| `LOG_LEVEL`                  | str  | INFO      | Logging level                                    |
| `LOG_JSON_OUTPUT`            | bool | true      | JSON or human-readable                           |
| `SEND_LOGS_TO_OPENSEARCH`    | bool | true      | Enable OpenSearch logging                        |
| `DISABLE_OPENSEARCH_LOGGING` | bool | false     | Force-disable OpenSearch logging even if enabled |
| `OPENSEARCH_LOG_HOST`        | str  | localhost | OpenSearch host                                  |
| `OPENSEARCH_LOG_PORT`        | int  | 9200      | OpenSearch port                                  |
| `OPENSEARCH_LOG_USERNAME`    | str  | (none)    | OpenSearch username                              |
| `OPENSEARCH_LOG_PASSWORD`    | str  | (none)    | OpenSearch password                              |

---

## Data Types

### Log Record Fields

OpenSearch stores logs with these field types:

| Field         | Type    | Example                                |
| ------------- | ------- | -------------------------------------- |
| `timestamp`   | date    | `2025-11-14T10:30:45.123Z`             |
| `level`       | keyword | `INFO`, `ERROR`                        |
| `logger`      | keyword | `certus_ask.services.datalake`         |
| `message`     | text    | `bucket.created`                       |
| `request_id`  | keyword | `550e8400-e29b-41d4-a716-446655440000` |
| `duration_ms` | float   | `250.5`                                |
| `doc_id`      | keyword | `my-document-123`                      |
| `method`      | keyword | `POST`                                 |
| `path`        | keyword | `/v1/index/`                           |
| `status_code` | integer | `200`                                  |
| `error_type`  | keyword | `ValueError`                           |
| `module`      | keyword | `datalake`                             |
| `function`    | keyword | `ensure_bucket`                        |
| `line_number` | integer | `42`                                   |
| `process_id`  | integer | `12345`                                |
| `thread_name` | keyword | `MainThread`                           |

---

## Exception Handling

### Logging Exceptions

```python
try:
    operation()
except Exception as exc:
    logger.error(
        "operation.failed",
        error=str(exc),
        error_type=type(exc).__name__,
        exc_info=True  # Include full traceback
    )
    raise
```

### Safe Exception Logging

The logging system safely handles exceptions:

- Won't crash on logging errors
- Will continue with console logging if OpenSearch unavailable
- Automatically includes tracebacks when requested

---

## Performance Characteristics

| Metric                 | Value               |
| ---------------------- | ------------------- |
| Memory per log         | ~500-1000 bytes     |
| Queue max size         | 1000 logs (~1-2 MB) |
| Batch size             | 100 logs            |
| Flush timeout          | 2 seconds           |
| CPU overhead           | <1%                 |
| Request latency impact | None (async)        |

---

## Workflows / Operations

1. **Configure logging** via `configure_logging(level, json_output, opensearch_handler)`.
2. **Register middleware** (`RequestLoggingMiddleware`) to capture request context.
3. **Emit logs** using `get_logger(__name__)`.
4. **Optional infrastructure bootstrap** – call `setup_logs_infrastructure()` during provisioning to create indices/policies.

## Configuration / Interfaces

- Environment variables (table above) control behavior.
- Settings model (`certus_ask.core.config.Settings`) exposes type-safe access (`get_settings()`).
- For programmatic handlers, instantiate `AsyncOpenSearchHandler(hosts=[...])` and pass to `configure_logging`.

## Troubleshooting / Gotchas

- Handler emits warnings (queue full, connection failures) but the API continues to function—monitor backend logs for `OpenSearch logging handler` messages.
- Always call `logger.bind()` to persist context between async tasks; forgetting to bind results in missing `trace_id`.
- Lifecycle helpers expect OpenSearch credentials to be valid; run them with elevated permissions or via automation during deployments.

## Related Documents

- [Usage Guide](usage.md)
- [Configuration](configuration.md)
- [OpenSearch Logging Guide](opensearch.md)
- [Troubleshooting](troubleshooting.md)
