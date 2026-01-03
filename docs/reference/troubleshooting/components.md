# Troubleshooting Guide

This guide helps you diagnose and fix common issues with Certus Integrity.

## Quick Diagnostics

### Health Check Checklist

Run these commands to verify your setup:

```bash
# 1. Check service is running
docker ps | grep -E 'ask-certus-backend|otel-collector|victoriametrics|grafana'

# 2. Check integrity middleware is active (look for rate limit headers)
curl -v http://localhost:8000/v1/health 2>&1 | grep X-RateLimit

# 3. Check metrics are being collected
curl http://localhost:8428/api/v1/labels | jq

# 4. Check OTEL collector is receiving data
curl http://localhost:8889/metrics | grep integrity

# 5. Check trust service is accessible
curl http://localhost:8057/health

# 6. Check evidence directory
ls -lh /tmp/evidence/
```

**Expected Results**:
- ✅ All services running
- ✅ Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`
- ✅ Labels include: `decision`, `guardrail`, `shadow_mode`
- ✅ Metrics: `integrity_decisions_total`, `integrity_check_duration_seconds_bucket`
- ✅ Trust service: `{"status": "healthy"}`
- ✅ Evidence files: `dec_*.json`

## Common Issues

### Issue 1: No Rate Limit Headers

**Symptoms**:
```bash
curl -v http://localhost:8000/v1/health
# No X-RateLimit-* headers in response
```

**Possible Causes**:

#### A. Middleware not configured

**Check**: Look for `configure_observability()` in your app:
```bash
grep -r "configure_observability" certus_ask/main.py
```

**Solution**: Add to your FastAPI app factory:
```python
from certus_integrity.telemetry import configure_observability

configure_observability(
    app=app,
    service_name="my-service",
    log_level="INFO",
    enable_json_logs=True,
    otel_endpoint="http://otel-collector:4318"
)
```

#### B. Middleware added before routes

**Problem**: `configure_observability()` must be called **after** all routes are defined.

**Solution**: Move to end of `create_app()`:
```python
def create_app():
    app = FastAPI()

    # Define routes first
    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Configure observability LAST
    configure_observability(app=app, ...)

    return app
```

#### C. Environment variables not loaded

**Check**:
```bash
docker exec ask-certus-backend env | grep INTEGRITY
```

**Solution**: Ensure environment variables are set in `docker-compose.yml`:
```yaml
environment:
  - INTEGRITY_SHADOW_MODE=true
  - INTEGRITY_RATE_LIMIT_PER_MIN=100
```

### Issue 2: Metrics Not Appearing in VictoriaMetrics

**Symptoms**:
```bash
curl http://localhost:8428/api/v1/query?query=integrity_decisions_total
# Returns: {"data":{"resultType":"vector","result":[]}}
```

**Diagnosis Steps**:

#### Step 1: Check OTEL Collector

```bash
# Check collector is running
docker ps | grep otel-collector

# Check collector is exporting Prometheus metrics
curl http://localhost:8889/metrics | grep integrity
```

**If no metrics**: OTEL collector not receiving data from app.

**Solution**: Check `OTEL_EXPORTER_OTLP_ENDPOINT` in app:
```bash
docker exec ask-certus-backend env | grep OTEL_EXPORTER_OTLP_ENDPOINT
# Should be: http://otel-collector:4318
```

#### Step 2: Check VictoriaMetrics is Scraping

```bash
# Check VictoriaMetrics targets
curl http://localhost:8428/api/v1/targets

# Check Prometheus config
cat docker/prometheus.yaml
```

**Expected**:
```yaml
scrape_configs:
  - job_name: 'otel-collector'
    scrape_interval: 10s
    static_configs:
      - targets: ['otel-collector:8889']
```

**Solution**: Ensure `otel-collector:8889` is reachable from VictoriaMetrics container:
```bash
docker exec victoriametrics wget -O- http://otel-collector:8889/metrics
```

#### Step 3: Generate Traffic

Metrics only appear after requests are made:

```bash
# Generate 10 requests
for i in {1..10}; do curl http://localhost:8000/v1/health; done

# Wait 15 seconds (scrape interval)
sleep 15

