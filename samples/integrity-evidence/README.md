# Certus Integrity Evidence Bundle Samples

This directory contains realistic sample evidence bundles demonstrating how Certus Integrity middleware detects and blocks malicious traffic patterns.

## Scenario: Automated Scraper Attack (December 15, 2025)

These 75 evidence bundles represent a real-world attack scenario where automated scrapers attempt to overwhelm the Certus Ask service, and the integrity middleware successfully detects and blocks the malicious traffic while allowing legitimate users to continue accessing the system.

### Timeline

**14:25:00 - 14:31:00**: Normal operations
**14:30:00 - 14:31:30**: Attack begins (subtle ramp-up)
**14:32:00 - 14:34:30**: Rate limiting blocks sustained attack
**14:35:00 - 14:35:10**: Burst attack detected and blocked
**14:36:00 - 14:38:00**: Distributed attack from multiple IPs
**14:40:00+**: System returns to normal operations

## Evidence Bundle Categories

### 1. Normal Traffic (15 bundles)
**Files**: `01_normal_*.json`

Legitimate users accessing various endpoints with normal request patterns.

- **IPs**: 192.168.1.100-192.168.1.115
- **Endpoints**: `/v1/default/ask`, `/v1/health`, `/v1/workspaces`
- **Decision**: `allowed`
- **Reason**: `within_rate_limit`
- **Request Rates**: 5-40 requests/minute (well under the 100/min limit)
- **Timestamps**: Spread across 6 minutes (14:25:00 to 14:31:00)

### 2. Attack Beginning (5 bundles)
**Files**: `02_attack_begin_*.json`

Scraper starting slowly to avoid immediate detection.

- **IP**: 203.0.113.50
- **Endpoint**: `/v1/default/ask`
- **Decision**: `allowed` (still within limits initially)
- **Requests**: 60-95 requests/minute (approaching the 100/min limit)
- **Timestamps**: 14:30:00 to 14:31:30 (90 seconds)

### 3. Rate Limit Blocks (20 bundles)
**Files**: `03_rate_limit_denied_*.json`

The attack accelerates and exceeds the rate limit threshold.

- **IP**: 203.0.113.50 (same attacker)
- **Endpoint**: `/v1/default/ask`
- **Decision**: `denied`
- **Reason**: `rate_limit_exceeded`
- **Requests**: 101-210 requests/minute (exceeding 100/min limit)
- **Timestamps**: Concentrated in 2.5 minutes (14:32:00 to 14:34:30)
- **Metadata**: Includes `retry_after: 60` seconds

### 4. Burst Attack (10 bundles)
**Files**: `04_burst_attack_*.json`

A different attacker tries a burst strategy (many requests in short time).

- **IP**: 198.51.100.25
- **Endpoint**: `/v1/default/query`
- **Decision**: `denied`
- **Reason**: `burst_limit_exceeded`
- **Burst Limit**: 20 requests per 10 seconds
- **Actual**: 21-30 requests in 10 seconds
- **Timestamps**: All within 10 seconds (14:35:00 to 14:35:10)

### 5. Distributed Attack (15 bundles)
**Files**: `05_distributed_attack_*.json`

Attackers rotate through multiple IP addresses to evade detection.

- **IPs**: 45.76.132.10-45.76.132.25 (rotating)
- **Endpoint**: `/v1/default/ask`
- **Decision**: Mixed (`allowed` for first requests, `denied` once rate limited)
- **Pattern**: Each IP starts allowed, then gets rate limited
- **Timestamps**: 14:36:00 to 14:38:00 (2 minutes)

### 6. Post-Attack Normal (10 bundles)
**Files**: `06_post_attack_normal_*.json`

System returns to normal after attacks are blocked.

- **IPs**: Various legitimate IPs (192.168.x.x, 10.0.0.x, 172.16.0.x)
- **Endpoints**: Mixed (`/v1/default/ask`, `/v1/health`, `/v1/workspaces`)
- **Decision**: `allowed`
- **Timestamps**: 14:40:00 onwards

## Evidence Bundle Structure

Each evidence bundle follows the `SignedEvidence` schema from `certus_integrity/evidence.py`:

