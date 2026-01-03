# Security Engineer

> **Status:** ⚠️ In progress (conversational tooling partially prototyped; full workflow TBD)

For this particular set of workflows, we will focus on the activities and decision processes of a Security Engineer. These workflows illustrate how the engineer engages with assurance mechanisms throughout the lifecycle of evidence capture, validation, and analysis. To provide a complete picture, these interactions are presented within the context of an a conversational chatbot interface designed to guide, validate, and document assurance activities in real time. The chatbot acts as both a facilitator and a verifier, ensuring that each action taken by the Security Engineer is traceable, policy-aligned, and cryptographically verifiable.

By modeling these workflows through a chat-based interaction, we can highlight how automation, provenance, and AI reasoning converge to enhance trust, transparency, and accountability in modern security assurance operations.

---

#### 1) Session Initialization: Context Bootstrapping

> _Ensure authrozied people start session with verified outputs._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant ENG as Security_Engineer
    participant AGENT as Assurance_Chat_Agent
    participant TC as TrustCentre
    autonumber

        %% Engineer Authenticates
        ENG->>AGENT: Authenticate via OIDC / SSO (with MFA)
        AGENT->>AGENT: Bind session to identity and key pair
        AGENT->>AGENT: Sign and timestamp all prompts/responses
        Note right of AGENT: Secure session established for trusted reasoning

        %% Session Context Retrieval
        AGENT->>TC: Retrieve Assurance Manifest, scan results, AI outputs, ledger entries
        TC-->>AGENT: Return signed data and metadata
        AGENT->>ENG: Display context summary<br/>System X (build 2025.10.10)<br/>78 findings, 4 waivers pending

        %% Trust Validation
        AGENT->>TC: Verify OCI signatures and Rekor entries
        TC-->>AGENT: Provide verification status
        AGENT-->>ENG: Confirm provenance validated before reasoning
    ```

**Actors**

- _Security Engineer_ – Authenticates, queries, and reviews assurance context.
- _Assurance Chat Agent_ – Verifies provenance and orchestrates retrieval/reasoning.
- _TrustCentre_ – Source of signed manifests, ledger entries, and evidence.

**Actions**

1. _Engineer Authenticates_
   - Logs in via **OIDC / enterprise SSO** (with MFA) to the Assurance Chat portal.
   - Chat session is bound to the engineer’s **identity and key pair** — all prompts/responses are **signed** and **timestamped**.

2. _Session Context Retrieval_
   - Agent auto-loads the current **Assurance Manifest**, latest **scan results** and **AI reasoning outputs**, and **Ledger entries** for the latest run.
   - Displays a contextual greeting:
     “You’re reviewing _System X_ (build 2025.10.10). **78** findings detected, **4** waivers pending review.”

3. _Trust Validation_
   - Before any reasoning, the agent verifies **OCI signatures** and **Rekor** entries.
   - The engineer is **never** reasoning on untrusted or unsigned data.

**Desired Outcomes**

| Outcome                         | Description                                                                |
| ------------------------------- | -------------------------------------------------------------------------- |
| **Verified Session Context**    | All artifacts loaded for the session are signed, timestamped, and current. |
| **Identity-Bound Interactions** | Each query and response is bound to the engineer’s identity and key.       |
| **Provenance-First Workflow**   | Reasoning only occurs on cryptographically verified inputs.                |
| **Frictionless Kickoff**        | The engineer starts with an actionable, trustworthy summary.               |

---

#### 2) Exploratory Querying & Analysis

> _Explore and analyze the threat surface in detail._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant ENG as Security_Engineer
    participant AGENT as Assurance_Chat_Agent
    participant RET as Retriever
    participant LED as Ledger
    autonumber

        %% Step 1 - Exploration
        ENG->>AGENT: Ask for high-severity issues in auth service
        AGENT->>RET: Query retriever index (BM25 + embeddings)
        AGENT->>LED: Get recent ledger changes
        AGENT-->>ENG: Return summarized findings

        %% Step 2 - Code Context
        ENG->>AGENT: Show code and fix for hardcoded secret
        AGENT->>RET: Fetch code snippet and related policy rule
        AGENT-->>ENG: Provide summary and remediation advice

        %% Step 3 - Cross-System Reasoning
        ENG->>AGENT: Check if issue appeared before
        AGENT->>LED: Search historical records by fingerprint
        AGENT-->>ENG: Reply with occurrence history and waiver reason
    ```

