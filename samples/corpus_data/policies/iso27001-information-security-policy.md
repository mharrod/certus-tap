# ISO/IEC 27001 Information Security Policy

## Purpose
Defines the management system for protecting information assets in alignment with ISO/IEC 27001:2022. Supports certification and continual improvement of the Information Security Management System (ISMS).

## Scope
The ISMS includes TAP ingestion pipelines, FastAPI backend, OpenSearch clusters, LocalStack environment, CI/CD tooling, and supporting cloud services.

## Information Security Objectives
1. Maintain confidentiality, integrity, and availability of customer and internal data.
2. Ensure ingestion guardrails respect robots.txt and regulatory requirements.
3. Provide reliable audit evidence through automated scripts (`preflight.sh`, ingestion logs, IaC change records).
4. Drive continual improvement through quarterly internal audits and management review.

## Key ISO 27001 Annex A Controls
- **A.5 Policies:** All policies stored in `samples/corpus_data/policies` and reviewed at least annually.
- **A.6 Organization:** Roles/responsibilities defined in governance policy, including separation of duties for deployment approvals.
- **A.8 Asset Management:** Every data source ingested is cataloged with owner, classification, retention, and lawful basis.
- **A.9 Access Control:** SSO + MFA enforced; least privilege and just-in-time access for engineering systems.
- **A.12 Operations Security:** Secure configurations codified in IaC; ingestion pipelines run within controlled environments with integrity checks.
- **A.15 Supplier Relationships:** Contracts require security clauses, right to audit, and breach notification windows.
- **A.17 Business Continuity:** DR plans cover OpenSearch snapshot restores, LocalStack rebuilds, and doc ingestion retries.

## ISMS Operation
1. **Risk Assessment:** Conducted twice per year per ISO 27005, capturing threat likelihood/impact and mapping to Annex A controls.
2. **Internal Audit:** Rotating cross-functional team inspects compliance evidence, remediation tracked in governance tracker.
3. **Management Review:** Executive leadership reviews performance metrics, audit findings, and improvement actions annually.
4. **Corrective Action:** Nonconformities logged in ticketing system with root cause, action plan, verification, and closure evidence.

## Documentation & Records
- Statement of Applicability (SoA) tied to this policy.
- Secure storage with retention period aligned to regulatory commitments (minimum three years).
- Version control via Git to maintain traceability.

## Enforcement
Any employee who violates this policy may face disciplinary action per HR guidelines. Critical deviations trigger immediate ISMS review and potential suspension of affected services.
