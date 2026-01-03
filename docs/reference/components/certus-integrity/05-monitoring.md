# Monitoring and Observability

This guide covers how to monitor Certus Integrity using metrics, traces, logs, and Grafana dashboards.

## Observability Stack

Certus Integrity integrates with the full observability stack:

```
┌─────────────────┐
│  Your Service   │
│  + Integrity    │
└────────┬────────┘
         │ OTLP/HTTP
         ▼
┌─────────────────┐
│ OTEL Collector  │
│  Port 4318      │
└─────┬───┬───┬───┘
      │   │   │
  ┌───┘   │   └────┐
  │       │        │
  ▼       ▼        ▼
┌────┐ ┌────┐ ┌──────────┐
│Prom│ │Open│ │  Stdout  │
│    │ │Srch│ │   Logs   │
└─┬──┘ └─┬──┘ └──────────┘
  │      │
  ▼      ▼
┌────────────────┐
│    Grafana     │
│  Port 3001     │
└────────────────┘
```

**Services**:
- **OTEL Collector**: Receives telemetry, routes to backends
- **VictoriaMetrics**: Prometheus-compatible metrics storage
- **OpenSearch**: Trace and log storage
- **Grafana**: Visualization and alerting

## Metrics

### Available Metrics

#### 1. `integrity_decisions_total` (Counter)

Total number of integrity decisions made.

**Labels**:
- `decision`: `allowed`, `denied`, `degraded`
- `guardrail`: `rate_limit`, `burst_protection`, etc.
- `reason`: `pass_through`, `rate_limit_exceeded`, etc.
- `shadow_mode`: `true`, `false`
- `service`: `certus-ask`, `certus-trust`, etc.

**Example Queries**:

```promql
# Total decisions per second
rate(integrity_decisions_total[5m])

# Denial rate
rate(integrity_decisions_total{decision="denied"}[5m])

# Shadow violations
rate(integrity_decisions_total{
  decision="allowed",
  shadow_mode="true",
  reason="rate_limit_exceeded"
}[5m])

# Breakdown by guardrail
sum by(guardrail) (rate(integrity_decisions_total[5m]))
```

#### 2. `integrity_check_duration_seconds` (Histogram)

Duration of integrity checks (latency overhead).

**Labels**:
- `guardrail`: `all`, `rate_limit`, etc.

**Buckets**: 0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0

**Example Queries**:

```promql
# p95 latency of integrity checks
histogram_quantile(0.95,
  rate(integrity_check_duration_seconds_bucket[5m])
)

# p99 latency
histogram_quantile(0.99,
  rate(integrity_check_duration_seconds_bucket[5m])
)

# Average duration
rate(integrity_check_duration_seconds_sum[5m]) /
rate(integrity_check_duration_seconds_count[5m])
```

#### 3. `integrity_rate_limit_violations_total` (Counter)

Total number of rate limit violations (regardless of shadow mode).

**Labels**:
- `client_ip`: IP address or `unknown`
- `shadow_mode`: `true`, `false`

**Example Queries**:

```promql
# Violations per IP
sum by(client_ip) (rate(integrity_rate_limit_violations_total[5m]))

# Top 10 offending IPs
topk(10,
  sum by(client_ip) (integrity_rate_limit_violations_total)
)

# Violation rate spike (for alerting)
rate(integrity_rate_limit_violations_total[5m]) > 1
```

#### 4. HTTP Metrics (from FastAPI instrumentation)

**`certus_http_server_duration_milliseconds_bucket`** (Histogram):
- Labels: `http_method`, `http_target`, `http_status_code`, `service`

**`certus_http_server_active_requests`** (Gauge):
- Current number of active requests

**Example Queries**:

```promql
# Request rate by endpoint
sum by(http_target) (rate(certus_http_server_duration_milliseconds_count[5m]))

# p95 response time
histogram_quantile(0.95,
  sum by(le) (rate(certus_http_server_duration_milliseconds_bucket[5m]))
)

# 429 error rate
rate(certus_http_server_duration_milliseconds_count{http_status_code="429"}[5m])
```

