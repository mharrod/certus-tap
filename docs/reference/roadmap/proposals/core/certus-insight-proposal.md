# Certus-Insight Service

**Status:** Draft
**Author:** System Architecture
**Date:** 2025-12-07
## Executive Summary

Certus-Insight is a new microservice that transforms raw Certus-Assurance outputs (SARIF, SBOM, provenance) into executive-ready reports, risk analytics, and supply-chain intelligence. It signs and publishes compliance reports, verifies OCI attestations, aggregates findings over time, and exposes APIs that downstream tools (Certus-Ask, MCP/ACP agents, dashboards) can consume. The MVP will provide templated reports backed by sample data; subsequent phases add live data sources, graph queries, and connectors.

## Motivation

### Current State

- Certus-Assurance and Certus-Trust produce verified scan artifacts and provenance but lack a reporting/analytics surface.
- Certus-Ask focuses on ingestion/RAG workflows; compliance reports and dashboards are handcrafted or external.
- Supply-chain verification (OCI attestations, SLSA provenance) exists in tutorials but not as a reusable service.

### Problems Addressed

1. **Reporting Gap** – No centralized service to generate signed compliance reports (PDF/HTML/JSON).
2. **Supply-Chain Intelligence** – No API to verify OCI artifacts, SBOMs, or provenance before ingestion.
3. **Risk Analytics** – No consolidated dashboard tracking findings, remediation, or compliance frameworks.
4. **Publishing & Notifications** – Report uploads, signatures, and notifications are ad-hoc scripts, not APIs.

## Goals & Non-Goals

| Goals                                                                           | Non-Goals                                                                 |
| ------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| Provide APIs for compliance reporting, analytics, and supply-chain verification | Replace Certus-Assurance/Trust pipelines                                  |
| Publish signed reports to Certus Transform and expose shareable links           | Build a full UI dashboard (initially API-first)                           |
| Aggregate findings across scans for trends/compliance scoring                   | Become the primary ingestion workflow (Certus-Ask owns ingestion)         |
| Integrate with MCP/ACP so agents can request reports/metrics                    | Immediately support every compliance framework (start with targeted sets) |

## Proposed Solution

### Architecture Overview

```
┌───────────────────────────────────────────────┐
│                 Certus-Insight                │
├───────────────────────────────────────────────┤
│ API Layer (FastAPI)                           │
│   • /v1/reports (generate/list/download)      │
│   • /v1/analytics (risk, trends, compliance)  │
│   • /v1/attestations / sbom / provenance      │
│   • Webhooks + MCP/ACP adapters               │
│                                               │
│ Services                                      │
│   • Compliance Reporter (Jinja2 + PDF)        │
│   • Analytics Engine (SARIF/SBOM parsers)     │
│   • Supply-Chain Verifier (cosign, SLSA)      │
│   • Publisher (S3 upload, trust signing)      │
│                                               │
│ Data Sources                                  │
│   • Neo4j (verified scans)                    │
│   • OpenSearch (findings)                     │
│   • S3 / Certus Transform (artifacts)         │
│   • OCI Registry / Sigstore (attestations)    │
└───────────────────────────────────────────────┘
```

### Key Capabilities

1. **Compliance Reporting** – Generate PDF/HTML/JSON reports from verified scans with templates, exec summaries, remediation sections, and cosign signatures. Publish to Certus Transform S3 and return presigned links.
2. **Supply-Chain Intelligence** – Verify OCI artifacts (cosign, Rekor), analyze SBOMs (licenses, CVEs), and validate SLSA provenance before ingestion.
3. **Analytics & Dashboards** – Aggregate SARIF findings into risk metrics, trends, compliance scores (e.g., OWASP Top 10), and remediation progress; expose APIs for dashboards.
4. **Publishing & Notifications** – Upload reports to S3, serve via HTTP, emit webhooks/Slack notifications, and optionally send results to Jira or other systems.

## Dependencies

