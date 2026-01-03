# AI Model Lifecycle

> **Status:** 🔭 Concept / roadmap (model training/hosting not yet implemented in the PoC)

This workflow describes how data, training runs, evaluation, and deployment of AI/LLM components tie into the assurance stack.

---

## 1) Data Curation & Lineage

> _Collect and approve training/evaluation datasets under manifest control._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant DataTeam
    participant Catalog
    participant TrustCentre
    autonumber

        DataTeam->>Catalog: Register dataset (source, schema, sensitivity)
        Catalog->>TrustCentre: Generate dataset manifest (hashes, retention, approval workflow)
        TrustCentre-->>DataTeam: Provide dataset ID + policy references
    ```

**Highlights**

- Datasets inherit the same manifest framework as code artifacts (controls, retention, signatures).
- Lineage captures provenance (raw source → curated dataset → training split).

---

## 2) Training / Fine-Tuning Pipeline

> _Run training jobs with reproducible configs and signed outputs._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Trainer
    participant Compute
    participant Registry
    participant Ledger
    autonumber

        Trainer->>Compute: Launch job with manifest-approved dataset + hyperparams
        Compute-->>Trainer: Emit checkpoints, logs, metrics
        Trainer->>Registry: Store model artifacts + config bundle
        Trainer->>Ledger: Record run metadata (dataset IDs, commit hashes, signer)
    ```

**Highlights**

- Training configs (code, prompts, hyperparams) are versioned and signed.
- Outputs include hashes for weights/checkpoints plus references to input datasets.

---

## 3) Evaluation & Guardrails

> _Run automated eval suites (accuracy, bias, toxicity, hallucination) and enforce guardrails._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Evaluator
    participant Guardrails
    participant Human
    participant Ledger
    autonumber

        Evaluator->>Guardrails: Submit metrics (accuracy, bias, toxicity, hallucination)
        Guardrails->>Guardrails: Compare to manifest thresholds
        alt Pass
            Guardrails-->>Evaluator: Approve deployment
        else Needs Review
            Guardrails->>Human: Route for waiver/mitigation
            Human-->>Guardrails: Sign decision
        end
        Guardrails->>Ledger: Log results and rationale
    ```

**Highlights**

- Reuses the same policy gate pattern as other workflows.
- Bias/toxicity metrics feed waiver workflows when trade-offs are needed.

---

## 4) Packaging & Deployment

> _Publish approved models to serving infrastructure with provenance._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Registry
    participant Serving
    participant TrustCentre
    participant Ops
    autonumber

        Registry->>Serving: Provide signed model bundle (weights, tokenizer, prompts)
        Serving->>Serving: Validate signature, deploy with config (rate limits, guardrails)
        Serving->>TrustCentre: Register model version, capability, and manifest linkage
        Ops->>Serving: Monitor performance / drift alerts
    ```

**Highlights**

- Model packages include checksums, license info, prompt templates, and guardrail configs.
- Serving endpoints inherit guardrails (prompt filtering, output safety) defined elsewhere.

---

## 5) Drift Monitoring & Feedback

> _Track performance post-deployment and trigger retraining or policy updates._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Monitor
    participant Serving
    participant DataTeam
    participant Execs
    autonumber

        Monitor->>Serving: Collect telemetry (latency, rejection rate, guardrail hits)
        Serving-->>Monitor: Stream metrics
        Monitor-->>DataTeam: Alert on drift or degraded metrics
        DataTeam->>Execs: Propose retraining / manifest updates
    ```

**Highlights**

- Drift thresholds tie back to manifest entries; exceeding them triggers governance workflows.
- DataTeam iterates on datasets/training to address drift, feeding results back into the loop.

---

**Outcome:** An end-to-end model lifecycle that mirrors the rest of the Certus assurance pipeline—datasets, training runs, evaluations, deployments, and monitoring all inherit manifest governance, guardrails, and ledger logging.
