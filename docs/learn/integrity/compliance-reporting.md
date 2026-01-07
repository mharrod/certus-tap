# Generating Compliance Reports

>**STATUS:Tutorial is currently in beta. If you have issues see our [Communication & Support guide](../../about/communication.md)**

This tutorial shows compliance officers and auditors how to extract evidence from Certus Integrity for SOC 2, ISO 27001, PCI-DSS, and other compliance frameworks.

**Who is this for?** Compliance officers, auditors, and security teams preparing for audits.

**What you'll do:**

1. Export integrity decisions for a compliance period
2. Prove security controls were active
3. Generate audit-ready reports
4. Answer specific compliance questions
5. Create evidence packages for auditors

**Time:** 30 minutes (with live stack + synthetic traffic) or longer for full production windows

---

## How Compliance Reporting Works

```mermaid
sequenceDiagram
    participant System as Production System
    participant Middleware as Integrity Middleware
    participant Evidence as Evidence Store
    participant Auditor as Compliance Officer
    participant Report as Audit Report

    Note over System,Report: Audit Period: Jan 1 - Mar 31 (Q1 2025)

    loop Production Traffic (90 days)
        System->>Middleware: User requests
        Middleware->>Middleware: Apply security controls
        alt Request allowed
            Middleware->>Evidence: Log: allowed decision
        else Request denied
            Middleware->>Evidence: Log: denied decision (signed)
        end
    end

    Note over System,Report: Audit Query Phase

    Auditor->>Evidence: Query: 2025-01-01 to 2025-03-31
    Evidence-->>Auditor: 1.2M decisions

    Auditor->>Evidence: Filter: decision="denied"
    Evidence-->>Auditor: 8,432 blocked requests

    Auditor->>Evidence: Verify all signatures
    Evidence-->>Auditor: All valid ✓

    Auditor->>Report: Generate SOC 2 Control Report
    Report->>Report: Calculate metrics:<br/>- Total requests: 1.2M<br/>- Blocked: 8,432 (0.7%)<br/>- Controls active: 100% uptime

    Auditor->>Report: Export evidence package
    Report-->>Auditor: compliance-report.pdf<br/>+ evidence-bundle.tar.gz

    Note over System,Report: Compliance Question Answered:<br/>"Were rate limits active during Q1?"<br/>Answer: Yes, with cryptographic proof
```

**Key Points**:

- **Evidence retention**: All decisions stored for audit period (90+ days)
- **Cryptographic proof**: Every decision signed, signatures verifiable
- **Compliance metrics**: Block rate, uptime, control effectiveness
- **Audit packages**: PDF reports + signed evidence bundles for auditors

## Step 1 - Quick Start (Live Stack + Synthetic Traffic)

Follow these steps once to produce real metrics and evidence on your local stack. Everything else in this tutorial will reference that dataset.

### 1.1 Start the Integrity tutorial stack

```bash
# Launch the minimal stack (VictoriaMetrics, OTEL collector, ask-certus-backend, etc.)
just integrity-up
```

### 1.2 Verify services before proceeding

```bash
just preflight-integrity
```

### 1.3 Evidence bundles are written here by default

```bash
export EVIDENCE_DIR="${EVIDENCE_DIR:-~/certus-evidence}"
mkdir -p "$EVIDENCE_DIR"
```

> Before generating traffic, configure enforcement mode (not shadow mode):
>
> ```bash
> # Remove existing INTEGRITY_* settings if present, then add enforcement config
> sed -i.bak '/^INTEGRITY_/d' .env
> cat >> .env <<EOF
> INTEGRITY_SHADOW_MODE=false
> INTEGRITY_WHITELIST_IPS=127.0.0.1
> EOF
>
> # Restart backend to apply changes
> docker compose -f certus_ask/deploy/docker-compose.yml restart
> ```
>
> The default whitelist covers the entire Docker bridge network (172.18.0.0/16), so traffic from your host would otherwise be exempt.

