# ADR-0003: Error Handling with Custom Exceptions

## Status
**Accepted**

## Date
2025-11-14

## Context

### Problem
The application needed a consistent approach to error handling that:

1. **Provides semantic meaning** - Errors should indicate what type of problem occurred
2. **Produces user-friendly messages** - Never expose internal implementation details to clients
3. **Enables debugging** - Developers need context (what failed, why) in logs
4. **Allows selective handling** - Code can catch specific error types, not just generic exceptions
5. **Uses proper HTTP status codes** - Different errors map to correct HTTP codes (400, 404, 500, 503, etc.)
6. **Maintains consistency** - All endpoints follow same error response format

### Current State (Before)
```python
# Before: Inconsistent, too broad
try:
    result = pipeline.run(...)
except Exception as exc:  # Catches everything!
    raise HTTPException(status_code=500, detail=str(exc)) from exc
    # ❌ Exposes internal error message to user
    # ❌ No semantic meaning
    # ❌ Cannot distinguish between types of failures
    # ❌ Internal details leak to clients
```

### Constraints
- Application must return proper HTTP status codes
- Error messages must be suitable for API clients (not internal stack traces)
- Must support request tracing (include request ID in error context)
- Should not introduce performance overhead
- Must work with FastAPI's exception handling system

## Decision

We chose **custom exception hierarchy with semantic types and structured error responses** because:

### 1. Domain-Specific Exception Classes

```python
class DocumentIngestionError(DocumentProcessingError):
    """File upload/ingestion failed"""

class PrivacyViolationError(PrivacyError):
    """Document contains high-confidence PII in strict mode"""

class OpenSearchError(ExternalServiceError):
    """OpenSearch cluster unavailable"""
```

Benefits:
- Code can catch specific errors: `except DocumentIngestionError`
- Semantically clear what went wrong
- Enables different handling per error type
- Easy to add new error types as needed

### 2. Structured Error Details

```python
raise DocumentIngestionError(
    message="Failed to process document",
    error_code="ingestion_failed",
    details={"filename": "document.pdf", "reason": "unsupported_format"}
)
```

Benefits:
- Message: User-friendly explanation
- Error code: Machine-readable identifier (for programmatic handling)
- Details: Additional context (constraints, field names, etc.)
- Can be serialized to JSON for API responses

### 3. Specific Exception Catching (Not Broad Catches)

```python
# After: Specific, semantic
try:
    result = pipeline.run(...)
except TimeoutError as exc:
    raise HTTPException(status_code=504, detail="Operation timed out") from exc
except (ValueError, KeyError) as exc:
    raise HTTPException(status_code=400, detail="Invalid input") from exc
except DocumentParseError as exc:
    raise HTTPException(status_code=400, detail=exc.message) from exc
except ExternalServiceError as exc:
    raise HTTPException(status_code=503, detail="Service unavailable") from exc
except Exception as exc:
    # Last resort: unexpected error
    raise DocumentIngestionError(
        message="Unexpected failure",
        error_code="internal_error",
        details={}
    ) from exc
```

Benefits:
- Different HTTP codes for different failures (400, 404, 500, 503)
- User-friendly messages (not exposing internals)
- Can log detailed context for debugging
- Handles unexpected errors gracefully

### 4. Standardized Error Response Format

```json
{
  "error": "document_parse_failed",
  "message": "Failed to parse PDF document",
  "detail": {
    "filename": "document.pdf",
    "error": "Invalid PDF structure",
    "supported_formats": ["pdf", "txt", "docx"]
  }
}
```

Benefits:
- Clients know exactly what format to expect
- Can parse error code programmatically
- Can display message to end-user
- Can display details to help resolve issue

### 5. Proper HTTP Status Codes

| Status | Exception | Meaning |
|--------|-----------|---------|
| 400 | DocumentParseError, ValidationError | Bad request, invalid input |
| 404 | IndexNotFoundError, FileNotFoundError | Resource doesn't exist |
| 409 | ConflictErrorResponse | State conflict |
| 500 | DocumentIngestionError | Server error, unexpected failure |
| 503 | ExternalServiceError, OpenSearchError | Required service unavailable |
| 504 | TimeoutError | Operation timed out |

Benefits:
- Clients can programmatically detect error type from HTTP code
- Follows REST conventions
- Enables proper retry logic (503/504 should retry, 400 should not)

