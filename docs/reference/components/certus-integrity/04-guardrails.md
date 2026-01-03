# Guardrails Deep Dive

This guide provides detailed explanations of each guardrail in Certus Integrity, including algorithms, use cases, and configuration strategies.

## Overview

Guardrails are enforcement mechanisms that protect your services from abuse, resource exhaustion, and security threats. Each guardrail makes an **allow/deny/degrade** decision and records evidence for audit trails.

## Current Guardrails

### 1. Rate Limiting

**Purpose**: Prevent excessive requests from a single IP address to protect against DoS attacks and abuse.

#### Algorithm: Sliding Window

The rate limiter uses a sliding window algorithm with automatic cleanup:

```python
# Conceptual implementation
request_history = {
    "192.168.1.100": [timestamp1, timestamp2, timestamp3, ...]
}

def is_rate_limited(ip):
    now = time.time()
    history = request_history[ip]

    # Remove timestamps older than 60 seconds
    while history and history[0] < now - 60:
        history.pop(0)

    # Check if limit exceeded
    if len(history) >= RATE_LIMIT_PER_MIN:
        return True, 0  # Blocked

    # Record this request
    history.append(now)
    remaining = RATE_LIMIT_PER_MIN - len(history)
    return False, remaining  # Allowed
```

#### Configuration

```bash
INTEGRITY_RATE_LIMIT_PER_MIN=100  # Default: 100 requests/min
```

#### Behavior

**When limit NOT exceeded**:
```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1734262800
```

**When limit exceeded (enforcement mode)**:
```http
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1734262860
Retry-After: 60

{
  "detail": "rate_limit_exceeded"
}
```

**When limit exceeded (shadow mode)**:
```http
HTTP/1.1 200 OK
X-RateLimit-Limit: 100
X-RateLimit-Remaining: -1
X-RateLimit-Reset: 1734262860

[Normal response body - request was allowed]
```

#### Use Cases

**Scenario 1: Credential Stuffing Attack**

An attacker tries thousands of username/password combinations:
- Each attempt from same IP
- Rate limit kicks in after 100 attempts/minute
- Further attempts blocked with HTTP 429
- Evidence bundles record all attempts

**Scenario 2: Aggressive Web Scraper**

A bot scrapes your documentation site:
- Makes 500+ requests/minute
- Rate limit blocks after 100/min
- Legitimate users unaffected (different IPs)

**Scenario 3: Shared Corporate Proxy**

100 employees behind single IP:
- Each makes 2-3 requests/min
- Combined: 200-300 requests/min
- **Solution**: Whitelist corporate IP or increase limit

#### Choosing a Rate Limit

**Calculate based on legitimate traffic**:

1. Enable shadow mode for 1-2 weeks
2. Query 99th percentile of requests per IP:
   ```promql
   histogram_quantile(0.99,
     rate(certus_http_server_duration_milliseconds_bucket[1h])
   )
   ```
3. Set limit at 1.2x the 99th percentile

**Example**:
- P99 legitimate traffic: 80 requests/min
- Set limit: 80 × 1.2 = **96 requests/min**
- Round to: **100 requests/min**

### 2. Burst Protection

**Purpose**: Prevent rapid-fire attacks within short time windows that stay under per-minute limits.

#### Algorithm: Recent Request Count

```python
def is_burst_limited(ip):
    now = time.time()
    history = request_history[ip]

    # Count requests in last 10 seconds
    recent_count = sum(1 for ts in history if ts > now - 10)

    if recent_count >= BURST_LIMIT:
        return True  # Blocked

    return False  # Allowed
```

#### Configuration

```bash
INTEGRITY_BURST_LIMIT=20  # Default: 20 requests in 10 seconds
```

#### Relationship to Rate Limit

Burst limit should be ≤ `RATE_LIMIT_PER_MIN / 3` to catch attacks:

```bash
# Rate limit: 300/min (5/sec sustained)
INTEGRITY_RATE_LIMIT_PER_MIN=300

# Burst limit: 100 in 10 sec (10/sec burst)
INTEGRITY_BURST_LIMIT=100
```

This allows:
- **Sustained**: 5 requests/second over 60 seconds
- **Burst**: 10 requests/second for up to 10 seconds
- **Blocked**: 20 requests/second (script attack)

#### Use Cases

**Scenario 1: Login Brute Force**

Attacker tries 50 passwords in 5 seconds:
- Rate limit alone: Would allow first 100 attempts (60 seconds)
- Burst protection: Blocks after 20 attempts (10 seconds)
- **Result**: Attack stopped in 10 seconds instead of 60

**Scenario 2: API Key Enumeration**

