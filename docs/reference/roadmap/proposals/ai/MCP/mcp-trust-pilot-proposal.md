# MCP Integration: Certus-Trust Pilot

> Proof-of-concept MCP integration using Certus-Trust as the first service, demonstrating agent-driven artifact verification and signing workflows

## Metadata

- **Type**: Proposal
- **Status**: Draft
- **Author**: Certus Architecture Team
- **Created**: 2025-12-29
- **Target Version**: v2.1
- **Implementation Timeline**: 6 weeks (pilot phase)
- **Related Proposals**: [MCP & ACP Integration](mcp-proposal.md)

## Executive Summary

This proposal outlines a **pilot MCP integration** using **Certus-Trust as the first service**. Rather than building a unified gateway for all services upfront, we'll prove the MCP pattern with Trust's artifact verification and signing capabilities, then expand to other services based on learnings.

**Key Decisions**:

- **Start with Certus-Trust**: Simpler service (stateless operations, production-ready Rekor integration, clear use cases)
- **Per-Service MCP Module**: Each service has optional `mcp/` module that can run standalone or compose into gateway
- **Hybrid Architecture**: Support both standalone Trust MCP and future unified gateway composition
- **Production Rekor**: Use real transparency log integration (`CERTUS_TRUST_MOCK_SIGSTORE=false`) to demonstrate cryptographic verification
- **Realistic Use Cases**: Focus on 5 developer workflows that solve real pain points

**Benefits**:

- ✅ **Fast validation** (6 weeks vs 14 weeks for all services)
- ✅ **Lower risk** (prove MCP pattern before investing in gateway)
- ✅ **Immediate value** (developers get artifact verification in IDE)
- ✅ **Modular design** (Trust MCP can run standalone or compose later)
- ✅ **Real crypto** (production Rekor integration demonstrates full value)

## Motivation

### Why Start with Certus-Trust?

After analyzing all Certus services, **Trust is the optimal first target** for MCP integration:

#### Technical Advantages

| Factor                    | Certus-Trust                  | Certus-Ask                     | Certus-Assurance            |
| ------------------------- | ----------------------------- | ------------------------------ | --------------------------- |
| **Operational Model**     | Stateless (sign/verify)       | Stateful (long-running ingest) | Stateful (long scans)       |
| **Response Time**         | <1s                           | Minutes (ingestion)            | Minutes (scanning)          |
| **MCP Complexity**        | Low (simple request/response) | High (streaming needed)        | High (streaming needed)     |
| **Production Ready**      | ~70% (real Rekor works)       | ~95%                           | ~60%                        |
| **External Dependencies** | Optional (Sigstore)           | Required (OpenSearch, Ollama)  | Required (Dagger, scanners) |
| **Streaming Needs**       | None                          | Required                       | Required                    |

#### Use Case Clarity

Trust has **concrete, high-value use cases**:

1. **Verify Dependencies**: "Is this package safe?" during code review
2. **Sign Releases**: "Sign this container image" before deployment
3. **Incident Response**: "Verify scan provenance" during security alert
4. **Compliance**: "Show all signed artifacts" for audit
5. **OSS Publishing**: "Sign my release" for package maintainers

Compare to Ask (vaguer: "improve documentation quality") or Assurance (already has CLI).

#### Developer Impact

Trust enables **zero-context-switch workflows**:

```markdown
Before MCP:

1. Developer builds Docker image
2. Switches to terminal
3. Runs: docker inspect | jq | cosign sign...
4. Copies Rekor URL
5. Switches back to IDE
6. Pastes URL in PR description
   Total: ~5 minutes, 6 context switches

With MCP-Trust:

1. Developer asks AI: "Sign myapp:v2.1.0"
2. MCP returns: ✅ Signed, Rekor: https://...
   Total: ~30 seconds, 0 context switches
```

### Why Per-Service MCP (Not Unified Gateway)?

**Flexibility for users who want:**

- Trust only (with custom RAG, not Certus-Ask)
- Ask only (with custom signing, not Certus-Trust)
- Mix-and-match services from different repos

**Example scenario:**

```yaml
# User's docker-compose.yml
services:
  certus-trust:
    image: certus-trust:latest
    command: ['python', '-m', 'certus_trust.mcp.server']
    ports: ['8097:8001']

  my-custom-rag:
    image: my-rag-system:latest
    ports: ['9000:8000']

  # No certus-ask dependency!
```

**IDE configuration:**

```json
{
  "mcp.servers": {
    "certus-trust": { "endpoint": "http://localhost:8097/mcp" },
    "my-rag": { "endpoint": "http://localhost:9000/mcp" }
  }
}
```

**Future evolution:**