## Architecture

```
Application Code
      ↓
Business Logic
├─ Catches specific exceptions
├─ Logs context for debugging
├─ Creates user-friendly error response
      ↓
raise DocumentIngestionError(...)
      ↓
Exception Handler (in route)
├─ Maps exception to HTTP status code
├─ Creates ErrorDetailResponse
├─ Returns JSON to client
      ↓
Client receives:
{
  "error": "ingestion_failed",
  "message": "Failed to process document",
  "detail": {"filename": "..."}
}
```

## Exception Hierarchy

```
CertusException (base)
│
├── DocumentProcessingError
│   ├── DocumentIngestionError
│   ├── DocumentParseError
│   └── DocumentValidationError
│
├── PrivacyError
│   ├── PrivacyViolationError
│   └── PIIDetectionError
│
├── SearchError
│   ├── IndexNotFoundError
│   └── QueryExecutionError
│
├── StorageError
│   ├── BucketNotFoundError
│   ├── FileNotFoundError
│   └── FileUploadError
│
├── ExternalServiceError
│   ├── OpenSearchError
│   ├── S3Error
│   ├── LLMError
│   └── MLflowError
│
├── ConfigurationError
│
└── ValidationError
```

## Consequences

### Positive
✅ **Semantic errors** - Code says what went wrong, not just "Exception"
✅ **Selective handling** - Can catch specific error types
✅ **User-friendly** - Messages never expose internals
✅ **Debuggable** - Details included for developers
✅ **Consistent** - All errors follow same pattern
✅ **Machine-readable** - Error codes for programmatic handling
✅ **Proper HTTP codes** - Clients can retry intelligently
✅ **Traceable** - Exception chaining preserves full stack trace

### Negative
❌ **More exceptions** - 16 exception classes vs 1 generic Exception
❌ **More code** - Exception definitions + catching + mapping
❌ **Learning curve** - Developers need to know exception hierarchy

### Neutral
◯ **Performance** - Negligible overhead from exception raising
◯ **Compatibility** - HTTPException still used for final response

## Alternatives Considered

### 1. Generic HTTPException Only
```python
raise HTTPException(status_code=500, detail="Something failed")
```
**Rejected** - No semantic meaning, cannot selectively catch, all errors 500 status

### 2. Only Standard Library Exceptions
```python
raise ValueError("Invalid format")
raise FileNotFoundError("Document not found")
```
**Rejected** - Mixes business errors with system errors, no domain semantics

### 3. Error Codes as Enums
```python
class ErrorCode(Enum):
    INGESTION_FAILED = "ingestion_failed"
    PARSE_FAILED = "parse_failed"

raise HTTPException(status_code=500, detail=ErrorCode.INGESTION_FAILED)
```
**Rejected** - No inheritance, less structured, harder to extend

### 4. Monolithic Error Class
```python
class AppError(Exception):
    def __init__(self, error_code, message, status_code, details):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details
```
**Rejected** - Loses semantic meaning of error type, all errors treated same

### 5. No Custom Exceptions (All Generic)
```python
try:
    ...
except Exception as exc:
    if "parse" in str(exc):
        status = 400
    else:
        status = 500
    raise HTTPException(status_code=status, detail="Error")
```
**Rejected** - String parsing fragile, no type safety, unmaintainable

## Implementation Details

### Exception Definition (`certus_ask/core/exceptions.py`)

```python
class CertusException(Exception):
    """Base exception with message, code, and details"""

    def __init__(
        self,
        message: str,
        error_code: str | None = None,
        details: dict | None = None,
    ) -> None:
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)

    def to_dict(self) -> dict:
        """Convert to API response dict"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details if self.details else None,
        }
```

### Error Response Schema (`certus_ask/schemas/errors.py`)

```python
class ErrorDetailResponse(BaseModel):
    error: str  # Machine-readable code
    message: str  # User-friendly message
    detail: dict[str, Any] | None = None  # Additional context
```

### Exception Handling in Routes

