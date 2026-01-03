# Integrity Tutorial - Setup Complete

## Summary

The Certus Integrity tutorial environment has been fully configured and is now working end-to-end.

## Issues Fixed

### 1. Evidence File Naming Pattern

**Problem**: Code was saving files as `{uuid}.json` but tutorial expected `dec_*.json`

**Solution**:

- Updated `certus_integrity/evidence.py:109` to add `dec_` prefix
- Updated 3 unit tests to expect the new pattern
- Updated 13 locations in `docs/learn/integrity/compliance-reporting.md`

### 2. X-Forwarded-For Header Support

**Problem**: Middleware ignored `X-Forwarded-For` header, so all requests appeared as `127.0.0.1` (whitelisted)

**Solution**:

- Added X-Forwarded-For parsing to `certus_integrity/middleware.py:139-144`
- Now properly extracts client IP from proxy headers for rate limiting

### 3. Evidence Directory Permissions

**Problem**: Docker container couldn't write to `/tmp/evidence` due to permission issues on macOS

**Solution**:

- Changed evidence directory to `~/certus-evidence` (user home directory)
- Updated `certus_ask/deploy/docker-compose.yml` volume mount
- Set proper permissions (777) for container write access

### 4. VictoriaMetrics Metrics Collection

**Problem**: Metrics were exported to Prometheus format but VictoriaMetrics wasn't scraping them

**Solution**:

- Created `docker/victoriametrics/prometheus.yml` scrape configuration
- Updated `certus_infrastructure/docker-compose.yml` to mount config and add scrape flags
- VictoriaMetrics now scrapes OTEL collector on port 8889

## Verification

✅ **Evidence Generation**: Files created with `dec_*.json` pattern in `~/certus-evidence/`
✅ **X-Forwarded-For**: Client IPs properly captured and rate-limited
✅ **VictoriaMetrics**: Metrics visible with proper aggregation
✅ **Tutorial Workflow**: Compliance reporting tutorial now works end-to-end

## Quick Start

```bash
# Start the integrity environment
just integrity-up

# Wait for services to be ready (10-15 seconds)
sleep 15

# Generate test traffic
for i in {1..20}; do
  curl -s -H "X-Forwarded-For: 192.168.1.100" "${CERTUS_ASK_URL}/v1/health" >/dev/null
done

# Generate burst traffic to trigger rate limits
for i in {1..100}; do
  curl -s -H "X-Forwarded-For: 10.0.0.250" "${CERTUS_ASK_URL}/v1/health" >/dev/null &
done
wait

# Check evidence bundles
export EVIDENCE_DIR="$HOME/certus-evidence"
find $EVIDENCE_DIR -name "dec_*.json" | head -5

# Check metrics
curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=sum(certus_integrity_decisions_total)by(decision)" | jq
```

## Files Modified

### Code Changes

- `certus_integrity/evidence.py` - Added `dec_` prefix to filenames
- `certus_integrity/middleware.py` - Added X-Forwarded-For support
- `certus_integrity/tests/unit/test_evidence.py` - Updated 3 test cases
- `certus_ask/deploy/docker-compose.yml` - Changed evidence volume mount

### Infrastructure Changes

- `certus_infrastructure/docker-compose.yml` - Added VictoriaMetrics scrape config
- `docker/victoriametrics/prometheus.yml` - Created scrape configuration

### Documentation Changes

- `docs/learn/integrity/compliance-reporting.md` - Updated 13 file pattern references

## Environment Configuration

Required environment variables in `.env`:

```bash
INTEGRITY_SHADOW_MODE=false
INTEGRITY_RATE_LIMIT_PER_MIN=100
INTEGRITY_BURST_LIMIT=20
INTEGRITY_WHITELIST_IPS=127.0.0.1
```

## Evidence Location

Evidence bundles are now stored in: `~/certus-evidence/`

You can change this by setting the `EVIDENCE_DIR` environment variable before running the tutorial.

## Metrics Available

- `certus_integrity_decisions_total` - Total decisions by type (allowed/denied)
- `certus_integrity_check_duration_seconds` - Duration of integrity checks
- `certus_integrity_rate_limit_violations_total` - Rate limit violations

Query example:

```bash
curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=certus_integrity_decisions_total" | jq
```

## Next Steps

1. Follow the compliance reporting tutorial: `docs/learn/integrity/compliance-reporting.md`
2. Generate synthetic workload as described in the tutorial
3. Run audit queries to extract evidence for your compliance period
4. Export evidence bundles for auditors

## Troubleshooting

### No evidence files created

- Check docker logs: `docker logs ask-certus-backend`
- Verify permissions: `ls -ld ~/certus-evidence`
- Ensure X-Forwarded-For header is set (IPs must NOT be whitelisted)

### No metrics in VictoriaMetrics

- Wait 15-30 seconds for scraping to occur
- Check OTEL collector metrics: `curl ${OTEL_COLLECTOR_METRICS}/metrics | grep integrity`
- Verify VictoriaMetrics is scraping: `docker logs victoriametrics | grep promscrape`

### Rate limits not triggering

- Ensure `INTEGRITY_SHADOW_MODE=false` in `.env`
- Use non-whitelisted IP in X-Forwarded-For header
- Send >100 requests per minute from same IP

## Success Criteria

✅ `just integrity-up` starts all services
✅ Evidence files appear in `~/certus-evidence/dec_*.json`
✅ VictoriaMetrics shows `certus_integrity_decisions_total` metric
✅ Rate limits trigger when sending burst traffic
✅ Tutorial compliance reporting scripts work correctly