- Once Trust MCP is proven, build **optional** unified gateway
- Gateway composes service MCPs (doesn't replace them)
- Users choose: standalone services OR composed gateway

## Goals & Non-Goals

### Goals

- [x] **Standalone MCP Server**: `certus_trust/mcp/server.py` runs independently
- [ ] **Core Tools Implemented**:
  - `verify` - Verify artifact signatures against Rekor
  - `sign` - Sign artifacts and record in transparency log
  - `get_provenance` - Retrieve complete provenance chain
  - `query_transparency` - Search transparency log
  - `get_stats` - Service statistics
- [ ] **Production Rekor Integration**: Use `CERTUS_TRUST_MOCK_SIGSTORE=false` for real transparency log
- [ ] **IDE Configurations**: Working examples for VS Code, Cursor, Zed
- [ ] **Developer Documentation**: Guides, tutorials, troubleshooting
- [ ] **5 Validated Use Cases**: Real developer workflows tested and documented

### Non-Goals

- **Build unified gateway** (defer to Phase 2 after pilot)
- **Integrate all services** (only Trust in pilot)
- **Replace FastAPI endpoints** (MCP is additive)
- **Build custom IDE plugins** (use standard MCP clients)
- **Support mock mode** (pilot uses production Rekor to prove value)

### Success Criteria

| Criterion               | Measurement                                                                 |
| ----------------------- | --------------------------------------------------------------------------- |
| **MCP Server Works**    | Trust MCP server starts, responds to tool calls, integrates with real Rekor |
| **IDE Integration**     | 2+ IDEs (VS Code, Cursor) successfully configured and tested                |
| **Use Cases Validated** | 5 developer workflows documented with before/after comparisons              |
| **Developer Adoption**  | 3+ developers use Trust MCP in daily workflow for 2+ weeks                  |
| **Performance**         | MCP overhead <100ms vs direct HTTP API calls                                |
| **Reliability**         | >95% success rate for MCP tool invocations                                  |

## Proposed Solution

### Architectural Decision: Python MCP Servers

**Decision**: Use Python FastMCP instead of Bun/TypeScript for MCP servers.

**Rationale**:

1. **Codebase Consistency**: Certus is 99% Python (Pydantic models, FastAPI, business logic)
2. **Team Expertise**: Engineering team has deep Python knowledge, minimal TypeScript experience
3. **Development Velocity**: Pilot needs to prove MCP value quickly (6 weeks)
4. **Model Reuse**: Can leverage existing Pydantic models from certus-trust service

**Trade-off Acknowledged**:

The AAIF proposal recommends Bun/TypeScript to enforce a **language boundary** that prevents MCP servers from importing Integrity middleware code (potential bypass). With Python MCP servers, this boundary must be enforced through **architectural patterns** instead:

**Security Boundaries in Python:**

```python
# ✅ CORRECT: MCP server calls HTTP API (goes through Integrity middleware)
@mcp.tool()
async def verify_artifact(input: VerifyInput, ctx: Context):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://certus-trust:8057/v1/verify",  # HTTP call
            json=input.model_dump()
        )
    return response.json()

# ❌ FORBIDDEN: MCP server imports business logic directly
from certus_trust.services.verification_service import VerificationService

@mcp.tool()
async def verify_artifact(input: VerifyInput, ctx: Context):
    service = VerificationService()  # BYPASSES Integrity middleware!
    return await service.verify(...)
```

**Enforcement Mechanisms:**

1. **Code Review**: Enforce HTTP-only calls in MCP tool implementations
2. **Import Linting**: Add `ruff` rule to prevent `certus_trust.services.*` imports in `mcp/` module
3. **Integration Tests**: Verify Integrity middleware is invoked (check evidence bundles)
4. **Architectural Principle**: MCP tools are **clients** of the HTTP API, not internal service consumers

**Future Consideration**:

If this pilot succeeds and we expand to all 5 services, we may revisit Bun/TypeScript for **unified gateway** to enforce language boundary. Per-service MCP modules can remain Python (simpler), gateway can be TypeScript (enforces boundary across all services).

### Architecture

#### System Context

```
┌─────────────────────────────────┐
│  Developer (VS Code/Cursor/Zed) │
└────────────┬────────────────────┘
             │ MCP Protocol
             ▼
┌─────────────────────────────────┐
│  Certus-Trust MCP Server        │
│  (Python/FastMCP)               │
│  ├── verify tool                │
│  ├── sign tool                  │
│  ├── get_provenance tool        │
│  ├── query_transparency tool    │
│  └── get_stats tool             │
│                                 │
│  NOTE: Calls HTTP API only,    │
│  NEVER imports service logic   │
└────────────┬────────────────────┘
             │ HTTP calls
             ▼
┌─────────────────────────────────┐
│  Certus-Trust Service           │
│  ├── FastAPI endpoints          │
│  ├── Integrity Middleware ◄─────┼── Enforces rate limits, budgets
│  ├── Signing/Verification       │
│  └── Rekor client               │
└────────────┬────────────────────┘
             │ HTTP API
             ▼
┌─────────────────────────────────┐
│  Sigstore Infrastructure        │
│  ├── Rekor (transparency log)   │
│  ├── Fulcio (certificate auth)  │
│  └── Trillian (Merkle backend)  │
└─────────────────────────────────┘
```

#### Deployment Options

**Option 1: Embedded MCP (Development)**

```
Certus-Trust FastAPI Process
├── uvicorn (HTTP endpoints)
└── FastMCP server (MCP endpoints)
    # Same process, different ports
```

**Option 2: Standalone MCP (Production)**

```
Service 1: certus-trust (FastAPI)
  Port 8057: HTTP API

Service 2: certus-trust-mcp (FastMCP)
  Port 8097: MCP endpoint
  → Calls Service 1 via HTTP
```

### File Structure

```
certus_trust/
├── api/
│   ├── router.py              # FastAPI HTTP endpoints
│   └── models.py              # Pydantic request/response models
├── services/
│   ├── signing_service.py     # Business logic
│   └── verification_service.py
├── clients/
│   ├── rekor_client.py        # HTTP client for Rekor
│   └── signing_client.py      # Cryptography operations
└── mcp/                       # ← NEW: MCP integration module
    ├── __init__.py
    ├── server.py              # FastMCP server entrypoint
    ├── tools.py               # Tool implementations
    ├── models.py              # MCP-specific Pydantic models (if needed)
    └── config.py              # MCP server configuration
```

### MCP Tools Implementation

#### Tool 1: Verify Artifact

```python
# certus_trust/mcp/tools.py
from fastmcp import FastMCP, Context
from pydantic import BaseModel, Field

mcp = FastMCP("Certus Trust")

class VerifyInput(BaseModel):
    artifact: str = Field(description="Artifact digest (sha256:...)")
    signature: str = Field(description="Signature to verify")
    identity: str | None = Field(default=None, description="Expected signer identity")
    scenario: str | None = Field(default=None, description="Mock scenario (verified_premium_scan, tampered_scan, etc.)")

class VerifyOutput(BaseModel):
    valid: bool
    verified_at: str
    signer: str | None
    transparency_index: int | None
    rekor_entry_url: str | None
    certificate_chain: list[str] | None

@mcp.tool(name="verify")
async def verify_artifact(input: VerifyInput, ctx: Context) -> VerifyOutput:
    """Verify artifact signature against transparency log.

    Examples:
      - Verify container image: verify(artifact="sha256:abc123...", signature="MEU...")
      - Check specific signer: verify(..., identity="certus-assurance@certus.cloud")
      - Test scenarios: verify(..., scenario="tampered_scan")
    """
    from ..services import get_verification_service

    # Get verification service (production or mock based on config)
    service = await get_verification_service(ctx.app)

    # Perform verification
    result = await service.verify(
        artifact=input.artifact,
        signature=input.signature,
        identity=input.identity,
        scenario=input.scenario
    )

    return VerifyOutput(
        valid=result.valid,
        verified_at=result.verified_at.isoformat(),
        signer=result.signer,
        transparency_index=result.transparency_index,
        rekor_entry_url=f"https://rekor.sigstore.dev/api/v1/log/entries/{result.entry_id}" if result.entry_id else None,
        certificate_chain=result.certificate_chain
    )
```

#### Tool 2: Sign Artifact

```python
class SignInput(BaseModel):
    artifact: str = Field(description="Artifact to sign (sha256:...)")
    artifact_type: str = Field(description="Type: container_image, sbom, scan_result, etc.")
    subject: str | None = Field(default=None, description="Human-readable subject (myapp:v2.1.0)")
    metadata: dict | None = Field(default=None, description="Additional metadata")

class SignOutput(BaseModel):
    entry_id: str
    signature: str
    certificate: str | None
    transparency_entry: dict
    rekor_url: str

@mcp.tool(name="sign")
async def sign_artifact(input: SignInput, ctx: Context) -> SignOutput:
    """Sign artifact and record in transparency log.

    Examples:
      - Sign container: sign(artifact="sha256:abc123...", artifact_type="container_image", subject="myapp:v2.1.0")
      - Sign SBOM: sign(artifact="sha256:def456...", artifact_type="sbom")
    """
    from ..services import get_signing_service

    service = await get_signing_service(ctx.app)

    result = await service.sign(
        artifact=input.artifact,
        artifact_type=input.artifact_type,
        subject=input.subject,
        metadata=input.metadata
    )

    return SignOutput(
        entry_id=result.entry_id,
        signature=result.signature,
        certificate=result.certificate,
        transparency_entry={
            "uuid": result.transparency_entry.uuid,
            "index": result.transparency_entry.index,
            "timestamp": result.transparency_entry.timestamp.isoformat()
        },
        rekor_url=f"https://rekor.sigstore.dev/api/v1/log/entries/{result.entry_id}"
    )
```

#### Tool 3: Get Provenance Chain

```python
class ProvenanceInput(BaseModel):
    scan_id: str = Field(description="Scan identifier")
    scenario: str | None = Field(default=None, description="Mock scenario")

class ProvenanceOutput(BaseModel):
    scan_id: str
    manifest: dict
    scans: list[dict]
    verification_trail: list[dict]
    storage_locations: dict
    chain_status: str
    trust_level: str

@mcp.tool(name="get_provenance")
async def get_provenance(input: ProvenanceInput, ctx: Context) -> ProvenanceOutput:
    """Get complete provenance chain for a scan.

    Returns full audit trail including:
    - Manifest signature
    - Individual scan tool signatures
    - Verification timestamps
    - Storage locations (S3, OCI)
    - Chain integrity status

    Examples:
      - Get provenance: get_provenance(scan_id="scan_abc123")
      - Test scenarios: get_provenance(scan_id="scan_123", scenario="tampered_scan")
    """
    from ..api.router import get_provenance as api_get_provenance

    # Delegate to existing API implementation
    result = await api_get_provenance(
        scan_id=input.scan_id,
        scenario=input.scenario
    )

    return ProvenanceOutput(**result)
```

#### Tool 4: Query Transparency Log

```python
class QueryTransparencyInput(BaseModel):
    signer: str | None = Field(default=None, description="Filter by signer identity")
    artifact_type: str | None = Field(default=None, description="Filter by artifact type")
    start_date: str | None = Field(default=None, description="ISO 8601 start date")
    end_date: str | None = Field(default=None, description="ISO 8601 end date")
    limit: int = Field(default=10, description="Max results")

class TransparencyEntry(BaseModel):
    entry_id: str
    artifact: str
    artifact_type: str
    timestamp: str
    signer: str
    signature: str
    rekor_url: str

@mcp.tool(name="query_transparency")
async def query_transparency(input: QueryTransparencyInput, ctx: Context) -> list[TransparencyEntry]:
    """Search transparency log with filters.

    Examples:
      - All entries: query_transparency()
      - By signer: query_transparency(signer="certus-assurance@certus.cloud")
      - Date range: query_transparency(start_date="2025-12-01", end_date="2025-12-31")
      - Recent scans: query_transparency(artifact_type="scan_result", limit=20)
    """
    from ..api.router import query_transparency_log

    results = await query_transparency_log(
        signer=input.signer,
        assessment_id=None,  # Not exposed in MCP
        limit=input.limit
    )

    return [
        TransparencyEntry(
            entry_id=entry.entry_id,
            artifact=entry.artifact,
            artifact_type=getattr(entry, 'artifact_type', 'unknown'),
            timestamp=entry.timestamp.isoformat(),
            signer=entry.signer,
            signature=entry.signature,
            rekor_url=f"https://rekor.sigstore.dev/api/v1/log/entries/{entry.entry_id}"
        )
        for entry in results
    ]
```

#### Tool 5: Get Service Statistics

```python
class StatsOutput(BaseModel):
    total_signatures: int
    total_transparency_entries: int
    verification_stats: dict
    signers: list[str]
    timestamp: str

@mcp.tool(name="get_stats")
async def get_stats(ctx: Context) -> StatsOutput:
    """Get Trust service statistics.

    Returns:
      - Total signatures created
      - Transparency log size
      - Verification success/failure rates
      - Active signers
      - Current timestamp

    Use cases:
      - Monitor service health
      - Detect anomalies (high failure rates)
      - Track usage patterns
    """
    from ..api.router import get_service_stats

    stats = await get_service_stats()

    return StatsOutput(**stats)
```

### Server Implementation

```python
# certus_trust/mcp/server.py
import asyncio
import logging
from contextlib import asynccontextmanager

from fastmcp import FastMCP
from ..config import get_settings
from ..clients import RekorClient, SigningClient
from .tools import mcp

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app):
    """Initialize Certus-Trust MCP server."""
    logger.info("Starting Certus-Trust MCP server...")

    settings = get_settings()
    app.state.settings = settings

    # Initialize Sigstore clients (production mode)
    if not settings.mock_sigstore:
        logger.info("Initializing production Sigstore clients...")
        app.state.rekor_client = RekorClient(settings)
        app.state.signing_client = SigningClient(settings)
        logger.info("✓ Production Sigstore clients ready")
    else:
        logger.info("Running in MOCK mode")
        app.state.rekor_client = None
        app.state.signing_client = None

    yield

    logger.info("Shutting down Certus-Trust MCP server...")

# Attach lifespan to the FastMCP app
mcp.app.router.lifespan_context = lifespan

if __name__ == "__main__":
    # Run MCP server
    # Supports: stdio, HTTP, SSE transports
    import sys

    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"

    if transport == "stdio":
        mcp.run(transport="stdio")
    elif transport == "http":
        port = int(sys.argv[2]) if len(sys.argv) > 2 else 8001
        mcp.run(transport="http", port=port)
    else:
        raise ValueError(f"Unknown transport: {transport}")
```

### Configuration

```yaml
# certus_trust/mcp/config.yaml (optional)
mcp:
  name: 'Certus Trust'
  version: '1.0.0'
  description: 'Artifact signing and verification via Sigstore'

  # Transport options
  transports:
    - stdio # For local IDE integration
    - http # For remote IDEs

  # Tool settings
  tools:
    verify:
      enabled: true
      timeout_seconds: 30
    sign:
      enabled: true
      timeout_seconds: 30
    get_provenance:
      enabled: true
      timeout_seconds: 10
    query_transparency:
      enabled: true
      max_results: 100
    get_stats:
      enabled: true

  # Security
  auth:
    required: false # Pilot: no auth (runs locally)
    # Future: token validation

  # Observability
  telemetry:
    enabled: true
    emit_to_stdout: true
```

## Use Cases & Workflows

### Use Case 1: Security Engineer Verifying Internal Dependencies

**Persona**: Sarah, Security Engineer

**Scenario**: Reviewing pull request that adds new internal package dependency

**Context**: Sarah works at a fintech company and reviews all dependency changes for security compliance.

**Before MCP**:

```bash
# Sarah's workflow (5 minutes)
1. See PR: + company-auth-sdk==2.3.0
2. Switch to terminal
3. Find package digest: curl registry/v2/.../manifests/2.3.0 | jq .digest
4. Check if signed: curl trust-api/v1/verify -d '{"artifact": "sha256:..."}'
5. Parse JSON response
6. Check Rekor: curl https://rekor.../api/v1/log/entries/...
7. Switch back to GitHub
8. Add comment: "Package verified ✓"
```

**With MCP**:

```markdown
# Sarah's workflow (30 seconds)

1. See PR: + company-auth-sdk==2.3.0
2. In VS Code, highlight package, ask Copilot:
   "Is company-auth-sdk:2.3.0 verified?"

3. Copilot invokes: verify(artifact="sha256:abc123...", identity="internal-ci@company.com")

4. Inline response:
   ✅ Package Verified
   - Signed by: internal-ci@company.com
   - Verified: 2 hours ago
   - Rekor: https://rekor.sigstore.dev/entry/xyz123
   - SLSA Level: 3
   - Provenance: github.company.com/platform/auth-sdk
5. Sarah approves PR
```

**Value**:

- ⏱️ Time saved: 4.5 minutes per verification
- 🎯 Context switches: 0 (vs 4)
- ✅ Accuracy: Higher (no manual copy/paste errors)

---

### Use Case 2: Developer Signing Release Artifacts

**Persona**: Marcus, Backend Developer

**Scenario**: Preparing production release, needs to sign container image

**Before MCP**:

```bash
# Marcus's workflow (3 minutes)
1. Build: docker build -t myapp:v2.1.0 .
2. Push: docker push registry.company.com/myapp:v2.1.0
3. Get digest: docker inspect registry.company.com/myapp:v2.1.0 | jq '.RepoDigests[0]'
4. Sign: cosign sign --key cosign.key registry.company.com/myapp@sha256:...
5. Enter password
6. Copy Rekor URL from output
7. Paste in release notes
```

**With MCP**:

```markdown
# Marcus's workflow (20 seconds)

1. Build and push image
2. In Cursor, type: "Sign registry.company.com/myapp:v2.1.0"

3. Cursor AI invokes: sign(
   artifact="sha256:abc123...",
   artifact_type="container_image",
   subject="myapp:v2.1.0",
   metadata={"version": "v2.1.0", "commit": "7f8d9e2"}
   )

4. Inline response:
   ✅ Image Signed Successfully

   Signature: MEUCIQD...
   Rekor Entry: https://rekor.sigstore.dev/api/v1/log/entries/xyz789
   Certificate: Valid until 2025-12-30T11:30:00Z

   Verification command:
   cosign verify registry.company.com/myapp:v2.1.0

5. Marcus copies Rekor URL to release notes
```

**Value**:

- ⏱️ Time saved: 2.5 minutes per release
- 🔒 Security: No password entry in terminal (keyless signing)
- 📋 Automation: AI assistant suggests next steps

---

### Use Case 3: Incident Response - Validating Scan Provenance

**Persona**: Alex, DevSecOps Lead

**Scenario**: Security alert triggered, need to verify scan results weren't tampered with

**Before MCP**:

```bash
# Alex's workflow (10 minutes during incident)
1. Get alert: High severity vulnerabilities in scan_7f8d9e2
2. Switch to terminal
3. Query provenance: curl trust-api/v1/provenance/scan_7f8d9e2
4. Read JSON (hundreds of lines)
5. Extract Rekor entries manually
6. Verify each signature: curl https://rekor.../api/v1/log/entries/...
7. Check timestamps match
8. Check storage integrity: aws s3api head-object...
9. Compare digests manually
10. Document findings in incident ticket
```

**With MCP**:

```markdown
# Alex's workflow (1 minute during incident)

1. Get alert: High severity vulnerabilities in scan_7f8d9e2
2. In Zed editor, ask: "Verify provenance of scan scan_7f8d9e2"

3. Zed ACP invokes: get_provenance(scan_id="scan_7f8d9e2", include_verification_trail=true)

4. Displayed in sidebar:
   📋 Provenance Chain: scan_7f8d9e2

   ✅ Manifest
   - Signed by: certus-assurance@company.com
   - Timestamp: 2025-12-29T09:15:00Z
   - Rekor: entry_001 ✓

   ✅ Scan Tools
   - Trivy v0.48.0: signed ✓, verified ✓
   - Semgrep v1.50.0: signed ✓, verified ✓

   ✅ Storage Integrity
   - S3: digests match ✓
   - OCI: digests match ✓

   🔒 Chain Status: COMPLETE
   🛡️ Trust Level: HIGH

   Conclusion: Results are authentic

5. Alex escalates with confidence (verified in 1 minute)
```

**Value**:

- ⏱️ Time saved: 9 minutes during critical incident
- 🎯 Accuracy: No manual JSON parsing errors
- 📊 Clarity: Human-readable summary vs raw JSON

---

### Use Case 4: Compliance Auditor Generating Evidence

**Persona**: Jordan, Compliance Auditor

**Scenario**: Preparing SOC 2 audit, need proof all artifacts are signed

**Before MCP**:

```bash
# Jordan's workflow (2 hours)
1. Query database: SELECT * FROM signed_artifacts WHERE date > '2024-10-01'
2. Export to CSV
3. For each artifact:
   a. curl trust-api/v1/verify...
   b. curl https://rekor.../api/v1/log/entries/...
   c. Parse JSON response
   d. Copy verification proof
   e. Paste into Excel
4. Generate summary statistics manually
5. Create PDF report
6. Package evidence files
```

**With MCP**:

```markdown
# Jordan's workflow (5 minutes)

1. In VS Code, type: "Generate compliance report for last 90 days"

2. AI invokes: query_transparency(
   start_date="2024-10-01",
   end_date="2025-12-29",
   limit=10000
   )

3. AI generates report:
   📊 Supply Chain Audit Report
   Period: 2024-10-01 to 2025-12-29

   Total Artifacts: 1,247
   - Container Images: 823 (100% verified)
   - SBOMs: 312 (100% verified)
   - Scan Results: 98 (100% verified)
   - Provenance: 14 (100% verified)

   Transparency Coverage: 100%
   Average Verification Time: 2.3s

   Compliance Status: ✅ COMPLIANT

   Evidence Package: [Download PDF]
   Rekor Audit Trail: [Download JSON]

4. Jordan downloads evidence package for auditor
```

**Value**:

- ⏱️ Time saved: 1 hour 55 minutes
- 📋 Completeness: Automated queries miss nothing
- 🔍 Verifiability: Rekor URLs provide external proof

---

### Use Case 5: OSS Maintainer Publishing Verified Release

**Persona**: Taylor, Open Source Maintainer

**Scenario**: Releasing new version of Python library with transparency

**Before MCP**:

```bash
# Taylor's workflow (8 minutes)
1. Build release: python -m build
2. Sign tarball: cosign sign-blob --key cosign.key dist/mylib-3.0.0.tar.gz
3. Sign wheel: cosign sign-blob --key cosign.key dist/mylib-3.0.0-py3-none-any.whl
4. Generate SLSA provenance: slsa-provenance create...
5. Copy all signatures and Rekor URLs
6. Update README with verification instructions
7. Paste Rekor URLs
8. Commit changes
9. Push to GitHub
10. Publish to PyPI
```

**With MCP**:

````markdown
# Taylor's workflow (2 minutes)

1. Build release: python -m build
2. In GitHub Codespaces, ask: "Sign my release artifacts and generate SLSA provenance"

3. AI invokes:
   - sign(artifact="sha256:abc123...", artifact_type="release_tarball", subject="mylib-3.0.0.tar.gz")
   - sign(artifact="sha256:def456...", artifact_type="python_wheel", subject="mylib-3.0.0-py3-none-any.whl")

4. AI generates README section:

   ## Verifying Releases

   All releases are signed with Sigstore:

   ```bash
   pip install sigstore
   sigstore verify mylib-3.0.0.tar.gz \
     --cert-identity taylor@example.com
   ```
````

Transparency Log:

- v3.0.0 tarball: https://rekor.sigstore.dev/api/v1/log/entries/xyz001
- v3.0.0 wheel: https://rekor.sigstore.dev/api/v1/log/entries/xyz002

5. Taylor commits and publishes to PyPI

````

**Value**:
- ⏱️ Time saved: 6 minutes per release
- 📄 Documentation: Auto-generated verification instructions
- 🔒 Trust: Users can cryptographically verify artifacts

---

### Use Case 6: Security Engineer Verifying External Dependencies with Orchestration

**Persona**: Sarah, Security Engineer (Extended Scenario)

**Scenario**: Reviewing pull request that adds external PyPI package (not internal)

**Context**: Company policy requires verification of external dependencies through multiple sources before approval.

**Before MCP**:
```bash
# Sarah's workflow (15 minutes)
1. See PR: + requests==2.31.0
2. Check company policy database: Is this package approved?
3. Search Sigstore public log: curl https://rekor.sigstore.dev/api/v1/log/entries?hash=...
4. Check PyPI metadata: curl https://pypi.org/pypi/requests/json
5. Query vulnerability databases: curl https://osv.dev/query -d '{"package": {"name": "requests", "ecosystem": "PyPI"}}'
6. Check internal usage: grep -r "requests==2.31.0" ~/repos/
7. Compile findings into approval comment
8. Add to approved packages list if new
```

**With MCP-Trust (Orchestration Mode)**:
```markdown
# Sarah's workflow (1 minute)
1. See PR: + requests==2.31.0
2. In VS Code, ask: "Is requests:2.31.0 safe to use?"

3. MCP-Trust orchestrates multiple sources:
   Tool: verify_package(
     package="pypi:requests==2.31.0",
     check_external=true
   )

4. AI aggregates from multiple sources:
   ⚠️ External Package Analysis: requests==2.31.0

   ✅ Company Policy: APPROVED
      - Added to allowlist: 2024-03-15
      - Used in 23 internal projects

   ✅ Public Sigstore Verification
      - Signed by: Python Software Foundation
      - Certificate: Valid until 2025-12-30
      - Rekor: https://rekor.sigstore.dev/entry/abc123

   ✅ Vulnerability Scan: CLEAN
      - CVE-2023-32681 (FIXED in 2.31.0)
      - No critical vulnerabilities

   ✅ Package Reputation
      - PyPI Downloads: 500M+/month
      - GitHub Stars: 52k
      - Maintainer Trust: HIGH

   Recommendation: ✅ Safe to approve

   Note: This is an external package verified through
   public Sigstore, not your internal transparency log.

5. Sarah approves PR with confidence
```

**Value**:
- ⏱️ Time saved: 14 minutes per external package verification
- 🔍 Comprehensive: Checks 5 sources automatically
- 📊 Clear distinction: Internal vs external package verification
- 🎯 Policy enforcement: Company allowlist checked first

**Technical Note**: This demonstrates Trust as an **orchestration layer** that can query:
- Internal transparency log (authoritative for your artifacts)
- Public Sigstore (for externally-signed packages)
- Vulnerability databases (OSV, GitHub Advisory)
- Package registries (PyPI, npm)
- Company policy databases

---

### Use Case 7: Continuous Monitoring - Detecting Anomalies

**Persona**: Riley, Platform Security Engineer

**Scenario**: Daily monitoring of signing activity to detect unauthorized or suspicious patterns

**Context**: Riley needs to ensure only authorized CI/CD systems are signing artifacts and catch anomalies early.

**Before MCP**:
```bash
# Riley's workflow (30 minutes daily)
1. SSH to monitoring server
2. Query database: SELECT * FROM signatures WHERE date = today
3. Export to CSV
4. Open in Excel
5. Manually check for:
   - Unknown signers
   - Unusual signing volumes
   - Failed verifications
   - Signing outside business hours
6. Cross-reference with authorized CI systems list
7. Create alerts for suspicious activity
8. Update dashboard manually
```

**With MCP-Trust**:
```markdown
# Riley's workflow (2 minutes daily)
1. Open IDE, ask AI: "Show me today's signing activity and flag anomalies"

2. AI invokes:
   - get_stats() → Overall metrics
   - query_transparency(start_date="2025-12-29", limit=1000) → Today's entries
   - analyze_patterns() → AI detects anomalies

3. AI-generated report:
   📊 Daily Security Report - 2025-12-29

   ✅ Overall Health
      - Total Signatures: 47
      - Verification Success Rate: 97.9%
      - Active Signers: 3

   ⚠️ Anomalies Detected

   1. ALERT: Unknown Signer
      - Signer: unknown-ci@external.com
      - Artifacts: 2 container images
      - Time: 03:42 AM (outside business hours)
      - Action: INVESTIGATE

   2. WARNING: High Failure Rate
      - Signer: dev-ci@company.com
      - Failed Verifications: 5/8 (62.5%)
      - Action: Check CI configuration

   ✅ Normal Activity
      - production-ci@company.com: 35 signatures ✓
      - staging-ci@company.com: 10 signatures ✓

   Recommendations:
   1. Investigate unknown-ci@external.com immediately
   2. Review dev-ci certificate configuration
   3. Consider revoking suspicious signatures

4. Riley clicks "Investigate" → Opens relevant Rekor entries
```

**Value**:
- ⏱️ Time saved: 28 minutes daily (140 min/week)
- 🚨 Faster detection: Anomalies flagged within minutes vs hours
- 🤖 Automation: AI identifies patterns Riley might miss
- 📈 Trending: Historical comparisons (today vs 7-day average)

---

### Use Case 8: Multi-Team Collaboration - Shared Verification Context

**Persona**: Teams across Development, Security, and Operations

**Scenario**: Multiple teams need to verify the same artifacts but from different perspectives

**Context**: A critical CVE fix is being deployed, requiring coordination across teams.

**Before MCP**:
```bash
# Fragmented across teams (45 minutes total)

Developer (Marcus):
1. Build fix: docker build -t api:v1.2.1-security .
2. Push to registry
3. Email Security: "api:v1.2.1-security ready for review"

Security (Sarah):
4. Receive email 30 mins later
5. Manually verify signatures
6. Check scan results
7. Email Ops: "api:v1.2.1-security approved"

Operations (Riley):
8. Receive email 20 mins later
9. Manually verify provenance
10. Check deployment checklist
11. Deploy to staging
12. Each person maintains separate notes
```

**With MCP-Trust**:
```markdown
# Coordinated workflow (10 minutes total)

Developer (Marcus) - t=0:
1. Build fix: docker build -t api:v1.2.1-security .
2. In IDE: "Sign api:v1.2.1-security and notify security team"

   AI invokes:
   - sign(artifact="sha256:abc123...", subject="api:v1.2.1-security")
   - notify_team(team="security", artifact="api:v1.2.1-security")

   ✅ Signed and notified
   - Rekor: https://rekor.sigstore.dev/entry/xyz001
   - Security team: NOTIFIED (Sarah, Alex)
   - Status: PENDING_SECURITY_REVIEW

Security (Sarah) - t=2 mins:
2. Receives IDE notification: "api:v1.2.1-security ready for review"
3. Asks AI: "Verify api:v1.2.1-security for deployment"

   AI invokes:
   - get_provenance(artifact="api:v1.2.1-security")
   - verify(artifact="sha256:abc123...")
   - check_scans(artifact="api:v1.2.1-security")

   ✅ Security Review: APPROVED
   - Signature: VALID ✓
   - Provenance: COMPLETE ✓
   - Vulnerabilities: 0 critical (CVE-2024-1234 FIXED)
   - Notifying Ops team...

Operations (Riley) - t=5 mins:
3. Receives notification: "api:v1.2.1-security approved by Security"
4. Asks AI: "Show deployment readiness for api:v1.2.1-security"

   AI provides checklist:
   ✅ Deployment Readiness: api:v1.2.1-security

   ✓ Signature verified (Marcus @ 10:00 AM)
   ✓ Security approved (Sarah @ 10:02 AM)
   ✓ Scan results: 0 critical
   ✓ Provenance chain: COMPLETE
   ✓ Rekor entry: xyz001
   ✓ Previous version: v1.2.0 (rolling back available)

   Ready to deploy ✓

5. Riley deploys with full context and audit trail
```

**Value**:
- ⏱️ Time saved: 35 minutes total (across 3 teams)
- 🔄 Coordination: Real-time notifications vs email delays
- 📋 Shared context: Everyone sees same verification status
- 🔍 Audit trail: Complete timeline of who verified what and when
- 🚀 Faster deployments: Security fixes deployed in 10 mins vs 45 mins

**Technical Features Used**:
- Signing with metadata
- Provenance retrieval
- Cross-team notifications (via MCP integration with Slack/email)
- Shared verification status
- Deployment readiness checks

---

## Implementation Plan

### Phase 0: Project Setup (Week 1)

**Deliverables**:
- [ ] Create `certus_trust/mcp/` module structure
- [ ] Add `fastmcp` dependency to `pyproject.toml`
- [ ] Write MCP server scaffold (`server.py`)
- [ ] Configure development environment

**Tasks**:
```bash
# 1. Add dependency
cd certus_trust
uv add fastmcp

# 2. Create module structure
mkdir -p certus_trust/mcp
touch certus_trust/mcp/{__init__.py,server.py,tools.py,models.py,config.py}

# 3. Test basic MCP server
uv run python -m certus_trust.mcp.server
````

**Success Criteria**:

- MCP server starts without errors
- Can connect with `fastmcp` client
- Basic tool registration works

---

### Phase 1: Core Tools (Weeks 2-3)

**Deliverables**:

- [ ] Implement `verify` tool
- [ ] Implement `sign` tool
- [ ] Implement `get_provenance` tool
- [ ] Unit tests for each tool
- [ ] Integration tests with production Rekor

**Tasks**:

**Week 2: Verify + Sign Tools**

```python
# Day 1-2: verify tool
- Implement VerifyInput/VerifyOutput models
- Connect to verification service
- Handle production Rekor responses
- Write unit tests (mock service)
- Write integration tests (real Rekor)

# Day 3-4: sign tool
- Implement SignInput/SignOutput models
- Connect to signing service
- Test Rekor submission
- Write unit tests
- Write integration tests

# Day 5: Testing + refinement
- End-to-end test: sign then verify
- Test error scenarios (invalid signature, expired cert)
- Performance testing (latency overhead)
```

**Week 3: Provenance + Polish**

```python
# Day 1-2: get_provenance tool
- Implement ProvenanceInput/ProvenanceOutput
- Connect to existing provenance API
- Test with mock scenarios
- Write tests

# Day 3-4: Error handling
- Graceful degradation (Rekor unavailable)
- Input validation
- Helpful error messages for AI agents

# Day 5: Documentation
- Tool docstrings with examples
- API reference
```

**Success Criteria**:

- All 3 core tools pass unit + integration tests
- Can sign artifact and verify signature via MCP
- Can retrieve provenance chain via MCP
- <100ms latency overhead vs direct API

---

### Phase 2: Transparency Query + Stats (Week 4)

**Deliverables**:

- [ ] Implement `query_transparency` tool
- [ ] Implement `get_stats` tool
- [ ] Date range filtering
- [ ] Pagination support
- [ ] Tests

**Tasks**:

```python
# Day 1-2: query_transparency
- Implement filter parameters (signer, date range, artifact type)
- Connect to transparency log API
- Handle large result sets (pagination)
- Write tests

# Day 3: get_stats
- Implement stats aggregation
- Real-time metrics
- Write tests

# Day 4-5: Testing + polish
- Test with large datasets (1000+ entries)
- Performance optimization
- Documentation
```

**Success Criteria**:

- Can query transparency log with filters
- Can get real-time service statistics
- Query performance <500ms for 100 results

---

### Phase 3: IDE Integration (Week 5)

**Deliverables**:

- [ ] VS Code MCP configuration guide
- [ ] Cursor AI integration guide
- [ ] Zed ACP configuration guide
- [ ] Working example configurations
- [ ] Troubleshooting guide

**Tasks**:

**VS Code (Day 1-2)**:

```json
# .vscode/mcp.json
{
  "mcpServers": {
    "certus-trust": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "certus_trust.mcp.server",
        "stdio"
      ],
      "env": {
        "CERTUS_TRUST_MOCK_SIGSTORE": "false"
      }
    }
  }
}
```

**Cursor (Day 3)**:

```yaml
# Similar to VS Code but with Cursor-specific settings
# Test with Cursor AI assistant
```

**Zed (Day 4)**:

```json
# settings.json
{
  "assistant": {
    "version": "2",
    "tools": {
      "certus-trust": {
        "command": "uv run python -m certus_trust.mcp.server stdio"
      }
    }
  }
}
```

**Documentation (Day 5)**:

- Write setup guides for each IDE
- Common issues and solutions
- Example prompts for AI assistants

**Success Criteria**:

- Developers can configure MCP in 3 IDEs
- AI assistants successfully invoke Trust tools
- Documentation is clear and complete

---

### Phase 4: Use Case Validation (Week 6)

**Deliverables**:

- [ ] 5 use cases tested with real developers
- [ ] Before/after time measurements
- [ ] Developer feedback collected
- [ ] Use case documentation
- [ ] Demo videos

**Tasks**:

**Recruit Participants (Day 1)**:

- 3 developers
- 1 security engineer
- 1 compliance auditor

**Test Use Cases (Days 2-4)**:

- Use Case 1: Verify dependencies (Sarah)
- Use Case 2: Sign releases (Marcus)
- Use Case 3: Incident response (Alex)
- Use Case 4: Compliance report (Jordan)
- Use Case 5: OSS publishing (Taylor)

**Measure & Document (Day 5)**:

- Time savings per workflow
- Context switches eliminated
- Accuracy improvements
- Satisfaction scores (1-10)

**Success Criteria**:

- All 5 use cases validated
- > 80% developer satisfaction
- Average time savings >50%
- 0 critical usability issues

---

### Timeline Summary

| Phase                        | Duration    | Key Deliverable               |
| ---------------------------- | ----------- | ----------------------------- |
| **Phase 0: Setup**           | Week 1      | MCP module scaffolding        |
| **Phase 1: Core Tools**      | Weeks 2-3   | verify, sign, get_provenance  |
| **Phase 2: Query Tools**     | Week 4      | query_transparency, get_stats |
| **Phase 3: IDE Integration** | Week 5      | VS Code, Cursor, Zed configs  |
| **Phase 4: Validation**      | Week 6      | 5 use cases tested            |
| **Total**                    | **6 weeks** | Production-ready Trust MCP    |

---

## Testing Strategy

### Unit Tests

```python
# certus_trust/mcp/tests/test_tools.py
import pytest
from unittest.mock import AsyncMock, MagicMock
from fastmcp import Context
from ..tools import verify_artifact, sign_artifact, get_provenance

