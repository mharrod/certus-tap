# ADR 0008 – Separate certus-evaluate from certus-integrity

## Status

Accepted – November 2025

## Context

We introduced certus-evaluate to run DeepEval, RAGAS, Haystack evaluators, and security guardrails. certus-integrity already enforces HTTP guardrails and signs `IntegrityDecision` objects via Certus-Trust. Initially, certus-evaluate could have been implemented as a set of plugins inside certus-integrity, but that would:

- Tie heavy dependencies (DeepEval, RAGAS, Presidio, MLflow) to every service using certus-integrity.
- Complicate deployments where integrity must remain lightweight (edge cases, air-gapped environments).
- Mix pure middleware concerns (auth, quotas, global policies) with evaluation/pipeline logic.

## Decision

Keep certus-evaluate and certus-integrity as separate modules/services:

- **certus-evaluate** owns evaluation pipelines, guardrails, Haystack components, CLI, and MLflow integrations. It depends on certus-integrity through the `EvaluationIntegrityBridge`.
- **certus-integrity** remains the lightweight guardrail/signing layer for any service (Ask, Transform, Assurance, Evaluate), exposing consistent APIs and optional middleware.

Integration happens via:

- `IntegrityDecision` payloads sent from certus-evaluate to certus-integrity.
- Shared evidence storage + Certus-Trust for signing.
- Optional co-location (e.g., deploy both services inside the same pod when desired) but no hard dependency.

## Consequences

- certus-integrity stays small and easier to embed or run centrally.
- certus-evaluate can evolve its dependency graph without impacting other services.
- Deployments can choose where to place certus-integrity (embedded, central, SaaS) while reusing the same certus-evaluate binaries.
- Both modules must maintain a stable contract (schema/version) for `IntegrityDecision` objects and evidence references.
