# Developer & QA

> **Status:** ⚠️ In progress (portions supported via current pipelines, additional automation planned)

These workflows describe how product and platform engineers interact with the assurance framework while building and releasing software. They focus on day-to-day activities—running security tests, responding to findings, and publishing evidence—without prescribing specific tools.

---

## 1) Feature Kickoff & Manifest Alignment

> _Developers pull the applicable assurance contract before starting work._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Dev as Developer
    participant Repo as Source_Control
    participant Contract as Assurance_Manifest_Service
    autonumber

            Dev->>Repo: Clone repository / create feature branch
            Dev->>Contract: Request workspace manifest + policy set
            Contract-->>Dev: Return manifest hash, policy IDs, scanner matrix
            Dev->>Dev: Configure local tooling (feature flags, guardrails, env vars)
            Dev-->>Contract: Acknowledge manifest version in work item
    ```

**Highlights**

- Every feature branch is bound to a manifest version (e.g., `manifest:v2024.09`). Dev tools know which scans, thresholds, and data contracts apply.
- Local IDE extensions or CLI helpers can warn if the developer is using an outdated manifest.

---

## 2) Local & Pre-Commit Guardrails

> _Before pushing code, developers run fast security/privacy checks locally._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant DevEnv as Dev_Environment
    participant Guard as Guardrail_Toolchain
    participant Tracker as Local_Log
    autonumber

        DevEnv->>Guard: Run quick scans (secret detection, linting, IaC policies)
        Guard-->>DevEnv: Return pass/fail + remediation hints
        Guard->>Tracker: Record summary (tool version, manifest hash, result)
        DevEnv-->>DevEnv: Block commit / allow commit based on policy
    ```

**Highlights**

- Guardrails align with the manifest: if “no hardcoded secrets” is in scope, the IDE plugin enforces it pre-commit.
- Local summaries include tool versions and manifest hash so downstream automation can prove the developer ran required checks.

---

## 3) CI/CD Security & Assurance Pipeline

> _On push or pull request, the pipeline executes the full manifest-defined suite._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant CI as CI_Pipeline
    participant SUT as Build/Test_Artifacts
    participant Gate as Policy_Gate
    participant Ledger
    autonumber

        CI->>CI: Fetch manifest version referenced in branch
        CI->>SUT: Run scans (SAST, SCA, IaC, privacy probes, AI evals) per manifest
        SUT-->>CI: Emit SARIF/logs/proofs
        CI->>Gate: Submit normalized findings + metrics
        Gate-->>CI: Return pass/fail/waiver-required decisions
        CI->>Ledger: Log run metadata (commit, manifest hash, controls)
    ```

**Highlights**

- The pipeline fails fast if required scans are missing or manifest hashes don’t match.
- Policy Gates enforce release criteria (e.g., “no Critical CVEs”). Waivers require human reviewers and are logged with signatures.

---

## 4) Developer Findings Triage

> _Developers review findings via structured UX (dashboard, chat agent, IDE)._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Dev
    participant Assistant as Assurance_Assistant
    participant Evidence as Evidence_Registry
    participant Ledger
    autonumber

        Assistant->>Evidence: Pull prioritized findings for developer's branch
        Assistant-->>Dev: Summarize impact, code context, remediation guidance
        Dev->>Assistant: Ask clarifying questions / simulate fixes
        Assistant->>Ledger: Record interaction outcomes (acknowledged, false positive, needs waiver)
    ```

**Highlights**

- Conversations are bound to the developer’s identity and manifest version to maintain traceability.
- Assistant responses cite evidence URIs so developers can independently verify results.

---

## 5) Waivers & Remediation Publishing

> _If an exception is justified, it is signed and linked to the manifest; otherwise, remediation artifacts are published._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Dev
    participant Reviewer
    participant Gate
    participant TrustCentre
    autonumber

        Dev->>Gate: Submit waiver request (finding id, justification, compensating controls)
        Gate->>Reviewer: Route to approver with context
        Reviewer-->>Gate: Approve / reject with signature
        Gate->>TrustCentre: Store waiver record (signed, timestamped)
        alt Remediated
            Dev->>TrustCentre: Publish remediation evidence (patch diff, new scan results)
            TrustCentre-->>Gate: Update finding status to resolved
        end
    ```

**Highlights**

- Waivers include expiration dates and compensating controls; policy gates can re-check them on future runs.
- Remediation artifacts (e.g., follow-up scan reports) are published so auditors can verify the fix.

---

## 6) Release & Post-Release Monitoring

> _Developer-owned services continue to emit assurance signals after merge._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Runtime as Deployed_Service
    participant Monitor
    participant DevTeam
    participant TrustCentre
    autonumber

        Runtime->>Monitor: Emit telemetry (scan cadence, drift alerts, policy status)
        Monitor-->>DevTeam: Notify on regressions or manifest violations
        DevTeam->>TrustCentre: Confirm remediation / update manifest thresholds
        TrustCentre-->>Runtime: Provide refreshed policy pack
    ```

**Highlights**

- Developers stay accountable post-release: if drift or key rotation occurs, the TrustCentre issues updated policy packs.
- Continuous monitoring closes the loop, ensuring development practices remain aligned with assurance expectations.

---

**Outcome:** Developers have an end-to-end view of how their day-to-day actions (coding, testing, waivers, releases) tie into the same assurance workflows used by auditors and operators, fostering a shared trust model.
````
