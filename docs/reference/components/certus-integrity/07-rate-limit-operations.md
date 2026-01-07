# Rate Limit Operations Guide

## Overview

This guide covers production operations for Certus Integrity rate limiting, including IP classification, staging validation, production rollout strategies, and ongoing monitoring. Use this after completing the [Testing Rate Limits](../../../learn/integrity/testing-rate-limits.md) tutorial.

**Prerequisites:**
- Completed Testing Rate Limits tutorial
- Understanding of shadow mode vs enforcement mode
- Access to VictoriaMetrics and OpenSearch
- Staging and production environments configured

---

## Step 1: Classify High-Traffic IPs

After analyzing rate limit evidence in shadow mode, classify IPs to determine appropriate actions.

### 1.1 Identify High-Volume IPs

Find IPs generating the most requests:

```bash
EVIDENCE_DIR="/tmp/certus-evidence/integrity/rate-limit"

cd "$EVIDENCE_DIR"
jq -r '.decision.metadata.client_ip' dec_*.json 2>/dev/null | \
  sort | uniq -c | sort -rn | head -20
```

**Example Output:**
```
    150 203.0.113.25
     80 10.0.1.100
     30 192.168.1.100
     15 192.168.1.101
```

### 1.2 Analyze Denial Rates

For each high-volume IP, check how often it was denied:

```bash
IP="203.0.113.25"  # Replace with target IP

echo "=== Analysis for $IP ==="
TOTAL=$(jq -r --arg ip "$IP" 'select(.decision.metadata.client_ip==$ip) | .decision.metadata.client_ip' dec_*.json 2>/dev/null | wc -l | tr -d ' ')
DENIED=$(jq -r --arg ip "$IP" 'select(.decision.metadata.client_ip==$ip and .decision.decision=="denied") | .decision.metadata.client_ip' dec_*.json 2>/dev/null | wc -l | tr -d ' ')

echo "Total requests: $TOTAL"
echo "Denied requests: $DENIED"

if [ "$TOTAL" -gt 0 ]; then
  RATE=$(echo "scale=1; ($DENIED * 100) / $TOTAL" | bc)
  echo "Denial rate: $RATE%"
fi
```

### 1.3 Classification Decision Matrix

| Denial Rate | Request Volume | Classification | Recommended Action |
|-------------|---------------|----------------|-------------------|
| 0-10% | Any | Legitimate | Whitelist if business-critical |
| 10-30% | Low (<100/min) | Legitimate burst | Monitor, adjust burst size |
| 10-30% | High (>100/min) | Batch job | Coordinate with team, schedule off-peak |
| 30-70% | Any | Potential abuse | Apply rate limit, monitor |
| >70% | High | Attack/misconfiguration | Block or apply strict limit |

### 1.4 Document Your Decisions

Create an IP classification file:

```bash
cat > /tmp/ip-classifications.json <<EOF
{
  "whitelisted": [
    {"ip": "192.168.1.0/24", "reason": "Internal network", "approved_by": "ops-team"},
    {"ip": "10.0.1.100", "reason": "Scheduled batch job", "approved_by": "data-team"}
  ],
  "monitored": [
    {"ip": "203.0.113.25", "reason": "High traffic, needs investigation", "expires": "2025-01-15"}
  ],
  "blocked": [
    {"ip": "198.51.100.42", "reason": "Attack pattern confirmed", "blocked_date": "2025-01-01"}
  ]
}
EOF
```

---

## Step 2: Test Enforcement in Staging

Before enabling enforcement in production, validate in staging.

### 2.1 Configure Staging Environment

Update staging `.env`:

```bash
# Staging rate limits (stricter than production initially)
sed -i.bak '/^INTEGRITY_/d' .env
cat >> .env <<EOF
INTEGRITY_SHADOW_MODE=false
INTEGRITY_WHITELIST_IPS=10.0.1.100,192.168.1.0/24
INTEGRITY_RATE_LIMIT_PER_MINUTE=45
INTEGRITY_RATE_LIMIT_BURST=15
EOF

docker compose -f certus_ask/deploy/docker-compose.yml restart
```

