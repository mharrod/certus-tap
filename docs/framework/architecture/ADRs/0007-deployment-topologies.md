# ADR 0007 – Deployment Topologies (Hybrid, Self-Hosted, SaaS)

## Status

Accepted – November 2025

## Context

Customers have varying requirements around data residency, operational control, and regulatory compliance. Some want Certus to provide everything as a managed SaaS, others need on-prem / air-gapped deployments, and many prefer a hybrid split where Certus hosts the conversational and signing services while the customer retains control over scanning + storage.

The architecture already supports:

- Certus-Assurance, Certus-Transform, and raw/golden storage running in customer infrastructure.
- Certus-Ask, certus-evaluate, and Certus-Trust operated as SaaS or in customer control.
- `certus_integrity` running either embedded with workloads or as a central shared service.

We need to formalize these topologies so product and engineering teams can reason about data flows, feature compatibility, and SLAs.

## Decision

Adopt three supported deployment models:

1. **Hybrid SaaS (default):**
   - Customer runs Certus-Assurance, Certus-Transform, `certus_integrity` (optional), raw/golden buckets, and the security module.
   - Certus hosts Certus-Ask, certus-evaluate, Certus-Trust, and a shared integrity service.
   - HTTPS ingress + signed evidence link the two environments. Only prompts/responses/derived metadata leave the customer boundary.

2. **Fully Self-Hosted:**
   - Customer deploys every Certus service (Ask, Evaluate, Assurance, Transform, Integrity, Trust) plus Sigstore dependencies, MLflow, and observability stacks.
   - Certus provides reference Helm charts / Compose files but does not operate any runtime components.

3. **Fully SaaS:**
   - Certus operates the entire stack; customers interact via API, CLI, or secure uploads.
   - Customers can still embed `certus_integrity` or the security module if they want local guardrails, but it is optional.

`certus_integrity` remains a portable module that can run embedded with workloads or as a shared service in any model.

## Consequences

- Documentation, deployment scripts, and support processes must explicitly call out which features are available per model (e.g., hybrid requires outbound access to Certus-Trust).
- Pricing/SLAs can align with the chosen topology (hosted vs self-managed).
- Engineering must keep the APIs stable so both SaaS and self-hosted deployments stay interoperable.
- Future services should be evaluated against these models to confirm they can operate with customer-controlled storage and optional internet connectivity.
