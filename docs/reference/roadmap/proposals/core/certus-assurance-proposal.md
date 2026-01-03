# Certus-Assurance Modernization

**Status:** Draft
**Author:** DevOps/RAG Agent
**Date:** 2025-12-07
## Executive Summary

Certus-Assurance is the mock security scanning service bundled with Certus TAP. It currently accepts scan requests, emits deterministic SARIF/SPDX bundles, and powers provenance tutorials. We will evolve this incubated service into the production scan runner by:

1. Refactoring the pipeline to reuse the Dagger module (see `dagger-proposal.md`) so scans run through one shared engine.
2. Exposing both HTTP and CLI interfaces—the same Python package will be callable via FastAPI, `just` targets, Dagger, MCP, and ACP.
3. Aligning storage, provenance, and signer contracts with Certus Trust and Transform (S3 uploads, registry pushes).
4. Preparing the service for extraction (managed SaaS or customer-hosted) once milestones are complete.

## Motivation

### Current State

- Certus-Assurance service lives in `certus_assurance/` with a FastAPI router, job manager, and mock pipeline.
- Artifact schema, API endpoints, and tutorials are well documented (`certus-assurance-roadmap.md`, `docs/learn/provenance/*`).
- Scan execution uses placeholder runners; security scans run in-process per request.
- Integrations with Certus Trust/Transform (upload requests, verification proofs) are functional but not hardened.

### Problems Addressed

1. **Duplicate pipelines:** The mock runner differs from the upcoming Dagger module; keeping them in sync is labor-intensive.
2. **Inconsistent interfaces:** CLI users call `tools/security/run_certus_assurance_security.py`, while API calls hit the FastAPI service; behavior may diverge.
3. **Limited observability:** Status polling and logs exist, but there’s no streaming/log aggregation or MCP/ACP support.
4. **Scale constraints:** The current threaded job manager isn’t ready for parallel scans, quotas, or managed hosting.

## Goals & Non-Goals

| Goals                                                                                    | Non-Goals                                                                                           |
| ---------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Adopt the Dagger security module as the canonical scan engine for Certus-Assurance       | Replace Certus-Assurance with an entirely new service                                               |
| Provide both API (FastAPI) and CLI/Dagger entry points backed by the same Python package | Force all customers to adopt the API (CLI workflows remain supported)                               |
| Align storage, provenance, and signer contracts with Certus Trust/Transform              | Redesign Trust/Transform themselves                                                                 |
| Prepare Certus-Assurance to act as the managed scan service that powers MCP/ACP flows    | Immediately split Certus-Assurance into a separate repository (extraction happens after milestones) |

## Proposed Solution

### Architecture Overview

```
┌────────────────────────────────────────────┐
│            Certus-Assurance vNext          │
├────────────────────────────────────────────┤
│  Application Layer                         │
│    • FastAPI service (REST+WebSocket)      │
│    • CLI / Dagger entry points             │
│    • MCP & ACP adapters (future)           │
│                                            │
│  Scan Engine                               │
│    • Python package wrapping `security.light/heavy` from dagger-proposal |
│    • Shared configuration (profiles, tool toggles)                       |
│    • Streamed logs + events                                                   |
│                                            │
│  Orchestration & Storage                  │
│    • Job manager (Celery/Dagger runner)    │
│    • S3 (Certus Transform) artifact store  │
│    • Registry + cosign signing             │
│    • Telemetry to Certus Insight/OpenSearch│
└────────────────────────────────────────────┘
```

- FastAPI service exposes `POST /v1/security-scans`, `GET /v1/security-scans/{id}`, upload hooks, and WebSocket streaming. It calls the shared scan package (which sits on top of the Dagger module) so CLI/CI/API all behave identically.
- CLI / `just test-security-*` call the same package directly; Dagger profiles remain accessible via `dagger call`.
- MCP/ACP adapters (per the MCP proposal) invoke the FastAPI endpoints to give IDEs/agents the same experience.
- Artifact storage moves from local `.artifacts/` to the Certus Transform S3-compatible store, using the contract defined in the roadmap.

### Key Enhancements