### 2.2 Run Staging Tests

Simulate production traffic patterns:

```bash
bash -c '
API_BASE="http://localhost:8000/v1/health"

# Test 1: Normal traffic (should pass)
echo "Test 1: Normal user traffic..."
for i in {1..30}; do
  RESPONSE=$(curl -s -w "\n%{http_code}" -H "X-Forwarded-For: 192.168.1.50" "$API_BASE")
  STATUS=$(echo "$RESPONSE" | tail -1)
  if [ "$STATUS" != "200" ]; then
    echo "FAIL: Normal traffic blocked (status $STATUS)"
    exit 1
  fi
  sleep 2
done
echo "PASS: Normal traffic allowed"

# Test 2: Whitelisted IP (should always pass)
echo "Test 2: Whitelisted batch job..."
for i in {1..100}; do
  RESPONSE=$(curl -s -w "\n%{http_code}" -H "X-Forwarded-For: 10.0.1.100" "$API_BASE")
  STATUS=$(echo "$RESPONSE" | tail -1)
  if [ "$STATUS" != "200" ]; then
    echo "FAIL: Whitelisted IP blocked (status $STATUS)"
    exit 1
  fi
  sleep 0.3
done
echo "PASS: Whitelisted IP allowed unlimited access"

# Test 3: Attack pattern (should block)
echo "Test 3: Simulated attack..."
BLOCKED_COUNT=0
for i in {1..100}; do
  RESPONSE=$(curl -s -w "\n%{http_code}" -H "X-Forwarded-For: 203.0.113.99" "$API_BASE")
  STATUS=$(echo "$RESPONSE" | tail -1)
  if [ "$STATUS" = "429" ]; then
    BLOCKED_COUNT=$((BLOCKED_COUNT + 1))
  fi
  sleep 0.1
done

if [ "$BLOCKED_COUNT" -lt 50 ]; then
  echo "FAIL: Attack not blocked (only $BLOCKED_COUNT/100 blocked)"
  exit 1
fi
echo "PASS: Attack blocked ($BLOCKED_COUNT/100 requests denied)"
'
```

### 2.3 Validate Evidence Generation

Confirm all enforcement decisions are logged:

```bash
EVIDENCE_DIR="/tmp/certus-evidence/integrity/rate-limit"

# Check recent evidence files
ls -lth "$EVIDENCE_DIR"/dec_*.json | head -5

# Verify cryptographic signatures
cd "$EVIDENCE_DIR"
for file in $(ls dec_*.json | head -3); do
  echo "Checking $file..."
  jq -r '.signature.algorithm' "$file"
  jq -r '.signature.public_key_id' "$file"
  jq -r '.signature.value' "$file" | head -c 50
  echo "..."
done
```

---

## Step 3: Production Rollout

Use a phased rollout to minimize risk.

### 3.1 Phase 1: Shadow Mode with Production Limits

Run in shadow mode with production-intended limits for 7 days:

```bash
# Production limits (more permissive than staging)
cat >> .env <<EOF
INTEGRITY_SHADOW_MODE=true
INTEGRITY_WHITELIST_IPS=10.0.1.100,192.168.1.0/24,172.16.0.0/12
INTEGRITY_RATE_LIMIT_PER_MINUTE=60
INTEGRITY_RATE_LIMIT_BURST=20
EOF

docker compose -f certus_ask/deploy/docker-compose.yml restart
```

**Monitoring checklist:**
- [ ] No legitimate users would be blocked (denial rate <1% for known IPs)
- [ ] Evidence files generating at expected rate (~1KB per denied request)
- [ ] No performance degradation (P95 latency <50ms overhead)
- [ ] Attack patterns detected and logged

### 3.2 Phase 2: Enforcement for Non-Critical Endpoints

Enable enforcement only for non-critical endpoints:

