# ADR 0009 – Guardrail Framework Standardization

## Status

Accepted – November 2025

## Context

Certus services require consistent guardrails for prompt injection, PII leakage, code safety, vulnerability hallucination, data exfiltration, jailbreak attempts, and other security concerns. Early prototypes used ad hoc scripts within each service. That made it hard to reuse logic (e.g., Ask vs Evaluate), hard to enforce shadow/enforce modes, and difficult to emit signed evidence.

We evaluated:

- Building every guard from scratch per service.
- Using third-party SaaS guardrail products.
- Standardizing on open-source libraries (LLM Guard, NeMo Guardrails, Microsoft Presidio) plus custom validators.

## Decision

Create a guardrail framework inside certus-evaluate (and re-exported via certus-integrity middleware) with these characteristics:

1. **Validated Tooling:** Use a combination of open-source libraries (Microsoft Presidio, LLM Guard, NeMo Guardrails, Bandit/Semgrep) augmented by Certus-specific validators (prompt injection patterns, CVE/CWE validation, exfil heuristics).
2. **Shadow/Enforce Modes:** Every guard supports `shadow_mode` (log only) and `enforce` (block response). Configuration lives in environment variables / feature flags.
3. **Evidence Generation:** Guards emit `IntegrityDecision` payloads with structured metadata (detected entities, severity, scores) and send them through certus-integrity.
4. **Reusable Components:** Haystack components (`PIIGuard`, `PromptInjectionGuard`, `CodeSafetyGuard`, etc.) and FastAPI middleware adapt the same guard policies, so Ask, Evaluate, and future services share logic.
5. **Pluggable Policies:** Thresholds and allowed entities are set via configuration; customers can opt into stricter rules or add allowlists.

## Consequences

- Guardrail logic lives primarily in certus-evaluate (Haystack components) and certus-integrity (middleware), reducing duplication.
- Updates to guard policies can be rolled out centrally and automatically apply to both inline and batch workflows.
- Shadow mode enables safe rollout; evidence logs provide auditability even before enforcement.
- Engineering must keep third-party dependencies patched and scanned (the Dagger security module plus Certus-Assurance cover this).