- **Certus-Assurance** – Provides scan artifacts consumed by Insight; alignment with the Dagger-based pipeline ensures consistent schema.
- **Certus-Trust** – Signs reports and provides verification proofs; Insight must integrate with Trust for signature APIs.
- **Certus Transform** – Stores published reports and analytics outputs in its S3-compatible buckets.
- **Neo4j/OpenSearch** – Provide verified scan data and findings for analytics.
- **MCP/ACP Gateway** – Later phases expose Insight capabilities via MCP/ACP, reusing the service endpoints.

## Phased Roadmap

### Phase 0 – Service Skeleton & Sample Data (Weeks 0-1)

- Scaffold FastAPI app with `/v1/reports` endpoints backed by sample data (`samples/non-repudiation`).
- Implement Jinja2 + WeasyPrint templates for HTML/PDF generation.
- Upload reports to Certus Transform S3 (or LocalStack) and return presigned URLs.
- Mock signing metadata to mirror future Trust integration.

### Phase 1 – Analytics & Dashboards (Weeks 2-3)

- Parse sample SARIF/SBOM files to compute risk posture, trends, and compliance scores.
- Implement `/v1/analytics/*` endpoints returning aggregated metrics.
- Provide dashboard summary API (counts, remediation progress, top findings).
- Ensure sample data fallback works when live data sources are unavailable.

### Phase 2 – Supply-Chain Intelligence (Weeks 4-5)

- Add SBOM analysis API (license compliance, vuln checks) using sample data first.
- Implement attestation verification API: ORAS pulls, cosign verification (test keys), Rekor lookup.
- Provide provenance validation endpoint (mock SLSA initially, extend later).
- Publish sample attestation verification results for tutorials.

### Phase 3 – Live Data Integration (Weeks 6-8)

- Connect to Neo4j (verified scans) and OpenSearch (findings) for real reports/analytics.
- Support fallback to samples when data sources are offline.
- Integrate with Certus-Trust signing APIs to sign reports and include Rekor entries.
- Add webhooks/Slack notifications for report completion.

### Phase 4 – MCP/ACP & Polished Integrations (Weeks 9-11)

- Expose Insight capabilities via the MCP/ACP gateway so IDEs/agents can request reports/analytics.
- Add connectors (Jira, GitHub code scanning, Insight dashboards) and scheduling (weekly/monthly reports).
- Provide self-service configuration for templates, notification targets, and compliance frameworks.

### Phase 5 – Production Hardening (Post-M11)

- Authentication/authorization, rate limiting, audit logging, and full test coverage.
- Real cosign signing (no mocks) with error handling, retries, and monitoring.
- Document deployment/extraction steps for standalone Insight service.

## Deliverables

- FastAPI service (`certus_insight/`) with reporting, analytics, and supply-chain endpoints.
- Templates (HTML/PDF/JSON) for compliance reports with signing metadata.
- SBOM/attestation verification utilities and sample data integration.
- S3 publishing, webhook notification, and optional Slack/Jira connectors.
- Documentation updates (component guides, tutorials) demonstrating Insight workflows.

## Success Metrics

1. **Report Generation:** 100% of targeted assessments produce signed reports with presigned URLs.
2. **Analytics Adoption:** Certus Insight APIs power dashboards/PDFs for at least two internal teams.
3. **Supply-Chain Coverage:** OCI attestation verification and SBOM analysis succeed for sample + live data.
4. **Integration Readiness:** MCP/ACP pilots can request reports/analytics with <5% latency overhead.
5. **Data Alignment:** Reports derived from live Neo4j/OpenSearch data match sample outputs within expected tolerances.

## Next Steps

1. Approve this proposal and allocate engineering resources aligned with the Certus-Assurance and MCP/ACP roadmaps.
2. Create an implementation epic with the phase checklist and dependencies (Neo4j data availability, Trust signing APIs, S3 buckets).
3. Begin Phase 0 by scaffolding the FastAPI service, wiring sample data, and updating documentation references.