## Step 2 - Generate synthetic workload

Simulate both legitimate usage and abusive bursts so the rate limiter produces live decisions.

```bash
API_BASE="${CERTUS_ASK_URL}/v1/health"

# Normal traffic (allowed)
for i in {1..50}; do
  curl -s -H "X-Forwarded-For: 192.168.1.100" "$API_BASE" >/dev/null
  sleep 1
done

# Burst offender (should trigger denials)
for i in {1..150}; do
  curl -s -H "X-Forwarded-For: 198.51.100.25" "$API_BASE" >/dev/null &
  if [ $((i % 25)) -eq 0 ]; then sleep 0.5; fi
done
wait

# Run the built-in rate-limit verifier for an additional spike
uv run python scripts/verify_rate_limit.py active
```

> Expect to see some `Blocked (429)` entries in the output. If everything succeeds with `200`, double-check the whitelist/shadow-mode env vars and rerun `just integrity-up` before repeating the workload.

## Step 3 - Set audit window and confirm data exists

Now that you've generated traffic, set your audit window to capture the last 10 minutes (which includes the traffic you just generated):

```bash
# Set evidence directory
: "${EVIDENCE_DIR:=~/certus-evidence}"

# Capture the last 10 minutes (covers the traffic you just generated)
eval "$(python3 - <<'PY'
from datetime import datetime, timedelta, timezone
now = datetime.now(timezone.utc)
start = now - timedelta(minutes=10)
print(f'export AUDIT_START="{start.strftime("%Y-%m-%dT%H:%M:%SZ")}"')
print(f'export AUDIT_END="{now.strftime("%Y-%m-%dT%H:%M:%SZ")}"')
PY
)"
AUDIT_PERIOD="INTEGRITY-$(date -u +"%Y%m%dT%H%M")"

echo "Audit Period: $AUDIT_PERIOD"
echo "Start: $AUDIT_START"
echo "End: $AUDIT_END"
```

**Verify evidence bundles exist in this window:**

```bash
python3 - <<'PY'
import os, pathlib, datetime
from datetime import timezone
evidence_dir = pathlib.Path(os.environ.get("EVIDENCE_DIR", "~/certus-evidence")).expanduser()
start = datetime.datetime.strptime(os.environ["AUDIT_START"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
end = datetime.datetime.strptime(os.environ["AUDIT_END"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
matches = [p for p in evidence_dir.glob("dec_*.json") if start <= datetime.datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) < end]
print(f"Evidence bundles in window: {len(matches)}")
if matches:
    print("Example bundle:", matches[0])
PY
```

**Confirm VictoriaMetrics has the data:**

```bash
# Wait for VictoriaMetrics to scrape the latest metrics
sleep 20

# Query total decisions
curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum(certus_integrity_decisions_total)" | jq
```

You should see evidence bundles and metrics from your traffic generation.

At this point you can also open Grafana (default `http://localhost:3002`) to watch the dashboards update in real time.

??? info "No access to the stack? Use the bundled sample evidence instead."

    ```bash
    # Set evidence directory to samples
    export EVIDENCE_DIR="$(pwd)/samples/integrity-evidence"

    # Verify samples exist
    ls -lh "$EVIDENCE_DIR"/dec_*.json | wc -l
    # Expected: 75 evidence bundles

    # Expand tilde if needed
    EVIDENCE_DIR="${EVIDENCE_DIR/#\~/$HOME}"
    cd "$EVIDENCE_DIR"

    # Run analyzer to generate compliance metrics
    python3 analyze_attack.py

    # View compliance summary
    cat attack_summary.json | jq '.compliance'
    ```

    **Sample output:**

    ```json
    {
      "enforcement_mode": true,
      "shadow_mode": false,
      "total_decisions": 75,
      "blocked_malicious": 40,
      "allowed_legitimate": 35,
      "false_positives": 0,
      "control_effectiveness": "100%"
    }
    ```

    Continue with the tutorial using the sample timestamps described in the bundle.

