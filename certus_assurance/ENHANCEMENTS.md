# Certus Assurance Enhancements (Post-Tier 0)

**Date:** 2025-12-13
**Status:** Implemented

This document describes enhancements added to `certus_assurance` after completing Tier 0 of the implementation roadmap.

## Overview

One enhancement was implemented to improve observability and align with certus_trust and certus_transform:

1. **Stats & Observability Endpoint** - Monitor service activity

---

## 1. Stats & Observability Endpoint

### Endpoint: `GET /stats`

Returns service activity statistics for monitoring and debugging.

**Response:**
```json
{
  "total_scans": 42,
  "scans_by_status": {
    "queued": 2,
    "running": 3,
    "succeeded": 35,
    "failed": 2
  },
  "upload_stats": {
    "pending": 5,
    "permitted": 30,
    "uploaded": 28,
    "denied": 2
  },
  "active_streams": 3,
  "timestamp": "2025-12-13T19:30:45Z"
}
```

**Implementation:**
- Queries in-memory job manager for current state
- Counts jobs by status (queued, running, succeeded, failed)
- Tracks upload workflow stages (pending, permitted, uploaded, denied)
- Shows active WebSocket streams
- Located in `certus_assurance/service.py`

**Usage:**
```bash
# Manual check
curl http://localhost:8056/stats | jq

# Prometheus scraping
GET http://certus-assurance:8056/stats

# Kubernetes health probe
livenessProbe:
  httpGet:
    path: /stats
    port: 8056
```

**Metrics Tracked:**
- `total_scans` - Total scans submitted since service start
- `scans_by_status.queued` - Scans waiting to run
- `scans_by_status.running` - Scans currently executing
- `scans_by_status.succeeded` - Completed successfully
- `scans_by_status.failed` - Failed scans
- `upload_stats.pending` - Upload requests not yet submitted to Trust
- `upload_stats.permitted` - Trust granted permission
- `upload_stats.uploaded` - Artifacts uploaded to S3
- `upload_stats.denied` - Trust denied upload
- `active_streams` - Active WebSocket connections for log streaming

**Design Consistency:**

Matches the pattern used in `certus_trust` and `certus_transform`:
- Simple JSON response (not Prometheus format yet)
- In-memory statistics (reset on restart)
- Accessed via `/stats` endpoint
- Returns timestamp for monitoring staleness

**Files Modified:**
- `certus_assurance/service.py` - Added stats endpoint and models

**Example Monitoring Queries:**

```bash
# Check for stuck scans (running too long)
curl -s http://localhost:8056/stats | jq '.scans_by_status.running'

# Monitor upload success rate
curl -s http://localhost:8056/stats | jq '.upload_stats'

# Check active WebSocket connections
curl -s http://localhost:8056/stats | jq '.active_streams'

# Alert if too many failures
FAILED=$(curl -s http://localhost:8056/stats | jq '.scans_by_status.failed')
if [ "$FAILED" -gt 10 ]; then
  echo "Alert: Too many failed scans!"
fi
```

**Integration with Monitoring Stack:**

```python
# Prometheus exporter (future enhancement)
from prometheus_client import Gauge

scans_total = Gauge('certus_assurance_scans_total', 'Total scans')
scans_by_status = Gauge('certus_assurance_scans_status', 'Scans by status', ['status'])

@app.get("/metrics")
async def metrics():
    stats = await get_stats()
    scans_total.set(stats.total_scans)
    for status, count in stats.scans_by_status.items():
        scans_by_status.labels(status=status).set(count)
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
```

---

## Testing

### Manual Testing

```bash
# Start certus_assurance
uvicorn certus_assurance.service:app --port 8056

# Check stats (should show 0 scans initially)
curl http://localhost:8056/stats | jq

# Submit a scan
curl -X POST http://localhost:8056/v1/security-scans \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "test",
    "component_id": "test-component",
    "assessment_id": "test-assessment",
    "git_url": "https://github.com/example/repo",
    "branch": "main",
    "profile": "light"
  }'

# Check stats again (should show 1 scan)
curl http://localhost:8056/stats | jq
# Expected: total_scans: 1, scans_by_status.queued: 1 or running: 1

# Wait for scan to complete
sleep 60

# Check final stats
curl http://localhost:8056/stats | jq
# Expected: scans_by_status.succeeded: 1
```

