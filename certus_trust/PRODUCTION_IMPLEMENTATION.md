# Certus-Trust Production Implementation Guide

## Overview

This guide shows how to migrate from the mock Phase 1 implementation to a production-ready implementation using real Sigstore services (Rekor, Fulcio).

## What's Been Created

### 1. Dependencies Added

**File:** `pyproject.toml`

```toml
"sigstore>=3.0.0",        # Official Sigstore Python client
"cryptography>=41.0.0",   # Cryptographic operations
```

**Install:**

```bash
uv sync
```

### 2. Sigstore Client Wrappers

#### `certus_trust/clients/rekor_client.py`

- Submit entries to Rekor transparency log
- Query entries by UUID
- Search by artifact hash
- Get inclusion proofs

#### `certus_trust/clients/signing_client.py`

- Key-based signing (RSA/ECDSA)
- Keyless signing preparation
- Signature verification
- Artifact hashing

## Migration Steps

### Step 1: Update Router to Use Real Clients

Replace the mock signing in `api/router.py`:

**BEFORE (Mock):**

```python
@router.post("/v1/sign")
async def sign_artifact(request: SignRequest) -> SignResponse:
    # Mock signing
    entry_id = str(uuid.uuid4())
    response = SignResponse(
        entry_id=entry_id,
        signature=f"mock-signature-{entry_id[:8]}",
        certificate=f"mock-certificate-{entry_id[:8]}",
        ...
    )
    _signed_artifacts[entry_id] = {...}
    return response
```

**AFTER (Production):**

```python
from ..clients import RekorClient, SigningClient

# Initialize clients (do this in lifespan or dependency injection)
rekor_client = RekorClient(settings)
signing_client = SigningClient(settings)

@router.post("/v1/sign")
async def sign_artifact(request: SignRequest) -> SignResponse:
    # Convert artifact hash to bytes for signing
    artifact_bytes = bytes.fromhex(request.artifact.replace("sha256:", ""))

    # Real signing
    signature, certificate, artifact_hash = await signing_client.sign_artifact(
        artifact_bytes,
        use_keyless=settings.enable_keyless
    )

    # Submit to Rekor
    rekor_entry = await rekor_client.submit_entry(
        artifact_hash=artifact_hash,
        signature=signature,
        certificate=certificate
    )

    # Build response
    response = SignResponse(
        entry_id=rekor_entry["uuid"],
        signature=signature.hex(),
        certificate=certificate.decode() if certificate else None,
        transparency_entry=TransparencyEntry(
            uuid=rekor_entry["uuid"],
            index=rekor_entry["index"],
            timestamp=rekor_entry["integrated_time"],
        ),
    )

    return response
```

### Step 2: Update Verification Endpoint

**BEFORE (Mock):**

```python
@router.post("/v1/verify")
async def verify_signature(request: VerifyRequest) -> VerifyResponse:
    # Mock verification
    valid = True
    for idx, entry in enumerate(_transparency_log):
        if entry.signature == request.signature:
            valid = True
            break
    return VerifyResponse(valid=valid, ...)
```

**AFTER (Production):**

```python
@router.post("/v1/verify")
async def verify_signature(request: VerifyRequest) -> VerifyResponse:
    # Convert signature and artifact to bytes
    signature = bytes.fromhex(request.signature)
    artifact_bytes = bytes.fromhex(request.artifact.replace("sha256:", ""))

    # Verify signature cryptographically
    certificate = request.certificate.encode() if request.certificate else None

    is_valid = await signing_client.verify_signature(
        artifact_data=artifact_bytes,
        signature=signature,
        certificate=certificate
    )

    if not is_valid:
        return VerifyResponse(
            valid=False,
            verified_at=datetime.now(timezone.utc),
            signer="unknown",
            transparency_index=None
        )

    # Search Rekor for this artifact
    artifact_hash = signing_client.compute_artifact_hash(artifact_bytes)
    rekor_entries = await rekor_client.search_by_hash(artifact_hash)

    if not rekor_entries:
        return VerifyResponse(
            valid=False,
            verified_at=datetime.now(timezone.utc),
            signer="unknown",
            transparency_index=None
        )

    # Get first entry (most recent)
    entry = rekor_entries[0]

    return VerifyResponse(
        valid=True,
        verified_at=datetime.now(timezone.utc),
        signer=extract_signer_from_entry(entry),  # Helper function
        transparency_index=entry.get("logIndex"),
        certificate_chain=[certificate.decode()] if certificate else None
    )
```

### Step 3: Update Transparency Endpoints

**BEFORE (Mock):**

```python
@router.get("/v1/transparency/{entry_id}")
async def get_transparency_entry(entry_id: str) -> TransparencyLogEntry:
    for idx, entry in enumerate(_transparency_log):
        if entry.entry_id == entry_id:
            return entry
    raise HTTPException(status_code=404, detail="Not found")
```

**AFTER (Production):**

