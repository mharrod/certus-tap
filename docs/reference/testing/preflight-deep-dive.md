# Preflight Deep Dive

`./scripts/preflight.sh` is the acceptance suite that keeps Certus TAP honest. This guide explains what it does, how to interpret the output, and how to recover when something fails.

## 1. Prerequisites

- Docker + Docker Compose running locally.
- `uv`/`pip` dependencies installed (`uv sync` or `pip install -e .[dev]`).
- Sample data available (repo `samples/` folder).
- Enough disk (OpenSearch + LocalStack images take ~4GB) and at least 8GB RAM.

Before the first run:

```bash
just destroy        # optional: clean start
uv sync             # ensure the virtualenv is up to date
```

## 2. What Preflight Does

The script orchestrates these stages:

1. **Bootstrap Containers** – `docker compose up -d` for OpenSearch, LocalStack (S3), MLflow, and the FastAPI backend.
2. **Health Checks** – Polls `/v1/health/*` until dependencies respond.
3. **Sample Ingestion** – Uses the ingestion API to upload sample files, preprocess into the datalake, and index them via the Haystack pipeline.
4. **Query Smoke Tests** – Runs representative questions against the RAG API to ensure embeddings + OpenSearch connections work.
5. **Evaluation Smoke (optional)** – If evaluation features are enabled, runs a minimal MLflow workflow.
6. **Log/Metric Scrape** – Ensures structlog output reaches the console and OpenSearch logging handler if enabled.

> **Note:** Security scanning is intentionally decoupled. Run `just test-security-light`
> (Dagger module) or the heavier `just test-security` workflows alongside preflight
> when you need vulnerability/secrets evidence.

## 3. Running the Script

```bash
./scripts/preflight.sh
```

Options:

- `SKIP_BUILD=1 ./scripts/preflight.sh` – reuse existing images.
- `VERBOSE=1 ./scripts/preflight.sh` – print each command before execution.

The script is idempotent; rerun after fixing issues.

## 4. Interpreting Output

Key sections to watch:

- **Container status** – if `docker compose` fails, check `docker compose logs <service>`.
- **Health checks** – repeated failures on `/v1/health/datalake` usually mean LocalStack isn’t ready.
- **Ingestion** – look for `datalake.initialization_complete` and `document.indexed` logs. Missing indicates pipeline regressions.
- **Query tests** – expect a JSON reply; `503` or `504` means your OpenSearch or LLM dependency isn’t reachable from the container (check `.env` `LLM_URL`).

## 5. Debugging Failures

| Symptom                                       | Likely Cause                                  | Fix                                                                                                        |
| --------------------------------------------- | --------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `Cannot connect to the Docker daemon`         | Docker stopped                                | Restart Docker Desktop and rerun.                                                                          |
| `/v1/health/ingestion` times out              | OpenSearch still warming up or wrong env vars | Inspect `docker compose logs opensearch`; ensure `.env` values match compose network names.                |
| S3 upload errors (`AccessDenied`)             | LocalStack credentials not exported           | The script sets `AWS_ACCESS_KEY_ID/SECRET_ACCESS_KEY=localstack`. If overridden, reset your shell.         |
| Query stage returns `503 service_unavailable` | LLM or OpenSearch unreachable from container  | Confirm the host’s LLM is listening on the `LLM_URL` reachable inside Docker (use `host.docker.internal`). |
| Script exits early with `preflight_failed`    | Any of the above                              | Inspect the log snippets the script prints; rerun sections manually if needed.                             |

## 6. Cleanup

Preflight leaves containers running so you can inspect them. When done:

```bash
just cleanup   # stop containers but keep volumes
just destroy   # stop and remove volumes (fresh start)
```

Use `docker compose ps` to confirm everything stopped.

## 7. Automating in CI

- Gate merges on `./scripts/preflight.sh` in nightly or main-branch workflows (requires Linux runners with Docker).
- Limit concurrency; preflight is resource heavy.
- Archive logs/artifacts for easier debugging.

## 8. Tips

- Keep `DISABLE_OPENSEARCH_LOGGING=true` when running pytest, but allow the handler during preflight to validate log shipping.
- Update `samples/` data carefully; preflight depends on those files existing.
- When editing Dockerfiles or compose, run `preflight` locally before pushing – it’s the fastest way to catch configuration drift.