```json
{
  "evidence_id": "uuid-v4",
  "timestamp": "2025-12-20T17:31:32.948173Z",
  "decision": {
    "decision_id": "uuid-v4",
    "timestamp": "2025-12-15T14:25:00Z",
    "trace_id": "32-char-hex-opentelemetry-trace-id",
    "span_id": "16-char-hex-opentelemetry-span-id",
    "service": "certus-ask",
    "decision": "allowed|denied|degraded",
    "reason": "within_rate_limit|rate_limit_exceeded|burst_limit_exceeded",
    "guardrail": "rate_limit",
    "metadata": {
      "client_ip": "x.x.x.x",
      "endpoint": "/v1/endpoint",
      "shadow_mode": false,
      "requests_in_window": 50,
      "limit": 100,
      "burst_limit": 20,
      "duration_ms": 12.5
    }
  },
  "content_hash": "sha256-hash-of-decision-content",
  "signature": "base64-encoded-signature",
  "signer_certificate": "PEM-encoded-certificate",
  "transparency_log_entry": {
    "uuid": "rekor-entry-uuid",
    "log_index": 12345678,
    "log_id": "rekor-log-id",
    "integrated_time": 1234567890,
    "inclusion_proof": {
      "tree_size": 100000000,
      "root_hash": "merkle-tree-root-hash",
      "log_index": 12345678,
      "hashes": ["hash1", "hash2", "..."]
    }
  },
  "verification_status": "signed"
}
```

### Key Fields

- **evidence_id**: Unique identifier for the evidence bundle
- **timestamp**: When the evidence bundle was created (UTC)
- **decision**: The full integrity decision object
  - **decision_id**: Unique identifier for this decision
  - **trace_id**: OpenTelemetry trace ID for distributed tracing
  - **span_id**: OpenTelemetry span ID
  - **service**: Which service made the decision (always "certus-ask")
  - **decision**: `allowed`, `denied`, or `degraded`
  - **reason**: Human-readable explanation
  - **guardrail**: Which protection mechanism triggered (`rate_limit`, `graph_budget`, etc.)
  - **metadata**: Contextual data (IP, endpoint, request counts, etc.)
- **content_hash**: SHA256 hash of the canonical JSON decision (for integrity verification)
- **signature**: Cryptographic signature from Certus Trust (mock in samples)
- **signer_certificate**: X.509 certificate of the signer (mock in samples)
- **transparency_log_entry**: Rekor transparency log proof (mock in samples)
- **verification_status**: `signed`, `unsigned`, `failed`, or `offline`

## Use Cases

### Tutorial Examples

1. **Verifying Evidence Integrity**: Use `content_hash` to verify decision hasn't been tampered with
2. **Audit Trail Analysis**: Track decisions over time using `timestamp` and `decision_id`
3. **Attack Pattern Detection**: Analyze metadata to identify malicious patterns
4. **Rate Limit Tuning**: Study normal vs attack traffic to optimize limits
5. **Distributed Tracing**: Use `trace_id` and `span_id` to correlate with application logs

### Analysis Queries

**Count decisions by outcome:**
```bash
grep -h '"decision":' *.json | sort | uniq -c
```

**Find all denied requests:**
```bash
grep -l '"decision": "denied"' *.json
```

**Extract all attacking IPs:**
```bash
jq -r '.decision.metadata.client_ip' 03_rate_limit_denied_*.json | sort -u
```

**Get timeline of attack:**
```bash
jq -r '"\(.decision.timestamp) \(.decision.client_ip) \(.decision.decision)"' *.json | sort
```

## Generating Custom Samples

The `generate_samples.py` script can be modified to create different scenarios:

```bash
python3 generate_samples.py
```

Edit the script to:
- Change IP ranges
- Adjust rate limits
- Modify timestamps
- Add new attack patterns
- Include different guardrails (e.g., `graph_budget`)

## Integration with Certus Components

These evidence bundles are generated by:
- **certus_integrity/middleware.py**: Makes the enforcement decision
- **certus_integrity/evidence.py**: Creates and signs the evidence bundle
- **certus-trust**: Signs the content hash and provides transparency log proof

They can be consumed by:
- **certus-assurance**: Verify integrity and provenance
- **certus-ask**: Include in audit logs
- **Analytics systems**: Detect patterns and anomalies
- **Compliance systems**: Provide tamper-proof audit trail

## Notes

- All signatures and certificates in these samples are **mock data** for tutorial purposes
- Real production evidence would have valid cryptographic signatures from Certus Trust
- Transparency log entries would reference actual Rekor/Sigstore infrastructure
- Content hashes are real SHA256 hashes of the decision content
- Timestamps reflect the December 15, 2025 attack scenario
- All UUIDs, trace IDs, and span IDs are uniquely generated

## Related Documentation

- `/Users/harma/src/certus/certus-TAP/certus_integrity/README.md` - Integrity middleware overview
- `/Users/harma/src/certus/certus-TAP/certus_integrity/evidence.py` - Evidence generation code
- `/Users/harma/src/certus/certus-TAP/certus_integrity/middleware.py` - Decision logic
- `/Users/harma/src/certus/certus-TAP/certus_integrity/schemas.py` - Data models