```bash
# Update configuration to enforce only on health/metrics endpoints
cat >> .env <<EOF
INTEGRITY_SHADOW_MODE=false
INTEGRITY_ENFORCE_PATHS=/v1/health,/metrics
INTEGRITY_SHADOW_PATHS=/v1/chat,/v1/search,/v1/upload
EOF

docker compose -f certus_ask/deploy/docker-compose.yml restart
```

**Monitor for 48 hours:**
```bash
# Check if legitimate traffic is being blocked
EVIDENCE_DIR="/tmp/certus-evidence/integrity/rate-limit"

cd "$EVIDENCE_DIR"
echo "Top denied IPs (last 1000 decisions):"
jq -r 'select(.decision.decision=="denied") | .decision.metadata.client_ip' $(ls -t dec_*.json | head -100) | \
  sort | uniq -c | sort -rn | head -10
```

### 3.3 Phase 3: Full Enforcement

After validating phases 1-2, enable full enforcement:

```bash
cat >> .env <<EOF
INTEGRITY_SHADOW_MODE=false
INTEGRITY_WHITELIST_IPS=10.0.1.100,192.168.1.0/24,172.16.0.0/12
INTEGRITY_RATE_LIMIT_PER_MINUTE=60
INTEGRITY_RATE_LIMIT_BURST=20
EOF

docker compose -f certus_ask/deploy/docker-compose.yml restart
```

### 3.4 Rollback Plan

If issues arise, immediately revert to shadow mode:

```bash
# Emergency rollback
sed -i.bak 's/INTEGRITY_SHADOW_MODE=false/INTEGRITY_SHADOW_MODE=true/' .env
docker compose -f certus_ask/deploy/docker-compose.yml restart

# Verify rollback
curl -s http://localhost:8000/v1/health | jq -r '.integrity.shadow_mode'
# Should return: true
```

---

## Step 4: Ongoing Monitoring

Establish continuous monitoring and alerting.

### 4.1 Daily Evidence Review

Automate daily analysis of rate limit decisions:

```bash
#!/bin/bash
# /opt/certus/scripts/daily-rate-limit-report.sh

EVIDENCE_DIR="/tmp/certus-evidence/integrity/rate-limit"
REPORT_DATE=$(date -u +%Y-%m-%d)
REPORT_FILE="/var/log/certus/rate-limit-report-$REPORT_DATE.txt"

cd "$EVIDENCE_DIR"

{
  echo "=== Certus Integrity Rate Limit Report - $REPORT_DATE ==="
  echo ""

  echo "Top 10 Denied IPs (last 24h):"
  jq -r 'select(.decision.decision=="denied") | .decision.metadata.client_ip' dec_*.json 2>/dev/null | \
    sort | uniq -c | sort -rn | head -10

  echo ""
  echo "Decisions by Outcome:"
  jq -r '.decision.decision' dec_*.json 2>/dev/null | sort | uniq -c

  echo ""
  echo "Evidence Files Generated:"
  ls dec_*.json 2>/dev/null | wc -l | tr -d ' '

  echo ""
  echo "Total Storage Used:"
  du -sh "$EVIDENCE_DIR"

} > "$REPORT_FILE"

cat "$REPORT_FILE"
```

Schedule via cron:
```bash
# Add to crontab
0 8 * * * /opt/certus/scripts/daily-rate-limit-report.sh
```

### 4.2 VictoriaMetrics Alerts

Create alerting rules in VictoriaMetrics:

```yaml
# /etc/victoriametrics/alerts/rate-limits.yml
groups:
  - name: certus_integrity_rate_limits
    interval: 1m
    rules:
      - alert: HighRateLimitDenialRate
        expr: |
          (
            rate(certus_integrity_requests_denied_total[5m])
            /
            rate(certus_integrity_requests_total[5m])
          ) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High rate limit denial rate (>10%)"
          description: "{{ $value | humanizePercentage }} of requests denied in last 5m"

      - alert: PotentialAttack
        expr: |
          rate(certus_integrity_requests_denied_total{client_ip=~".*"}[1m]) > 50
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Potential attack detected from {{ $labels.client_ip }}"
          description: "{{ $value }} requests/min denied from single IP"

      - alert: RateLimitMiddlewareDown
        expr: |
          up{job="certus-integrity"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Certus Integrity middleware is down"
```

