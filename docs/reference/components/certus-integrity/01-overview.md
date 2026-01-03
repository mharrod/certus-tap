# Certus Integrity: Overview

## What is Certus Integrity?

Certus Integrity is a runtime enforcement and observability layer that provides security guardrails, audit trails, and compliance evidence for the Certus platform. It acts as a protective layer that monitors, controls, and records all requests flowing through your Certus services.

## Why Use Certus Integrity?

### Security and Protection
- **Rate Limiting**: Protect your services from abuse and DoS attacks with per-IP rate limits
- **Burst Protection**: Prevent rapid-fire attacks within short time windows
- **IP Whitelisting**: Exempt trusted internal services from enforcement

### Compliance and Auditability
- **Evidence Generation**: Every enforcement decision is recorded with cryptographic signatures
- **Transparency Logging**: Integration with Sigstore Rekor for tamper-proof audit trails
- **Trace Correlation**: Link enforcement decisions to application traces for full request visibility

### Observability
- **OpenTelemetry Integration**: Native support for traces, metrics, and logs
- **Grafana Dashboards**: Pre-built visualizations for monitoring guardrail health
- **Structured Logging**: JSON-formatted logs with trace correlation

### Safe Rollout
- **Shadow Mode**: Test guardrails in production without blocking requests
- **Gradual Enforcement**: Collect baseline metrics before enabling enforcement
- **Runtime Configuration**: Adjust thresholds without code changes

## Architecture

Certus Integrity is implemented as a **FastAPI middleware library** that embeds directly into your services:

```
┌─────────────────────────────────────────────────────┐
│                  Client Request                      │
└──────────────────┬──────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────┐
│            IntegrityMiddleware                       │
│  ┌──────────────────────────────────────────────┐   │
│  │ 1. Check IP Whitelist                        │   │
│  │ 2. Check Rate Limit (sliding window)         │   │
│  │ 3. Check Burst Protection                    │   │
│  │ 4. Record Decision + Emit Telemetry          │   │
│  │ 5. Generate Evidence Bundle                  │   │
│  └──────────────────────────────────────────────┘   │
└──────────────────┬──────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
        ▼                     ▼
   [Allow]               [Deny 429]
        │
        ▼
┌─────────────────────────────────────────────────────┐
│            Application Logic                         │
│  (FastAPI routes, business logic, database)         │
└─────────────────────────────────────────────────────┘
```

### Key Components

1. **IntegrityMiddleware** (`certus_integrity/middleware.py`)
   - Core enforcement engine
   - Intercepts all incoming HTTP requests
   - Makes allow/deny decisions based on configured guardrails

2. **EvidenceGenerator** (`certus_integrity/evidence.py`)
   - Creates cryptographically signed audit trails
   - Integrates with certus-trust for signing
   - Persists evidence bundles to disk

3. **Telemetry Configuration** (`certus_integrity/telemetry.py`)
   - One-function setup for OpenTelemetry
   - Configures traces, metrics, and logs
   - Automatically adds IntegrityMiddleware to your app

## Current Guardrails

### 1. Rate Limiting
Prevents excessive requests from a single IP address using a sliding window algorithm.

- **Default**: 100 requests per minute per IP
- **Algorithm**: Sliding window with automatic cleanup
- **Response**: HTTP 429 with retry headers

### 2. Burst Protection
Blocks rapid-fire attacks within short time windows.

- **Default**: 20 requests in 10 seconds
- **Use Case**: Prevent script-based attacks that stay under per-minute limits
- **Implementation**: Independent check alongside rate limiting

### 3. IP Whitelisting
Exempts trusted IP addresses or CIDR ranges from all guardrails.

- **Supports**: Individual IPs (`127.0.0.1`) and CIDR ranges (`172.18.0.0/16`)
- **Default**: Localhost and Docker internal networks
- **Use Case**: Allow internal services unlimited access

## Planned Guardrails (Future)

- **Graph Budget Enforcement**: Limit Neo4j query complexity to prevent graph explosions
- **PII Redaction**: Automatically detect and redact sensitive data using Presidio
- **Context Budget**: Limit LLM context window usage to control costs
- **Grounding Enforcement**: Ensure LLM responses cite retrieved context

## Integration Points

Certus Integrity integrates with:

1. **FastAPI Applications** - Middleware-based integration
2. **Certus Trust** - Cryptographic signing of evidence bundles
3. **OpenTelemetry Collector** - Metrics, traces, and logs export
4. **VictoriaMetrics/Prometheus** - Time-series metrics storage
5. **Grafana** - Visualization and alerting
6. **OpenSearch** - Trace and log storage

## Evidence Bundles

Every enforcement decision generates a signed evidence bundle:

```json
{
  "evidence_id": "evi_abc123",
  "timestamp": "2025-12-15T10:30:00Z",
  "decision": {
    "decision_id": "dec_abc123",
    "decision": "denied",
    "guardrail": "rate_limit",
    "reason": "rate_limit_exceeded",
    "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
    "metadata": {
      "client_ip": "192.168.1.100",
      "requests_in_window": 101,
      "limit": 100
    }
  },
  "content_hash": "sha256:abc123...",
  "signature": "mock-signature-abc123",
  "transparency_log_entry": {
    "uuid": "entry-id",
    "index": 42
  },
  "verification_status": "signed"
}
```

These bundles provide:
- **Non-repudiation**: Cryptographic proof of when decisions were made
- **Transparency**: Publicly verifiable via Rekor transparency log
- **Compliance**: Audit-ready evidence for regulatory requirements

## Shadow Mode vs Enforcement Mode

### Shadow Mode (Default)
- Violations are **logged but NOT enforced**
- Requests that would be blocked are **allowed through**
- Perfect for testing and baseline collection
- Metrics tagged with `shadow_mode: true`

### Enforcement Mode
- Violations **block requests** with HTTP 429
- Production-ready enforcement
- Recommended after analyzing shadow mode metrics

## Next Steps

- **[Getting Started](02-getting-started.md)**: Add Certus Integrity to your service
- **[Configuration](03-configuration.md)**: Configure rate limits and guardrails
- **[Monitoring](05-monitoring.md)**: Set up Grafana dashboards and alerts
