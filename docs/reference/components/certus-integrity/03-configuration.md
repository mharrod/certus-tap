# Configuration Guide

This guide covers all configuration options for Certus Integrity, including environment variables, runtime behavior, and best practices.

## Environment Variables

All Certus Integrity configuration is done via environment variables. This allows runtime configuration without code changes.

### Core Integrity Settings

#### `INTEGRITY_SHADOW_MODE`

**Type**: Boolean (string: `"true"` or `"false"`)
**Default**: `"true"`
**Description**: Controls whether violations are enforced or just logged.

- `"true"`: Violations logged but requests allowed (shadow mode)
- `"false"`: Violations block requests with HTTP 429 (enforcement mode)

**Recommendation**: Start in shadow mode, collect baseline metrics for 1-2 weeks, then enable enforcement.

**Example**:
```bash
# Shadow mode (testing)
INTEGRITY_SHADOW_MODE=true

# Enforcement mode (production)
INTEGRITY_SHADOW_MODE=false
```

#### `INTEGRITY_RATE_LIMIT_PER_MIN`

**Type**: Integer
**Default**: `100`
**Description**: Maximum number of requests allowed per IP address per minute.

**How It Works**: Uses a sliding window algorithm that removes timestamps older than 60 seconds. If the count of remaining timestamps exceeds this limit, the request is rate-limited.

**Choosing a Value**:
- **Light traffic**: 50-100 requests/min
- **Moderate traffic**: 100-300 requests/min
- **Heavy traffic**: 500-1000 requests/min
- **Disable**: Set to `0` to disable rate limiting

**Example**:
```bash
# Conservative limit
INTEGRITY_RATE_LIMIT_PER_MIN=50

# Liberal limit for high-traffic APIs
INTEGRITY_RATE_LIMIT_PER_MIN=500

# Disable rate limiting
INTEGRITY_RATE_LIMIT_PER_MIN=0
```

#### `INTEGRITY_BURST_LIMIT`

**Type**: Integer
**Default**: `20`
**Description**: Maximum number of requests allowed within a 10-second window.

**Purpose**: Prevents rapid-fire attacks that stay under the per-minute limit by spacing requests.

**Relationship to Rate Limit**: Should be ≤ `RATE_LIMIT_PER_MIN / 3` to catch burst attacks.

**Example**:
```bash
# Rate limit: 300/min, Burst: 100 in 10s
INTEGRITY_RATE_LIMIT_PER_MIN=300
INTEGRITY_BURST_LIMIT=100

# Strict burst protection
INTEGRITY_RATE_LIMIT_PER_MIN=100
INTEGRITY_BURST_LIMIT=10
```

#### `INTEGRITY_WHITELIST_IPS`

**Type**: Comma-separated list of IPs or CIDR ranges
**Default**: `"127.0.0.1,172.18.0.0/16"`
**Description**: IP addresses or CIDR ranges that bypass all integrity checks.

**Supports**:
- Individual IPs: `127.0.0.1`, `192.168.1.100`
- CIDR ranges: `172.18.0.0/16`, `10.0.0.0/8`

**Common Use Cases**:
- Internal services (Docker networks, Kubernetes pods)
- Health check endpoints (load balancers)
- Admin access (trusted IPs)

**Example**:
```bash
# Localhost + Docker network
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16

# Add internal services
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16,10.0.1.0/24

# Production load balancer + admin IPs
INTEGRITY_WHITELIST_IPS=192.168.1.10,203.0.113.5
```

### Trust Service Configuration

#### `TRUST_BASE_URL`

**Type**: URL
**Default**: `"http://certus-trust:8000"`
**Description**: Base URL for the certus-trust signing service.

**Example**:
```bash
# Local development
TRUST_BASE_URL=http://localhost:8057

# Docker Compose
TRUST_BASE_URL=http://certus-trust:8000

# Kubernetes
TRUST_BASE_URL=http://certus-trust.default.svc.cluster.local:8000
```

**Fallback Behavior**: If trust service is unreachable, evidence bundles are created with `verification_status: "failed"`. Service continues to operate normally.

### OpenTelemetry Configuration

#### `OTEL_SERVICE_NAME`

**Type**: String
**Default**: None (required)
**Description**: Name of your service in traces and metrics.

**Naming Convention**: Use kebab-case: `certus-ask`, `certus-transform`, `my-service`

#### `OTEL_EXPORTER_OTLP_ENDPOINT`

**Type**: URL
**Default**: `"http://otel-collector:4318"`
**Description**: OpenTelemetry Collector endpoint for OTLP over HTTP.

**Ports**:
- `4317`: OTLP over gRPC
- `4318`: OTLP over HTTP (recommended)