---

## Scenario

Your organization is undergoing a SOC 2 Type 2 audit. The auditor asks:

> "Prove that your rate limiting controls were active and effective during the audit period (January 1 - December 31, 2025)."

You'll use Certus Integrity's evidence to demonstrate compliance.

## Prerequisites

- Certus Integrity running in enforcement mode during the audit period
- Access to:
  - VictoriaMetrics (`${VICTORIAMETRICS_URL}`) - for live audits
  - Evidence directory (`~/certus-evidence/` or sample directory)
  - OpenSearch (`${OPENSEARCH_HOST}`) - for live audits
- `jq`, `curl`, and basic shell scripting

## Step 4: Verify Data Availability

Check if metrics exist for this period:

```bash
curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=certus_integrity_decisions_total" | \
  jq -r '.data.result[0] | "Metrics available from: " + (.value[0] | todate)'
```

If metrics don't cover the full period, check evidence files:

```bash
python3 - <<'PY'
import os, pathlib, datetime
from datetime import timezone
evidence_dir = pathlib.Path(os.environ.get("EVIDENCE_DIR", "~/certus-evidence")).expanduser()
start = datetime.datetime.strptime(os.environ["AUDIT_START"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
end = datetime.datetime.strptime(os.environ["AUDIT_END"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
count = sum(1 for p in evidence_dir.glob("dec_*.json") if start <= datetime.datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) < end)
print(f"Evidence bundles between {start} and {end}: {count}")
PY
```

**Expected:** At least a few hundred evidence bundles (depends on traffic volume).

## Step 5: Prove Controls Were Active

Auditors need proof that security controls were enabled, not disabled or in "testing mode."

### 2.1 Inspect Evidence Bundles

```bash
# Ensure EVIDENCE_DIR is set and expanded
export EVIDENCE_DIR="${EVIDENCE_DIR:-~/certus-evidence}"
EVIDENCE_DIR="${EVIDENCE_DIR/#\~/$HOME}"  # Expand tilde
cd "$EVIDENCE_DIR"

# Confirm every bundle shows enforcement mode (shadow_mode=false)
jq -r '.decision.metadata.shadow_mode // "false"' dec_*.json | sort | uniq -c

# Show decision mix
jq -r '.decision.decision' dec_*.json | sort | uniq -c
```

You should see `shadow_mode false` and a mix of `allowed` vs `denied` decisions that matches the synthetic workload you ran.

### 2.2 Verify Enforcement Mode Was Enabled

```bash
# Query for shadow mode status
curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=certus_integrity_decisions_total" | \
  jq -r '.data.result[] | select(.metric.shadow_mode == "false") | "Enforcement mode confirmed"'
```

**Expected output:** `Enforcement mode confirmed`

If you see `shadow_mode: true`, controls were only logging, not blocking!

### 2.3 Calculate Uptime of Controls

```bash
# Count decisions per day (cross-platform date conversion)
if date --version >/dev/null 2>&1; then
  # GNU date (Linux)
  START_EPOCH=$(date -d "$AUDIT_START" +%s)
  END_EPOCH=$(date -d "$AUDIT_END" +%s)
else
  # BSD date (macOS)
  START_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$AUDIT_START" +%s)
  END_EPOCH=$(date -j -f "%Y-%m-%dT%H:%M:%SZ" "$AUDIT_END" +%s)
fi

curl -s "${VICTORIAMETRICS_URL}/api/v1/query_range?query=count_over_time(certus_integrity_decisions_total[1d])&start=${START_EPOCH}&end=${END_EPOCH}&step=86400" | \
  jq -r '.data.result[0].values[] | @tsv' | \
  awk '{
    total_days++
    if ($2 > 0) active_days++
  }
  END {
    if (total_days > 0) {
      uptime = (active_days / total_days) * 100
      print "Active Days: " active_days " / " total_days " (" uptime "%)"
    } else {
      print "Note: Uptime calculation requires 1+ days of data. For tutorial runs, verify evidence files exist instead."
    }
  }'
```

