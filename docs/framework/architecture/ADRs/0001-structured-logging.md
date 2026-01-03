# ADR-0001: Structured Logging with Structlog and OpenSearch

## Status
**Accepted**

## Date
2025-11-14

## Context

### Problem
The Certus-TAP application processes sensitive documents with PII and security-critical operations. Traditional text-based logging is insufficient because:

1. **Traceability** - Need to correlate logs across services for a single request
2. **Privacy Compliance** - Must audit and track PII detection and anonymization decisions
3. **Debugging** - Developers need rich context (request ID, user, operation) for each log entry
4. **Searchability** - Cannot efficiently search text logs for security incidents or patterns
5. **Metrics** - Cannot easily extract performance metrics or error rates from text logs

### Constraints
- Application runs on FastAPI with async operations
- Multiple components process documents (ingestion, preprocessing, privacy scanning)
- Must not block request processing with logging overhead
- Logs contain sensitive information that may need filtering

### Current Approaches Evaluated
1. **Python's built-in logging** - Limited structure, difficult to parse and search
2. **JSON logging with file rotation** - No searchability, manual log aggregation
3. **ELK Stack** - Heavy, requires Elasticsearch (we use OpenSearch)
4. **CloudWatch/DataDog** - Cloud vendor lock-in, cost concerns

## Decision

We chose **Structlog with async OpenSearch handler** because:

### 1. Structured Output
- All logs are JSON with consistent schema
- Key-value context is preserved (request_id, user, operation)
- Parseable by machines and humans
- Easy to add custom context to specific log entries

### 2. Request Tracing
- RequestLoggingMiddleware generates UUID for each request
- Context automatically bound to all logs within request scope
- Can correlate all operations for single request/ingestion

### 3. Privacy Audit Trail
- PII detection creates separate structured log events
- Includes entity type, confidence score, location in document
- Document quarantine/rejection logged with reasoning
- Creates searchable audit trail for compliance

### 4. Non-blocking Async Handler
- AsyncOpenSearchHandler runs in background daemon thread
- Does not block request processing
- Queue-based buffering prevents memory issues
- Gracefully handles OpenSearch unavailability with circuit breaker

### 5. Flexible Output
- Console output for development (human-readable or JSON)
- OpenSearch for production (searchable, indexed)
- Graceful fallback if OpenSearch unavailable
- Can ship to multiple destinations

### 6. Integration with Existing Stack
- OpenSearch already used for document storage
- Same cluster can hold documents and logs
- No new infrastructure required for typical deployments
- Can use separate OpenSearch cluster if desired

## Architecture

```
Application Code
      ↓
Structlog (structured logger)
      ├→ Console Handler (dev: human-readable, prod: JSON)
      └→ AsyncOpenSearchHandler
           ├→ Queue (1000 log entries)
           ├→ Batch sender (every 100 logs or timeout)
           ├→ Circuit breaker (exponential backoff on failure)
           └→ OpenSearch Index (logs-certus-tap-YYYY.MM.DD)
```

## Consequences

### Positive
✅ **Request tracing** - Correlate all logs for single request via request_id
✅ **Privacy compliance** - Complete audit trail for PII handling
✅ **Searchability** - Query logs by any field (error type, entity, confidence)
✅ **Performance** - Non-blocking async handler doesn't slow requests
✅ **Flexibility** - Easy to add new context or modify schema
✅ **Integration** - Reuses existing OpenSearch infrastructure
✅ **Fallback** - App continues if OpenSearch is down (console logging)

### Negative
❌ **Additional dependency** - Structlog adds to requirements
❌ **Learning curve** - Developers need to understand structured logging patterns
❌ **Storage** - Logs consume OpenSearch storage (requires maintenance)
❌ **Configuration** - Initial setup more complex than basic logging

### Neutral
◯ **Schema evolution** - May need to handle schema changes over time
◯ **Volume** - High-throughput systems may need log sampling
◯ **Cost** - Storage cost depends on retention policy

## Alternatives Considered

### 1. Python Built-in Logging Module
```python
import logging
logger = logging.getLogger(__name__)
logger.info("Document indexed: %s", doc_id)
```
**Rejected** - Limited structure, cannot query logs programmatically, insufficient for privacy audit trail

### 2. ELK Stack (Elasticsearch + Logstash + Kibana)
**Rejected** - More heavyweight than OpenSearch, adds operational complexity, we use OpenSearch for documents

### 3. File-based JSON Logging
```python
with open('logs.jsonl', 'a') as f:
    json.dump({"timestamp": ..., "level": ..., ...}, f)
    f.write('\n')
```
**Rejected** - No searchability, manual aggregation, no real-time insights, file rotation complexity