### Querying Metrics

**Via VictoriaMetrics API**:
```bash
# Instant query
curl "http://localhost:8428/api/v1/query?query=integrity_decisions_total"

# Range query (last hour)
curl "http://localhost:8428/api/v1/query_range?query=rate(integrity_decisions_total[5m])&start=$(date -u -d '1 hour ago' +%s)&end=$(date +%s)&step=60"

# Available labels
curl "http://localhost:8428/api/v1/labels"
```

**Via Grafana Explore**:
1. Navigate to http://localhost:3001/explore
2. Select "Prometheus" datasource
3. Enter PromQL query
4. Click "Run query"

## Traces

### Trace Structure

Every request creates an integrity span:

```
Trace ID: 4bf92f3577b34da6a3ce929d0e0e4736
│
├─ integrity.request (2ms)
│  ├─ Attributes:
│  │  ├─ integrity.decision: allowed
│  │  ├─ integrity.guardrail: rate_limit
│  │  ├─ integrity.reason: pass_through
│  │  ├─ integrity.shadow_mode: true
│  │  ├─ integrity.client_ip: 192.168.1.100
│  │  └─ integrity.shadow_violation: false
│  │
│  └─ Child Spans:
│     ├─ fastapi.request (1500ms)
│     │  └─ neo4j.query (800ms)
│     │     └─ llm.generate (600ms)
```

### Span Attributes

**Standard Attributes**:
- `integrity.decision`: `allowed`, `denied`, `degraded`
- `integrity.guardrail`: `rate_limit`, `burst_protection`, etc.
- `integrity.reason`: `pass_through`, `rate_limit_exceeded`, etc.
- `integrity.shadow_mode`: `true`, `false`
- `integrity.client_ip`: Source IP address

**Shadow Violation Attributes** (only when violation occurs in shadow mode):
- `integrity.shadow_violation`: `True`

### Querying Traces