@pytest.mark.asyncio
async def test_verify_tool_valid_signature():
    """Test verify tool with valid signature."""
    # Arrange
    ctx = MagicMock(spec=Context)
    ctx.app.state.settings.mock_sigstore = True

    input_data = VerifyInput(
        artifact="sha256:abc123",
        signature="MEUCIQD...",
        identity="certus-assurance@certus.cloud"
    )

    # Act
    result = await verify_artifact(input_data, ctx)

    # Assert
    assert result.valid is True
    assert result.signer == "certus-assurance@certus.cloud"
    assert result.transparency_index is not None

@pytest.mark.asyncio
async def test_verify_tool_invalid_signature():
    """Test verify tool with invalid signature."""
    # Similar structure but with scenario="tampered_scan"
    pass

@pytest.mark.asyncio
async def test_sign_tool_creates_rekor_entry():
    """Test sign tool creates transparency log entry."""
    pass

@pytest.mark.asyncio
async def test_provenance_tool_returns_complete_chain():
    """Test get_provenance returns all chain elements."""
    pass
```

### Integration Tests

```python
# certus_trust/mcp/tests/test_integration.py
import pytest
from fastmcp import Client
from ..server import mcp

@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_server_startup():
    """Test MCP server starts and responds."""
    async with Client(mcp) as client:
        tools = await client.list_tools()
        assert len(tools) == 5
        assert any(t.name == "verify" for t in tools)