1. **Dagger Module Integration:** Replace the mock pipeline with the `security.light`/`security.heavy` module (with profile flags for customers). The Certus-Assurance package becomes the thin orchestration layer.
2. **API + CLI Parity:** Build scan orchestration as a Python package so both the FastAPI service and CLI entry points reuse the same functions.
3. **Observability:** Add WebSocket streaming, structured logs, and Insight telemetry for every scan (status transitions, artifacts, policy gate outcomes).
4. **Managed Workflow:** Support MCP/ACP adapters plus REST webhooks so Certus-Assurance can run scans on behalf of other teams, returning signed artifacts and uploading to Certus Transform automatically.
5. **Policy & Profiles:** Allow workspace-specific policy bundles (severity thresholds, tool allowlists) and scan templates (PCI, FedRAMP, nightly) so teams can enforce compliance consistently.
6. **Integrations:** Provide native webhooks for Slack/Jira/GitHub code scanning, plus connectors to push findings into Certus Insight dashboards automatically.
7. **Secrets & Runner Isolation:** Offer self-service secret management (Git/registry/cosign credentials) with audit logging, and support sandboxed runners (Kubernetes pods, ephemeral builders) for tenant isolation.

### Phase 2 Snapshot (Current Implementation)

- **Manifest + profile aware API:** `POST /v1/security-scans` now requires an exported manifest (`manifest` field) and the desired profile (`profile`). The same JSON is forwarded to the shared `security_module`, so CLI, Dagger, and API runs execute an identical tool/toolchain map and honor manifest-defined severity gates.
- **Streaming telemetry:** Every scan advertises `stream_url` in the response (`/v1/security-scans/{scan_id}/stream`). WebSocket clients receive `tool_start`, `tool_complete`, and `log` events in real time; the history is persisted inside each bundle (`logs/runner.log` + `stream.jsonl`) for provenance.
- **Heavy profile parity:** API callers can select `"heavy"` (or any manifest profile) and get the same stack bootstrap + placeholder DAST/API passes we exercise in the Dagger CLI (`security-scan --profile heavy`). Light/heavy parity is now verified in tests and wired through Certus-Assurance end to end.
- **Raw → golden uploads:** After Trust permits an upload, the service stages artifacts under `s3://raw/security-scans/{scan_id}/incoming/...` and copies them to `s3://golden/security-scans/{scan_id}/golden/...`, stamping `manifest_digest` + `scan_id` metadata on every object so Certus Transform can verify and promote bundles deterministically.
- **Enriched metadata:** `GET /v1/security-scans/{scan_id}` now returns `manifest_digest`, `manifest_metadata`, and the canonical `stream_url` alongside artifact paths, registry info, and Trust state. Downstream services (Transform, Trust, TAP ingestion) can reason about the manifest + websocket endpoint without guessing.

## Dependencies

- **Dagger Security Module:** `dagger-proposal.md` must deliver the reusable scan functions (light/heavy profiles, tool orchestration, artifact publishing). Certus-Assurance depends on those functions to avoid duplicating scan logic.
- **Certus Transform S3 store:** Artifact uploads are routed through Transform; bucket/prefix configuration must be wired into Certus-Assurance settings.
- **Certus Trust verification APIs:** Upload/verification flows continue to hit Trust; adjustments may be required to accommodate new signer metadata or provenance fields.
- **MCP/ACP Gateway:** Future MCP/ACP adapters will reuse Certus-Assurance endpoints; ensure the API supports token-based auth and streaming required by the gateway.

## Phased Roadmap

### Phase 0 – Alignment (Weeks 0-1)

- Audit existing pipeline, API, and artifact contracts; document gaps between current implementation and Dagger module outputs.
- Define shared Python package interface (`certus_assurance.scans.run_scan(profile, params)`).
- Update documentation (`docs/reference/components/certus-assurance.md`) to reference the upcoming changes.

### Phase 1 – Shared Scan Engine (Weeks 2-4)

- Integrate the Dagger module (`security.light`/`security.heavy`) into Certus-Assurance’s Python package.
- Add FastAPI endpoints that invoke the shared scan functions; ensure CLI/Dagger entry points import the same package.
- Support streaming logs/status via WebSocket and structured JSON responses.
- Update tests (`tests/certus_assurance/*`) to cover the shared package and API.

### Phase 2 – Storage & Provenance Hardening (Weeks 5-7)

- Move artifact storage to Certus Transform’s S3-compatible bucket; ensure the layout matches `certus-assurance-roadmap.md`.
- Wire cosign/in-toto signing using the Dagger module’s outputs; push signed images to the configured registry.
- Integrate with Certus Trust upload APIs to automate verification proof generation post-scan.
- Emit telemetry (OpenSearch/Insight) for every scan event with references to artifacts and trust status.