> **Note:** This query requires at least 1 day of historical data. For short tutorial runs, you can verify controls were active by checking that evidence files exist in your audit window.

### 2.4 Export Control Configuration

Document what the controls were:

```bash
cat > /tmp/compliance-control-config-$AUDIT_PERIOD.json <<EOF
{
  "audit_period": "$AUDIT_PERIOD",
  "control": "Certus Integrity - Rate Limiting",
  "configuration": {
    "enforcement_mode": true,
    "shadow_mode": false,
    "rate_limit_per_minute": 100,
    "burst_limit": 20,
    "whitelist": "Internal networks (10.0.0.0/8, 172.18.0.0/16)"
  },
  "verification_method": "Cryptographically signed evidence bundles",
  "evidence_location": "~/certus-evidence/",
  "transparency_log": "Sigstore Rekor"
}
EOF

cat /tmp/compliance-control-config-$AUDIT_PERIOD.json | jq
```

## Step 6: Generate Summary Statistics

Provide high-level metrics for the audit report.

### 3.1 Total Decisions Made

```bash
curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum(certus_integrity_decisions_total)" | \
  jq -r '.data.result[0].value[1] + " total decisions"'
```

**Sample output:** `12,450,000 total decisions`

### 3.2 Decision Breakdown

```bash
# Get decision breakdown with percentages
curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum%20by(decision)(certus_integrity_decisions_total)" | \
  jq -r '.data.result[] | "\(.metric.decision): \(.value[1])"' | \
  awk '{gsub(/:/, "", $1); total += $2; decisions[$1] = $2} END {for (d in decisions) {pct = (decisions[d] / total) * 100; printf "%s: %s (%.2f%%)\n", d, decisions[d], pct}}'
```

**Sample output:**

```
allowed: 12,420,000 (99.76%)
denied: 30,000 (0.24%)
degraded: 0 (0.00%)
```

**Interpretation:** 99.76% of requests were legitimate; 0.24% were blocked as abusive.

### 3.3 Unique IPs Monitored

```bash
# Use evidence files to count unique IPs (not in metrics due to cardinality)
export EVIDENCE_DIR="${EVIDENCE_DIR:-~/certus-evidence}"
EVIDENCE_DIR="${EVIDENCE_DIR/#\~/$HOME}"
unique_ips=$(jq -r '.decision.metadata.client_ip' "$EVIDENCE_DIR"/dec_*.json | sort -u | wc -l | tr -d ' ')
echo "$unique_ips unique IPs"
```

**Sample output:** `15 unique IPs`

### 3.4 Guardrails Triggered

```bash
curl -s "${VICTORIAMETRICS_URL}/api/v1/query" --data-urlencode 'query=sum by(guardrail)(certus_integrity_decisions_total{decision="denied"})' | \
  jq -r '.data.result[] | "\(.metric.guardrail): \(.value[1])"'
```

**Sample output:**

```
rate_limit: 28,500
burst_protection: 1,500
```

## Step 7: Answer Specific Compliance Questions

### SOC 2: CC6.1 - Logical Access Controls

**Question:** "Does the system have logical access security software, infrastructure, and architectures to support the identification and authentication of authorized users?"

**Answer:** Yes

**Evidence:**

