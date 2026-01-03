# Certus-Trust Quick Start Guide

## Toggle Between Mock and Production

### One Environment Variable Controls Everything

```bash
# Mock Mode (Development/Testing)
export CERTUS_TRUST_MOCK_SIGSTORE=true

# Production Mode (Staging/Production)
export CERTUS_TRUST_MOCK_SIGSTORE=false
```

## Quick Commands

### Check Current Mode

```bash
curl http://localhost:8057/v2/mode
```

### Start in Mock Mode

```bash
export CERTUS_TRUST_MOCK_SIGSTORE=true
./scripts/deploy-trust-production.sh start
```

### Start in Production Mode

```bash
export CERTUS_TRUST_MOCK_SIGSTORE=false
./scripts/deploy-trust-production.sh start
```

### Switch Modes (Without Rebuild)

```bash
# Update environment variable in docker-compose
docker compose -f certus_trust/deploy/docker-compose.prod.yml \
  exec certus-trust sh -c 'export CERTUS_TRUST_MOCK_SIGSTORE=false'

# Restart service
docker compose -f certus_trust/deploy/docker-compose.prod.yml restart
```

## Test Both Modes

### Test Sign Endpoint

**Mock Mode:**

```bash
curl -X POST http://localhost:8057/v2/sign \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123def456",
    "artifact_type": "sbom",
    "subject": "myapp:v1.0.0"
  }'

# Returns immediately with mock signature
# Logs show: [MOCK] Signed artifact...
```

**Production Mode:**

```bash
curl -X POST http://localhost:8057/v2/sign \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123def456",
    "artifact_type": "sbom",
    "subject": "myapp:v1.0.0"
  }'

# Takes longer (real crypto + Rekor submission)
# Logs show: [PRODUCTION] Signed artifact... (Rekor index: 123)
# Verify in Rekor: curl http://localhost:3001/api/v1/log/entries/{entry_id}
```

## Migration Paths

### Path 1: Add v2 Endpoints (Recommended)

**Keep existing v1 (mock), add new v2 (toggle):**

```python
# In main.py
from .api import router      # v1 - existing mock
from .api import router_v2   # v2 - new toggle support

app.include_router(router, prefix="", tags=["trust-v1"])
app.include_router(router_v2, prefix="", tags=["trust-v2"])
```

**Result:**

- `/v1/sign` - Always mock
- `/v2/sign` - Toggle support

### Path 2: In-Place Migration

**Update existing router.py:**

```python
# BEFORE (mock)
@router.post("/v1/sign")
async def sign_artifact(request: SignRequest):
    entry_id = str(uuid.uuid4())
    signature = f"mock-signature-{entry_id[:8]}"
    ...

# AFTER (toggle)
from ..services import SigningService, get_signing_service

@router.post("/v1/sign")
async def sign_artifact(
    request: SignRequest,
    signing_service: SigningService = Depends(get_signing_service),
):
    return await signing_service.sign(request)
```

## Docker Compose Configs

### Dev (Mock)

```yaml
# docker-compose.dev.yml
services:
  certus-trust:
    environment:
      - CERTUS_TRUST_MOCK_SIGSTORE=true
    # No Sigstore dependencies needed
```

### Prod (Real Sigstore)

```yaml
# docker-compose.prod.yml
services:
  certus-trust:
    environment:
      - CERTUS_TRUST_MOCK_SIGSTORE=false
    depends_on:
      - rekor
      - fulcio
```

## Files You Need to Know

### New Files (Toggle Implementation)

- `services/signing_service.py` - Mock + Production signing
- `services/verification_service.py` - Mock + Production verification
- `services/transparency_service.py` - Mock + Production transparency
- `api/router_v2.py` - Example endpoints with toggle

### Updated Files

- `config.py` - Added `mock_sigstore` toggle
- `main.py` - Added client initialization

### Unchanged Files (Still Work)

- `api/router.py` - v1 endpoints with mock
- `clients/*` - Production Sigstore clients

## Common Issues

### Issue: Mode doesn't change after export

**Solution:**

```bash
# The environment variable needs to be in docker-compose
# Edit docker-compose file directly:
environment:
  - CERTUS_TRUST_MOCK_SIGSTORE=false

# Then restart
docker compose restart certus-trust
```

### Issue: Production mode can't connect to Sigstore

**Check infrastructure:**

```bash
# Verify Rekor is running
curl http://localhost:3001/api/v1/log

# Verify Fulcio is running
curl http://localhost:5555/healthz

# If not running, start Sigstore
docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d
```

### Issue: Dependencies not installed

**Solution:**

```bash
uv sync
```

## Complete Documentation

- **Toggle Implementation**: `TOGGLE_IMPLEMENTATION.md`
- **Production Setup**: `PRODUCTION_IMPLEMENTATION.md`
- **Deployment Script**: `scripts/deploy-trust-production.sh`

## Key Takeaways

✅ **One Variable**: `CERTUS_TRUST_MOCK_SIGSTORE` controls everything
✅ **Zero Code Changes**: Same codebase for dev and production
✅ **Backward Compatible**: Existing v1 endpoints unchanged
✅ **Easy Testing**: Switch modes anytime
✅ **Production Ready**: Real Sigstore when you need it

**You're all set!** 🚀
