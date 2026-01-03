# Logging Usage Guide

## Purpose
Show how to instrument Certus TAP services with structured logs: importing the logger, binding context (trace IDs, workspace, tenant), emitting consistent events, and handling errors.

## Audience & Prerequisites
- Backend engineers and pipeline authors writing new features.
- Familiarity with Python, FastAPI, and the Certus TAP request context helpers.

## Overview
Every module should obtain its logger via `get_logger(__name__)`, then emit events using a consistent naming scheme (`area.action`). The middleware automatically injects `trace_id`, but you can bind additional context (document IDs, workspace IDs, user IDs) per unit of work. The patterns below cover operations, batches, file handling, and API handlers.

## Key Concepts

### Import & Log Levels
```python
from certus_ask.core.logging import get_logger
logger = get_logger(__name__)

logger.info("operation.start", doc_id="123", action="upload")
logger.debug("processing.step", step="validation", took_ms=45)
logger.warning("operation.slow", duration_ms=5000)
logger.error("operation.failed", doc_id="123", error=str(exc))
logger.critical("service.down", service="opensearch")
```

### Context Binding
```python
from certus_ask.core.context import get_trace_id

logger = logger.bind(
    trace_id=get_trace_id(),
    workspace_id=workspace_id,
    tenant_id=tenant_id,
)
logger.info("document.processed", doc_id="123", duration_ms=250)
```

### Event Naming Convention
- Use `domain.action` (e.g., `document.indexed`, `privacy.quarantine`, `batch.complete`).
- Emit `operation.start`, `operation.complete`, and `operation.failed` where possible to keep flows searchable.
- Never log secrets; redact tokens and PII before logging.

## Workflows / Operations

### Operation Lifecycle
```python
logger.info("operation.start", op_id=op_id, action="process_document")
try:
    # work
    logger.info("operation.complete", op_id=op_id, duration_ms=250, success=True)
except Exception as exc:
    logger.error("operation.failed", op_id=op_id, error=str(exc), exc_info=True)
    raise
```

### Batch Processing
```python
logger.info("batch.processing", item_count=len(items))
success = 0
for item in items:
    logger = logger.bind(item_id=item.id)
    try:
        process_item(item)
        logger.debug("item.processed")
        success += 1
    except Exception as exc:
        logger.error("item.failed", error=str(exc))
logger.info("batch.complete", success_count=success, failed_count=len(items)-success)
```

### File Operations
```python
logger.info("file.upload_start", file_path=file.filename, size_bytes=file.size)
try:
    upload_file(...)
    logger.info("file.upload_complete", bucket="raw", key=key)
except Exception as exc:
    logger.error("file.upload_failed", error=str(exc))
    raise
```

### API Handler Pattern
```python
@router.post("/v1/index/")
async def index_document(...):
    scoped_logger = logger.bind(filename=file.filename)
    scoped_logger.info("upload.start")
    try:
        # validate/save/queue background work
        scoped_logger.info("upload.complete")
        return {"status": "success"}
    except ValidationError as exc:
        scoped_logger.error("upload.failed", error=str(exc), recoverable=True)
        raise
```

## Configuration / Interfaces
- Middleware automatically logs `http.request.start/end` and sets `trace_id`. Use `get_trace_id()` anywhere in the call stack to reuse it.
- For background jobs without middleware, call `get_trace_id()` once (it will lazily generate a UUID) and bind it to logs manually.
- JSON vs. text output and log levels are managed via the env vars documented in [Configuration](configuration.md).

## Troubleshooting / Gotchas
- **Missing trace IDs:** Always import and use `get_trace_id()` when emitting custom logs; failing to bind it makes tracing harder.
- **Inconsistent naming:** Stick to `verb.noun` or `domain.action` patterns. Random strings (e.g., `"started"`) make Kibana dashboards difficult to build.
- **Logging secrets:** Scrub tokens, passwords, and PII before logging. Privacy audits treat log leakage as a failure.

## Related Documents
- [Configuration](configuration.md)
- [Getting Started](getting-started.md)
- [OpenSearch Logging Guide](opensearch.md)
- [Privacy Operations](privacy-operations.md)