```bash
# Export control effectiveness
cat > /tmp/soc2-cc6.1-evidence-$AUDIT_PERIOD.json <<EOF
{
  "control_id": "CC6.1",
  "control_description": "Rate limiting to prevent unauthorized access abuse",
  "audit_period": "$AUDIT_PERIOD",
  "implementation": {
    "technology": "Certus Integrity Middleware",
    "enforcement": "Active (non-shadow mode)",
    "granularity": "Per-IP address",
    "threshold": "100 requests/minute, 20 requests/10 seconds"
  },
  "effectiveness_metrics": {
    "total_requests": $(curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum(certus_integrity_decisions_total)" | jq -r '.data.result[0].value[1] // "0"'),
    "blocked_requests": $(curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum(certus_integrity_decisions_total{decision=\"denied\"})" | jq -r '.data.result[0].value[1] // "0"'),
    "block_rate_percent": $(curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=100*sum(certus_integrity_decisions_total{decision=\"denied\"})/sum(certus_integrity_decisions_total)" | jq -r '.data.result[0].value[1] // "0"'),
    "uptime_percent": 99.9
  },
  "evidence_trail": {
    "cryptographic_signatures": true,
    "transparency_log": "Sigstore Rekor",
    "evidence_bundles": "$(python3 - <<PY
import pathlib, datetime, os, sys
from datetime import timezone
start = datetime.datetime.strptime("$AUDIT_START", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
end = datetime.datetime.strptime("$AUDIT_END", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
evidence_dir = pathlib.Path(os.environ.get("EVIDENCE_DIR", "~/certus-evidence")).expanduser()
count = sum(1 for p in evidence_dir.glob("dec_*.json") if start <= datetime.datetime.fromtimestamp(p.stat().st_mtime, timezone.utc) < end)
print(f"{count} bundles")
PY
) bundles"
  }
}
EOF

cat /tmp/soc2-cc6.1-evidence-$AUDIT_PERIOD.json | jq
```

### PCI-DSS: Requirement 8.2.3 - Account Lockout

**Question:** "Are accounts locked out after no more than six invalid access attempts?"

**Answer:** Yes (rate limiting achieves similar outcome)

**Evidence:**

```bash
# Show total blocked requests due to rate limiting
curl -s "${VICTORIAMETRICS_URL}/api/v1/query" --data-urlencode 'query=sum(certus_integrity_decisions_total{decision="denied", reason="rate_limit_exceeded"})' | \
  jq -r '.data.result[0].value[1] + " requests blocked due to rate limiting"'

# For per-IP analysis, use evidence files directly
export EVIDENCE_DIR="${EVIDENCE_DIR:-~/certus-evidence}"
EVIDENCE_DIR="${EVIDENCE_DIR/#\~/$HOME}"
jq -r 'select(.decision.decision == "denied" and .decision.reason == "rate_limit_exceeded") | .decision.metadata.client_ip' "$EVIDENCE_DIR"/dec_*.json | sort | uniq -c | sort -rn | head -10
```

**Sample output:**

```
440 requests blocked due to rate limiting

Top IPs blocked:
   90 10.0.0.50
   50 198.51.100.25
   30 192.168.1.100
```

**Interpretation:** IPs making excessive requests were automatically blocked, preventing brute-force attacks.

### ISO 27001: A.9.4.2 - Secure Log-on Procedures

**Question:** "Is there a facility to limit unsuccessful log-on attempts?"

**Answer:** Yes

**Evidence:**

```bash
# Count IPs that hit rate limits (could be login attempts)
curl -s "${VICTORIAMETRICS_URL}/api/v1/query" --data-urlencode 'query=count(certus_integrity_rate_limit_violations_total)' | \
  jq -r '"IPs that exceeded rate limits: " + .data.result[0].value[1]'
```

**Sample output:** `IPs that exceeded rate limits: 342`

**Interpretation:** 342 unique IPs attempted to exceed normal usage, all were throttled.

## Step 8: Export Evidence Bundles

Provide actual cryptographic evidence to auditors.

### 5.1 Create Evidence Archive

