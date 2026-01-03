# Certus-Trust Service

**Supply Chain Integrity Service using Sigstore Stack**

Certus-Trust provides cryptographic signing, verification, and transparency for assessment artifacts using the Sigstore infrastructure (Fulcio, Rekor, TUF, Keycloak).

## Phase 1-3 Implementation Status

### ✅ Phase 1: FastAPI Skeleton + Configuration
- [x] FastAPI application with lifespan management
- [x] Configuration via environment variables (.env.trust)
- [x] Structured logging setup
- [x] CORS middleware
- [x] Request ID tracking
- [x] Exception handling

### ✅ Phase 2: Core Signing Endpoint
- [x] `POST /v1/sign` - Sign artifacts
  - Mocked Fulcio integration
  - In-memory transparency log storage
  - Realistic response structure
  - Ready for real Fulcio integration

### ✅ Phase 3: Verification & Transparency
- [x] `POST /v1/verify` - Verify signatures
  - Checks against in-memory log
  - Optional identity verification
  - Mocked verification logic
- [x] `GET /v1/transparency/{entry_id}` - Retrieve log entries
- [x] `GET /v1/transparency` - Query log with filters
  - Pagination support
  - Signer filtering
  - Assessment ID filtering

### ✅ Bonus: Non-Repudiation Endpoints (Phase 4-5 Foundation)
- [x] `POST /v1/sign-artifact` - Dual-signature signing (mocked)
- [x] `POST /v1/verify-chain` - Complete chain verification (mocked)
- [x] TUF public key endpoints for distribution

### ✅ Health & Status Endpoints
- [x] `GET /v1/health` - Liveness probe
- [x] `GET /v1/ready` - Readiness probe with component checks

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- curl (for testing)

### Running with Docker Compose

```bash
# Navigate to project directory
cd /Users/harma/src/certus/certus-TAP

# Start Certus-Trust with full Sigstore stack
docker-compose -f docker-compose.certus-trust.yml up -d

# Verify services are running
docker-compose -f docker-compose.certus-trust.yml ps

# Check Certus-Trust health
curl http://localhost:8888/v1/health
```

### Running Locally (Development)

```bash
# Install dependencies
pip install fastapi uvicorn pydantic pydantic-settings

# Run service
python -m uvicorn certus_trust.main:app --host 0.0.0.0 --port 8888 --reload

# Service available at http://localhost:8888
```

## API Endpoints

### Phase 1-3 (Implemented)

#### Health & Status
```bash
# Liveness check
curl http://localhost:8888/v1/health

# Readiness check
curl http://localhost:8888/v1/ready
```

#### Phase 1: Signing
```bash
# Sign an artifact
curl -X POST http://localhost:8888/v1/sign \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123",
    "artifact_type": "sbom",
    "subject": "myapp:v1.0.0",
    "predicates": {"timestamp": "2025-12-02T00:00:00Z"}
  }'
```

#### Phase 2: Verification
```bash
# Verify a signature
curl -X POST http://localhost:8888/v1/verify \
  -H "Content-Type: application/json" \
  -d '{
    "artifact": "sha256:abc123",
    "signature": "mock-signature-...",
    "identity": "certus-assurance@certus.cloud"
  }'
```

#### Phase 3: Transparency Log
```bash
# Get specific entry
curl http://localhost:8888/v1/transparency/{entry_id}

# Query log with filters
curl 'http://localhost:8888/v1/transparency?signer=certus-trust@certus.cloud&limit=10'
```

#### Phase 4-5: Non-Repudiation (Mocked)
```bash
# Sign assessment with dual signatures
curl -X POST http://localhost:8888/v1/sign-artifact \
  -H "Content-Type: application/json" \
  -d '{
    "artifact_locations": {
      "s3": {"uri": "s3://bucket/uuid/"},
      "registry": {"uri": "registry.../v1.0.0"}
    },
    "inner_signatures": {
      "signer": "certus-assurance@certus.cloud",
      "timestamp": "2025-12-03T00:45:10Z",
      "signature": "...",
      "files": [...]
    },
    "assessment_metadata": {
      "assessment_id": "uuid-123",
      "client_id": "client-abc"
    }
  }'

# Verify complete chain
curl -X POST http://localhost:8888/v1/verify-chain \
  -H "Content-Type: application/json" \
  -d '{...}'
```