### 4.3 OpenSearch Dashboards

Create saved searches for incident investigation:

```bash
# Query: Recent denials with high request rates
POST /traces-otel/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"attributes.http.status_code": 429}},
        {"range": {"@timestamp": {"gte": "now-1h"}}}
      ]
    }
  },
  "aggs": {
    "by_ip": {
      "terms": {
        "field": "attributes.client.address.keyword",
        "size": 20
      }
    }
  }
}
```

### 4.4 Evidence Archive Strategy

Manage evidence storage growth:

```bash
#!/bin/bash
# /opt/certus/scripts/archive-old-evidence.sh

EVIDENCE_DIR="/tmp/certus-evidence/integrity/rate-limit"
ARCHIVE_DIR="/var/archive/certus-evidence/integrity/rate-limit"
RETENTION_DAYS=90

# Create archive directory structure
mkdir -p "$ARCHIVE_DIR/$(date +%Y)/$(date +%m)"

# Move files older than 7 days to archive
find "$EVIDENCE_DIR" -name "dec_*.json" -mtime +7 -exec mv {} "$ARCHIVE_DIR/$(date +%Y)/$(date +%m)/" \;

# Compress monthly archives older than 30 days
find "$ARCHIVE_DIR" -type d -name "[0-9][0-9]" -mtime +30 -exec tar -czf {}.tar.gz {} \; -exec rm -rf {} \;

# Delete archives older than retention period
find "$ARCHIVE_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Report storage usage
du -sh "$EVIDENCE_DIR" "$ARCHIVE_DIR"
```

Schedule via cron:
```bash
0 2 * * * /opt/certus/scripts/archive-old-evidence.sh
```

---

## Incident Response Playbook

### Scenario 1: Legitimate User Blocked

**Symptoms:** User reports 429 errors, support ticket created

**Response:**
1. Identify user's IP from support ticket
2. Check evidence files:
   ```bash
   EVIDENCE_DIR="/tmp/certus-evidence/integrity/rate-limit"
   IP="<user-ip>"

   cd "$EVIDENCE_DIR"
   jq -r --arg ip "$IP" 'select(.decision.metadata.client_ip==$ip)' dec_*.json | tail -5
   ```
3. Determine if traffic pattern is legitimate:
   - Scheduled batch job → Add to whitelist
   - Browser refresh spam → Educate user
   - Application bug → Fix application
4. Add to whitelist if appropriate:
   ```bash
   # Add to .env
   CURRENT_WHITELIST=$(grep INTEGRITY_WHITELIST_IPS .env | cut -d'=' -f2)
   sed -i.bak "s/INTEGRITY_WHITELIST_IPS=.*/INTEGRITY_WHITELIST_IPS=$CURRENT_WHITELIST,$IP/" .env
   docker compose -f certus_ask/deploy/docker-compose.yml restart
   ```
5. Document decision in IP classification file

### Scenario 2: Attack in Progress

**Symptoms:** Alerting fires, high denial rates from single IP

**Response:**
1. Confirm attack pattern:
   ```bash
   EVIDENCE_DIR="/tmp/certus-evidence/integrity/rate-limit"

   cd "$EVIDENCE_DIR"
   echo "Recent denied IPs:"
   jq -r 'select(.decision.decision=="denied") | .decision.metadata.client_ip' $(ls -t dec_*.json | head -50) | \
     sort | uniq -c | sort -rn | head -5
   ```
2. If rate limiting is insufficient, block at firewall:
   ```bash
   # Block at iptables (requires sudo)
   sudo iptables -A INPUT -s <attacker-ip> -j DROP
   ```
