# Getting Started with Certus Integrity

This guide will walk you through adding Certus Integrity to your FastAPI service in minutes.

## Prerequisites

- Python 3.11+
- FastAPI application
- Access to certus-trust service (for evidence signing)
- OpenTelemetry Collector (for observability)

## Quick Start

### Step 1: Install Dependencies

Certus Integrity is included in the main Certus project. If you're building a new service, ensure your `pyproject.toml` includes:

```toml
[project]
dependencies = [
    "fastapi>=0.104.0",
    "opentelemetry-api>=1.20.0",
    "opentelemetry-sdk>=1.20.0",
    "opentelemetry-instrumentation-fastapi>=0.41b0",
    "structlog>=23.1.0",
]
```

### Step 2: Add Integrity to Your App

Update your FastAPI app factory (e.g., `main.py`):

```python
from fastapi import FastAPI
from certus_integrity.telemetry import configure_observability

def create_app() -> FastAPI:
    app = FastAPI(title="My Service")

    # Add your routes
    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Configure observability + integrity (do this LAST)
    configure_observability(
        app=app,
        service_name="my-service",
        log_level="INFO",
        enable_json_logs=True,
        otel_endpoint="http://otel-collector:4318"
    )

    return app

app = create_app()
```

That's it! The `configure_observability()` function:
1. Sets up OpenTelemetry traces and metrics
2. Configures structured logging
3. **Automatically adds IntegrityMiddleware** to your app

### Step 3: Configure Environment Variables

Create a `.env` file or add to your `docker-compose.yml`:

```bash
# Integrity Configuration
INTEGRITY_SHADOW_MODE=true              # Start in shadow mode
INTEGRITY_RATE_LIMIT_PER_MIN=100        # 100 requests/min per IP
INTEGRITY_BURST_LIMIT=20                # 20 requests in 10 seconds
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16

# Trust Service
TRUST_BASE_URL=http://certus-trust:8000

# OpenTelemetry
OTEL_SERVICE_NAME=my-service
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

### Step 4: Start Your Service

```bash
# Using uvicorn directly
uvicorn main:app --host 0.0.0.0 --port 8000

# Or with Docker Compose
docker compose up my-service
```

### Step 5: Verify It's Working

**1. Check Health Endpoint**
```bash
curl http://localhost:8000/health
```

You should see:
```json
{"status": "ok"}
```

**2. Check Rate Limit Headers**

Make a few requests and inspect the response headers:

```bash
curl -v http://localhost:8000/health
```

Look for:
```
< X-RateLimit-Limit: 100
< X-RateLimit-Remaining: 99
< X-RateLimit-Reset: 1734262800
```

**3. Verify Metrics**

Query VictoriaMetrics to see if metrics are being collected:

```bash
curl http://localhost:8428/api/v1/query?query=integrity_decisions_total
```

**4. Check Evidence Bundles**

By default, evidence bundles are saved to `/tmp/evidence/`:

```bash
ls -lh /tmp/evidence/
cat /tmp/evidence/dec_*.json | jq
```

## Example: Complete Integration

Here's a complete example showing how certus_ask integrates Certus Integrity:

```python
# certus_ask/main.py
from fastapi import FastAPI, Request
from certus_integrity.telemetry import configure_observability
import structlog

logger = structlog.get_logger()

def create_app() -> FastAPI:
    app = FastAPI(
        title="Certus Ask",
        version="1.0.0"
    )

    # Your routes
    @app.get("/v1/health")
    def health():
        return {"status": "healthy"}

    @app.post("/v1/{workspace_id}/ask")
    async def ask(workspace_id: str, request: Request):
        data = await request.json()
        question = data.get("question")

        logger.info("processing_question",
                   workspace_id=workspace_id,
                   question_length=len(question))

        # Your RAG logic here
        answer = "Sample answer"

        return {"answer": answer}

    # Configure observability (MUST be last)
    configure_observability(
        app=app,
        service_name="certus-ask",
        log_level="INFO",
        enable_json_logs=True,
        otel_endpoint="http://otel-collector:4318"
    )

    return app

app = create_app()
```

## Testing Shadow Mode

Shadow mode allows you to test guardrails without blocking requests.

### Simulate Rate Limit Violation

Use the provided verification script:

```bash
python scripts/verify_rate_limit.py shadow
```

This sends 110 requests to test the rate limit. In shadow mode:
- All 110 requests should **succeed** (200 OK)
- Metrics should show violations with `shadow_mode: true`
- Logs should contain `shadow_violation: True` spans

Check the logs:

```bash
docker logs ask-certus-backend | grep shadow_violation
```

You should see:
```json
{
  "event": "integrity_decision",
  "decision": "allowed",
  "guardrail": "rate_limit",
  "reason": "rate_limit_exceeded",
  "shadow_mode": true,
  "trace_id": "abc123..."
}
```

## Enabling Enforcement Mode

Once you've validated shadow mode metrics, enable enforcement:

### 1. Update Configuration

```bash
# In .env or docker-compose.yml
INTEGRITY_SHADOW_MODE=false
```

### 2. Restart Service

```bash
docker compose restart my-service
```

### 3. Test Enforcement

```bash
python scripts/verify_rate_limit.py active
```

Now you should see:
- First 100 requests: **200 OK**
- Requests 101-110: **429 Too Many Requests**

Response headers for blocked requests:
```
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1734262860
Retry-After: 60

{
  "detail": "rate_limit_exceeded"
}
```

## Docker Compose Example

Complete `docker-compose.yml` service definition:

```yaml
services:
  my-service:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: my-service
    ports:
      - "8000:8000"
    environment:
      # Integrity
      - INTEGRITY_SHADOW_MODE=true
      - INTEGRITY_RATE_LIMIT_PER_MIN=100
      - INTEGRITY_BURST_LIMIT=20
      - INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16

      # Trust Service
      - TRUST_BASE_URL=http://certus-trust:8000

      # OpenTelemetry
      - OTEL_SERVICE_NAME=my-service
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
    depends_on:
      - certus-trust
      - otel-collector
    networks:
      - certus-net

networks:
  certus-net:
    external: true
```

## Common Issues

### Issue: Metrics Not Appearing

**Cause**: OpenTelemetry Collector not reachable

**Solution**: Verify collector is running and accessible:
```bash
docker ps | grep otel-collector
curl http://localhost:8889/metrics  # Should show Prometheus metrics
```

### Issue: Evidence Bundles Not Signed

**Cause**: certus-trust service unreachable

**Solution**: Check trust service health:
```bash
curl http://localhost:8057/health
```

Evidence bundles will be created with `verification_status: "failed"` if signing fails. The service continues to operate normally.

### Issue: All Requests Blocked Immediately

**Cause**: Whitelist not configured correctly

**Solution**: Add your client IP to the whitelist:
```bash
# Find your client IP
docker logs my-service | grep client_ip

# Add to whitelist
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16,YOUR_IP
```

## Next Steps

- **[Configuration Guide](03-configuration.md)**: Fine-tune rate limits and guardrails
- **[Guardrails Deep Dive](04-guardrails.md)**: Understand how each guardrail works
- **[Monitoring](05-monitoring.md)**: Set up Grafana dashboards and alerts
- **[Troubleshooting](06-troubleshooting.md)**: Debug common issues