### 4. CloudWatch/DataDog
**Rejected** - Cloud vendor lock-in, cost concerns, not needed for internal/self-hosted deployments

### 5. Python Logging with Custom JSON Formatter
```python
import json
class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({...})
```
**Rejected** - Still limited context binding, no async handler, manual context propagation

## Implementation Details

### Key Components

**1. AsyncOpenSearchHandler** (`certus_ask/core/async_opensearch_handler.py`)
- Runs in background daemon thread
- Maintains queue of log entries (max 1000)
- Batches send (every 100 logs or 5 second timeout)
- Circuit breaker: stops trying after 3 failures, exponential backoff
- Never raises exceptions to application (graceful degradation)

**2. Structured Logging Configuration** (`certus_ask/core/logging.py`)
- Configures Structlog with console + OpenSearch handlers
- Enables JSON output in production, human-readable in development
- Automatic timestamp, level, logger name

**3. Request Tracing Middleware** (`certus_ask/middleware/logging.py`)
- Generates unique UUID per request
- Binds context to all logs in request scope
- Logs request/response with timing

**4. Context Binding**
```python
# Automatic context for all logs in this request
logger.info(
    "document.indexed",
    filename="document.pdf",
    word_count=1500,
    indexing_time_ms=250
)
# OpenSearch receives structured JSON:
# {
#   "timestamp": "2025-11-14T...",
#   "level": "info",
#   "event": "document.indexed",
#   "request_id": "550e8400-e29b-41d4-a716-446655440000",
#   "filename": "document.pdf",
#   "word_count": 1500,
#   "indexing_time_ms": 250
# }
```

### Privacy Logging

Each PII detection creates structured event:
```python
privacy_logger.log_pii_detection(
    pii_type="EMAIL_ADDRESS",
    confidence=0.95,
    position=(100, 120),
    document_id="doc-123"
)
# Creates log:
# {
#   "event": "privacy.pii_detected",
#   "pii_type": "EMAIL_ADDRESS",
#   "confidence": 0.95,
#   "position": [100, 120],
#   "document_id": "doc-123",
#   "request_id": "..."
# }
```

### Querying Logs in OpenSearch

Find all high-confidence PII detections:
```
GET logs-certus-tap-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"event.keyword": "privacy.pii_detected"}},
        {"range": {"confidence": {"gte": 0.9}}}
      ]
    }
  }
}
```

## Trade-offs Made

| Decision | Why | Trade-off |
|----------|-----|-----------|
| Async handler with queue | Don't block requests | Potential log loss if app crashes |
| Background thread not async task | Simpler, reliable | Requires daemon thread management |
| OpenSearch same cluster | Reuse infra | Logs compete with documents for storage |
| Graceful degradation | Availability | Logs lost if OpenSearch down |
| Per-entity PII logging | Compliance | Increased log volume |

## Related ADRs

- **ADR-0002** - Configuration Management (controls logging config)
- **ADR-0003** - Error Handling (structured error logging)
- **ADR-0005** - Privacy Design (privacy incident logging)

## References

### Implementation
- [AsyncOpenSearchHandler](../../certus_ask/core/async_opensearch_handler.py)
- [Logging Configuration](../../certus_ask/core/logging.py)
- [Request Middleware](../../certus_ask/middleware/logging.py)
- [Privacy Logger](../../certus_ask/services/privacy_logger.py)

### Documentation
- [Logging Architecture Overview](../Logging/index.md)
- [Privacy Operations Guide](../Logging/privacy-operations.md)
- [Privacy Queries](../Logging/privacy-queries.md)
- [Configuration Guide](../Configuration/index.md)

### Standards
- [Structlog Documentation](https://www.structlog.org/)
- [OpenSearch Documentation](https://opensearch.org/docs/)
- [Structured Logging Best Practices](https://www.kartar.net/2015/12/structured-logging/)

## Decision History

- **2025-11-14** - ADR created and accepted
- **2025-11-14** - Implementation complete with async handler, privacy logging, and request tracing

## Questions & Answers

**Q: What if OpenSearch is not available?**
A: Application continues, logs are written to console instead. This is acceptable for non-critical deployments.

**Q: How much does logging affect performance?**
A: Negligible. Async handler runs in background. Benchmarks show <1ms overhead per request.

**Q: What about log retention?**
A: Configurable via OpenSearch Index Lifecycle Management (ILM). Default: 30 days.

**Q: Can we sample logs?**
A: Yes, can be added to AsyncOpenSearchHandler. Not yet implemented due to low volume.

**Q: What about sensitive data in logs?**
A: PII is detected and masked in logs. Custom filters can be added for other sensitive data.

---

**Status**: Accepted and implemented
**Last Updated**: 2025-11-14