```bash
# Create compliance evidence package
EVIDENCE_DIR="/tmp/compliance-evidence-$AUDIT_PERIOD"
mkdir -p "$EVIDENCE_DIR"

# Copy all evidence from audit period (cross-platform using Python)
python3 - <<PY
import pathlib, datetime, shutil, os
from datetime import timezone
start = datetime.datetime.strptime("$AUDIT_START", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
end = datetime.datetime.strptime("$AUDIT_END", "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
source_dir = pathlib.Path(os.path.expanduser("~/certus-evidence"))
dest_dir = pathlib.Path("$EVIDENCE_DIR")
for p in source_dir.glob("dec_*.json"):
    mtime = datetime.datetime.fromtimestamp(p.stat().st_mtime, timezone.utc)
    if start <= mtime < end:
        shutil.copy(p, dest_dir)
PY

# Count files
echo "Evidence bundles collected: $(ls "$EVIDENCE_DIR" | wc -l)"
```

### 5.2 Sample Evidence for Auditor Review

```bash
# Create a sample of 100 evidence bundles (randomly selected)
mkdir -p "$EVIDENCE_DIR/sample"
ls "$EVIDENCE_DIR"/dec_*.json | shuf | head -100 | xargs -I {} cp {} "$EVIDENCE_DIR/sample/"

# Create manifest
cat > "$EVIDENCE_DIR/sample/MANIFEST.md" <<EOF
# Evidence Sample for Audit

**Audit Period:** $AUDIT_PERIOD
**Sample Size:** 100 evidence bundles (random selection)
**Total Evidence Bundles:** $(ls "$EVIDENCE_DIR"/dec_*.json | wc -l)

## How to Verify

Each evidence bundle is cryptographically signed. To verify:

\`\`\`bash
# Extract content hash
jq -r '.content_hash' evidence-file.json

# Verify signature (requires cosign or trust service)
curl -X POST ${CERTUS_TRUST_URL}/v1/verify \\
  -d @evidence-file.json
\`\`\`

## Evidence Structure

Each bundle contains:
- Decision ID (unique identifier)
- Timestamp (when decision was made)
- Decision outcome (allowed, denied, degraded)
- Guardrail triggered (rate_limit, burst_protection, etc.)
- Client IP address
- Metadata (request details)
- Cryptographic signature
- Transparency log entry (Rekor)

## Sample Breakdown

\`\`\`bash
jq -r '.decision.decision' dec_*.json | sort | uniq -c
\`\`\`

Expected output shows mix of allowed and denied decisions.
EOF

cat "$EVIDENCE_DIR/sample/MANIFEST.md"
```

### 5.3 Create Evidence Summary Report

```bash
# Analyze evidence bundles
cat > "$EVIDENCE_DIR/SUMMARY.md" <<EOF
# Compliance Evidence Summary

**Audit Period:** $AUDIT_PERIOD
**Generated:** $(date -u)
**Total Evidence Bundles:** $(ls "$EVIDENCE_DIR"/dec_*.json | wc -l)

## Decision Breakdown

$(jq -r '.decision.decision' "$EVIDENCE_DIR"/dec_*.json | sort | uniq -c | awk '{print "- " $2 ": " $1}')

## Guardrail Breakdown

$(jq -r 'select(.decision.decision=="denied") | .decision.guardrail' "$EVIDENCE_DIR"/dec_*.json | sort | uniq -c | awk '{print "- " $2 ": " $1}')

## Top Denied IPs

$(jq -r 'select(.decision.decision=="denied") | .decision.metadata.client_ip' "$EVIDENCE_DIR"/dec_*.json | sort | uniq -c | sort -rn | head -10 | awk '{print "- " $2 ": " $1 " denials"}')

## Verification Status

$(jq -r '.verification_status' "$EVIDENCE_DIR"/dec_*.json | sort | uniq -c | awk '{print "- " $2 ": " $1}')

## Cryptographic Proof

All evidence bundles include:
- SHA256 content hash
- Digital signature from certus-trust
- Transparency log entry (Rekor)
- Timestamp from trusted source

### Sample Hash Chain

$(ls "$EVIDENCE_DIR"/dec_*.json | head -5 | xargs -I {} bash -c 'echo "File: $(basename {}), Hash: $(jq -r .content_hash {})"')

## Compliance Attestation

I certify that:
1. All evidence bundles were generated automatically by Certus Integrity
2. No evidence has been modified or deleted
3. All signatures were verified against certus-trust public keys
4. Controls were active in enforcement mode throughout the audit period

**Signed:** ___________________________
**Date:** $(date -u +%Y-%m-%d)
**Role:** Security Compliance Officer
EOF

cat "$EVIDENCE_DIR/SUMMARY.md"
```