**Actors**

- _Security Engineer_ – Explores, filters, and inspects findings.
- _Assurance Chat Agent_ – Queries **Retriever index (BM25 + Embeddings)**, **Audit Ledger**, and **AI Reasoning Memory**.

**Actions**

1. _Natural Language Exploration_
   - Engineer asks: “Show me all **high-severity** vulnerabilities in the authentication microservice since the last patch.”
   - Agent queries retrievers, ledger changes since last run, and prior AI recommendations.
   - Response example:
     `3 findings detected:`
     `• CVE-2024-5832 in auth.py:142 – Token reuse vulnerability.`
     `• Hardcoded secret in jwt_manager.py – found via OpenGrep.`
     `• Dependency outdated (Flask 2.0.3 < 3.0.0) – known exploit path.`

2. _Code Context Summarization_
   - Engineer: “Show the code context around the hardcoded secret and a recommended fix.”
   - Agent retrieves function-level snippet from **RAG memory** and merges it with the **policy rule** on secret rotation; emits a **signed** contextual explanation.

3. _Cross-System Reasoning_
   - Engineer: “Did this issue appear in previous builds?”
   - Agent searches historical ledger, matches fingerprints, and replies:
     “First seen **2025.09.12**, waived once, reintroduced by commit `6d2f…`. Waiver reason: _legacy configuration handling_.”

**Desired Outcomes**

| Outcome                         | Description                                                             |
| ------------------------------- | ----------------------------------------------------------------------- |
| **Conversational Discovery**    | Natural-language queries reliably retrieve signed findings and context. |
| **Context-Rich Summaries**      | Explanations include code, policy, and prior decisions.                 |
| **History-Aware Insights**      | Fingerprint matching reveals regressions and waiver lineage.            |
| **Signed Analytical Responses** | Explanations are emitted as verifiable artifacts.                       |

---

#### 3) Deep Reasoning & Threat Simulation

> _Run simulations to see what security defects might exist._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant Engineer
    participant Agent
    autonumber

        %% Step 1 - Exploitability Simulation
        Engineer->>Agent: Request simulation for JWT reuse and hardcoded secret chain
        Agent->>Agent: Retrieve related code and dependency graph
        Agent->>Agent: Build attack chain hypothesis in three stages
        Agent-->>Engineer: Run scenario
        Agent->>Agent: Sign and store threat scenario artifact

        %% Step 2 - Dynamic Querying
        Engineer->>Agent: Run analysis assuming pull request two eight four merged
        Agent->>Agent: Collect code changes and update retriever data
        Agent->>Agent: Recalculate and compare new risk level
        Agent-->>Engineer: Provide updated scenario with reduced risk summary
    ```

**Actors**

- _Security Engineer_ – Requests simulations and what-if analysis.
- _Assurance Chat Agent_ – Performs fusion retrieval and produces signed **Threat Scenario** artifacts.

**Actions**

1. _Exploitability Simulation_
   - Engineer: “Reason through the exploitability if JWT reuse and a hardcoded secret are chained.”
   - Agent retrieves related code and dependency graphs, builds an **attack-chain hypothesis**:
     `1) Secret exfil from jwt_manager.py → 2) Token forgery (CWE-345) → 3) Bypass via /auth/refresh.`
     `Risk: Critical | EPSS 0.93 | CVSSv3 9.1`
   - Output is signed as a **Threat Scenario Artifact**.

2. _Dynamic Querying_
   - Engineer: “Re-run assuming PR #284 is merged.”
   - Agent fetches diffs, updates embeddings, re-evaluates, and reports **risk reduction** deltas.

**Desired Outcomes**

| Outcome                     | Description                                                       |
| --------------------------- | ----------------------------------------------------------------- |
| **Actionable Attack Paths** | Simulations describe credible, evidence-linked exploit chains.    |
| **What-If Reruns**          | Proposed fixes can be tested virtually against current evidence.  |
| **Quantified Risk**         | Scenarios include EPSS/CVSS and confidence indicators.            |
| **Signed Scenarios**        | Threat reasoning is preserved as immutable, replayable artifacts. |

---

#### 4) AI-Augmented Root Cause Analysis

> _Chat to root-cause._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant Engineer
    participant Agent
    autonumber

        %% Causal Reasoning
        Engineer->>Agent: Request root causes for recurring credential issues
        Agent->>Agent: Cluster findings by category including CWE seven nine eight and CWE five two two
        Agent-->>Engineer: Common root causes\nInconsistent secret handling\nLack of central key management\nLinting overrides
        Agent-->>Engineer: Recommended controls\nEnforce centralized key management\nPresubmit secret checks with static scanning

        %% Auto Enrichment
        Engineer->>Agent: Add policy and metric context
        Agent->>Agent: Attach manifest control id SEC zero eight
        Agent->>Agent: Include recent MTTA metrics and ledger identifiers for traceability
        Agent-->>Engineer: Return mapped controls and metrics with traceability summary
    ```