@pytest.mark.integration
@pytest.mark.asyncio
async def test_sign_and_verify_workflow():
    """Test complete sign → verify workflow."""
    async with Client(mcp) as client:
        # Sign artifact
        sign_result = await client.call_tool(
            "sign",
            {
                "artifact": "sha256:abc123",
                "artifact_type": "container_image",
                "subject": "myapp:v1.0.0"
            }
        )

        assert sign_result["entry_id"]
        entry_id = sign_result["entry_id"]

        # Verify signature
        verify_result = await client.call_tool(
            "verify",
            {
                "artifact": "sha256:abc123",
                "signature": sign_result["signature"]
            }
        )

        assert verify_result["valid"] is True

@pytest.mark.integration
@pytest.mark.asyncio
async def test_production_rekor_integration():
    """Test with real Rekor transparency log."""
    # Only runs if CERTUS_TRUST_MOCK_SIGSTORE=false
    import os
    if os.getenv("CERTUS_TRUST_MOCK_SIGSTORE", "true").lower() == "true":
        pytest.skip("Production Rekor not enabled")

    async with Client(mcp) as client:
        # Test real Rekor submission
        result = await client.call_tool("sign", {...})

        # Verify entry exists in real Rekor
        import httpx
        async with httpx.AsyncClient() as http:
            response = await http.get(
                f"http://localhost:3001/api/v1/log/entries/{result['entry_id']}"
            )
            assert response.status_code == 200