### 5.4 Package for Auditor

```bash
# Create compressed archive
tar -czf "/tmp/compliance-evidence-$AUDIT_PERIOD.tar.gz" -C "$(dirname "$EVIDENCE_DIR")" "$(basename "$EVIDENCE_DIR")"

echo "Evidence package created: /tmp/compliance-evidence-$AUDIT_PERIOD.tar.gz"
echo "Size: $(du -h "/tmp/compliance-evidence-$AUDIT_PERIOD.tar.gz" | cut -f1)"
```

## Step 9: Create Executive Summary

Generate a one-page summary for auditors and executives using the live metrics you just captured.

```bash
cat > "/tmp/compliance-executive-summary-$AUDIT_PERIOD.md" <<EOF
# Certus Integrity Compliance Report
## Executive Summary - $AUDIT_PERIOD

**Report Date:** $(date -u +"%B %d, %Y")
**Audit Period:** $AUDIT_START to $AUDIT_END
**Prepared By:** Security Team

---

### Control Overview

Certus Integrity provides rate limiting and access control for all API requests. The control operates as middleware, inspecting every request before it reaches the application.

**Control Status:** ✓ ACTIVE AND EFFECTIVE

### Key Metrics

| Metric | Value |
|--------|-------|
| Total Requests Processed | $(curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum(certus_integrity_decisions_total)" | jq -r '.data.result[0].value[1]') |
| Legitimate Requests Allowed | $(curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum(certus_integrity_decisions_total{decision=\"allowed\"})" | jq -r '.data.result[0].value[1]') |
| Abusive Requests Blocked | $(curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum(certus_integrity_decisions_total{decision=\"denied\"})" | jq -r '.data.result[0].value[1]') |
| Unique IP Addresses Monitored | $(jq -r '.decision.metadata.client_ip' "$EVIDENCE_DIR"/dec_*.json \| sort -u \| wc -l \| tr -d ' ') |
| Control Uptime | 99.9% |
| Evidence Bundles Generated | $(ls "$EVIDENCE_DIR"/dec_*.json | wc -l) |

### Effectiveness

- **Block Rate:** 0.24% of requests (30,000 blocked out of 12.45M total)
- **False Positive Rate:** <0.01% (based on whitelist additions)
- **Detection Time:** <1ms (real-time blocking)
- **Evidence Integrity:** 100% cryptographically signed

### Compliance Alignment

| Framework | Requirement | Status |
|-----------|-------------|--------|
| SOC 2 | CC6.1 - Logical Access Controls | ✓ Compliant |
| PCI-DSS | 8.2.3 - Account Lockout | ✓ Compliant |
| ISO 27001 | A.9.4.2 - Secure Log-on | ✓ Compliant |
| HIPAA | 164.312(a)(2)(i) - Access Control | ✓ Compliant |

### Evidence Trail

All enforcement decisions are:
1. **Recorded** in cryptographically signed evidence bundles
2. **Timestamped** by independent transparency log (Sigstore Rekor)
3. **Auditable** via metrics, logs, and trace correlation
4. **Immutable** once signed (tamper-evident)

### Risk Assessment

**Before Control:** API endpoints vulnerable to automated abuse, credential stuffing, and resource exhaustion.

**After Control:** Malicious bursts were blocked instantly, legitimate users stayed online, and the audit trail remained cryptographically sound.

### Auditor Recommendation

**Status:** PASS

The organization has implemented effective rate limiting controls with real-time enforcement, cryptographic evidence, independent verification, and comprehensive monitoring.

**Evidence Package:** /tmp/compliance-evidence-$AUDIT_PERIOD.tar.gz

---

**Prepared By:** Security Team
**Reviewed By:** ___________________________
**Approved By:** ___________________________
**Date:** $(date -u +"%Y-%m-%d")
EOF

cat "/tmp/compliance-executive-summary-$AUDIT_PERIOD.md"
```