**Actors**

- _Security Engineer_ – Seeks systemic contributors and controls.
- _Assurance Chat Agent_ – Clusters findings and maps to policies/metrics.

**Actions**

1. _Causal Reasoning_
   - Engineer: “Root causes for recurring credential issues?”
   - Agent clusters **CWE-798 / CWE-522** findings, producing:
     `Common Root Causes:`
     `• Inconsistent secret handling`
     `• Lack of central KMS enforcement`
     `• Linting overrides`
     `Recommended Controls:`
     `• Enforce centralized KMS`
     `• Presubmit OpenGrep secret checks`

2. _Auto-Enrichment_
   - Adds **Manifest control ID (SEC-08)**, recent **MTTA** metrics, and relevant **ledger IDs** for traceability.

**Desired Outcomes**

| Outcome                     | Description                                              |
| --------------------------- | -------------------------------------------------------- |
| **Systemic Insight**        | Patterns across services surface shared weaknesses.      |
| **Policy-Linked Guidance**  | Recommendations reference concrete controls and metrics. |
| **Traceable Analytics**     | Root-cause outputs cite ledger events and artifacts.     |
| **Prioritized Remediation** | Focus shifts from symptoms to durable controls.          |

---

#### 5) Generating Signed Findings & Evidence

> _Review verified artifacts and findings._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant Engineer
    participant Agent
    participant Ledger
    participant OCI
    participant Manifest
    autonumber

        %% 1) Engineer Promotes Insight
        Engineer->>Agent: Click record as insight
        Agent->>Agent: Format analysis as JSON using insight schema
        Agent->>Agent: Sign with OIDC identity and Cosign
        Agent->>Ledger: Record analysis event
        Ledger-->>Agent: Return event reference

        %% 2) AI Creates Evidence Artifact
        Agent->>Agent: Package transcript and context references
        Agent->>Agent: Include reasoning trace and DeepEval metrics
        Agent->>OCI: Seal as versioned artifact in WORM OCI
        OCI-->>Agent: Return artifact reference and digest

        %% 3) Link Back to Assurance Manifest
        Agent->>Manifest: Add extended evidence entry with artifact digest
        Manifest-->>Agent: Confirm manifest updated
        Agent-->>Engineer: Provide evidence reference and manifest update summary
    ```

**Actors**

- _Security Engineer_ – Promotes insights to evidence.
- _Assurance Chat Agent_ – Packages and signs analysis; updates ledger and manifest links.

**Actions**

1. _Engineer Promotes Insight_
   - Clicks **Record as Insight**.
   - Agent formats analysis as JSON (`/insight` schema), **signs** it (OIDC + Cosign), and records an **Analysis Event** in the **Audit Ledger**.

2. _AI Creates Evidence Artifact_
   - Packages transcript, context refs (findings, code, ledger IDs), **LLM reasoning trace**, and **DeepEval** metrics.
   - Seals to **WORM OCI** as a versioned artifact.

3. _Link Back to Assurance Manifest_
   - Adds artifact digest as an **Extended Evidence URI** to the current **Assurance Manifest**.

**Desired Outcomes**

| Outcome                     | Description                                                       |
| --------------------------- | ----------------------------------------------------------------- |
| **Evidence-Grade Insights** | Human–AI conclusions are promoted to signed, queryable artifacts. |
| **Full Provenance Bundle**  | Artifacts include prompts, contexts, metrics, and outputs.        |
| **Manifest Binding**        | New evidence is discoverable via the manifest record.             |
| **Auditable Lifecycle**     | Each step leaves verifiable ledger entries.                       |

---

#### 6) Release Gate Handoff

> _Ensure policy engines and release workflows consume the latest security insights._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant Engineer
    participant Gate as Policy_Gate
    participant Release as Release_Orchestrator
    participant Ledger
    autonumber

        Engineer->>Gate: Publish insight/waiver ids ready for enforcement
        Gate->>Gate: Validate signatures, manifest linkage, SLA status
        Gate->>Release: Emit policy verdicts (pass, fail, waiver) with evidence refs
        Release-->>Gate: Confirm gating decision (block/release)
        Gate->>Ledger: Log enforcement outcome with references to insights
    ```