# Check again
curl http://localhost:8428/api/v1/query?query=integrity_decisions_total
```

### Issue 3: All Requests Blocked (HTTP 429)

**Symptoms**:
```bash
curl http://localhost:8000/v1/health
# HTTP/1.1 429 Too Many Requests
```

**Even first request is blocked.**

**Diagnosis**:

#### Check Rate Limit Configuration

```bash
docker exec ask-certus-backend env | grep INTEGRITY_RATE_LIMIT_PER_MIN
```

**Possible Issues**:

**A. Rate limit set to 0**:
```bash
INTEGRITY_RATE_LIMIT_PER_MIN=0  # Blocks all requests
```

**Solution**: Set to reasonable value:
```bash
INTEGRITY_RATE_LIMIT_PER_MIN=100
docker compose restart ask-certus-backend
```

**B. Client IP not whitelisted**:

If accessing via proxy/load balancer, IP might not be localhost:

```bash
# Check logs for client IP
docker logs ask-certus-backend | grep client_ip
```

**Solution**: Add IP to whitelist:
```bash
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16,YOUR_IP
```

**C. Enforcement mode enabled too early**:

```bash
INTEGRITY_SHADOW_MODE=false  # Enforcement mode
```

**Solution**: Switch to shadow mode first:
```bash
INTEGRITY_SHADOW_MODE=true
docker compose restart ask-certus-backend
```

### Issue 4: Evidence Bundles Not Signed

**Symptoms**:

Evidence files have `verification_status: "failed"`:
```bash
cat /tmp/evidence/dec_*.json | jq '.verification_status'
# Output: "failed"
```

**Diagnosis**:

#### Check Trust Service Health

```bash
curl http://localhost:8057/health
```

**If unreachable**:

```bash
# Check trust service is running
docker ps | grep certus-trust

# Check logs for errors
docker logs certus-trust

# Restart if needed
docker compose restart certus-trust
```

#### Check Trust Service URL

```bash
docker exec ask-certus-backend env | grep TRUST_BASE_URL
# Should match trust service endpoint
```

**Solution**: Update `TRUST_BASE_URL` to match trust service:
```bash
# Docker Compose
TRUST_BASE_URL=http://certus-trust:8000

# Kubernetes
TRUST_BASE_URL=http://certus-trust.default.svc.cluster.local:8000
```

#### Check Network Connectivity

```bash
# From app container, try reaching trust service
docker exec ask-certus-backend curl http://certus-trust:8000/health
```

**If fails**: Ensure both services are on same Docker network:
```yaml
services:
  ask-certus-backend:
    networks:
      - certus-net

  certus-trust:
    networks:
      - certus-net

networks:
  certus-net:
    external: true
```

### Issue 5: Shadow Mode Not Working

**Symptoms**:

Requests are being blocked even with `INTEGRITY_SHADOW_MODE=true`.

**Diagnosis**:

#### Check Environment Variable Value

```bash
docker exec ask-certus-backend env | grep INTEGRITY_SHADOW_MODE
```

**Common Mistake**: Setting to `1` instead of `"true"`:
```bash
# WRONG
INTEGRITY_SHADOW_MODE=1

# CORRECT
INTEGRITY_SHADOW_MODE=true
```

**Solution**: Use string `"true"` or `"false"`:
```yaml
environment:
  - INTEGRITY_SHADOW_MODE=true  # Not 1 or True
```

#### Check Logs for Shadow Violations

```bash
docker logs ask-certus-backend | grep shadow_violation
```

**Expected**: Should see logs with `shadow_mode: true` and `decision: allowed`.

### Issue 6: High Latency After Adding Integrity

**Symptoms**:

Response times increased significantly after enabling Certus Integrity.

**Diagnosis**:

#### Measure Integrity Overhead

```bash
# Check p99 latency of integrity checks
curl "http://localhost:8428/api/v1/query?query=histogram_quantile(0.99, rate(integrity_check_duration_seconds_bucket[5m]))"
```

**Acceptable**: <10ms
**Warning**: 10-50ms
**Critical**: >50ms

#### Check for Memory Leak

```bash
# Check number of tracked IPs
docker exec ask-certus-backend python -c "
from certus_integrity.middleware import IntegrityMiddleware
# Access internal state (requires adding debug endpoint)
"

# Or check memory usage
docker stats ask-certus-backend
```

**If memory constantly growing**: Cleanup not running properly.

**Solution**: Restart service (cleanup runs every 5 minutes):
```bash
docker compose restart ask-certus-backend
```

#### Check Whitelist Size

Large whitelists can slow down IP matching:

```bash
docker exec ask-certus-backend env | grep INTEGRITY_WHITELIST_IPS
```

**If >100 entries**: Use CIDR ranges instead:
```bash
# SLOW (100 individual IPs)
INTEGRITY_WHITELIST_IPS=192.168.1.1,192.168.1.2,...,192.168.1.100

# FAST (single CIDR)
INTEGRITY_WHITELIST_IPS=192.168.1.0/24
```

### Issue 7: Grafana Shows No Data

**Symptoms**:

Grafana dashboards are empty or show "No data".

**Diagnosis**:

#### Check Datasource Connection

1. Navigate to Grafana: http://localhost:3001
2. Go to Configuration → Data Sources → Prometheus
3. Click "Test"

**Expected**: "Data source is working"

**If fails**:
- Check VictoriaMetrics URL: `http://victoriametrics:8428`
- Ensure Grafana and VictoriaMetrics on same network

#### Check Metrics Exist

```bash
# Query VictoriaMetrics directly
curl "http://localhost:8428/api/v1/query?query=integrity_decisions_total"
```

