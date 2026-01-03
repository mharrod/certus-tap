# Guardrails

> **Status:** ⚠️ In progress (privacy guardrails exist; additional control types are roadmap)

This workflow captures how assurance guardrails—privacy filters, policy checks, AI safety controls—operate alongside ingestion and evaluation pipelines.

---

## 1) Privacy Scanning & Quarantine

> _Detect and handle sensitive information before it reaches shared storage._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Intake
    participant Guard as Privacy_Guardrail
    participant Ledger
    participant Reviewer
    autonumber

        Intake->>Guard: Stream document chunks + metadata
        Guard->>Guard: Detect PII entities, classify severity
        Guard-->>Intake: Return clean, anonymized, or quarantined docs
        Guard->>Ledger: Log entity counts, confidence, action
        alt Quarantine
            Guard->>Reviewer: Request human approval/masking
            Reviewer-->>Guard: Approve/waive with signature
        end
    ```

**Highlights**

- Supports multiple dispositions: pass-through, mask in-place, quarantine for review.
- Structured logs feed privacy incident metrics and tuning.

---

## 2) Policy Guardrails (Security, AI Safety, Compliance)

> _Apply configurable rules on findings, prompts, or outputs._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Pipeline
    participant Policy as Guardrail_Service
    participant Human
    participant Ledger
    autonumber

        Pipeline->>Policy: Submit finding/output for guardrail evaluation
        Policy->>Policy: Apply rule set (e.g., prompt safety, critical vuln block)
        alt Pass
            Policy-->>Pipeline: Allow execution, attach policy hash
        else Needs Review
            Policy->>Human: Request escalation with context
            Human-->>Policy: Approve waiver / reject
        end
        Policy->>Ledger: Log decision with rule id + signer
    ```

**Highlights**

- Extensible to different guardrail domains—security, AI prompt/output filtering, compliance checks.
- Human escalation covers ambiguous cases; all decisions are logged.

---

## 3) Incident & Drift Detection

> _Monitor guardrail outcomes to spot anomalies or regressions._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Monitor
    participant Guardrails
    participant Ops
    participant Execs
    autonumber

        Monitor->>Guardrails: Collect metrics (violations, waivers, confidence)
        Guardrails-->>Monitor: Stream events
        Monitor-->>Ops: Alert on spikes/drift
        Ops->>Execs: Escalate if thresholds breached, trigger playbooks
    ```

**Highlights**

- Enables SLA tracking (time to approve quarantines, waiver volume, etc.).
- Supports exec scorecards and platform operations response plans.

---

## 4) Governance & Tuning

> _Adjust guardrail thresholds, models, and routing policies under change control._

- Propose configuration/model updates with rationale.
- Route for approval (security/privacy leads, legal, execs).
- Track versions, effective dates, and rollback plans in the TrustCentre/manifest.

**Outcome:** Guardrails evolve with business needs while retaining auditability.

---

## 5) Cross-Workflow Integration

- **Ingestion:** Guardrails run immediately after intake → see [Document Ingestion](ingestion-query.md).
- **Developer:** Local guardrails mirror centralized policies → see [Developer Workflows](developer.md).
- **Security Engineer:** Chat agent surfaces guardrail decisions and allows waivers → see [Security Engineer](engineer.md).
- **Platform Ops:** Monitor guardrail health, roll out config updates → see [Platform](platform.md).
- **Executive/Audit:** View guardrail metrics and approvals via scorecards → see [Executive](executive.md) / [Assurance & Audit](assurance.md).

---

**Outcome:** A modular guardrail system that enforces privacy, security, and compliance policies consistently across ingestion, evaluation, and runtime—ready to extend beyond privacy into broader control surfaces.
