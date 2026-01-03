# Workflows

These workflows describe how actors within the assurance ecosystem interact to achieve specific objectives. They capture **who** is involved, **what** each participant does, and **why** the interaction matters in maintaining trust and verifiable assurance.

> **Aspirational reference:** The flows in this section represent the target-state Certus assurance experience. Current PoCs (e.g., `certus-ask`, `certus-trust`) implement subsets of these interactions, and the remaining steps serve as forward-looking use cases for the platform roadmap.

**Library overview**

- [Core Processes](system.md) – Manifest-driven assurance lifecycle.
- [Ingestion & Query](ingestion-query.md) – Intake, normalization, chunking, indexing, and query readiness.
- [Guardrails & Controls](guardrails.md) – Privacy/security guardrails, escalation, and governance.
- [Datalake Promotion & Verification](datalake.md) – Raw-to-golden flows with digest enforcement.
- [AI / Model Lifecycle](model-lifecycle.md) – Dataset curation, training, evaluation, deployment, and drift monitoring.
- [Evaluation & Feedback](evaluation.md) – Test generation, scoring, and policy feedback.
- [Developer Workflows](developer.md) – Day-to-day secure development and waiver flows.
- [Platform & Operations Workflows](platform.md) – Environment provisioning, health, upgrades, and incidents.
- [Executive & C-Suite Workflows](executive.md) – Trust scorecards, governance, and escalations.
- [Customer & Regulator Workflows](customer.md) – Evidence sharing and independent verification.
- [Assurance & Audit](assurance.md) – Third-party auditor journey.
- [Security Engineer](engineer.md) – Human-in-the-loop analysis via conversational tooling.
- [Construction Use Case](construction.md) – Cross-domain adaptation of the assurance pattern.

These workflows serve three main purposes:

1. **Clarity and Communication**
   They provide a clear narrative of how assurance workflows function end to end, ensuring both technical and non-technical stakeholders understand the process.

2. **Traceability and Accountability**
   Each use case ties actions to identifiable actors, artifacts, and verification points — establishing the foundation for auditability and compliance.

3. **Design and Validation**
   They help model the expected system behavior, define boundaries of responsibility, and validate that assurance mechanisms align with the defined trust model.

---

## Relationship to the Diagrams

Each use case in this section is paired with a **Mermaid sequence diagram** that visualizes the same scenario in an interaction format. These diagrams depict the exchange of data, evidence, and verification messages between actors such as the **System Under Test**, **AI Reasoner**, **Human Reviewer**, and **TrustCentre**.

The combination of narrative and visual flow enables readers to quickly understand both the intent and operational behavior of the assurance lifecycle.