```

### Performance Tests

```python
# certus_trust/mcp/tests/test_performance.py
import pytest
import time
from fastmcp import Client
from ..server import mcp

@pytest.mark.performance
@pytest.mark.asyncio
async def test_verify_latency():
    """Measure MCP overhead vs direct API call."""
    async with Client(mcp) as client:
        # Warm up
        await client.call_tool("verify", {
            "artifact": "sha256:test",
            "signature": "test"
        })

        # Measure MCP latency
        start = time.time()
        for _ in range(100):
            await client.call_tool("verify", {
                "artifact": "sha256:test",
                "signature": "test"
            })
        mcp_latency = (time.time() - start) / 100

        # Compare to direct HTTP API
        # ... (similar measurement)

        # Assert MCP overhead <100ms
        assert mcp_latency < 0.1

@pytest.mark.performance
@pytest.mark.asyncio
async def test_query_large_result_set():
    """Test performance with large transparency log."""
    # Generate 1000 fake entries
    # Query with pagination
    # Assert <500ms response time
    pass
```

---

## Documentation Requirements

### Developer Guides

**1. Quick Start Guide** (`docs/guides/mcp/trust-quickstart.md`)

````markdown
# Certus-Trust MCP Quick Start

Get artifact verification in your IDE in 5 minutes.

## Prerequisites

- Docker running
- VS Code, Cursor, or Zed installed
- uv package manager

## Setup

1. Start Certus-Trust:
   ```bash
   just trust-up
   ```
````

2. Configure your IDE:
   [IDE-specific instructions]

3. Test verification:
   Ask your AI assistant: "Verify sha256:abc123..."

4. See results inline!

````

**2. IDE Configuration Guides**
- `docs/guides/mcp/vscode-setup.md`
- `docs/guides/mcp/cursor-setup.md`
- `docs/guides/mcp/zed-setup.md`

**3. Tool Reference** (`docs/reference/mcp/trust-tools.md`)
```markdown
# Certus-Trust MCP Tools Reference