#### `OTEL_EXPORTER_OTLP_PROTOCOL`

**Type**: String
**Default**: `"http/protobuf"`
**Options**: `"http/protobuf"`, `"grpc"`

**Example Complete OTEL Configuration**:
```bash
OTEL_SERVICE_NAME=my-service
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
```

### Logging Configuration

These are passed to `configure_observability()` in code, not environment variables:

```python
configure_observability(
    app=app,
    service_name="my-service",
    log_level="INFO",           # DEBUG, INFO, WARNING, ERROR
    enable_json_logs=True,      # True for production, False for development
    otel_endpoint="http://otel-collector:4318"
)
```

## Configuration Patterns

### Development Environment

```bash
# .env.development
INTEGRITY_SHADOW_MODE=true
INTEGRITY_RATE_LIMIT_PER_MIN=1000        # High limit for testing
INTEGRITY_BURST_LIMIT=100
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16

TRUST_BASE_URL=http://localhost:8057
OTEL_SERVICE_NAME=my-service-dev
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

**Python Code**:
```python
configure_observability(
    app=app,
    service_name="my-service-dev",
    log_level="DEBUG",
    enable_json_logs=False,     # Human-readable logs
    otel_endpoint="http://localhost:4318"
)
```

### Staging Environment

```bash
# .env.staging
INTEGRITY_SHADOW_MODE=false              # Enforcement mode
INTEGRITY_RATE_LIMIT_PER_MIN=200         # Moderate limit
INTEGRITY_BURST_LIMIT=30
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16,10.0.0.0/8

TRUST_BASE_URL=http://certus-trust:8000
OTEL_SERVICE_NAME=my-service-staging
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
```

**Python Code**:
```python
configure_observability(
    app=app,
    service_name="my-service-staging",
    log_level="INFO",
    enable_json_logs=True,      # JSON logs for aggregation
    otel_endpoint="http://otel-collector:4318"
)
```

### Production Environment

```bash
# .env.production
INTEGRITY_SHADOW_MODE=false              # Enforcement mode
INTEGRITY_RATE_LIMIT_PER_MIN=100         # Conservative limit
INTEGRITY_BURST_LIMIT=20
INTEGRITY_WHITELIST_IPS=10.0.0.0/8       # Internal network only

TRUST_BASE_URL=http://certus-trust.production.svc.cluster.local:8000
OTEL_SERVICE_NAME=my-service
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector.observability.svc.cluster.local:4318
```

**Python Code**:
```python
configure_observability(
    app=app,
    service_name="my-service",
    log_level="WARNING",        # Reduce log volume
    enable_json_logs=True,
    otel_endpoint="http://otel-collector.observability.svc.cluster.local:4318"
)
```

## Docker Compose Configuration

Complete service definition with all integrity settings:

```yaml
services:
  my-service:
    build: .
    container_name: my-service
    ports:
      - "8000:8000"
    environment:
      # === Integrity Configuration ===
      - INTEGRITY_SHADOW_MODE=${INTEGRITY_SHADOW_MODE:-true}
      - INTEGRITY_RATE_LIMIT_PER_MIN=${INTEGRITY_RATE_LIMIT_PER_MIN:-100}
      - INTEGRITY_BURST_LIMIT=${INTEGRITY_BURST_LIMIT:-20}
      - INTEGRITY_WHITELIST_IPS=${INTEGRITY_WHITELIST_IPS:-127.0.0.1,172.18.0.0/16}

      # === Trust Service ===
      - TRUST_BASE_URL=http://certus-trust:8000

      # === OpenTelemetry ===
      - OTEL_SERVICE_NAME=my-service
      - OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4318
      - OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf

      # === Logging ===
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - LOG_JSON_OUTPUT=${LOG_JSON_OUTPUT:-true}

    depends_on:
      - certus-trust
      - otel-collector

    networks:
      - certus-net

networks:
  certus-net:
    external: true
```

Use with `.env` file:
```bash
# .env
INTEGRITY_SHADOW_MODE=true
INTEGRITY_RATE_LIMIT_PER_MIN=200
INTEGRITY_BURST_LIMIT=30
LOG_LEVEL=DEBUG
LOG_JSON_OUTPUT=false
```

## Kubernetes Configuration

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: my-service-config
  namespace: default
data:
  INTEGRITY_SHADOW_MODE: "false"
  INTEGRITY_RATE_LIMIT_PER_MIN: "100"
  INTEGRITY_BURST_LIMIT: "20"
  INTEGRITY_WHITELIST_IPS: "10.0.0.0/8"
  TRUST_BASE_URL: "http://certus-trust.default.svc.cluster.local:8000"
  OTEL_SERVICE_NAME: "my-service"
  OTEL_EXPORTER_OTLP_ENDPOINT: "http://otel-collector.observability.svc.cluster.local:4318"
  OTEL_EXPORTER_OTLP_PROTOCOL: "http/protobuf"
```

### Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-service
spec:
  replicas: 3
  template:
    spec:
      containers:
      - name: my-service
        image: my-service:latest
        envFrom:
        - configMapRef:
            name: my-service-config
        ports:
        - containerPort: 8000
```

## Runtime Configuration Changes

### Changing Rate Limits

**Without Restart** (not currently supported):
Rate limits are loaded at startup and cannot be changed without restart.

**With Restart**:
1. Update environment variable in `.env` or ConfigMap
2. Restart service:
   ```bash
   # Docker Compose
   docker compose restart my-service

   # Kubernetes
   kubectl rollout restart deployment/my-service
   ```

### Transitioning from Shadow to Enforcement

**Step 1**: Collect baseline metrics (1-2 weeks in shadow mode)

```bash
# Check violation rate in shadow mode
curl "http://localhost:8428/api/v1/query?query=rate(integrity_rate_limit_violations_total{shadow_mode=\"true\"}[1h])"
```

**Step 2**: Analyze patterns

- What IPs are hitting limits?
- Are they legitimate users or attacks?
- Should limits be adjusted or IPs whitelisted?

**Step 3**: Update whitelist if needed

```bash
# Add legitimate high-traffic IPs to whitelist
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16,192.168.1.50
```

**Step 4**: Enable enforcement during low-traffic period

```bash
INTEGRITY_SHADOW_MODE=false
docker compose restart my-service
```

**Step 5**: Monitor closely

```bash
# Watch for increased 429 errors
watch -n 5 'curl "http://localhost:8428/api/v1/query?query=rate(integrity_decisions_total{decision=\"denied\"}[5m])"'
```

## Best Practices

### 1. Start Conservative

Begin with stricter limits in shadow mode:
```bash
INTEGRITY_SHADOW_MODE=true
INTEGRITY_RATE_LIMIT_PER_MIN=50
INTEGRITY_BURST_LIMIT=10
```

Loosen after analyzing real traffic patterns.

### 2. Whitelist Internal Services

Always whitelist internal networks to prevent self-DoS:
```bash
# Docker
INTEGRITY_WHITELIST_IPS=172.18.0.0/16

# Kubernetes
INTEGRITY_WHITELIST_IPS=10.0.0.0/8
```

### 3. Use Different Limits per Environment

- **Development**: Very high limits or disabled (`RATE_LIMIT=0`)
- **Staging**: Production-like limits in shadow mode
- **Production**: Tuned limits in enforcement mode

### 4. Document Your Configuration

Keep a README with your chosen limits and reasoning:
```markdown
## Rate Limit Configuration

- **Rate Limit**: 100 req/min (chosen based on 99th percentile of legitimate traffic: 80 req/min)
- **Burst Limit**: 20 (prevents script attacks)
- **Whitelist**: Internal network (10.0.0.0/8) + monitoring systems
```

### 5. Monitor and Adjust

Set up alerts for:
- High violation rates (potential attack or misconfigured limit)
- High latency of integrity checks (performance issue)
- Evidence signing failures (trust service down)

See [Monitoring Guide](05-monitoring.md) for details.

## Troubleshooting Configuration

### Issue: Configuration Not Taking Effect

**Cause**: Old environment variables cached

**Solution**: Force restart with clean environment
```bash
docker compose down
docker compose up -d
```

### Issue: All Requests Whitelisted

**Cause**: Whitelist CIDR too broad

**Solution**: Narrow CIDR range
```bash
# Too broad (all private IPs)
INTEGRITY_WHITELIST_IPS=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16

# Better (specific Docker network)
INTEGRITY_WHITELIST_IPS=172.18.0.0/16
```

### Issue: Legitimate Users Getting Blocked

**Cause**: Rate limit too strict for shared IP scenarios (corporate proxy, NAT)

**Solution**: Increase limit or whitelist the IP
```bash
# Option 1: Increase limit
INTEGRITY_RATE_LIMIT_PER_MIN=300

# Option 2: Whitelist the proxy IP
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16,203.0.113.10
```

## Next Steps

- **[Guardrails Deep Dive](04-guardrails.md)**: Understand how each guardrail works
- **[Monitoring](05-monitoring.md)**: Set up Grafana dashboards and alerts
- **[Troubleshooting](06-troubleshooting.md)**: Debug common issues
