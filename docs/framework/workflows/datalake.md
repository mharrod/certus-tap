# Datalake

> **Status:** ⚠️ Partially implemented in the Certus PoC (LocalStack buckets + datalake router; advanced verification/automation still in progress)

This workflow describes how raw assurance artifacts move from ingestion buckets into curated “golden” storage after verification, tying together digest enforcement, provenance proofs, and promotion automation. It stays technology agnostic so any object store, ledger, or policy engine can implement the same controls.

---

## 1) Raw Landing & Registration

> _Artifacts first land in a restricted raw bucket with accompanying metadata._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Producer
    participant Raw as Raw_Store
    participant Catalog
    autonumber

        Producer->>Raw: Upload artifact (SARIF, report, attestation, repo snapshot)
        Producer->>Catalog: Register metadata (source, commit, expected digest)
        Catalog-->>Raw: Provide object key policy (prefix, retention)
        Raw-->>Producer: Confirm object URI + write timestamp
    ```

**Highlights**

- Raw storage isolates unverified submissions and retains auxiliary files (scan outputs, verification proofs, signatures) needed for later checks.
- Catalog metadata includes expected digests, verification tier, and chain-of-custody references that downstream automation can evaluate.

---

## 2) Verification-Oriented Promotion Request

> _An actor or scheduler asks to promote specific objects/prefixes._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Operator
    participant Gate as Promotion_Service
    participant Raw
    autonumber

        Operator->>Gate: Request promotion (source key/prefix, destination prefix, tier)
        Gate->>Raw: Enumerate objects under source
        Raw-->>Gate: Return object list + metadata
        Gate-->>Operator: Acknowledge request + tracking id
    ```

**Highlights**

- Promotion requests can be single-object (e.g., specific SARIF) or batch (prefix-based). They carry tier hints such as “requires signed verification-proof.json present.”
- The gate service controls access to destination buckets: only verified requests can copy data forward.

---

## 3) Digest & Chain Verification

> _Before copying, the service enforces integrity and provenance rules._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Gate
    participant Proofs as Verification_Proofs
    participant Ledger
    autonumber

        Gate->>Proofs: Fetch expected digests / verification metadata
        Proofs-->>Gate: Return manifest (artifact digests, signer info, proof URIs)
        Gate->>Gate: Compute digest of raw payload
        Gate->>Gate: Compare computed digest vs expected digest
        Gate->>Ledger: Log pass/fail with detail (source key, proof hash, operator)
    ```

**Highlights**

- Enforces “trust but verify”: even automation requires a matching digest before data leaves raw storage.
- Ledger entries (or audit logs) make failed promotions discoverable and enable forensics on tampering or misconfiguration.

---

## 4) Copy, Mask, or Quarantine

> _Based on verification and privacy flags, objects are copied, transformed, or held._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Gate
    participant Raw
    participant Golden as Golden_Store
    participant Quarantine
    autonumber

        alt Verified & Clean
            Gate->>Golden: Copy object with preserved metadata (digests, proof pointers)
        else Verified but Requires Masking
            Gate->>Gate: Apply masking/anonymization transform
            Gate->>Golden: Write masked object + metadata
        else Verification Failed
            Gate->>Quarantine: Move object + reason, block promotion
        end
    ```

**Highlights**

- Promotion preserves provenance by copying metadata (original key, digest, verification proof reference, policy tier) alongside the file.
- Quarantine buckets (or queues) hold rejected artifacts for manual review; they never reach golden storage until reconciled.

---

## 5) Destination Initialization & Structure

> _Golden storage enforces opinionated structure for downstream consumers._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Golden
    participant Catalog
    participant Consumers
    autonumber

        Golden->>Golden: Ensure folder prefixes (incoming/processing/golden/archive)
        Golden->>Catalog: Update index with promoted object URIs + proofs
        Catalog-->>Consumers: Serve lookup APIs (list run artifacts, fetch verification status)
        Consumers->>Golden: Retrieve curated artifacts for ingestion / graphing / evidence portals
    ```

**Highlights**

- Golden buckets or registries expose predictable prefixes for actors like ingestion pipelines, Neo4j loaders, or TrustCentre publishing jobs.
- Catalog entries track which raw artifacts were promoted, when, by whom, and under which verification policy.

---

## 6) Observability & Auto-Healing

> _Operators monitor promotions and reconcile gaps._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Gate
    participant Monitor
    participant Operator
    autonumber

        Gate->>Monitor: Emit events (promoted count, failures, quarantines)
        Monitor-->>Operator: Alerts / dashboards (per prefix, per tier)
        Operator->>Gate: Retry or approve quarantined artifacts
    ```

**Highlights**

- Promotion metrics highlight drift (e.g., sudden spike in digest mismatches) and ensure golden storage reflects current scans.
- Manual approvals are still auditable: retries include reason codes and signature/identity references.

---

**Outcome:** A defensible object lifecycle where only verified artifacts graduate from raw intake to curated “golden” storage, supporting the broader assurance platform regardless of the specific storage or verification tooling deployed.