**Via OpenSearch Dashboards** (http://localhost:5601):

1. Navigate to "Discover"
2. Select `traces-otel-*` index pattern
3. Search for traces with specific attributes:
   ```
   attributes.integrity.decision: "denied"
   attributes.integrity.shadow_mode: "true"
   ```

**Via OpenSearch API**:
```bash
# Find all denied traces
curl -X POST "http://localhost:9200/traces-otel-*/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "match": {
        "attributes.integrity.decision": "denied"
      }
    }
  }'
```

### Trace Correlation

**Link Evidence to Traces**:

Every evidence bundle includes `trace_id` and `span_id`:

```json
{
  "decision": {
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "span_id": "00f067aa0ba902b7"
  }
}
```

**Find trace for evidence**:
```bash
# Extract trace_id from evidence
TRACE_ID=$(jq -r '.decision.trace_id' /tmp/evidence/dec_abc123.json)

# Query OpenSearch
curl "http://localhost:9200/traces-otel-*/_search?q=traceId:$TRACE_ID"
```

## Logs

### Log Structure

Logs are structured JSON (when `enable_json_logs=True`):

```json
{
  "event": "integrity_decision",
  "timestamp": "2025-12-15T10:30:00.123456Z",
  "level": "info",
  "decision": "denied",
  "guardrail": "rate_limit",
  "reason": "rate_limit_exceeded",
  "client_ip": "192.168.1.100",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "span_id": "00f067aa0ba902b7",
  "service": "certus-ask"
}
```

### Log Events

**`integrity_decision`**: Every allow/deny decision
**`evidence_generation_failed`**: Evidence signing failed
**`signing_service_unavailable`**: certus-trust unreachable
**`evidence_save_failed`**: Disk write error
**`integrity_cleanup`**: Memory cleanup triggered

### Querying Logs

**Via Docker Logs**:
```bash
# All logs from service
docker logs ask-certus-backend

# Follow logs in real-time
docker logs -f ask-certus-backend

# Filter for integrity events
docker logs ask-certus-backend | grep integrity_decision

# Parse JSON with jq
docker logs ask-certus-backend | grep integrity_decision | jq
```

**Via OpenSearch** (if `SEND_LOGS_TO_OPENSEARCH=true`):

```bash
# Search for denied decisions
curl -X POST "http://localhost:9200/logs-otel-*/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "bool": {
        "must": [
          {"match": {"event": "integrity_decision"}},
          {"match": {"decision": "denied"}}
        ]
      }
    }
  }'
```

## Grafana Dashboards

### Pre-configured Dashboard

The integrity dashboard is located at:
```
docker/grafana/provisioning/dashboards/integrity.json
```

**Access**: http://localhost:3001/dashboards → "Certus Dashboards"

### Creating Custom Dashboards

#### Panel 1: Decision Rate

**Visualization**: Time series
**Query**:
```promql
sum by(decision) (rate(integrity_decisions_total[5m]))
```

**Configuration**:
- Legend: `{{decision}}`
- Y-axis: Decisions/sec
- Colors: Green (allowed), Red (denied), Yellow (degraded)

#### Panel 2: Denial Rate

**Visualization**: Stat
**Query**:
```promql
sum(rate(integrity_decisions_total{decision="denied"}[5m]))
```

**Configuration**:
- Unit: req/sec
- Thresholds:
  - Green: 0-0.1
  - Yellow: 0.1-1
  - Red: >1

#### Panel 3: Shadow Violations

**Visualization**: Time series
**Query**:
```promql
sum by(reason) (
  rate(integrity_decisions_total{
    shadow_mode="true",
    reason!="pass_through"
  }[5m])
)
```

**Purpose**: Show what would be blocked if enforcement was enabled.

#### Panel 4: Top Violating IPs

**Visualization**: Table
**Query**:
```promql
topk(10,
  sum by(client_ip) (integrity_rate_limit_violations_total)
)
```

**Columns**:
- Client IP
- Total Violations
- Violation Rate (5m)

#### Panel 5: Integrity Check Latency

**Visualization**: Time series
**Query**:
```promql
histogram_quantile(0.95,
  rate(integrity_check_duration_seconds_bucket[5m])
)
```

**Configuration**:
- Unit: seconds
- Y-axis: Log scale
- Threshold: >0.1s (red)

#### Panel 6: 429 Error Rate

**Visualization**: Stat
**Query**:
```promql
sum(rate(certus_http_server_duration_milliseconds_count{http_status_code="429"}[5m]))
```

**Configuration**:
- Unit: errors/sec
- Color: Red
- Alert threshold: >5/sec

### Dashboard Variables

Create variables for dynamic filtering:

**Variable: `service`**
- Type: Query
- Query: `label_values(integrity_decisions_total, service)`
- Multi-value: Yes

**Variable: `time_range`**
- Type: Interval
- Options: 5m, 15m, 1h, 6h, 24h
- Default: 5m

**Use in queries**:
```promql
sum by(decision) (
  rate(integrity_decisions_total{service="$service"}[$time_range])
)
```

## Alerts

### Recommended Alerts

#### 1. High Denial Rate

**Query**:
```promql
sum(rate(integrity_decisions_total{decision="denied"}[5m])) > 5
```

**Threshold**: >5 denials/sec
**Severity**: Warning
**Action**: Investigate if attack or misconfigured limit

#### 2. Shadow Violation Spike

**Query**:
```promql
sum(rate(integrity_decisions_total{
  shadow_mode="true",
  reason="rate_limit_exceeded"
}[5m])) > 10
```

**Threshold**: >10 violations/sec
**Severity**: Info
**Action**: Consider adjusting rate limit before enabling enforcement

#### 3. Integrity Check Latency

**Query**:
```promql
histogram_quantile(0.99,
  rate(integrity_check_duration_seconds_bucket[5m])
) > 0.1
```

**Threshold**: p99 >100ms
**Severity**: Warning
**Action**: Performance issue, investigate memory cleanup

#### 4. Evidence Signing Failures

**Query**:
```promql
sum(rate(logs{event="evidence_generation_failed"}[5m])) > 0.1
```

**Threshold**: >0.1 failures/sec
**Severity**: Critical
**Action**: certus-trust service down, check health

#### 5. Repeated Violator

**Query**:
```promql
max by(client_ip) (integrity_rate_limit_violations_total) > 1000
```

**Threshold**: >1000 total violations from single IP
**Severity**: Warning
**Action**: Potential attack, consider IP ban

### Configuring Alerts in Grafana

**1. Create Alert Rule**:
- Grafana → Alerting → New Alert Rule
- Name: "High Integrity Denial Rate"
- Query: (see above)
- Condition: Alert when above 5
- Evaluate every: 1m
- For: 5m (sustained for 5 minutes)

**2. Create Notification Channel**:
- Grafana → Alerting → Notification Channels
- Type: Slack, PagerDuty, Email, etc.
- Configure webhook/credentials

**3. Add to Dashboard**:
- Edit panel → Alert tab
- Create alert
- Set thresholds and notification channel

## Metrics-Driven Operations

### Shadow Mode Analysis

**Goal**: Determine optimal rate limit before enabling enforcement.

**Process**:

1. **Collect baseline** (1-2 weeks in shadow mode):
   ```promql
   # Total requests per IP (over 2 weeks)
   sum by(client_ip) (
     increase(certus_http_server_duration_milliseconds_count[2w])
   )
   ```

2. **Calculate P99 per-minute rate**:
   ```promql
   # Requests per minute per IP
   sum by(client_ip) (
     rate(certus_http_server_duration_milliseconds_count[1m])
   ) * 60
   ```

3. **Identify outliers**:
   ```promql
   # IPs exceeding 100/min
   sum by(client_ip) (
     rate(certus_http_server_duration_milliseconds_count[1m]) * 60
   ) > 100
   ```

4. **Decide**:
   - Legitimate users? Whitelist or increase limit
   - Bots/attackers? Keep limit, enable enforcement

### Enforcement Rollout

**Goal**: Enable enforcement with minimal false positives.

**Process**:

1. **Enable enforcement during low-traffic period**:
   ```bash
   INTEGRITY_SHADOW_MODE=false
   docker compose restart ask-certus-backend
   ```

2. **Monitor denial rate**:
   ```promql
   sum(rate(integrity_decisions_total{decision="denied"}[5m]))
   ```

3. **Identify false positives** (legitimate users blocked):
   ```promql
   # IPs with denials
   topk(10,
     sum by(client_ip) (integrity_decisions_total{decision="denied"})
   )
   ```

4. **Adjust**:
   - Whitelist false positives
   - OR increase rate limit
   - Redeploy

5. **Repeat** until denial rate stabilizes

### Performance Monitoring

**Goal**: Ensure integrity checks don't add significant latency.

**Metrics**:

```promql
# Integrity overhead as % of total request time
100 * (
  rate(integrity_check_duration_seconds_sum[5m]) /
  rate(certus_http_server_duration_milliseconds_sum[5m])
)
```

**Acceptable**: <5% overhead
**Warning**: 5-10% overhead
**Critical**: >10% overhead

**If overhead too high**:
- Check for memory leaks (cleanup running?)
- Reduce whitelist size (CIDR instead of individual IPs)
- Consider distributed rate limiter (Redis-based)

## Next Steps

- **[Troubleshooting](06-troubleshooting.md)**: Debug common monitoring issues
- Set up custom Grafana dashboards for your use case
- Configure PagerDuty/Slack alerts for critical issues