### Integration Testing

```python
# tests/test_stats.py
import httpx
import pytest

@pytest.mark.asyncio
async def test_stats_endpoint():
    async with httpx.AsyncClient(base_url="http://localhost:8056") as client:
        response = await client.get("/stats")
        assert response.status_code == 200

        data = response.json()
        assert "total_scans" in data
        assert "scans_by_status" in data
        assert "upload_stats" in data
        assert "active_streams" in data
        assert "timestamp" in data

@pytest.mark.asyncio
async def test_stats_after_scan():
    async with httpx.AsyncClient(base_url="http://localhost:8056") as client:
        # Submit scan
        scan_response = await client.post("/v1/security-scans", json={
            "workspace_id": "test",
            "component_id": "test",
            "assessment_id": "test",
            "git_url": "https://github.com/example/repo",
            "profile": "light"
        })
        assert scan_response.status_code == 202

        # Check stats incremented
        stats_response = await client.get("/stats")
        stats = stats_response.json()
        assert stats["total_scans"] >= 1
        assert stats["scans_by_status"]["queued"] + stats["scans_by_status"]["running"] >= 1
```

---

## Migration Notes

### No Breaking Changes

The stats endpoint is **additive only**:
- New `/stats` endpoint (no existing consumers)
- No changes to existing API endpoints
- No database schema changes

### Deployment

No special deployment steps needed:
1. Deploy updated `certus_assurance` service
2. Stats are immediately available via `/stats`
3. In-memory counters start at current job state

### Monitoring

After deployment, monitor:
- `GET /stats` - Verify endpoint returns valid JSON
- Stats accuracy - Compare with actual job submissions
- Performance - Endpoint should respond in < 100ms

---

## Future Enhancements (Not Implemented)

### Deferred to Tier 1+

1. **Batch Scan Submission** (Tier 1)
   - Submit multiple scans in one request
   - Reduces API overhead for AI agents
   - Effort: 2 hours

2. **List/Query Scans Endpoint** (Tier 1)
   - `GET /v1/security-scans?workspace_id=X&status=SUCCEEDED`
   - Filter by workspace, assessment, status
   - Pagination support
   - Effort: 2 hours

3. **Scan Timeout Configuration** (Tier 1)
   - Configurable timeout per scan (default 10 minutes)
   - Prevents indefinite hanging
   - Effort: 1 hour

4. **Prometheus Metrics** (Production)
   - Upgrade from JSON stats to Prometheus format
   - Time-series storage and Grafana dashboards
   - Effort: 4 hours

5. **Persistent Job Storage** (Tier 2)
   - SQLite or JSON file backing for jobs
   - Survive service restarts
   - Audit trail and debugging
   - Effort: 6 hours

---

## Comparison with Other Services

All three services now have consistent stats endpoints:

| Service | Endpoint | Key Metrics |
|---------|----------|-------------|
| **certus_trust** | `GET /v1/stats` | Signatures, verifications, transparency entries |
| **certus_transform** | `GET /health/stats` | Uploads, privacy scans, promotions |
| **certus_assurance** | `GET /stats` | Scans by status, uploads, active streams |

**Design Philosophy:**
- Simple JSON (not Prometheus format yet)
- In-memory counters (stateless)
- Read-only (no POST/PUT/DELETE)
- Fast response (< 100ms)
- Consistent structure across services

---

## Files Changed Summary

```
certus_assurance/
├── service.py             [MODIFIED] - Added stats endpoint and models
└── ENHANCEMENTS.md        [NEW] - This document
```

**Total Lines Changed:** ~60 lines added
**Effort:** 1 hour
**Breaking Changes:** None
**Migration Required:** No

---

## Related Documentation

- [certus_trust/MOCK_FEATURES.md](../certus_trust/MOCK_FEATURES.md) - Trust service stats
- [certus_transform/ENHANCEMENTS.md](../certus_transform/ENHANCEMENTS.md) - Transform service stats
- [Implementation Priority](../docs/reference/roadmap/implementation-priority.md) - Tier 0 roadmap
