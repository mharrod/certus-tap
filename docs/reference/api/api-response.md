# Standardized Response Format & Trace IDs

## Purpose
Guarantee that every Certus TAP API response—success or error—shares the same envelope and traceability semantics so client integrations remain trivial and support teams can correlate requests end-to-end.

## Audience & Prerequisites
- Backend engineers building/maintaining API endpoints.
- Client developers consuming the REST API.
- Familiarity with FastAPI responses and the [API Error Codes](api-error-codes.md).

## Overview
- Every response contains `status`, `data`, `error`, `timestamp`, and `trace_id`.
- Success payloads live inside `data`; error metadata lives inside `error`.
- Trace IDs are generated (or propagated) per request and surface in logs, headers, and response bodies.
- Helper functions in `certus_ask.core.response_utils` enforce this contract.

## Key Concepts

### Response Envelope

```json
{
  "status": "success | error",
  "data": {},
  "error": null,
  "timestamp": "ISO8601 UTC",
  "trace_id": "UUID4"
}
```

- `status`: `"success"` or `"error"`.
- `data`: Response payload (success only).
- `error`: `{ "code": "...", "message": "...", "context": {...} }` (error only).
- `timestamp`: Set when the response is generated.
- `trace_id`: Unique request identifier used throughout the stack.

### Success Responses (2xx)

```json
{
  "status": "success",
  "data": {
    "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
    "message": "Indexed document document.pdf",
    "document_count": 42
  },
  "error": null,
  "timestamp": "2024-11-14T12:34:56.789Z",
  "trace_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

- `data` aligns with the endpoint’s pydantic response model.
- Typical HTTP codes: `200 OK`, `201 Created`.

### Error Responses (4xx / 5xx)

```json
{
  "status": "error",
  "data": null,
  "error": {
    "code": "file_too_large",
    "message": "File exceeds maximum size of 100MB",
    "context": {
      "max_size_mb": 100,
      "actual_size_mb": 256
    }
  },
  "timestamp": "2024-11-14T12:34:56.789Z",
  "trace_id": "550e8400-e29b-41d4-a716-446655440001"
}
```

- `code` references the canonical list in [API Error Codes](api-error-codes.md).
- `context` is optional metadata that helps clients debug.
- HTTP codes map to the failure (400 validation, 404 missing resource, 500 internal, etc.).

### Trace IDs

#### Lifecycle
1. Middleware looks for an `X-Trace-ID` header; if absent, it generates a UUID4.
2. The trace ID is stored in request context and available to downstream services/loggers.
3. Structured logs include `trace_id`.
4. Responses surface the trace ID in both the JSON body and `X-Trace-ID` response header.

#### Usage

```bash
curl -X POST "http://localhost:8000/v1/ask" \
  -H "X-Trace-ID: my-custom-trace-id-123" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the privacy policy?"}'
```

- Clients may supply their own ID; otherwise, one is generated.
- Trace IDs simplify debugging: search logs for the same ID to follow request flow.

#### Log Correlation Example

```
timestamp=2024-11-14T12:34:56 trace_id=550e8400-e29b-41d4-a716-446655440000 event=http.request.start method=POST path=/v1/ask
timestamp=2024-11-14T12:34:58 trace_id=550e8400-e29b-41d4-a716-446655440000 event=http.request.end status_code=200 duration_ms=1234
```

## Workflows / Operations
1. **Inside endpoints**, call `success_response(data)` or `error_response(code, message, context)` from `certus_ask.core.response_utils`.
2. **For FastAPI exceptions**, wrap errors in `HTTPException` but structure the response dictionary to match the standard envelope.
3. **Ensure tests** assert on `status`, `error.code`, and `trace_id` to prevent regressions.
4. **Forward trace IDs** to downstream services (OpenSearch, LocalStack) when applicable.

## Configuration / Interfaces
- Middleware responsible for trace IDs lives in `certus_ask/core/tracing.py` (propagation) and `certus_ask/main.py` (FastAPI setup).
- Response helpers are defined in `certus_ask/core/response_utils.py`.
- Structured logging attaches `trace_id` automatically via `structlog` processors.

## Troubleshooting / Gotchas
- **Missing trace IDs:** Verify the tracing middleware is registered before routers; check for conflicting ASGI middleware.
- **Custom responses bypass helpers:** Always return the standardized envelope, even for streaming endpoints.
- **Clock skew:** Timestamps should use `datetime.utcnow()`—ensure servers have synchronized clocks.
- **Context bloat:** Keep `error.context` concise; avoid adding full payloads or secrets.

## Related Documents
- [API Documentation Standard](api-doc-standard.md)
- [API Error Codes](api-error-codes.md)
- [Logging – Overview](../logging/overview.md)
- [Metadata Envelopes](metadata-envelopes.md)
