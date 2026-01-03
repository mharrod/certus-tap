<p align="center">
  <img src="docs/assets/images/logo.png" alt="Agentic RAG TAP Logo" width="150"/>
</p>

# currently very unstable

# Certus TAP

This repository contains **Certus TAP** (Transparency, Assurance, and Privacy), a reference implementation of the broader [Certus Trust & Assurance Platform](docs/framework/index.md). The TAP framework defines the technology-agnostic principles, architecture, workflows, ontology, and practices for building trustworthy assurance systems. Certus TAP demonstrates those concepts with concrete technologies (FastAPI, Haystack, OpenSearch, LocalStack, Sigstore, etc.) so teams can validate the framework end-to-end. Not every aspirational workflow in the framework is fully realized yet, but this codebase evolves toward that target and provides a living example of how to assemble the components.

Think of the relationship like this:

- **Workflows** describe the aspirational end-to-end motions (developer, auditor, ops, etc.).
- Those workflows inform the **framework architecture** (contracts, components, guardrails).
- The PoC implements specific **capabilities** that bring portions of that architecture to life today.

This application allows users to ingest documents, process them using the Haystack pipeline for NLP tasks, and store the processed documents in an OpenSearch index. The API is built using FastAPI and supports multiple file types, including PDF, Markdown, and text files. There is also functionality for scraping websites and ingesting git repos

**PLEASE NOTE:** This prototype is intended for exploration and reaearch only. only. The proper testing and security features are not added and should be added before adapting this prototype for production.

## Project Status & Participation

**Current Phase:** Pre-Alpha / Experimental

Certus TAP is in early development. The repository is public to share ideas, architecture, and research direction—not to solicit open contributions at scale.

- **Contributions:** Gated by default. Interested collaborators should review [docs/about/participation.md](docs/about/participation.md).
- **Governance:** See [GOVERNANCE.md](GOVERNANCE.md) for decision-making and project stewardship.

## Licensing

`Certus TAP` is licensed under **AGPL v3**.

This ensures that all improvements to the platform remain open and benefit the entire research community. If you modify this software for network use (e.g., running it as a service), you must make your source code available to users of that service.

For full license details, see [LICENSE](LICENSE).

## Features

- Unified FastAPI service exposing ingestion, query, datalake, and evaluation endpoints.
- Ingest documents via file upload or from an S3 bucket.
- Process documents with the Haystack NLP pipeline:
  - Split long documents into smaller chunks.
  - Clean documents (remove unwanted characters).
  - Embed documents using SentenceTransformers.
  - Store documents in an OpenSearch document store.
- Expose a simple API to trigger document ingestion and processing.
- Use Docker and Docker Compose for easy setup and deployment.

## Quick Start Snapshot

1. Clone the repo and sync dependencies with `uv sync --group backend --dev`.
2. Start the docs serve `just docs-serve`
3. Copy `.env.example` to `.env`, then adjust OpenSearch, LocalStack, and LLM settings as needed.
4. Bring up the local stack (`just up` or `./scripts/start-up.sh`) to launch FastAPI, OpenSearch, LocalStack, and MLflow.
5. Run `just preflight` or `./scripts/preflight.sh` to execute the smoke ingestion suite before testing new changes.

## Customer Data Prep Service

Running `just up` now launches a second FastAPI container (`certus-transform`, port `8100`) that lives alongside LocalStack. This service encapsulates the on-prem workflow—uploading into `raw/active`, running Presidio scans/quarantine, promoting to the golden bucket, and triggering SaaS ingestion via `/v1/{workspace}/index/security/s3`. Configure it with two additional environment variables:

- `SAAS_BACKEND_URL`: the base URL for the hosted Ask Certus API (defaults to `http://ask-certus-backend:8000` inside Docker).
- `SAAS_API_KEY` (optional): bearer token that will be forwarded with ingestion requests.

Use the new `/health`, `/v1/uploads/raw`, `/v1/privacy/scan`, `/v1/promotions/golden`, and `/v1/ingest/security` endpoints to automate the full raw → golden → SaaS ingestion flow without copying files back to your workstation.

## Embedding Cache Hardening

- The backend Docker image now preloads `sentence-transformers/all-MiniLM-L6-v2` during build so Haystack can run offline. Rebuild with `docker compose build --no-cache ask-certus-backend` whenever dependencies change.
- `docker-compose.yml` mounts a persistent Hugging Face cache volume at `/opt/huggingface` (`HF_HOME`) so container restarts reuse the cached weights.
- `./scripts/preflight.sh` calls the new `GET /v1/health/embedder` endpoint, which instantiates the embedder and fails fast if the cache is missing or corrupt.

## Datalake Bootstrap

- `./scripts/start-up.sh` now sources `.env` and auto-creates both `DATALAKE_RAW_BUCKET` and `DATALAKE_GOLDEN_BUCKET` (plus default folders) inside LocalStack right after the stack becomes healthy.
- `./scripts/preflight.sh` hits `GET /v1/health/datalake` to confirm the backend can reach both buckets before continuing with smoke ingestion.

## Sample Upload Bundle

- `samples/datalake-demo/` ships with mixed Markdown, TXT, CSV, HTML, and PDF files you can safely ingest.
- `samples/privacy-pack/` contains the artifacts used in `docs/Learn/privacy-screening.md` (Markdown, RTF, PDF with intentional PII) so you can practice guardrail workflows.
- The backend image copies this folder to `/app/samples/datalake-demo`, so `/datalake/upload` can read it without extra mounts.
- Run `just datalake-upload-samples` (or `./scripts/datalake-upload-sample.sh`) to push the bundle into the `raw` bucket.
- Ingest any object directly from S3 via `POST /datalake/ingest` (no need to download locally first).
- Tutorials: raw-only flow (`docs/Learn/sample-datalake-upload.md`) and golden promotion flow (`docs/Learn/golden-bucket.md`).

## Documentation Map

It is preffered that you access documentation through the mkdocs server but you can also access through the links below:

- [Project overview (`docs/Index.md`)](docs/Index.md) — motivation, architecture, roadmap, and guardrails.
- [Architecture reference (`docs/architecture/index.md`)](docs/architecture/index.md) — system diagrams, deployment flows, and security considerations.
- [Installation guide (`docs/Installation/index.md`)](docs/Installation/index.md) — environment setup, dependency management, and stack bootstrap instructions.
- [Learn hub (`docs/Learn/index.md`)](docs/Learn/index.md) — ingestion tutorials, troubleshooting tips, and advanced usage guides.
- [Runbook & troubleshooting (`docs/Learn/troubleshooting.md`)](docs/Learn/troubleshooting.md) — common failures, scripts like `just up` / `./scripts/preflight.sh`, and recovery playbooks.

See the MkDocs site (served from the `docs/` directory) for diagrams, ingestion walkthroughs, and extended guidance on extending the pipelines.