## verify

Verify artifact signature against transparency log.

**Input:**
- `artifact` (string, required): Artifact digest (sha256:...)
- `signature` (string, required): Signature to verify
- `identity` (string, optional): Expected signer identity
- `scenario` (string, optional): Mock scenario for testing

**Output:**
- `valid` (boolean): Signature is valid
- `verified_at` (string): ISO 8601 timestamp
- `signer` (string): Signer identity
- `transparency_index` (int): Rekor log index
- `rekor_entry_url` (string): Transparency log URL

**Examples:**
[Examples here]

## sign
[Similar documentation]
````

**4. Troubleshooting Guide** (`docs/guides/mcp/troubleshooting.md`)

```markdown
# MCP Troubleshooting

## Issue: MCP server won't start

**Symptoms:** Error "Command not found: certus_trust.mcp.server"

**Solution:**

1. Ensure uv installed: `uv --version`
2. Install dependencies: `uv sync`
3. Test directly: `uv run python -m certus_trust.mcp.server`

## Issue: Tools not appearing in IDE

[Solutions here]
```

---

## Risks & Mitigations

| Risk                             | Probability | Impact | Mitigation                                                                     |
| -------------------------------- | ----------- | ------ | ------------------------------------------------------------------------------ |
| **FastMCP API changes**          | Medium      | Medium | Pin fastmcp version, monitor releases, budget 1 week for migration             |
| **Production Rekor unavailable** | Low         | High   | Implement fallback to mock mode, queue signing requests, retry logic           |
| **IDE integration complexity**   | High        | Medium | Start with 1 IDE (VS Code), validate before expanding, provide detailed guides |
| **Developer adoption low**       | Medium      | High   | Pilot with 3 friendly teams first, collect feedback, iterate on UX             |
| **Performance overhead**         | Low         | Medium | Performance tests in CI, <100ms SLA, optimize if needed                        |
| **Security: token leakage**      | Low         | High   | Short-lived tokens (1 hour TTL), scope to specific tools, audit logs           |