```python
@router.get("/v1/transparency/{entry_id}")
async def get_transparency_entry(
    entry_id: str,
    include_proof: bool = True
) -> TransparencyLogEntry:
    # Get entry from Rekor
    entry = await rekor_client.get_entry(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail=f"Entry {entry_id} not found")

    # Get inclusion proof if requested
    proof = None
    if include_proof:
        proof = await rekor_client.get_inclusion_proof(entry_id)

    # Convert to our model
    return TransparencyLogEntry(
        entry_id=entry_id,
        artifact=extract_artifact_from_entry(entry),  # Helper function
        timestamp=datetime.fromtimestamp(entry["integratedTime"], tz=timezone.utc),
        signer=extract_signer_from_entry(entry),
        signature=extract_signature_from_entry(entry),
        proof=proof
    )
```

### Step 4: Add Persistent Storage

Replace in-memory dictionaries with database:

**Create database models:**

```python
# certus_trust/models/database.py
from sqlalchemy import Column, String, DateTime, Integer, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class SignedArtifact(Base):
    __tablename__ = "signed_artifacts"

    id = Column(String, primary_key=True)  # UUID
    artifact_hash = Column(String, nullable=False, index=True)
    artifact_type = Column(String, nullable=False)
    subject = Column(String, nullable=False)
    signature = Column(String, nullable=False)
    certificate = Column(String, nullable=True)
    rekor_uuid = Column(String, nullable=False, unique=True, index=True)
    rekor_index = Column(Integer, nullable=False)
    integrated_time = Column(DateTime, nullable=False)
    predicates = Column(JSON, nullable=True)
    created_at = Column(DateTime, nullable=False)

class VerificationRecord(Base):
    __tablename__ = "verification_records"

    id = Column(String, primary_key=True)
    artifact_hash = Column(String, nullable=False, index=True)
    signature = Column(String, nullable=False)
    valid = Column(Boolean, nullable=False)
    signer = Column(String, nullable=True)
    verified_at = Column(DateTime, nullable=False)
    rekor_index = Column(Integer, nullable=True)
```

**Add to configuration:**

```python
# config.py
class CertusTrustSettings(BaseSettings):
    # ... existing settings ...

    # Database
    database_url: str = "postgresql://trust:trust@trust-db:5432/certus_trust"

    # Production mode
    mock_sigstore: bool = False  # Set to False for production
```

### Step 5: Update Docker Compose for Production

**Create `certus_trust/deploy/docker-compose.prod.yml`:**

```yaml
services:
  # PostgreSQL database for Trust service
  trust-db:
    image: postgres:15-alpine
    container_name: trust-db
    environment:
      - POSTGRES_DB=certus_trust
      - POSTGRES_USER=trust
      - POSTGRES_PASSWORD=trust
    volumes:
      - trust-db-data:/var/lib/postgresql/data
    networks:
      - certus-network
    healthcheck:
      test: ['CMD-SHELL', 'pg_isready -U trust']
      interval: 10s
      timeout: 5s
      retries: 5

  certus-trust:
    build:
      context: ../..
      dockerfile: certus_trust/Dockerfile
    container_name: certus-trust
    ports:
      - '8057:8000'
    env_file:
      - ../../.env
    environment:
      - SERVICE_NAME=certus-trust
      - LOG_LEVEL=INFO

      # Production mode
      - CERTUS_TRUST_MOCK_SIGSTORE=false
      - CERTUS_TRUST_ENABLE_KEYLESS=true
      - CERTUS_TRUST_ENABLE_TRANSPARENCY=true

      # Sigstore endpoints (real services)
      - CERTUS_TRUST_REKOR_ADDR=http://rekor:3000
      - CERTUS_TRUST_FULCIO_ADDR=http://fulcio:5555

      # Database
      - CERTUS_TRUST_DATABASE_URL=postgresql://trust:trust@trust-db:5432/certus_trust

      # Infrastructure
      - LOCALSTACK_ENDPOINT=http://localstack:4566
      - VICTORIAMETRICS_URL=http://victoriametrics:8428
    depends_on:
      trust-db:
        condition: service_healthy
      rekor:
        condition: service_healthy
      fulcio:
        condition: service_started
    networks:
      - certus-network
    healthcheck:
      test: ['CMD', 'curl', '-f', 'http://localhost:8000/v1/health']
      interval: 30s
      timeout: 10s
      retries: 3

volumes:
  trust-db-data:

networks:
  certus-network:
    external: true
    name: certus-network
```

### Step 6: Add Database Migrations

**Install Alembic:**

```bash
uv add alembic
```

**Initialize:**

```bash
cd certus_trust
alembic init alembic
```

**Create first migration:**

```bash
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### Step 7: Update Main Application

**Add lifespan for client initialization:**

```python
# main.py
from contextlib import asynccontextmanager
from .clients import RekorClient, SigningClient

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Sigstore clients
    settings = get_settings()

    if not settings.mock_sigstore:
        app.state.rekor_client = RekorClient(settings)
        app.state.signing_client = SigningClient(settings)
        logger.info("Initialized production Sigstore clients")
    else:
        app.state.rekor_client = None
        app.state.signing_client = None
        logger.info("Running in mock mode")

    yield

    # Cleanup
    logger.info("Shutting down Sigstore clients")
```

**Use dependency injection in routes:**

```python
# api/router.py
from fastapi import Depends, Request

