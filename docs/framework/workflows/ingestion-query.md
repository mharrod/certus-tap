# Ingestion & Query

> **Status:** ✅ Implemented in the current Certus PoC (FastAPI ingestion + Haystack pipelines)

This workflow captures the end-to-end flow for bringing unstructured content into the assurance knowledge base and preparing it for querying. Privacy/other guardrails are detailed in [Guardrails & Controls](guardrails.md).

---

## 1) Submission & Intake Contract

> _An actor submits a document bundle for ingestion under declared constraints._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Producer
    participant Intake as Ingestion_Gateway
    participant Contract as Intake_Contract_Store
    autonumber

        Producer->>Intake: Upload files / point to repository
        Intake->>Contract: Retrieve workspace policy (size, formats, retention)
        Contract-->>Intake: Return policy + privacy flags
        Intake-->>Producer: Confirm receipt + policy hash
    ```

**Highlights**

- Submissions are bound to a workspace- or engagement-level _intake contract_ describing permitted formats, privacy posture (strict vs allow-anonymize), and routing metadata.
- The contract hash accompanies every subsequent processing step, allowing downstream services to prove which constraints were enforced.

---

## 2) Normalization & Chunking

> _Clean documents are transformed into a retrieval-friendly representation._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Cleaner
    participant Splitter
    participant Enricher
    autonumber

        Cleaner->>Cleaner: Convert formats (PDF, DOCX, HTML) to canonical text
        Cleaner->>Splitter: Send normalized text with metadata envelope
        Splitter->>Splitter: Chunk content (windowing, overlap, heuristics)
        Splitter->>Enricher: Forward chunks + structural cues
        Enricher->>Enricher: Derive tags (workspace, source key, contract hash, privacy flags)
    ```

**Highlights**

- Normalization ensures heterogeneous files land in a consistent structure (e.g., Haystack `Document`, LangChain `Document`, or an internal schema).
- Enrichment attaches metadata needed for downstream routing: workspace IDs, source URIs, guardrail disposition, and any verification digests.

---

## 3) Enrichment & Metadata

> _Annotate chunks with derived metadata to improve routing and query precision._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Enricher
    participant Tagger
    participant Ledger
    autonumber

        Enricher->>Tagger: Provide chunk content + contract metadata
        Tagger->>Tagger: Auto-tag (service/component, language, data sensitivity)
        Tagger->>Tagger: Derive summaries, topics, NER results
        Tagger-->>Enricher: Return enriched metadata envelope
        Enricher->>Ledger: Record mapping (chunk id → source/contract/tags)
    ```

**Highlights**

- Metadata can include service ownership, repo/commit, environment, data classification, document language, etc.
- Derived fields (chunk summary, topic labels, named entities) speed up search, triage, and policy routing.
- Enrichment outputs feed both embedding indices and downstream systems (policy gates, datalake catalogs).

---

## 4) Embedding, Indexing & Traceability

> _Chunks become retrievable artifacts with provenance trails._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Embedder
    participant Index as Vector/Keyword_Index
    participant Archive as Evidence_Store
    autonumber

        Embedder->>Embedder: Generate vector representations per chunk
        Embedder->>Index: Upsert {chunk_id, embedding, metadata}
        Index-->>Embedder: Return document counts / write receipts
        Embedder->>Archive: Emit metadata preview (chunk ids, source keys, policy hash)
    ```

**Highlights**

- Index backends (OpenSearch, Vespa, Milvus, etc.) receive both dense and sparse representations along with a metadata envelope.
- A lightweight _metadata preview_ is preserved (e.g., in object storage or a ledger) so auditors can inspect what was indexed without querying the vector store itself.

---

## 5) Verification Handles & Replay

> _Maintain references so ingested content can be replayed, deleted, or re-verified._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Intake
    participant Archive
    participant Catalog
    autonumber

        Intake->>Archive: Persist chunk manifest (source key, chunk id, hash, metadata)
        Archive-->>Catalog: Provide lookup APIs (list chunks by source, manifest version)
        Catalog-->>Intake: Enable replay/delete requests using contract + chunk ids
    ```

**Highlights**

- Each chunk retains pointers back to the intake contract, source URI, and optional verification proofs (digests, signatures).
- Operators can deterministically replay ingestion (same chunk IDs/hashes) or surgically delete content if policies change.
- Downstream services (datalake, policy gates) can verify ingested content against stored digests.

---

## 6) Query Readiness & Observability

> _The system surfaces ingestion results, anomalies, and replay handles._

??? info "Sequence"
    ```mermaid
    sequenceDiagram
    participant Intake
    participant Observer as Observability_Plane
    participant Analyst
    autonumber

        Intake->>Observer: Emit ingestion summary (files processed, quarantined, chunk counts)
        Observer-->>Analyst: Provide dashboards / alerts
        Analyst->>Intake: Request replay or metadata preview
        Intake-->>Analyst: Serve reproducible records via contract + chunk ids
    ```

**Highlights**

- Operators can quickly confirm how many documents were ingested, how many required masking, and whether any failures need attention.
- Replay handles (contract hash + chunk IDs) allow deterministic reprocessing or targeted deletion without guessing the original file layout.

---

**Outcome:** A consistent ingestion pipeline ready for retrieval, reasoning, and later TrustCentre anchoring—agnostic of the exact NLP toolkit or storage vendor used. Pair this with [Guardrails & Controls](guardrails.md) to enforce privacy/security policies alongside ingestion.
