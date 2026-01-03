# Certus-Trust Toggle Implementation Guide

## Overview

The toggle system allows you to switch between **mock** and **production** Sigstore implementations with a single environment variable:

```bash
# Development/Testing - Mock mode (fast, in-memory)
export CERTUS_TRUST_MOCK_SIGSTORE=true

# Staging/Production - Real Sigstore
export CERTUS_TRUST_MOCK_SIGSTORE=false
```

**No code changes required!** The same codebase works in both modes.

## What's Been Implemented

### 1. Service Layer (Strategy Pattern)

Three service interfaces with mock and production implementations:

```
certus_trust/services/
├── __init__.py
├── signing_service.py          # SigningService (mock + production)
├── verification_service.py     # VerificationService (mock + production)
└── transparency_service.py     # TransparencyService (mock + production)
```

Each service has:

- **Abstract base class** (interface)
- **Mock implementation** (in-memory, fast)
- **Production implementation** (real Sigstore)
- **Dependency injection function** (auto-selects based on config)

### 2. Updated Configuration

```python
# config.py
class CertusTrustSettings(BaseSettings):
    mock_sigstore: bool = True  # Toggle here!
```

Environment variable: `CERTUS_TRUST_MOCK_SIGSTORE`

### 3. Client Initialization in main.py

```python
# Automatically initializes production clients only when needed
if not settings.mock_sigstore:
    app.state.rekor_client = RekorClient(settings)
    app.state.signing_client = SigningClient(settings)
else:
    # Mock mode - no clients needed
    pass
```

### 4. Example Router (router_v2.py)

Shows how to use the new pattern:

```python
@router.post("/v2/sign")
async def sign_artifact_v2(
    request: SignRequest,
    signing_service: SigningService = Depends(get_signing_service),  # Auto mock/prod!
):
    return await signing_service.sign(request)
```

## How to Use

### Quick Start

```bash
# 1. Install dependencies
uv sync

# 2. Start with mock (default)
export CERTUS_TRUST_MOCK_SIGSTORE=true
./scripts/deploy-trust-production.sh start

# 3. Test mock mode
curl -X POST http://localhost:8057/v2/sign -d '{...}'

# 4. Switch to production
export CERTUS_TRUST_MOCK_SIGSTORE=false
docker compose -f certus_trust/deploy/docker-compose.prod.yml restart

# 5. Test production mode
curl -X POST http://localhost:8057/v2/sign -d '{...}'
```

### Check Current Mode

```bash
curl http://localhost:8057/v2/mode
```

Response:

```json
{
  "mode": "mock",
  "mock_sigstore": true,
  "message": "Running in MOCK mode. Set CERTUS_TRUST_MOCK_SIGSTORE=false for production."
}
```

## Migration Path

### Option 1: Gradual Migration (Recommended)

Keep existing `/v1/*` endpoints using mock, add new `/v2/*` endpoints with toggle:

1. ✅ Existing `/v1/sign` → keeps working with mock
2. ✅ New `/v2/sign` → supports mock/production toggle
3. ✅ Gradually migrate users from v1 to v2
4. ✅ Eventually deprecate v1

**File structure:**

```
api/
├── router.py     # v1 endpoints (existing mock)
└── router_v2.py  # v2 endpoints (toggle support)
```

**In main.py:**

```python
app.include_router(router, prefix="", tags=["trust"])      # v1
app.include_router(router_v2, prefix="", tags=["trust"])   # v2
```

### Option 2: In-Place Migration (Breaking Change)

Replace mock code in existing `router.py` with toggle pattern:

**BEFORE:**

```python
# api/router.py
_signed_artifacts: Dict[str, Any] = {}  # Global mock storage

@router.post("/v1/sign")
async def sign_artifact(request: SignRequest):
    # Mock implementation
    entry_id = str(uuid.uuid4())
    signature = f"mock-signature-{entry_id[:8]}"
    ...
```

**AFTER:**

```python
# api/router.py
from ..services import SigningService, get_signing_service

@router.post("/v1/sign")
async def sign_artifact(
    request: SignRequest,
    signing_service: SigningService = Depends(get_signing_service),
):
    return await signing_service.sign(request)
```

**Steps:**

1. Import service dependencies
2. Replace function signature with `Depends()`
3. Delete global mock storage variables
4. Call service method instead of inline mock code
5. Test both modes

### Option 3: Hybrid Mode

Run both v1 (mock) and v2 (toggle) in parallel:

```python
# main.py
app.include_router(router, prefix="/v1", tags=["trust-v1-mock"])
app.include_router(router_v2, prefix="/v2", tags=["trust-v2-toggle"])
```

Users can choose:

- `/v1/*` - Always mock (stable, backward compatible)
- `/v2/*` - Toggle support (new features)

## Environment Configuration

### Development

```bash
# .env.dev
CERTUS_TRUST_MOCK_SIGSTORE=true
CERTUS_TRUST_ENABLE_KEYLESS=false
CERTUS_TRUST_ENABLE_TRANSPARENCY=false
```

### Staging

```bash
# .env.staging
CERTUS_TRUST_MOCK_SIGSTORE=false
CERTUS_TRUST_ENABLE_KEYLESS=true
CERTUS_TRUST_ENABLE_TRANSPARENCY=true
CERTUS_TRUST_REKOR_ADDR=http://rekor:3000
CERTUS_TRUST_FULCIO_ADDR=http://fulcio:5555
```