def get_rekor_client(request: Request) -> Optional[RekorClient]:
    return request.app.state.rekor_client

def get_signing_client(request: Request) -> Optional[SigningClient]:
    return request.app.state.signing_client

@router.post("/v1/sign")
async def sign_artifact(
    request: SignRequest,
    rekor: Optional[RekorClient] = Depends(get_rekor_client),
    signer: Optional[SigningClient] = Depends(get_signing_client),
) -> SignResponse:
    if not rekor or not signer:
        # Fall back to mock implementation
        return mock_sign_artifact(request)

    # Use real implementation
    return await real_sign_artifact(request, rekor, signer)
```

## Testing Production Implementation

### 1. Start Sigstore Infrastructure

```bash
# Start Rekor, Trillian, Fulcio
just up
# Or specifically:
docker compose -f certus_infrastructure/docker-compose.sigstore.yml up -d
```

### 2. Verify Services Running

```bash
# Check Rekor
curl http://localhost:3001/api/v1/log

# Check Fulcio
curl http://localhost:5555/healthz
```

### 3. Start Trust Service in Production Mode

```bash
docker compose -f certus_trust/deploy/docker-compose.prod.yml up -d
```

### 4. Test Signing

```bash
curl -X POST http://localhost:8057/v1/sign \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123...",
    "artifact_type": "sbom",
    "subject": "myapp:v1.0.0"
  }'
```

### 5. Verify in Rekor

```bash
# Get the entry_id from the response above
curl http://localhost:3001/api/v1/log/entries/{entry_id}
```

### 6. Test Verification

```bash
curl -X POST http://localhost:8057/v1/verify \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123...",
    "signature": "...",
    "certificate": "..."
  }'
```

## Rollback Plan

If production implementation has issues, you can roll back to mock:

```bash
# Set environment variable
export CERTUS_TRUST_MOCK_SIGSTORE=true

# Or use rollback compose
docker compose -f certus_trust/deploy/docker-compose.rollback.yml up -d
```

## Monitoring Production

### Key Metrics to Track

1. **Signing Operations**
   - Total signatures created
   - Success/failure rate
   - Latency (time to sign + submit to Rekor)

2. **Verification Operations**
   - Total verifications
   - Valid vs invalid ratio
   - Latency (time to verify + check Rekor)

3. **Rekor Interactions**
   - Submission success rate
   - Query latency
   - Inclusion proof generation time

4. **Database Performance**
   - Query latency
   - Connection pool usage
   - Storage growth

### Add Prometheus Metrics

```python
from prometheus_client import Counter, Histogram

signing_total = Counter(
    'certus_trust_signing_total',
    'Total signing operations',
    ['status', 'artifact_type']
)

signing_duration = Histogram(
    'certus_trust_signing_duration_seconds',
    'Time to sign and submit to Rekor'
)

verification_total = Counter(
    'certus_trust_verification_total',
    'Total verification operations',
    ['valid']
)
```

## Security Considerations

### 1. Key Management

- **Never commit private keys** to version control
- Use secrets management (HashiCorp Vault, AWS Secrets Manager)
- Rotate keys regularly
- Use keyless signing (Fulcio) when possible

### 2. Network Security

- TLS for all Sigstore communication in production
- Network policies to restrict access
- Rate limiting on endpoints

### 3. Audit Logging

- Log all signing operations
- Log all verification requests
- Store logs in centralized system (Elasticsearch, Splunk)

### 4. Access Control

- Implement authentication (JWT, API keys)
- Role-based access control (RBAC)
- Audit who can sign/verify

## Performance Optimization

### 1. Caching

```python
from aiocache import caches

# Cache Rekor entries
caches.set_config({
    'default': {
        'cache': "aiocache.SimpleMemoryCache",
        'serializer': {
            'class': "aiocache.serializers.JsonSerializer"
        }
    }
})

@cached(ttl=3600)  # Cache for 1 hour
async def get_rekor_entry_cached(uuid: str):
    return await rekor_client.get_entry(uuid)
```

### 2. Connection Pooling

```python
# Use connection pool for database
from sqlalchemy.pool import QueuePool

engine = create_async_engine(
    settings.database_url,
    poolclass=QueuePool,
    pool_size=20,
    max_overflow=10
)
```

### 3. Batch Operations

```python
# Submit multiple entries to Rekor in batch
async def submit_batch(artifacts: List[Artifact]):
    tasks = [
        rekor_client.submit_entry(...)
        for artifact in artifacts
    ]
    return await asyncio.gather(*tasks)
```

## Next Steps

1. ✅ Install dependencies: `uv sync`
2. ✅ Test Rekor/Fulcio connectivity
3. ⬜ Implement production router changes
4. ⬜ Add database models and migrations
5. ⬜ Update docker-compose for production
6. ⬜ Add monitoring and metrics
7. ⬜ Security hardening (auth, TLS, rate limiting)
8. ⬜ Load testing
9. ⬜ Documentation updates

## Support

For questions or issues:

- Review Sigstore documentation: https://docs.sigstore.dev/
- Check sigstore-python docs: https://github.com/sigstore/sigstore-python
- Open an issue in the repository