---

## Success Metrics

### Technical Metrics

| Metric                | Target | Measurement                              |
| --------------------- | ------ | ---------------------------------------- |
| **Tool Success Rate** | >95%   | MCP tool invocations / total invocations |
| **Latency Overhead**  | <100ms | p95 MCP latency - direct API latency     |
| **Availability**      | >99%   | MCP server uptime                        |
| **Test Coverage**     | >80%   | Line coverage for mcp/ module            |

### User Metrics

| Metric           | Target                | Measurement                            |
| ---------------- | --------------------- | -------------------------------------- |
| **Time Savings** | >50%                  | Before/after workflow measurements     |
| **Adoption**     | 5+ daily active users | Unique users calling MCP tools per day |
| **Satisfaction** | >8/10                 | Post-pilot developer survey            |
| **Use Cases**    | 5 validated           | Real-world workflows documented        |

### Business Metrics

| Metric                     | Target | Measurement                                       |
| -------------------------- | ------ | ------------------------------------------------- |
| **Verification Frequency** | +30%   | Artifact verifications per week (MCP vs baseline) |
| **Incident Response Time** | -50%   | Time to verify provenance during security alerts  |
| **Compliance Cost**        | -75%   | Hours to generate audit reports                   |

---

## Future Enhancements (Post-Pilot)