**If no data**: See [Issue 2: Metrics Not Appearing](#issue-2-metrics-not-appearing-in-victoriametrics)

#### Check Query Syntax

In Grafana Explore, try simple query first:
```promql
integrity_decisions_total
```

**If works**: Issue is with dashboard query syntax.
**If fails**: Issue is with datasource.

#### Check Time Range

Ensure time range covers period when requests were made:
- Grafana → Top right → Time picker
- Select "Last 5 minutes" or "Last 1 hour"

### Issue 8: Evidence Files Not Created

**Symptoms**:

`/tmp/evidence/` directory is empty.

**Diagnosis**:

#### Check Directory Exists and is Writable

```bash
docker exec ask-certus-backend ls -ld /tmp/evidence
```

**If doesn't exist**:
```bash
docker exec ask-certus-backend mkdir -p /tmp/evidence
```

**If not writable**:
```bash
docker exec ask-certus-backend chmod 777 /tmp/evidence
```

#### Check Logs for Write Errors

```bash
docker logs ask-certus-backend | grep evidence_save_failed
```

**If errors**: Disk space issue or permission problem.

#### Generate Evidence by Triggering Decision

```bash
# Trigger rate limit to generate evidence
for i in {1..101}; do
  curl -H "X-Forwarded-For: 10.0.0.99" http://localhost:8000/v1/health
done

# Check evidence created
ls -lh /tmp/evidence/
```

## Performance Tuning

### Reduce Integrity Overhead

**1. Optimize Whitelist**:
```bash
# Use CIDR instead of individual IPs
INTEGRITY_WHITELIST_IPS=172.18.0.0/16  # Instead of 172.18.0.1,172.18.0.2,...
```

**2. Disable Rate Limiting for Internal Endpoints**:

Only apply integrity to public endpoints (future feature).

**3. Increase Cleanup Interval** (requires code change):

Currently hardcoded to 5 minutes. For high-traffic systems, consider decreasing to 1 minute.

### Reduce Evidence Storage

**1. Disable Signing for High-Traffic Endpoints**:

Configure evidence generation to skip low-risk decisions (future feature).

**2. Rotate Evidence Files**:

```bash
# Add to cron
0 0 * * * find /tmp/evidence -mtime +7 -delete  # Delete after 7 days
```

**3. Store Evidence in S3** (future feature):

Instead of local disk, upload to object storage.

## Debugging Tips

### Enable Debug Logging

**Temporary** (requires restart):
```bash
# In docker-compose.yml or .env
LOG_LEVEL=DEBUG
docker compose restart ask-certus-backend
```

**Check logs**:
```bash
docker logs ask-certus-backend | grep integrity
```

### Inspect Request Headers

```bash
curl -v http://localhost:8000/v1/health 2>&1 | grep -E "X-RateLimit|X-Forwarded-For"
```

### Test Specific IP

```bash
# Simulate request from specific IP
curl -H "X-Forwarded-For: 192.168.1.100" http://localhost:8000/v1/health
```

### Inspect Evidence Bundle

```bash
# Pretty-print latest evidence
ls -t /tmp/evidence/ | head -1 | xargs -I{} cat /tmp/evidence/{} | jq
```

### Check OpenTelemetry Spans

```bash
# Query OpenSearch for integrity spans
curl -X POST "http://localhost:9200/traces-otel-*/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "match": {
        "name": "integrity.request"
      }
    },
    "size": 10,
    "sort": [{"@timestamp": "desc"}]
  }' | jq
```

## Getting Help

### Collect Diagnostic Information

When reporting issues, include:

```bash
# 1. Version info
git rev-parse HEAD
docker --version

# 2. Service status
docker ps

# 3. Environment configuration
docker exec ask-certus-backend env | grep INTEGRITY

# 4. Recent logs (last 100 lines)
docker logs --tail 100 ask-certus-backend

# 5. Metrics snapshot
curl http://localhost:8428/api/v1/query?query=integrity_decisions_total

# 6. Evidence sample
ls -lh /tmp/evidence/ | head -5
cat /tmp/evidence/$(ls -t /tmp/evidence/ | head -1) | jq
```

### Check for Known Issues

Search the Certus repository issues:
```bash
# Example GitHub search
https://github.com/your-org/certus/issues?q=is%3Aissue+integrity
```

### Test in Isolation

Create minimal reproduction:

```python
# test_integrity_minimal.py
from fastapi import FastAPI
from certus_integrity.telemetry import configure_observability

app = FastAPI()

@app.get("/health")
def health():
    return {"status": "ok"}

configure_observability(
    app=app,
    service_name="test",
    log_level="DEBUG",
    enable_json_logs=False,
    otel_endpoint="http://otel-collector:4318"
)

# Run: uvicorn test_integrity_minimal:app --port 8001
```

Test:
```bash
curl -v http://localhost:8001/health
```

If works: Issue is with your service integration.
If fails: Issue is with Certus Integrity setup.

## Next Steps

- **[Overview](01-overview.md)**: Refresh understanding of architecture
- **[Configuration](03-configuration.md)**: Review configuration settings
- **[Monitoring](05-monitoring.md)**: Set up better observability to catch issues early