### Interactive Documentation
- **Swagger UI:** http://localhost:8888/docs
- **ReDoc:** http://localhost:8888/redoc
- **OpenAPI JSON:** http://localhost:8888/openapi.json

## Testing

### Run Tests
```bash
# Install test dependencies
pip install pytest pytest-asyncio httpx

# Run all tests
pytest certus_trust/tests/ -v

# Run specific test file
pytest certus_trust/tests/test_api.py -v

# Run with coverage
pytest certus_trust/tests/ --cov=certus_trust --cov-report=html
```

### Test Coverage (Phase 1-3)
- ✅ Health check endpoints
- ✅ Sign endpoint (artifact creation)
- ✅ Verify endpoint (signature validation)
- ✅ Transparency log queries
- ✅ Non-repudiation endpoints (mocked)
- ✅ TUF metadata endpoints
- ✅ Error handling and validation

### Example Test
```bash
pytest certus_trust/tests/test_api.py::test_sign_artifact -v
```

## Architecture

### Service Components

```
Certus-Trust (FastAPI)
├── api/
│   ├── router.py      - All API endpoints
│   ├── models.py      - Request/response schemas
│   └── __init__.py
├── config.py          - Configuration management
├── main.py            - FastAPI application factory
└── tests/
    ├── conftest.py    - Pytest fixtures
    └── test_api.py    - API tests
```

### Sigstore Stack (Docker Compose)

```
certus-trust:8888
├── Fulcio (CA)           → fulcio:5555
├── Rekor (Transparency)  → rekor:3000
├── TUF (Metadata)        → tuf:8001
└── Keycloak (OIDC)       → keycloak:8080
```

## Configuration

### Environment Variables (.env.trust)

```bash
# Service
CERTUS_TRUST_HOST=0.0.0.0
CERTUS_TRUST_PORT=8888
CERTUS_TRUST_LOG_LEVEL=INFO
CERTUS_TRUST_ENVIRONMENT=development

# Sigstore Endpoints (Docker references)
CERTUS_TRUST_FULCIO_ADDR=http://fulcio:5555
CERTUS_TRUST_REKOR_ADDR=http://rekor:3000
CERTUS_TRUST_TUF_ADDR=http://tuf:8001
CERTUS_TRUST_KEYCLOAK_ADDR=http://keycloak:8080

# OIDC
CERTUS_TRUST_OIDC_ISSUER=http://keycloak:8080/realms/master
CERTUS_TRUST_OIDC_CLIENT_ID=certus

# Features
CERTUS_TRUST_ENABLE_KEYLESS=true
CERTUS_TRUST_ENABLE_TRANSPARENCY=true
```

## Data Storage (Phase 1-3)

**Note:** Phase 1-3 uses in-memory storage for demonstration. This is sufficient for:
- Testing endpoint contracts
- Validating request/response structure
- Demonstrating non-repudiation concepts

**Future phases will replace with:**
- Real Fulcio integration for signing
- Real Rekor querying for transparency log
- Persistent database for audit logs

## Integration Roadmap

### Phase 4-5 (Next)
- [ ] Real Fulcio integration for keyless signing
- [ ] Real Rekor client for transparency log
- [ ] Cosign wrapper implementation
- [ ] In-toto support for provenance

### Phase 6-8 (After)
- [ ] Integration with Certus-Transform
- [ ] Signature verification before ingest
- [ ] Audit logging to OpenSearch
- [ ] Neo4j linking in Certus-Ask

### Phase 9-13 (Later)
- [ ] Full end-to-end testing
- [ ] Production Sigstore endpoints
- [ ] Performance benchmarking
- [ ] Compliance documentation

## Documentation

See parent directory documentation:
- `CERTUS_TRUST_IMPLEMENTATION_PLAN.md` - Complete implementation roadmap
- `CERTUS_TRUST_REVIEW.md` - Architecture review notes
- `NON_REPUDIATION_FLOW.md` - Non-repudiation guarantees

## Status

**Phase 1-3 Complete ✅**

The standalone Certus-Trust service is now ready for:
- ✅ Independent testing
- ✅ API contract validation
- ✅ Integration with other services (Ask, Transform, Insights)
- ✅ Real Sigstore integration in Phase 4-5

## Support

For issues or questions, refer to the implementation plan or reach out to the Certus team.

---

**Next Steps:** Implement Phase 4-5 (Real Fulcio/Rekor integration)