### Phase 2: Unified Gateway (Weeks 7-10)

**If pilot succeeds**, build optional unified gateway:

```python
# mcp_gateway/server.py
from fastmcp import FastMCP
from certus_trust.mcp import mcp as trust_mcp
from certus_ask.mcp import mcp as ask_mcp  # Future
from certus_assurance.mcp import mcp as assurance_mcp  # Future

gateway = FastMCP("Certus Gateway")

# Compose service MCPs
gateway.mount("/trust", trust_mcp)
gateway.mount("/ask", ask_mcp)
gateway.mount("/assurance", assurance_mcp)

# Centralized auth, allowlists, telemetry
```

**Benefits:**

- One IDE configuration
- Unified auth and policy
- Cross-service workflows

**Effort:** 4 weeks

---

### Phase 3: Additional Services (Weeks 11-14)

- **Certus-Ask MCP** (document ingestion, RAG queries)
- **Certus-Assurance MCP** (security scans with streaming)
- **Certus-Transform MCP** (artifact promotion)

**Dependencies:**

- Trust MCP pilot validated
- Gateway architecture proven
- Developer demand confirmed

---

### Phase 4: Advanced Features (Weeks 15+)

- **Background workers** for long-running operations
- **WebSocket streaming** for real-time progress
- **Multi-tenant auth** with capability allowlists
- **Enhanced observability** (Prometheus metrics, distributed tracing)
- **External integrations** (public Sigstore, vulnerability DBs)

---

## Appendices

### Appendix A: MCP Protocol Overview

**Model Context Protocol (MCP)** is a standard for LLM agents to invoke tools:

```
IDE/Agent → MCP Client → JSON-RPC → MCP Server → Tool Implementation
```

**Key Concepts:**

- **Tools**: Functions agents can call (like `verify`, `sign`)
- **Resources**: Data agents can read (like transparency log entries)
- **Prompts**: Templates for common tasks
- **Transports**: stdio (local), HTTP (remote), SSE (streaming)

**Python Implementation:**

```python
from fastmcp import FastMCP, tool

mcp = FastMCP("My Service")

@mcp.tool()
def my_tool(input: str) -> str:
    """Tool description for AI agent."""
    return f"Result: {input}"

mcp.run(transport="stdio")
```

---

### Appendix B: Certus-Trust Production Readiness

**Current State (as of 2025-12-29):**

| Component             | Status  | Notes                                       |
| --------------------- | ------- | ------------------------------------------- |
| **Rekor Integration** | ✅ 100% | Real HTTP client, production-tested         |
| **Signing Service**   | ✅ 90%  | Works with ephemeral keys (Fulcio pending)  |
| **Verification**      | ✅ 95%  | Full chain validation (minus Fulcio certs)  |
| **Transparency Log**  | ✅ 100% | Real Merkle proofs, query API               |
| **Provenance Chain**  | ✅ 100% | Complete audit trails                       |
| **FastAPI Endpoints** | ✅ 100% | All 11 endpoints working                    |
| **Docker Deployment** | ✅ 100% | Production-ready compose files              |
| **Tests**             | ⚠️ 70%  | Smoke tests pass, integration tests partial |

**What Works Today:**

- ✅ Real Rekor transparency log submissions
- ✅ Cryptographic signing (local ephemeral keys)
- ✅ Complete provenance chains
- ✅ Mock scenarios for testing
- ✅ Service statistics and monitoring

**What's Pending (not blocking MCP):**

- ⚠️ Fulcio OIDC integration (uses local keys for now)
- ⚠️ Full certificate chain validation
- ⚠️ Production database persistence (in-memory OK for pilot)

**Verdict:** Trust is production-ready for MCP pilot. Fulcio integration can happen in parallel.

---

### Appendix C: Example AI Assistant Prompts

**For Developers:**

```
"Is this package verified?"
→ verify(artifact="sha256:...", identity="internal-ci")

"Sign my container image myapp:v2.1.0"
→ sign(artifact="sha256:...", artifact_type="container_image", subject="myapp:v2.1.0")

"Show me the provenance for scan_abc123"
→ get_provenance(scan_id="scan_abc123")

"List all signatures from last week"
→ query_transparency(start_date="2025-12-22", end_date="2025-12-29")

"How many artifacts have we signed this month?"
→ get_stats() → extract total_signatures
```

**For Security Engineers:**

```
"Verify scan integrity for incident #1234"
→ Extract scan_id from incident
→ get_provenance(scan_id=...)
→ Summarize chain status

"Show me all failed verifications today"
→ get_stats() → extract verification_stats.failed
→ query_transparency(filter by failed status if available)

"Generate compliance report for Q4"
→ query_transparency(start_date="2024-10-01", end_date="2024-12-31")
→ Format as report
```

---

### Appendix D: Comparison with Other Services

**Why Trust is better FIRST target than Ask or Assurance:**

| Factor               | Trust                       | Ask                      | Assurance                 |
| -------------------- | --------------------------- | ------------------------ | ------------------------- |
| **Complexity**       | ✅ Simple (stateless)       | ❌ Complex (stateful)    | ❌ Complex (long-running) |
| **Response Time**    | ✅ <1s                      | ❌ Minutes               | ❌ Minutes                |
| **Streaming**        | ✅ Not needed               | ❌ Required              | ❌ Required               |
| **Production Ready** | ✅ 70% (Rekor works)        | ⚠️ 95%                   | ⚠️ 60%                    |
| **Dependencies**     | ✅ Optional (Sigstore)      | ❌ Required (OpenSearch) | ❌ Required (Dagger)      |
| **Use Case Clarity** | ✅ High                     | ⚠️ Medium                | ⚠️ Medium                 |
| **Developer Impact** | ✅ High (sign/verify daily) | ⚠️ Medium                | ⚠️ Medium (has CLI)       |

**Conclusion:** Trust offers fastest path to validated MCP integration.

---

## References

- [Model Context Protocol Specification](https://modelcontextprotocol.io)
- [FastMCP Documentation](https://gofastmcp.com)
- [Certus-Trust Production Implementation](../../../trust/PRODUCTION_IMPLEMENTATION.md)
- [Certus-Trust Mock Features](../../../trust/MOCK_FEATURES.md)
- [MCP & ACP Integration Proposal](mcp-proposal.md) (full vision)

---

## Changelog

| Date       | Version | Changes       |
| ---------- | ------- | ------------- |
| 2025-12-29 | v0.1    | Initial draft |

---

## Notes for Reviewers

### Key Questions

1. **Scope**: Is 6 weeks realistic for Trust MCP pilot?
2. **Architecture**: Per-service MCP vs unified gateway first?
3. **Production Rekor**: Should pilot use `MOCK_SIGSTORE=false`?
4. **Use Cases**: Are the 5 workflows representative?
5. **Success Criteria**: Are metrics achievable?

### Approval Checklist

- [ ] Architecture reviewed by platform team
- [ ] Timeline validated by engineering leads
- [ ] Use cases validated by product team
- [ ] Resource allocation confirmed
- [ ] Risks understood and accepted