### Phase 3 – Observability & Policy (Weeks 8-9)

- Add rate limiting, per-tenant quotas, and severity gates; fail scans when policy budgets are exceeded.
- Implement Webhook callbacks and Slack notifications for scan completion/failure.
- Enhance UI/CLI to surface policy failures alongside artifacts.
- Expose policy bundles and scan templates (e.g., PCI, FedRAMP) so teams can select predefined toolsets and severity gates.

### Phase 4 – MCP/ACP & Managed Service (Weeks 10-12)

- Expose Certus-Assurance operations through the MCP/ACP gateway (per `mcp-acp-proposal.md`).
- Provide example IDE/agent configs for triggering scans via MCP/ACP.
- Pilot managed scan workflows with internal teams; ensure results flow back into TAP automatically.
- Add scheduling primitives (nightly/weekly scans), webhook/Jira/GitHub connectors, and self-service secret management to support fully managed workflows.

### Phase 5 – Extraction Readiness (Post-M12)

- Keep all Certus-Assurance code encapsulated in its module; document deployment steps.
- Evaluate splitting the service into a standalone repository or managed offering once milestones are satisfied.
- Layer in advanced platform features (scan templates, policy bundles, scheduled recurrence) so extraction delivers a full managed service out of the box.

## Deliverables

- Updates to `certus_assurance/` integrating the Dagger scan module and shared package.
- FastAPI service exposing parity with CLI/Dagger entry points plus WebSocket streaming.
- Artifact uploads to Certus Transform S3-compatible bucket with cosign/in-toto support.
- Telemetry dashboards (Certus Insight) showing scan volumes, policy outcomes, and artifact links.
- MCP/ACP adapters wrapping the Certus-Assurance API.
- Documentation updates (component guides, learn tutorials, testing references) reflecting the new workflow.

## Success Metrics

1. **Parity:** FastAPI and CLI entry points produce identical artifacts (x-check `scan.json` fingerprints).
2. **Runtime:** Light scans complete within 10 minutes; heavy scans within 45 minutes with caching (aligned with the Dagger proposal).
3. **Adoption:** All provenance tutorials and premium ingestion tests use the new scan engine without regressions.
4. **Artifact Delivery:** 100% of scans upload SARIF/SBOM/provenance to Certus Transform automatically.
5. **Agent Integration:** MCP/ACP pilot users successfully trigger scans and receive results inside their IDEs.

## Next Steps

1. Approve this proposal so work can begin alongside the Dagger module and MCP/ACP initiatives.
2. Create a tracking epic covering the phases above plus dependencies on Dagger and Certus Transform enhancements.
3. Begin Phase 0 alignment by finalizing the shared scan package interface and updating component docs.

### Integration Checklist

| Area                     | Requirements                                                                                                              | Status/Notes |
| ------------------------ | ------------------------------------------------------------------------------------------------------------------------- | ------------ |
| Engine adoption          | Certus-Assurance imports `security_module.run_scan`, retires mock runner, and exposes manifest/profile inputs via API/CLI |              |
| Artifact storage         | SARIF/SBOM/provenance uploaded to Certus Transform S3-compatible buckets with signed digests                              |              |
| Trust verification       | Automatic Trust upload + verification proofs post-scan, surfaced in metadata responses                                    |              |
| Streaming/telemetry      | WebSocket streaming, structured logs, Insight telemetry for status + policy outcomes                                      |              |
| Notifications & webhooks | Slack/Jira/GitHub webhook payloads for pass/fail, optional policy gate summaries                                          |              |
| MCP/ACP adapters         | IDE/agent adapters invoking API endpoints with streaming results                                                          |              |

### Dependencies & Interfaces

- Upstream: depends on the manifest schema/export (policy layer) and the runtime-agnostic `security_module` package (engine layer). Track readiness via `security-platform-architecture.md`.
- Downstream: feeds Certus Transform (artifact storage), Certus Trust (verification), TAP ingestion (OpenSearch/Insight), and MCP/ACP gateways. Coordinate any API/schema change with those consumers.

### Testing Strategy

- Unit tests for API schemas, job manager state transitions, and manifest ingestion.
- Integration tests invoking `security_module` via the FastAPI service (light/heavy profiles) with golden artifact comparisons.
- Storage/Trust smoke tests validating S3 uploads and verification proofs (can reuse TAP smoke suites).
- Load tests for concurrent job submissions, ensuring WebSocket/log streaming keeps up with target throughput.
