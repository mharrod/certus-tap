# Troubleshooting Cheat Sheet

Common issues and quick fixes for Certus TAP.

## Stack Fails to Start

- **Docker socket permission denied:** restart Colima (`colima start --network-address`) and rerun `docker compose ps`.
- **Ports already in use:** stop conflicting services or change exposed ports in `docker-compose.yml`.

## `./scripts/preflight.sh` Errors

- **FastAPI health 404:** rebuild the backend (`docker compose build --no-cache ask-certus-backend`) so `/v1/health/*` endpoints are registered.
- **OpenSearch check fails:** ensure OpenSearch container is running (`docker compose logs opensearch`). If the index is missing, re-ingest documents.
- **MLflow empty reply:** confirm port mapping is `5001:5001` and container logs show `mlflow ui --host 0.0.0.0 --port 5001`.
- **Embedder health fails:** clear the Hugging Face cache volume with `docker compose exec ask-certus-backend rm -rf /opt/huggingface/* && docker compose restart ask-certus-backend` to trigger a clean model download.
- **Datalake health fails:** rerun `./scripts/start-up.sh` (it recreates the `raw` bucket via LocalStack). If you removed LocalStack volumes manually, delete the `hf-cache`/`localstack-volume` volumes and restart.
- **Smoke query 500:**
  - Verify `sentence-transformers` is installed (re-run `uv lock` / rebuild).
  - Ensure documents are indexed (search OpenSearch or rerun ingestion).
  - Check Ollama connectivity (below).

## Ollama Connectivity Issues

- Default `.env` uses `LLM_URL=http://host.docker.internal:11434`.
- Run `curl http://localhost:11434/api/tags` on the host to confirm models are available.
- If calling a remote LLM, update `.env` and the pipeline component accordingly.

## Ingestion Failures

- **500 during `/v1/index`**: inspect backend logs; common causes include unsupported file types or missing converters.
- **LocalStack errors**: confirm credentials (`AWS_ACCESS_KEY_ID=test`, `AWS_SECRET_ACCESS_KEY=test`) and that LocalStack is running (`docker compose logs localstack`).

## Evaluation Issues

- **DeepEval model errors**: ensure environment variables for external LLMs are set if you use remote evaluation components.
- **MLflow not logging**: check `MLFLOW_TRACKING_URI` in `.env` and `docker compose logs mlflow`.

## General Tips

- `just cleanup` to stop containers without losing data.
- `just destroy` for a clean slate (all volumes removed).
- Use `docker compose logs -f ask-certus-backend` to tail the application.
- If in doubt, rerun `./scripts/preflight.sh` after fixes to confirm system health.

Keep this cheat sheet handy during development and extend it as you encounter new edge cases.