### Production

```bash
# .env.prod
CERTUS_TRUST_MOCK_SIGSTORE=false
CERTUS_TRUST_ENABLE_KEYLESS=true
CERTUS_TRUST_ENABLE_TRANSPARENCY=true
CERTUS_TRUST_REKOR_ADDR=https://rekor.sigstore.dev
CERTUS_TRUST_FULCIO_ADDR=https://fulcio.sigstore.dev
```

## Docker Compose Configurations

### Development (Mock)

```yaml
# docker-compose.dev.yml
services:
  certus-trust:
    environment:
      - CERTUS_TRUST_MOCK_SIGSTORE=true
    # No dependencies on Rekor/Fulcio needed
```

### Production (Real Sigstore)

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

## Testing

### Test Mock Mode

```bash
# Start in mock mode
export CERTUS_TRUST_MOCK_SIGSTORE=true
uvicorn certus_trust.main:app --reload

# Test signing
curl -X POST http://localhost:8888/v2/sign \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123",
    "artifact_type": "sbom",
    "subject": "test:v1.0.0"
  }'

# Should return immediately with mock signature
```

### Test Production Mode

```bash
# Start Sigstore infrastructure
docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d

# Start in production mode
export CERTUS_TRUST_MOCK_SIGSTORE=false
uvicorn certus_trust.main:app --reload

# Test signing
curl -X POST http://localhost:8888/v2/sign \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123",
    "artifact_type": "sbom",
    "subject": "test:v1.0.0"
  }'

# Should return with real Rekor entry
# Verify in Rekor
curl http://localhost:3001/api/v1/log/entries/{entry_id}
```

### Automated Tests

```python
# tests/test_toggle.py
import pytest
from certus_trust.config import CertusTrustSettings

def test_mock_mode():
    """Test signing in mock mode."""
    settings = CertusTrustSettings(mock_sigstore=True)
    # ... test logic

def test_production_mode():
    """Test signing in production mode."""
    settings = CertusTrustSettings(mock_sigstore=False)
    # ... test logic
```

## Logging

The service logs the current mode:

**Mock mode:**

```
INFO - Running in MOCK mode (set CERTUS_TRUST_MOCK_SIGSTORE=false for production)
INFO - [MOCK] Signed artifact sbom: abc-123
INFO - [MOCK] Verified signature: True
```

**Production mode:**

```
INFO - Initializing production Sigstore clients...
INFO - ✓ Production Sigstore clients initialized
INFO - [PRODUCTION] Signed artifact sbom: abc-123 (Rekor index: 12345)
INFO - [PRODUCTION] Verified signature successfully (Rekor index: 12345)
```

## Monitoring

Add metrics to track mode usage:

```python
from prometheus_client import Counter

mode_counter = Counter(
    'certus_trust_mode',
    'Service mode (mock or production)',
    ['mode']
)

# In lifespan
if settings.mock_sigstore:
    mode_counter.labels(mode='mock').inc()
else:
    mode_counter.labels(mode='production').inc()
```

## Troubleshooting

### Issue: Service starts in wrong mode

**Check:**

```bash
# View environment variables
docker compose exec certus-trust env | grep MOCK

# Check logs
docker compose logs certus-trust | grep -i mode
```

**Fix:**

```bash
# Update environment variable
export CERTUS_TRUST_MOCK_SIGSTORE=false

# Restart service
docker compose restart certus-trust
```

### Issue: Production mode fails to connect to Sigstore

**Check:**

```bash
# Verify Rekor is running
curl http://localhost:3001/api/v1/log

# Verify Fulcio is running
curl http://localhost:5555/healthz

# Check logs
docker compose logs rekor
docker compose logs fulcio
```

**Fix:**

```bash
# Restart Sigstore infrastructure
docker compose -f certus_infrastructure/docker-compose.sigstore.yml restart
```

### Issue: Dependencies not found

**Check:**

```bash
# Verify sigstore library installed
uv run python -c "import sigstore; print(sigstore.__version__)"
```

**Fix:**

```bash
# Reinstall dependencies
uv sync
```

## Best Practices

1. **Default to Mock** - Keep `mock_sigstore=true` as default for safety
2. **Explicit Production** - Require explicit `=false` for production
3. **Environment-Based** - Use different env files per environment
4. **Graceful Degradation** - If Sigstore fails, log error but don't crash
5. **Monitoring** - Track which mode is being used in production
6. **Testing** - Test both modes in CI/CD
7. **Documentation** - Document mode in API responses

## Summary

✅ **What You Get:**

- Single codebase for dev and production
- Zero code changes to switch modes
- Backward compatible with existing mock
- Gradual migration path
- Easy testing of both modes

✅ **Files Created:**

- `services/signing_service.py` - Sign with mock/production
- `services/verification_service.py` - Verify with mock/production
- `services/transparency_service.py` - Query log with mock/production
- `api/router_v2.py` - Example endpoints with toggle
- `config.py` - Updated with `mock_sigstore` flag
- `main.py` - Updated with client initialization

✅ **Next Steps:**

1. Test mock mode works
2. Test production mode works
3. Migrate existing endpoints (or keep v1 + add v2)
4. Update docker-compose files
5. Deploy to staging with toggle
6. Monitor and verify
7. Deploy to production

**Your toggle system is ready to use!** 🎉
