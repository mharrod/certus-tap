# Project Context

Current state of the Certus TAP ingestion backend. Keep this brief and up to date.

## System Synopsis

- **Purpose:** Document ingestion + RAG API built with FastAPI and Haystack.
- **Core Flow:** fetch → preprocess → (optional) anonymize → split → embed → write to OpenSearch.
- **Key Modules:** `certus_ask/` (API, pipelines, services), `scripts/` (ops + smoke tests).
- **Data Stores:** OpenSearch for vectors, LocalStack S3 buckets for raw/golden artifacts.

## Active Focus

1. Keep ingestion pipelines (files, git, SARIF, web) healthy and reproducible.
2. Maintain guardrails/anonymizers and LLM configuration safety.
3. Ensure the full stack (FastAPI, OpenSearch, LocalStack) stays green via `./scripts/preflight.sh`.

## Architecture Snapshot

| Layer     | What it does                                       | Anchor files                                |
| --------- | -------------------------------------------------- | ------------------------------------------- |
| API       | FastAPI routers + health checks                    | `certus_ask/main.py`, `certus_ask/routers/` |
| Pipelines | Haystack nodes + preprocessing utilities           | `certus_ask/pipelines/`                     |
| Services  | Connectors for GitHub, S3/LocalStack, web crawlers | `certus_ask/services/`                      |
| Storage   | OpenSearch index + LocalStack buckets              | `docker-compose.yml`, `.env`                |
| Tooling   | Docker/Compose, `uv`, `just`, helper scripts       | `Dockerfile`, `justfile`, `scripts/*.sh`    |

## Commands & Lifecycle

1. **Start stack:** `just up` or `./scripts/start-up.sh`.
2. **Edit code:** stay within assigned directories/tasks.
3. **Deps changed?** update `pyproject.toml`, run `uv lock`, and rebuild `ask-certus-backend`.
4. **Validate:** `./scripts/preflight.sh` (non-negotiable); add targeted tests as needed.
5. **Stop stack:** `just cleanup` or `just destroy`.

## Important Locations

- `samples/datalake-demo/` – mixed formats for ingestion smoke tests.
- `samples/privacy-pack/` – contains intentional PII to exercise guardrails.
- Buckets in LocalStack:
  - `DATALAKE_RAW_BUCKET` – uploaded/raw artifacts.
  - `DATALAKE_GOLDEN_BUCKET` – curated outputs.

## Guardrails & Gotchas

- Never change `.env` `LLM_URL` (must be `host.docker.internal`).
- New ingestion logic must fit the Haystack modular flow (anonymizer → splitter → embedder → writer).
- Docs live in `docs/learn/` (lowercase) with `.pages` updates.
- Web scraping must honor `robots.txt` and use Scrapy for recursive crawls.
- The backend image pre-caches embeddings—`docker compose build ask-certus-backend` is required after dependency changes.

## When Stuck

1. Re-read `AGENTS.md` for rules.
2. Check `.context/bootstrap*.txt` for role guidance.
3. Inspect logs (`docker compose logs -f ask-certus-backend`) and run `./scripts/preflight.sh`.
4. Ask a human if ambiguity remains.