3. Collect evidence bundle for analysis:
   ```bash
   ATTACKER_IP="<attacker-ip>"
   mkdir -p /tmp/incident-$(date +%Y%m%d)

   cd "$EVIDENCE_DIR"
   jq -r --arg ip "$ATTACKER_IP" 'select(.decision.metadata.client_ip==$ip) | input_filename' dec_*.json | \
     xargs -I {} cp {} /tmp/incident-$(date +%Y%m%d)/

   tar -czf /tmp/incident-$(date +%Y%m%d).tar.gz /tmp/incident-$(date +%Y%m%d)/
   ```
4. Document incident in security log

### Scenario 3: False Positive Rate Too High

**Symptoms:** >5% of requests denied, user complaints

**Response:**
1. Analyze recent denials:
   ```bash
   EVIDENCE_DIR="/tmp/certus-evidence/integrity/rate-limit"

   cd "$EVIDENCE_DIR"
   echo "Denial rate over last 1000 decisions:"
   TOTAL=$(ls dec_*.json | wc -l | tr -d ' ')
   DENIED=$(jq -r 'select(.decision.decision=="denied")' dec_*.json | wc -l | tr -d ' ')
   echo "scale=2; ($DENIED * 100) / $TOTAL" | bc
   echo "%"
   ```
2. Temporarily increase limits:
   ```bash
   # Emergency mitigation - increase by 50%
   sed -i.bak 's/INTEGRITY_RATE_LIMIT_PER_MINUTE=.*/INTEGRITY_RATE_LIMIT_PER_MINUTE=90/' .env
   sed -i.bak 's/INTEGRITY_RATE_LIMIT_BURST=.*/INTEGRITY_RATE_LIMIT_BURST=30/' .env
   docker compose -f certus_ask/deploy/docker-compose.yml restart
   ```
3. Investigate root cause:
   - Check if traffic patterns changed (new feature launch, marketing campaign)
   - Review denied IPs for legitimate business use cases
   - Analyze time-of-day patterns
4. Adjust limits based on findings

---

## Best Practices

### Configuration Management

1. **Use GitOps:** Store rate limit configurations in version control
   ```bash
   # environments/production/integrity.env
   INTEGRITY_SHADOW_MODE=false
   INTEGRITY_WHITELIST_IPS=10.0.1.100,192.168.1.0/24
   INTEGRITY_RATE_LIMIT_PER_MINUTE=60
   INTEGRITY_RATE_LIMIT_BURST=20
   ```

2. **Document all changes:** Include reason, approver, and rollback plan
   ```yaml
   # CHANGELOG.md
   ## 2025-01-15
   - Increased rate limit to 60 req/min (was 45)
   - Reason: New mobile app release increased baseline traffic
   - Approved by: ops-team
   - Rollback: `git revert abc123 && ./deploy.sh`
   ```

3. **Test in staging first:** Always validate configuration changes in non-production

### Evidence Management

1. **Regular backups:** Archive evidence files to long-term storage (S3, GCS)
2. **Retention policy:** Keep detailed evidence for 90 days, aggregated metrics for 1 year
3. **Compliance:** Ensure evidence collection complies with GDPR, CCPA (IP anonymization)

### Monitoring

1. **SLOs:** Define acceptable denial rates (<1% for legitimate traffic)
2. **Alerting thresholds:** Alert on anomalies (>3x normal denial rate)
3. **Regular reviews:** Weekly review of top denied IPs and classification

---

## Next Steps

- **Compliance Reporting:** See [Compliance Reporting](../../../learn/integrity/compliance-reporting.md) for audit workflows
- **Incident Investigation:** See [Investigating Incidents](../../../learn/integrity/investigating-incidents.md) for forensic analysis
- **Advanced Configuration:** See [Configuration Guide](03-configuration.md) for all rate limiting options
- **Monitoring Setup:** See [Monitoring Guide](05-monitoring.md) for VictoriaMetrics and OpenSearch setup

---

## Support

- **Documentation:** [Certus Integrity Overview](01-overview.md)
- **Troubleshooting:** [Troubleshooting Guide](06-troubleshooting.md)
- **Community:** [GitHub Discussions](https://github.com/certus/certus-integrity/discussions)
