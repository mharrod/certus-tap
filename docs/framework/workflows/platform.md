# Platform & Operations

> **Status:** ⚠️ In progress (scripts/preflight and docker-compose cover parts; full ops automation remains roadmap)

These workflows describe how platform and SRE teams operate the assurance stack—bootstrapping environments, running health checks, performing upgrades, and responding to incidents. They are technology agnostic so the same patterns apply whether Certus services run on laptops, Kubernetes, or managed platforms.

---

## 1) Environment Provisioning & Bootstrap

> _Spin up the assurance stack (ingestion, TrustCentre, supporting services) from scratch._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Operator
    participant IaC as Infrastructure_Code
    participant Secrets
    participant Services
    participant Preflight
    autonumber

        Operator->>IaC: Apply environment definition (Docker Compose, Terraform, etc.)
        IaC-->>Operator: Return endpoints, credentials placeholders
        Operator->>Secrets: Populate key material (LLM creds, signing keys, AWS keys)
        Operator->>Services: Launch core apps (certus-ask, certus-trust, OpenSearch, LocalStack, MLflow)
        Services-->>Operator: Report healthy/ready flags
        Operator->>Preflight: Run validation script (e.g., scripts/preflight.sh)
        Preflight-->>Operator: Summarize checks (ingestion, queries, evaluation, smoke tests)
    ```

**Highlights**

- Infrastructure as code captures the topology (vector store, LocalStack, MLflow, etc.), while secrets are injected securely post-provisioning.
- A single “preflight” command validates the full stack (e.g., doc ingestion, query path, evaluation, datalake promotion) before handing it to engineers or auditors.

---

## 2) Health Monitoring & Service Checks

> _Continuously verify the running environment and expose status to stakeholders._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Monitor
    participant Services
    participant Operator
    participant Stakeholder
    autonumber

        Monitor->>Services: Poll /health and /ready endpoints (ask, trust, OpenSearch, dependencies)
        Monitor-->>Operator: Alert on degraded status (latency, errors, queue depth)
        Operator->>Services: Inspect logs, adjust autoscaling, or restart components
        Stakeholder->>Monitor: Query status dashboard / API for trust reporting
    ```

**Highlights**

- Exposes both liveness and readiness so deployments can distinguish “process is up” vs “dependencies ready.”
- Dashboards/alerts surface key metrics: ingestion throughput, privacy guardrail incidents, TrustCentre signing backlog, etc.

---

## 3) Upgrade & Rollback Workflow

> _Safely deploy new versions of assurance services while preserving state._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Operator
    participant Git
    participant CI
    participant Prod as Prod_Cluster
    participant Rollback
    autonumber

        Operator->>Git: Prepare release build / container tags
        CI->>CI: Run full suite (unit, integration, preflight) against release candidate
        Operator->>Prod: Deploy new images (blue/green or canary) with config updates
        Prod-->>Operator: Emit health metrics, smoke test results
        alt Failure detected
            Operator->>Rollback: Trigger rollback plan (previous images/config, data restores if needed)
            Rollback-->>Operator: Confirm environment restored
        else Success
            Operator->>Prod: Finalize release, archive configs + manifests
        end
    ```

**Highlights**

- Upgrades respect manifest compatibility and data migrations (vector store indices, LocalStack buckets, MLflow DB).
- Rollback automation is essential to maintain continuous assurance SLAs when new builds misbehave.

---

## 4) Incident Response & Recovery

> _Respond to outages or data-integrity incidents within the assurance platform._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Monitor
    participant Operator
    participant IR as Incident_Command
    participant Stakeholder
    participant Ledger
    autonumber

        Monitor-->>Operator: Alert (e.g., ingestion pipeline failing, TrustCentre signing backlog, OpenSearch unavailable)
        Operator->>IR: Declare incident, assemble responders
        IR->>Operator: Run runbook (failover, replay, restore from backups, rotate keys)
        Operator->>Ledger: Record incident timeline + remediation steps for audit
        Stakeholder-->>IR: Receive status updates / RCA commitments
    ```

**Highlights**

- Response plans include unique assurance elements: ensuring no unverified artifacts slip through, re-running guardrails after recovery, re-anchoring ledger roots, etc.
- Stakeholders (auditors, customers) need timely updates because assurance SLAs may be affected.

---

## 5) Configuration & Secrets Governance

> _Manage manifests, feature toggles, and secrets across environments._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Operator
    participant Config as Config_Store
    participant Secrets
    participant Services
    participant Audit
    autonumber

        Operator->>Config: Update environment settings (feature flags, index names, policy toggles)
        Config-->>Services: Reload configuration (hot or rolling restart)
        Operator->>Secrets: Rotate keys (LLM tokens, signing keys, AWS creds) per policy
        Secrets-->>Services: Distribute new secrets (via vault, sealed secrets, etc.)
        Audit->>Config: Log who changed what, when, and why (manifest hashes, rollout plan)
    ```

**Highlights**

- Ensures manifest versions and policy toggles remain consistent across dev/staging/prod.
- Secrets rotation is coordinated with TrustCentre signing flows so cryptographic evidence remains valid.

---

**Outcome:** Platform & operations teams can confidently provision, monitor, upgrade, and recover the assurance stack while giving stakeholders a transparent view into system health and configuration history.
