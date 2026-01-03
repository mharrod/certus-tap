# Certus-Trust Service

**Status:** Draft
**Author:** System Architecture
**Date:** 2025-12-07
## Executive Summary

Certus-Trust is the supply-chain integrity service for Certus TAP. It wraps the Sigstore stack (Fulcio, Rekor, Cosign, TUF, Keycloak) to provide artifact signing, verification, and transparency proofs. Today Trust is intertwined with tutorials and mock flows. This proposal formalizes Certus-Trust as a standalone, independently testable service that issues outer signatures, verifies inner signatures from Certus-Assurance, and exposes APIs for other services (Transform, Ask, Insight, MCP/ACP agents). We will keep Trust agnostic to artifact storage—its job is to sign and verify regardless of where artifacts reside (S3, OCI registry, etc.).

## Motivation

### Current State

- Certus-Assurance produces inner signatures and provenance; Certus-Trust is partially embedded in tutorials.
- Sigstore components (Fulcio/Rekor/Keycloak) are spun up via Docker but not packaged as a cohesive service.
- APIs for signing/verifying are ad-hoc, and error handling or security hardening is limited.
- Transparency and key distribution workflows are manual; there is no single gateway for other services to request verification.

### Problems Addressed

1. **Fragmented Signing Flow** – No dedicated Trust API for signing/verification; each workflow handles cosign directly.
2. **Missing Transparency Guarantees** – Rekor/TUF usage is not standardized; clients cannot easily query attestations.
3. **Security & Hardening Gaps** – The service lacks clear auth, isolation, and failure handling.
4. **Integration Friction** – Certus Transform, Ask, Insight, and MCP/ACP agents need a stable interface to request signatures or verify attestations.

## Goals & Non-Goals

| Goals                                                                                       | Non-Goals                                                               |
| ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Provide stable REST APIs for signing, verifying, transparency queries, and key distribution | Host customer artifact registries (Transform handles storage)           |
| Package the Sigstore stack (Fulcio, Rekor, Keycloak, TUF) with Trust orchestration          | Replace Cosign CLI entirely (Trust will wrap cosign)                    |
| Keep Trust storage-agnostic (works with S3, registries, etc.)                               | Manage user registries or S3 buckets                                    |
| Support MCP/ACP adapters and future managed workflows                                       | Enforce external auth immediately (start internal-only; add auth later) |

## Proposed Solution

### Architecture Overview

```
┌──────────────────────────────────────────────┐
│               Certus-Trust API               │
├──────────────────────────────────────────────┤
│ FastAPI service (port 8888)                  │
│   • POST /v1/sign                            │
│   • POST /v1/verify                          │
│   • GET  /v1/transparency                    │
│   • GET  /v1/keys                            │
│   • Future: WebSockets / MCP commands        │
├──────────────────────────────────────────────┤
│ Signing Layer                                │
│   • Cosign integration (sign/verify)         │
│   • In-toto/SLSA attestation helpers         │
│   • Key management + policy checks           │
├──────────────────────────────────────────────┤
│ Sigstore Stack (Docker/K8s)                  │
│   • Fulcio (CA, port 5555)                   │
│   • Rekor (transparency log, port 3000)      │
│   • TUF metadata server (port 8001)          │
│   • Keycloak (OIDC provider, port 8080)      │
│   • Cosign CLI                               │
└──────────────────────────────────────────────┘
```

### Key Capabilities

1. **Signing (`POST /v1/sign`)** – Accept artifact references (S3 key, OCI digest, file hash), generate keyless signatures using Fulcio/Keycloak, record entries in Rekor, and return signed payloads plus outer signatures.
2. **Verification (`POST /v1/verify`)** – Validate inner/outer signatures against expected signers, confirm Rekor entries, and produce non-repudiation proofs.
3. **Transparency (`GET /v1/transparency`)** – Query Rekor/TUF for attestations and return inclusion proofs.
4. **Key Distribution (`GET /v1/keys`)** – Serve public keys/metadata, optionally via TUF for secure distribution.
5. **Policy Hooks** – Enforce signer expectations (e.g., inner signer must be Certus-Assurance), track audit logs, and surface warnings when Sigstore components are unavailable.

## Dependencies

- **Sigstore Components** – Fulcio, Rekor, TUF, Keycloak, Cosign; orchestrated via Docker Compose or Kubernetes.
- **Certus-Assurance** – Provides inner signatures and artifacts; Trust verifies these before applying outer signatures.
- **Certus Transform / Ask** – Downstream consumers call Trust APIs to verify artifacts during promotion or ingestion.
- **MCP/ACP Gateway** – Future adapters allow IDEs/agents to request verification or trust proofs from within the editor.

## Phased Roadmap

### Phase 0 – Sigstore Stack & API Skeleton (Weeks 0-2)

- Package Fulcio, Rekor, TUF, Keycloak, and Cosign in docker-compose with health checks.
- Scaffold FastAPI service with placeholder endpoints and smoke tests.
- Document environment configuration and initial runbooks.

### Phase 1 – Signing & Verification API (Weeks 3-5)

- Implement `POST /v1/sign` and `POST /v1/verify` that wrap Cosign for signing/verification.
- Support both S3 paths and OCI references (Trust remains storage-agnostic).
- Return structured proofs including Rekor entry IDs, signer metadata, timestamps.
- Add unit/integration tests using local artifacts from samples.

### Phase 2 – Transparency & Key Distribution (Weeks 6-7)

- Implement `GET /v1/transparency` and `GET /v1/keys` (TUF-backed).
- Provide CLI/SDK helpers so Certus Transform, Ask, and Insight can fetch keys and query attestations.
- Handle Sigstore component outages gracefully (surface warnings, retry policies).

### Phase 3 – Policy, Observability, & MCP (Weeks 8-9)

- Enforce signer policies (e.g., inner signer must be `certus-assurance@certus.cloud`) and emit audit logs.
- Add structured logging, metrics, and optional WebSocket/MCP adapters for real-time verification status.
- Provide example MCP commands so IDE agents can request verification via Certus-Trust.

### Phase 4 – Security Hardening & Extraction Prep (Weeks 10+)

- Add network-level controls (mTLS, network policies) and optional API-key/OIDC middleware without breaking current clients.
- Document deployment steps for running Certus-Trust as a standalone service (Kubernetes manifests, helm charts).
- Integrate with Certus Insight dashboards for signature/audit visibility.

## Deliverables

- FastAPI service (`certus_trust/`) with signing, verification, transparency, and key distribution endpoints.
- Docker/Kubernetes manifests for Fulcio/Rekor/TUF/Keycloak and Trust.
- Cosign/TUF helper utilities plus sample scripts for Certus Assurance and Transform integrations.
- Documentation covering API contracts, security model, failure handling, and runbooks.

## Success Metrics

1. **API Reliability:** Signing and verification endpoints succeed for 99% of requests under nominal load; failures return actionable errors.
2. **Transparency Coverage:** 100% of signatures are recorded in Rekor and retrievable via Trust APIs.
3. **Policy Enforcement:** All outer signatures enforce expected inner signer identities with audit logs.
4. **Integration Adoption:** Certus Assurance, Transform, and Insight call Trust APIs in automated workflows; MCP pilot uses Trust for verification.
5. **Operational Readiness:** Sigstore stack health checks, logging, and recovery procedures are documented and validated.

## Next Steps

1. Approve this proposal and align timelines with Certus-Assurance and MCP/ACP initiatives.
2. Create a tracking epic for the phases above, including Sigstore infrastructure tasks.
3. Begin Phase 0 by packaging the Sigstore stack, scaffolding the FastAPI service, and updating documentation references.