Attacker tests 1000 API keys:
- Spaces requests at 1.5/second (under rate limit)
- Each batch of 20 keys takes 10 seconds
- Burst limit blocks the rapid batches
- **Result**: Attack detected and blocked

**Scenario 3: Legitimate Batch Processing**

Service makes 50 requests on startup:
- All requests in 2 seconds
- Burst limit blocks after 20
- **Solution**: Whitelist the service IP or use exponential backoff

### 3. IP Whitelisting

**Purpose**: Exempt trusted IP addresses or networks from all integrity checks.

#### Algorithm: IP/CIDR Matching

```python
import ipaddress

def is_whitelisted(ip):
    # Check individual IPs
    if ip in WHITELIST:
        return True

    # Check CIDR ranges
    ip_obj = ipaddress.ip_address(ip)
    for entry in WHITELIST:
        if "/" in entry:
            network = ipaddress.ip_network(entry, strict=False)
            if ip_obj in network:
                return True

    return False
```

#### Configuration

```bash
# Individual IPs
INTEGRITY_WHITELIST_IPS=127.0.0.1,192.168.1.100

# CIDR ranges
INTEGRITY_WHITELIST_IPS=172.18.0.0/16,10.0.0.0/8

# Mixed
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16,192.168.1.100
```

#### Common Whitelists

**Docker Compose**:
```bash
# Default Docker bridge network
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.18.0.0/16
```

**Kubernetes**:
```bash
# Cluster pod network
INTEGRITY_WHITELIST_IPS=10.0.0.0/8
```

**Load Balancers**:
```bash
# AWS ALB health checks
INTEGRITY_WHITELIST_IPS=127.0.0.1,172.31.0.0/16

# GCP Load Balancer
INTEGRITY_WHITELIST_IPS=127.0.0.1,130.211.0.0/22,35.191.0.0/16
```

#### Use Cases

**Scenario 1: Internal Services**

Certus-transform calls certus-ask 1000+ times/min:
- Would exceed rate limit
- Whitelist Docker network: `172.18.0.0/16`
- Internal traffic unlimited

**Scenario 2: Monitoring Systems**

Prometheus scrapes `/metrics` every 5 seconds:
- 12 requests/minute per instance
- 10 Prometheus instances = 120/min (over limit)
- Whitelist monitoring network

**Scenario 3: Admin Access**

Operations team needs unrestricted access:
- Whitelist admin IP: `203.0.113.5`
- Admins bypass all guardrails

### 4. Memory Leak Prevention

**Purpose**: Prevent long-running services from accumulating empty IP entries in memory.

#### Algorithm: Periodic Cleanup

```python
import time

last_cleanup = time.time()

def cleanup_if_needed():
    global last_cleanup
    now = time.time()

    # Clean up every 5 minutes
    if now - last_cleanup > 300:
        for ip in list(request_history.keys()):
            if not request_history[ip]:  # Empty deque
                del request_history[ip]

        last_cleanup = now
```

#### Configuration

**Not configurable** - runs automatically every 5 minutes.

#### Impact

**Before cleanup** (24 hours runtime):
- 10,000 unique IPs seen
- 9,500 no longer active
- Memory: ~500KB wasted

**After cleanup**:
- Only 500 active IPs tracked
- Memory: ~25KB used
- 95% memory reduction

## Planned Guardrails (Future)

### Graph Budget Enforcement (Phase 2)

**Purpose**: Prevent Neo4j queries from returning millions of nodes/edges.

**Algorithm**:
```python
def check_graph_budget(query_result):
    node_count = len(query_result.nodes)
    edge_count = len(query_result.edges)

    if node_count > MAX_NODES or edge_count > MAX_EDGES:
        return "degraded", {
            "action": "truncate_results",
            "nodes_returned": min(node_count, MAX_NODES),
            "edges_returned": min(edge_count, MAX_EDGES)
        }

    return "allowed", {}
```

**Configuration**:
```bash
INTEGRITY_GRAPH_MAX_NODES=10000
INTEGRITY_GRAPH_MAX_EDGES=50000
```

### PII Redaction (Phase 2)

**Purpose**: Automatically detect and redact sensitive data using Presidio.

**Algorithm**:
```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

def check_pii(text):
    analyzer = AnalyzerEngine()
    results = analyzer.analyze(text, language='en')

    if results:
        anonymizer = AnonymizerEngine()
        redacted = anonymizer.anonymize(text, results)
        return "degraded", {"redacted_text": redacted.text}

    return "allowed", {}
```

**Configuration**:
```bash
INTEGRITY_PII_REDACTION_ENABLED=true
INTEGRITY_PII_ENTITIES=PERSON,EMAIL,PHONE_NUMBER,SSN
```

### Context Budget (Phase 3)