**Highlights**

- Keeps CI/CD in sync with security engineers: as soon as an insight or waiver is signed, the policy gate can enforce it without manual copying.
- Release systems receive structured verdicts and evidence URIs for audit trails.

**Desired Outcomes**

| Outcome                       | Description                                                                       |
| ----------------------------- | --------------------------------------------------------------------------------- |
| **Deterministic Enforcement** | Gates only trust signed, manifest-linked insights.                                |
| **Release Transparency**      | Deployment logs cite which insight/waiver allowed or blocked the release.         |
| **Closed Loop**               | Every gating event is recorded with evidence references for replay.               |
| **Reduced Drift**             | No divergence between what security engineers approve and what pipelines enforce. |

---

#### 6) Continuous Feedback & Improvement

> _(Provide meaningful feedback for AI improvement._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant Agent as Assurance_Chat_Agent
    participant Trust as TrustCentre
    autonumber

        %% Step 1 - Learning Feedback Loop
        Agent->>Agent: Add session context to retrieval memory
        Agent->>Agent: Store human corrections for later model reweighting
        Agent-->>Agent: Future queries inherit prior insights

        %% Step 2 - Periodic Verification
        Agent->>Trust: Emit insight added event
        Trust->>Trust: Reverify new artifacts
        Trust->>Trust: Reanchor digests to transparency service
        Trust-->>Agent: Return updated verification record
    ```

**Actors**

- _Assurance Chat Agent_ – Learns from prior interactions and corrections.
- _TrustCentre_ – Re-verifies new artifacts and anchors digests.

**Actions**

1. _Learning Feedback Loop_
   - Adds session context to **RAG**; future queries inherit prior insights.
   - Human corrections are logged for **re-weighting/fine-tuning**.

2. _Periodic Verification_
   - Ledger emits an **insight-added** event; TrustCentre re-verifies and **re-anchors** digests to **Rekor**.

**Desired Outcomes**

| Outcome                     | Description                                                |
| --------------------------- | ---------------------------------------------------------- |
| **Cumulative Intelligence** | Each session improves future retrieval and reasoning.      |
| **Integrity Renewal**       | New artifacts are continuously re-anchored for durability. |
| **Lower Noise Over Time**   | Feedback reduces false positives and redundant work.       |
| **Verified Learning Trail** | Model improvements remain auditably grounded.              |

---

#### 7) Collaboration & Case Management

> _Coordinate remediation and SLA tracking with product/feature teams._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant Engineer
    participant Case as Case_Tracker
    participant DevTeam
    participant Trust
    autonumber

        Engineer->>Case: Create/Update case with signed insight reference
        Case->>DevTeam: Notify responsible squad (SLA, evidence bundle)
        DevTeam->>Case: Acknowledge, attach remediation status
        DevTeam->>Trust: Publish remediation artifacts or request waivers
        Trust-->>Case: Update case with verification link
        Case-->>Engineer: Alert on SLA breaches or repeated findings
    ```

**Highlights**

- Ensures every finding has an owner and SLA, even outside the chat interface.
- Integrated with TrustCentre so remediation evidence/waivers stay linked to the original case.

**Desired Outcomes**

| Outcome                     | Description                                                                       |
| --------------------------- | --------------------------------------------------------------------------------- |
| **Accountable Remediation** | Each finding is tracked through closure with clear ownership.                     |
| **SLA Visibility**          | Missed deadlines or repeated issues trigger alerts/escalations.                   |
| **Shared Evidence**         | Dev teams access the same signed artifacts without duplicating data.              |
| **Lifecycle Traceability**  | Cases show the full timeline (insight → assignment → remediation → verification). |

---

#### 8) Reporting & Sharing

> _Generate reports and findings for the team._

??? info "Click to view"
    ```mermaid
    sequenceDiagram
    participant Engineer
    participant Agent
    participant Gate as Policy_Gate
    participant Centre as TrustCentre
    autonumber

        %% Step 1 - Generate Analysis Summary
        Engineer->>Agent: Request summary for KMS and credential issues from past ninety days
        Agent->>Agent: Aggregate SARIF data and related findings
        Agent->>Agent: Compose risk summary and create signed markdown report with provenance
        Agent-->>Engineer: Return generated report ready for review

        %% Step 2 - Submit for Peer Review
        Engineer->>Gate: Attach report for validation before peer review
        Gate->>Gate: Enforce evidence schema and completeness checks
        Gate-->>Engineer: Confirm report validated and accepted
        Engineer->>Centre: Make report available for supervisor or auditor verification
        Centre-->>Engineer: Verification record confirmed
    ```

**Actors**

- _Security Engineer_ – Requests summaries and distributes reports.
- _Assurance Chat Agent_ – Generates signed markdown reports and validates schema.

**Actions**

1. _Generate Analysis Summary_
   - Engineer: “Summarize all findings linked to **KMS** and credential mismanagement in the last **90 days**.”
   - Agent aggregates SARIF, composes risk summaries, and emits a **signed Markdown report** with provenance links.

2. _Submit for Peer Review_
   - Attaches report to **Jira/OpenProject**.
   - **Policy Gate** enforces evidence schema and completeness before submission.
   - Supervisors/auditors can verify directly in **TrustCentre**.

**Desired Outcomes**

| Outcome                   | Description                                             |
| ------------------------- | ------------------------------------------------------- |
| **Push-Button Reporting** | Curated, signed summaries with embedded evidence links. |
| **Workflow Integration**  | Reports flow into ticketing with policy checks.         |
| **Reviewer Confidence**   | Verifiers can independently validate in TrustCentre.    |
| **Consistent Narrative**  | Reports reflect the same signed data used in analysis.  |

---

## End-State: Verifiable Human–AI Collaboration

At the conclusion of these workflows:

- Every question, AI response, and human action is logged in the Audit Ledger.
- Every finding, insight, or simulated scenario is cryptographically signed and timestamped.
- The chat transcript itself is replayable and verifiable — demonstrating explainability, traceability, and accountability.

**Desired Outcomes**

| Outcome                       | Description                                                       |
| ----------------------------- | ----------------------------------------------------------------- |
| **Unified, Verifiable Trail** | Chat, reasoning, and evidence form a single cryptographic record. |
| **Explainability by Default** | Reasoning traces are preserved and independently checkable.       |
| **Stronger Governance**       | Human approvals/waivers are bound to artifacts and identities.    |
| **Operational Confidence**    | Teams act on insights they can verify end-to-end.                 |

---

### Outcome Summary

| Aspect              | Traditional Workflow                       | Assurance Chat Workflow                             |
| ------------------- | ------------------------------------------ | --------------------------------------------------- |
| **Data Access**     | Manual across tools (Jira, SIEM, scanners) | Unified RAG retrieval across TrustCentre + scanners |
| **Reasoning**       | Manual correlation                         | LLM fusion (retrievers + code + manifest)           |
| **Documentation**   | Manual report writing                      | Auto-signed insights and ledger entries             |
| **Integrity**       | Weak (editable reports)                    | Immutable evidence, signed, timestamped             |
| **Explainability**  | None                                       | Reasoning traces + DeepEval metrics                 |
| **Audit Readiness** | Reactive                                   | Continuous, verifiable, replayable                  |

---

### Example Chat Transcript (Condensed)

`👩‍💻 Engineer: "Show me any high EPSS vulnerabilities in the auth service since October."`
`🤖 System: "2 findings. CVE-2024-5832 (EPSS 0.93), Hardcoded JWT secret."`
`👩‍💻 Engineer: "Simulate attack chain combining those two."`
`🤖 System: "Critical chain detected: Token forgery possible. CVSSv3=9.1. Evidence: ledger:evt-524. Mitigation: Rotate secret, enforce KMS policy SEC-08."`
`👩‍💻 Engineer: "Record as insight and sign."`
`🤖 System: "Insight signed. Artifact: oci://trustcentre/org/secinsight@sha256:ae9f… anchored to Rekor log 9821."`

---