```python
@router.post("/index/")
async def index_document(uploaded_file: UploadFile) -> DocumentIngestionResponse:
    """Upload and index a document"""
    try:
        # Validate size
        if file_size > MAX_SIZE:
            raise FileUploadError(
                message="File exceeds maximum size",
                error_code="file_too_large",
                details={"max_size_mb": 100, "actual_size_mb": file_size/1024/1024}
            )

        # Process document
        result = pipeline.run(...)

    except FileUploadError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc
    except (ValueError, KeyError) as exc:
        raise DocumentParseError(
            message="Failed to parse document",
            error_code="parse_failed",
            details={"filename": uploaded_file.filename}
        ) from exc
    except Exception as exc:
        logger.error("unexpected_error", error=str(exc), exc_info=True)
        raise DocumentIngestionError(
            message="Failed to process document",
            error_code="ingestion_failed",
            details={"filename": uploaded_file.filename}
        ) from exc

    return DocumentIngestionResponse(...)
```

### Logging Integration

```python
try:
    ...
except DocumentIngestionError as exc:
    # Log with structured context
    logger.error(
        "ingestion.failed",
        error_code=exc.error_code,
        message=exc.message,
        details=exc.details,
        exc_info=True,  # Include stack trace
    )
    # Return to client
    raise HTTPException(status_code=500, detail=exc.message) from exc
```

## Error Handling Patterns

### Pattern 1: Validation Before Processing
```python
# Fail fast on invalid input
if not document.has_content():
    raise DocumentValidationError(
        message="Document has no extractable content",
        error_code="no_content",
        details={"document_id": doc_id}
    )
```

### Pattern 2: Wrap External Service Errors
```python
try:
    response = opensearch_client.search(...)
except ConnectionError as exc:
    raise OpenSearchError(
        message="Search service unavailable",
        error_code="opensearch_unavailable",
        details={"host": settings.opensearch_host}
    ) from exc
```

### Pattern 3: Provide Helpful Context
```python
if num_questions > MAX_ALLOWED:
    raise ValidationError(
        message="Number of questions exceeds limit",
        error_code="validation_failed",
        details={
            "field": "num_questions",
            "max": MAX_ALLOWED,
            "requested": num_questions,
            "suggestion": f"Use {MAX_ALLOWED} or fewer"
        }
    )
```

## Trade-offs Made

| Decision | Why | Trade-off |
|----------|-----|-----------|
| Multiple exception classes | Semantic meaning | More code to maintain |
| Structured details dict | Rich context | Need to document what keys to expect |
| HTTP status code mapping | Proper REST semantics | Must map exceptions to codes |
| Exception chaining (from exc) | Preserve stack trace | Slightly more verbose |
| Message + error_code | Both human and machine | More to document |

## Migration Path

If in future you want:

1. **Global exception handler** - Add FastAPI exception handler for CertusException
2. **Error tracking** - Add Sentry integration in exception handler
3. **Metrics** - Track error_code in Prometheus metrics
4. **Retry logic** - Client can retry on 503/504, not on 400

No changes to exception definitions needed.

## Related ADRs

- **ADR-0001** - Structured Logging (logs exception details)
- **ADR-0004** - Type Hints (exceptions use type hints)

## References

### Implementation
- [Custom Exceptions Module](../../certus_ask/core/exceptions.py)
- [Error Response Schemas](../../certus_ask/schemas/errors.py)
- [Ingestion Router](../../certus_ask/routers/ingestion.py)
- [Datalake Router](../../certus_ask/routers/datalake.py)
- [Query Router](../../certus_ask/routers/query.py)

### Documentation
- [Type Hints & Error Handling Guide](../index.md#type-hints--error-handling)
- [API Error Reference](../index.md#error-responses)

### Standards
- [RFC 7231 - HTTP Status Codes](https://tools.ietf.org/html/rfc7231#section-6)
- [Problem Details for HTTP APIs](https://www.rfc-editor.org/rfc/rfc7807)
- [Python Exceptions Guide](https://docs.python.org/3/library/exceptions.html)

## Questions & Answers

**Q: When should I create a new exception type?**
A: When you have a distinct category of errors that need different handling or status codes.

**Q: Should I catch CertusException or specific types?**
A: Always catch specific types. `except CertusException` defeats the purpose.

**Q: How do I log exceptions?**
A: Include `exc_info=True` in logger call to include stack trace. Log error_code and details.

**Q: What if I have nested exceptions?**
A: Use `from exc` to chain them. Python preserves the full stack trace.

**Q: Can I re-raise exceptions?**
A: Yes, you can transform them. Catch specific exception, raise different one with `from exc`.

---

**Status**: Accepted and implemented
**Last Updated**: 2025-11-14