**Purpose**: Limit LLM context window usage to control costs.

**Algorithm**:
```python
def check_context_budget(prompt, retrieved_context):
    total_tokens = count_tokens(prompt) + count_tokens(retrieved_context)

    if total_tokens > MAX_CONTEXT_TOKENS:
        # Truncate retrieved context
        truncated = truncate_to_tokens(retrieved_context,
                                       MAX_CONTEXT_TOKENS - count_tokens(prompt))
        return "degraded", {"truncated_context": truncated}

    return "allowed", {}
```

**Configuration**:
```bash
INTEGRITY_MAX_CONTEXT_TOKENS=8000
INTEGRITY_CONTEXT_TRUNCATION_STRATEGY=oldest_first
```

### Grounding Enforcement (Phase 3)

**Purpose**: Ensure LLM responses cite retrieved context.

**Algorithm**:
```python
def check_grounding(llm_response, retrieved_context):
    citations = extract_citations(llm_response)

    if not citations:
        return "denied", {"reason": "no_citations"}

    for citation in citations:
        if citation not in retrieved_context:
            return "denied", {"reason": "invalid_citation"}

    return "allowed", {}
```

**Configuration**:
```bash
INTEGRITY_REQUIRE_CITATIONS=true
INTEGRITY_MIN_CITATIONS=1
```

## Combining Guardrails

Multiple guardrails can trigger on the same request. The **most restrictive** decision wins:

```python
decisions = [
    "allowed",    # Rate limit check
    "denied",     # Burst limit check
    "allowed"     # Graph budget check
]

final_decision = "denied"  # Most restrictive wins
```

**Priority Order**:
1. `denied` - Request blocked
2. `degraded` - Request modified (e.g., truncated results)
3. `allowed` - Request passes

## Testing Guardrails

### Manual Testing

**Test Rate Limit**:
```bash
# Send 110 requests
for i in {1..110}; do
  curl -H "X-Forwarded-For: 10.0.0.50" \
       http://localhost:8000/v1/health
done
```

**Test Burst Protection**:
```bash
# Send 30 requests in 5 seconds
for i in {1..30}; do
  curl -H "X-Forwarded-For: 10.0.0.51" \
       http://localhost:8000/v1/health &
done
wait
```

**Test Whitelist**:
```bash
# Should never be blocked
for i in {1..200}; do
  curl http://localhost:8000/v1/health  # Uses 127.0.0.1
done
```

### Automated Testing

Use the provided verification script:

```bash
# Shadow mode (all should pass)
python scripts/verify_rate_limit.py shadow

# Enforcement mode (101-110 should be blocked)
python scripts/verify_rate_limit.py active
```

### Unit Tests

Run the full test suite:

```bash
# Rate limiting tests
pytest tests/unit/test_integrity/test_rate_limiting.py -v

# Middleware integration tests
pytest tests/unit/test_integrity/test_middleware.py -v
```

## Best Practices

### 1. Layer Guardrails

Use multiple guardrails for defense-in-depth:
```bash
INTEGRITY_RATE_LIMIT_PER_MIN=100     # Sustained abuse
INTEGRITY_BURST_LIMIT=20              # Rapid attacks
INTEGRITY_WHITELIST_IPS=...           # Trusted sources
```

### 2. Start Permissive, Tighten Gradually

```bash
# Week 1: Very permissive, shadow mode
INTEGRITY_SHADOW_MODE=true
INTEGRITY_RATE_LIMIT_PER_MIN=1000

# Week 2: Analyze, adjust to P99
INTEGRITY_RATE_LIMIT_PER_MIN=200

# Week 3: Enable enforcement
INTEGRITY_SHADOW_MODE=false
```

### 3. Document Exceptions

Keep a log of why IPs are whitelisted:
```bash
# Internal services (Docker network)
# Monitoring (Prometheus)
# Admin (ops team VPN: 203.0.113.5)
INTEGRITY_WHITELIST_IPS=172.18.0.0/16,10.0.1.0/24,203.0.113.5
```

### 4. Monitor for False Positives

Alert when whitelisted IPs would have been blocked:
```promql
rate(integrity_decisions_total{
  guardrail="rate_limit",
  client_ip="whitelisted_ip",
  decision="allowed"
}[5m]) > 2
```

### 5. Test Before Production

Always test in staging with production-like traffic:
1. Replay production traffic to staging
2. Enable guardrails in shadow mode
3. Analyze for false positives
4. Adjust configuration
5. Enable enforcement in production

## Next Steps

- **[Monitoring](05-monitoring.md)**: Set up Grafana dashboards to visualize guardrail effectiveness
- **[Troubleshooting](06-troubleshooting.md)**: Debug issues with guardrails
