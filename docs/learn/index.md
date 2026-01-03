# Learn Certus TAP

The Learn section curates focused tutorials, walkthroughs, and troubleshooting tips for building, operating, and extending the Certus TAP stack. Use these resources whenever you need more than the high-level overview in `docs/Index.md` or the setup checklist in `docs/Installation/index.md`.

Before diving into production, start with the opinionated proof-of-concept environment (prewired Colima profile, `just test-security-light`, and bundled Dagger security module). Running the PoC end-to-end teaches the core TAP flow—structured ingestion (raw → quarantine → golden), privacy guardrails, signed artifacts, and reproducible security scans—without customizing pipelines yet. Although the tooling focuses on software security, the same principles apply across healthcare, utilities, construction, public sector, and other regulated industries because TAP’s ingest → transform → provenance → review loop is domain agnostic.

## The Basics

These match the entries under “The Basics” in the sidebar:

1. **[Getting started](getting-started.md)** – first run experience, stack topology, and how to validate your installation.
2. **[Document ingestion](ingestion-pipelines.md)** – deep dive on Haystack components, anonymizers, splitters, embedders, and writers.
3. **[Sample datalake upload](sample-datalake-upload.md)** – quick-start for staging files in raw, promoting to golden, and verifying ingestion.
4. **[Golden bucket workflows](golden-bucket.md)** – promotion pipelines, privacy guardrails, and quarantine handling.
5. **[Monitoring with structured logging](monitoring-with-logging.md)** – track ingestion progress, capture privacy failures, and debug issues.
6. **[Streamlit UI](streamlit-ui.md)** – explore the analyst console without writing curl commands.

## Security Workflows

Hands-on tutorials that mirror the “Security Workflows” section in the navigation:

1. **[Keyword search](keyword-search.md)** – deterministic OpenSearch queries against SARIF/SBOM data.
2. **[Semantic search](semantic-search.md)** – ask questions with embedding-powered retrieval.
3. **[Knowledge graphs](neo4j-local-ingestion-query.md)** – load findings into Neo4j and traverse relationships.
4. **[Hybrid search](hybrid-search.md)** – combine keyword + semantic scores for better recall.
5. **[Provenance & attestation](provenance/sign-attestations.md)** – ingest OCI artifacts, verify signatures, and cross-link SBOM/SARIF/provenance.
6. **[Compliance reporting](compliance-reporting.md)** – generate and distribute signed compliance artifacts.
7. **[Security analyst capstone](security-analyst-capstone.md)** – end-to-end scenario tying keyword, semantic, and graph queries together.
8. **[Secure scan tutorial](secure-scan/index.md)** – learn how the incubating Certus Assurance service runs standalone scans and produces SARIF/SBOM/DAST bundles for later ingestion.

Contributions are welcome—open a PR if you add or significantly update a guide so the navigation stays accurate.
