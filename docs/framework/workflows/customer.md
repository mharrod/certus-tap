# Customer & Regulator

> **Status:** 🔭 Concept / roadmap (TrustCentre sharing APIs still under development)

These workflows outline how external stakeholders—customers, regulators, or independent assessors—consume evidence from the assurance platform. They emphasize transparency, self-service verification, and selective disclosure rather than internal pipeline mechanics.

---

## 1) Engagement Discovery & Access

> _A customer/regulator obtains scoped, read-only access to assurance artifacts._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Stakeholder
    participant Trust as TrustCentre
    participant Vendor
    autonumber

        Stakeholder->>Trust: Request access (portal or API) for engagement XYZ
        Trust->>Vendor: Notify owner for approval (optional)
        Trust-->>Stakeholder: Issue scoped credentials (OIDC/OAuth, signed scope)
        Stakeholder->>Trust: Retrieve engagement catalog (manifests, runs, attestations)
    ```

**Highlights**

- Access is least-privilege: scopes map to specific engagements or datasets (e.g., “read evidence for AI Service A – Q3 2024”).
- Catalog metadata exposes what evidence is available (manifests, SARIF, waiver logs, signed attestations) before any download.

---

## 2) Evidence Selection & Retrieval

> _Stakeholders pull only the artifacts they need, with provenance guarantees._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Stakeholder
    participant Catalog
    participant Evidence as Evidence_Store
    participant Ledger
    autonumber

        Stakeholder->>Catalog: Filter by framework/control/date (e.g., SOC2 CC6.6)
        Catalog-->>Stakeholder: Return artifact list + metadata (digests, signatures, policy link)
        Stakeholder->>Evidence: Download selected artifact bundles
        Stakeholder->>Ledger: Fetch verification proofs (Rekor entries, signer info)
    ```

**Highlights**

- Every download includes digests, signer identities, and linkage back to the manifest/policy set so external auditors can reconstruct context.
- Stakeholders can export a manifest snapshot alongside the evidence bundle to prove scope alignment.

---

## 3) Independent Verification & Tooling

> _Evidence is verified off-platform using open tooling._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Stakeholder
    participant CLI as Verification_CLI
    participant Transparency as Transparency_Log
    autonumber

        Stakeholder->>CLI: Run verification command (e.g., trustctl verify --manifest M --rekor --oci)
        CLI->>Transparency: Validate signatures, timestamps, inclusion proofs
        Transparency-->>CLI: Return pass/fail + proof metadata
        CLI-->>Stakeholder: Emit report (verified artifacts, exceptions, warnings)
    ```

**Highlights**

- The platform provides tooling or documentation for independent verification (Sigstore/Rekor, in-toto attestations).
- Stakeholders rely on standard protocols; they don’t need to trust vendor infrastructure beyond the published artifacts.

---

## 4) Selective Disclosure & Data Rooms

> _Vendors expose only the necessary evidence while keeping sensitive data controlled._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Vendor
    participant Trust
    participant Stakeholder
    autonumber

        Vendor->>Trust: Create evidence bundle (subset of artifacts) for stakeholder
        Trust->>Stakeholder: Notify bundle availability + terms (expiry, NDA)
        Stakeholder->>Trust: Access bundle via secure portal/API
        Trust->>Vendor: Log access + artifacts viewed for compliance
    ```

**Highlights**

- Supports temporary “data rooms” for diligence or regulatory reviews, with expirations and monitoring.
- Vendors control which artifacts are exposed (e.g., sanitized SARIF, aggregated metrics) while still providing verifiability.

---

## 5) Feedback & Follow-Up Actions

> _Customers/regulators can raise questions, request waivers, or demand remediation proof._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Stakeholder
    participant Vendor
    participant Trust
    autonumber

        Stakeholder->>Vendor: Ask for clarification / remediation plan on finding F
        Vendor->>Trust: Upload response artifacts (plan, updated scans, attestation)
        Trust-->>Stakeholder: Notify of new evidence
        Stakeholder->>Trust: Record acceptance / remaining concerns
    ```

**Highlights**

- Keeps external conversations grounded in verifiable artifacts—no email threads without cryptographic references.
- Acceptance decisions (e.g., “waiver approved by regulator”) are logged for posterity and can feed back into manifests or policy gates.

---

**Outcome:** External stakeholders have a clear, auditable path for discovering, downloading, verifying, and responding to assurance evidence without relying on privileged access, reinforcing transparency and trust.
