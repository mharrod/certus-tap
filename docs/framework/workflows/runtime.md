# Runtime Assurance (Runtime Analysis & Verification)

> **Status:** ✅ Live (backed by eBPF sensors, Certus Integrity, and Certus Assurance)

These workflows describe how Certus delivers continuous, verifiable runtime application security. eBPF signals act as objective evidence; Certus pipelines normalize, reason, and sign outcomes so customers, engineers, and auditors can trust runtime controls.

---

## 1) Runtime Control Declaration (Manifest Authoring)

> _Declare runtime expectations as contractual controls._

**Library:** Core Processes → Assurance Manifest Definition
**Primary Actor:** Customer / Vendor
**Supporting Actors:** Security Architect, TrustCentre

**Key Actions**

- Extend the Assurance Manifest with runtime statements like _“web services must not spawn shells”_, _“only allowlisted binaries may execute”_, _“sensitive files accessible only by approved workloads”_, or _“outbound connections restricted to approved destinations”_.
- For each control, define evidence source (eBPF finding class), evaluation window (rolling 24h, 7d, etc.), and pass/fail thresholds.
- Publish and sign the manifest update via TrustCentre so downstream services pick up the new policy pack.

**Outputs**

- Signed Assurance Manifest (vX.Y) with runtime clauses
- Immutable provenance entry inside TrustCentre

**Why it matters:** Runtime security becomes contractual instead of ad hoc; every eBPF signal maps to an explicit trust claim.

---

## 2) Runtime Evidence Collection (Scheduled Assurance Execution)

> _Gather windowed runtime behavior without inline blocking._

**Library:** Core Processes → Scheduled Assurance Execution
**Primary Actor:** Pipeline Orchestrator
**Supporting Actors:** Runtime Sensors (eBPF tools), Systems Under Test

**Key Actions**

- On the cadence defined in the manifest, collect normalized outputs from eBPF tooling (detections, policy violations, enforcement actions).
- Scope each job by application, environment, and time window; package artifacts with hashes, timestamps, and tool versions.
- Optionally push raw runtime bundles into RAG memory and TrustCentre OCI for later retrieval.

**Outputs**

- Raw runtime evidence bundle per scope
- Provenance metadata (tool versions, time window, scope)

**Why it matters:** Certus maintains continuous runtime assurance without being in the inline path.

---

## 3) Runtime Event Normalization & Contextualization

> _Turn noisy events into comparable findings._

**Library:** Core Processes → Normalization & Contextualization
**Primary Actor:** Normalization Component
**Supporting Actors:** AI Retrievers / Fusion Engine

**Key Actions**

- Normalize events into a canonical schema (rule ID, action such as exec/connect/open/privilege change, subject identity, target object).
- Generate stable fingerprints for cross-window deduplication and map severity into the Certus unified scale.
- Enrich each finding with manifest clause references, workload identity, and dependency graph context.

**Outputs**

- Deduplicated, normalized runtime findings
- Context-rich records ready for assurance reasoning

**Why it matters:** Runtime behavior becomes analyzable evidence instead of raw telemetry.

---

## 4) Runtime Threat & Assurance Enrichment

> _Correlate runtime events with threat and policy intent._

**Library:** Core Processes → Enrichment (Threat, Assurance & Policy)
**Primary Actor:** Enrichment Service
**Supporting Actors:** AI Fusion Logic / LLM Chain

**Key Actions**

- Correlate normalized findings with known attack patterns, trust boundary crossings, and historical baselines.
- Evaluate each finding against manifest intent, generating human-readable narratives plus exploitability/confidence scores.
- Validate structured outputs (schema + guardrails) before handing them to downstream policy engines.

**Outputs**

- Policy-ready runtime findings (`pass | fail | review`)
- Signed reasoning summaries per cluster of events

**Why it matters:** Runtime AppSec becomes contextual, not just static alerts.

---

## 5) Runtime Policy Evaluation & Human Review

> _Apply deterministic policy while keeping humans accountable._

**Library:** Core Processes → Policy Gate & Human-in-the-Loop
**Primary Actor:** Policy Engine (OPA / CUE)
**Supporting Actors:** Security Engineer

**Key Actions**

- Evaluate enriched findings against manifest thresholds automatically.
- Route low-confidence, exceptional, or escalated cases to a Security Engineer via chat/console.
- Capture approvals, waivers, or rejections; sign and timestamp every decision inside the audit ledger.

**Outputs**

- Final runtime policy verdicts
- Immutable audit entries referencing each decision and signer

**Why it matters:** Prevents silent drift without relying on brittle automation alone.

---

## 6) Security Engineer Runtime Analysis (Conversational)

> _Give engineers a provenance-backed UX to investigate runtime._

**Library:** Security Engineer
**Primary Actor:** Security Engineer
**Supporting Actors:** Assurance Chat Agent, TrustCentre

**Key Actions**

- Interact conversationally with runtime findings (_“show exec violations for auth-service”_, _“did this occur before?”_).
- Request attack-chain simulations, root-cause clustering, and what-if analyses aligned to manifest clauses.
- Promote validated insights to signed evidence artifacts and issue waivers or remediation guidance when necessary.

**Outputs**

- Signed runtime insight artifacts
- Manifest-linked evidence extensions and/or waivers

**Why it matters:** This is the primary UX for runtime AppSec assurance with full provenance.

---

## 7) Runtime Assurance Signing & Publication

> _Produce cryptographically verifiable assurance outcomes._

**Library:** Core Processes → Evidence Finalization & Signing
**Primary Actor:** TrustCentre Sign/Verify Service

**Key Actions**

- Aggregate runtime findings, AI summaries, policy decisions, and human approvals into a scoped Runtime Assurance Report.
- Sign, timestamp, and publish the report into WORM OCI; anchor digests to Rekor and the Audit Ledger.

**Outputs**

- Signed Runtime Assurance Artifact
- Publicly verifiable provenance chain

**Why it matters:** Converts runtime data into provable assurance instead of monitoring-only signals.

---

## 8) Runtime Metrics, Learning & Governance

> _Close the loop with metrics, learning, and executive narratives._

**Library:** Core Processes → Metrics, Visualization & Continuous Learning
**Primary Actor:** Metrics Service
**Supporting Actors:** AI Analyst Module, Executive Stakeholders

**Key Actions**

- Aggregate metrics such as violations per service, MTTA, waiver frequency, and remediation timeliness.
- Feed insights back into retriever tuning, AI reasoning weights, and manifest refresh cycles.
- Surface executive-ready runtime risk narratives and scorecards.

**Outputs**

- Dashboards, trend reports, and governance packs
- Updated manifests and policies informed by runtime outcomes

**Why it matters:** Runtime assurance becomes measurable, improvable, and governable.

---

## End-State Summary

- **eBPF provides runtime truth** — instrumentation delivers immutable signals.
- **Certus Integrity normalizes and preserves it** — evidence is deduplicated, contextualized, and stored with provenance.
- **Certus Assurance reasons, judges, and signs it** — AI + policy gates turn findings into verdicts.
- **Security Engineers stay accountable** — waivers, approvals, and insights remain human-signed.
- **Customers and auditors independently verify outcomes** — signed runtime artifacts anchor to Rekor, OCI, and the Audit Ledger.

This is Application Security Runtime Assurance—not monitoring, not EDR, and not SIEM.