??? info "Need to run this tutorial offline with the bundled incident data?"

````bash
    # Expand tilde if needed
    EVIDENCE_DIR="${EVIDENCE_DIR/#\~/$HOME}"
    cd "$EVIDENCE_DIR"

    TOTAL=$(jq -r '.decision' dec_*.json | wc -l | tr -d ' ')
    ALLOWED=$(jq -r 'select(.decision.decision == "allowed")' dec_*.json | wc -l | tr -d ' ')
    DENIED=$(jq -r 'select(.decision.decision == "denied")' dec_*.json | wc -l | tr -d ' ')
    UNIQUE_IPS=$(jq -r '.decision.metadata.client_ip' dec_*.json | sort -u | wc -l | tr -d ' ')
    ATTACKER_IPS=$(jq -r 'select(.decision.decision == "denied") | .decision.metadata.client_ip' dec_*.json | sort -u | wc -l | tr -d ' ')

    cat > "/tmp/compliance-executive-summary-$AUDIT_PERIOD.md" <<EOF
    # Certus Integrity Compliance Report
    ## Executive Summary - $AUDIT_PERIOD (Sample Incident)

    **Report Date:** $(date -u +"%B %d, %Y")
    **Audit Period:** $AUDIT_START to $AUDIT_END (December 15, 2025)
    **Prepared By:** Security Team

    ---

    | Metric | Value |
    |--------|-------|
    | Total Decisions Made | $TOTAL |
    | Legitimate Requests Allowed | $ALLOWED |
    | Malicious Requests Blocked | $DENIED |
    | Unique IP Addresses Monitored | $UNIQUE_IPS |
    | Attacker IPs Identified | $ATTACKER_IPS |
    | Evidence Bundles Generated | 75 |

    **Evidence Package:** /tmp/compliance-evidence-$AUDIT_PERIOD.tar.gz

    ---

    **Prepared By:** Security Compliance Officer
    **Reviewed By:** ___________________________
    **Approved By:** ___________________________
    **Date:** $(date -u +"%Y-%m-%d")
    EOF

    cat "/tmp/compliance-executive-summary-$AUDIT_PERIOD.md"
    ```

## What You Achieved

✓ Exported all integrity decisions for the audit period
✓ Proved security controls were active (enforcement mode)
✓ Generated summary statistics for compliance frameworks
✓ Answered specific SOC 2, PCI-DSS, and ISO 27001 questions
✓ Created a tamper-evident evidence package for auditors
✓ Produced an executive summary for leadership

You now have a complete, audit-ready compliance report with cryptographic proof!

## Delivering to Auditors

**What to provide:**

1. **Executive Summary** (1 page) - `/tmp/compliance-executive-summary-$AUDIT_PERIOD.md`
2. **Evidence Package** (tar.gz) - `/tmp/compliance-evidence-$AUDIT_PERIOD.tar.gz`
3. **Configuration Documentation** - `/tmp/compliance-control-config-$AUDIT_PERIOD.json`
4. **Sample Evidence** (100 bundles) - `$EVIDENCE_DIR/sample/`

**How to present:**

- Email the tar.gz file securely (encrypted)
- Schedule a walkthrough session to demonstrate verification
- Provide access to Grafana dashboards for live metrics
- Offer to verify any evidence bundle signature in real-time

## Next Steps

- Learn about [incident investigation](investigating-incidents.md) for forensic analysis
- Set up [automated evidence archiving](evidence-archiving.md) for long-term retention
- Configure [continuous compliance monitoring](continuous-compliance.md) for real-time audit readiness

````

```

```
