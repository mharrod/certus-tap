# Application Set-up

This page assumes you already completed the basic workstation prep in `docs/installation/index.md`. Use it as the “operator’s manual” for running, rebuilding, and troubleshooting the local stack.

## 1. Before you begin

Make sure the following are in place:

- Docker Desktop (or another Docker engine) is running.
- `uv`, `just`, and the AWS CLI are installed (`just install` was executed at least once).
- `.env` reflects how you want to run the stack (default values target localhost).

## 2. Start / stop the stack

Use the `just` recipes to manage lifecycle:

| Command        | Description                                                                                                                                               |
| -------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `just up`      | Creates the `opensearch-net` network (if needed) and runs `docker compose up -d` for OpenSearch, Dashboards, LocalStack, MLflow, and the FastAPI backend. |
| `just down`    | Stops containers but keeps volumes.                                                                                                                       |
| `just cleanup` | Stops and removes containers (volumes retained).                                                                                                          |
| `just destroy` | Removes containers **and** named volumes (fresh start).                                                                                                   |

Tail logs with `docker compose logs -f <service>` or `just up; docker compose logs -f ask-certus-backend` during development.

## 3. Rebuild after dependency changes

Whenever you edit `pyproject.toml`, `uv.lock`, or Dockerfiles:

```bash
uv lock                      # optional: refresh lockfile
docker compose build ask-certus-backend
just up                      # restarts services with the new image
```

If you only changed docs or scripts, restarting isn’t necessary—use `just docs-serve` or rerun `./scripts/preflight.sh` as appropriate.

## 4. AWS CLI profile for LocalStack

Point the AWS CLI at LocalStack so ingestion scripts can push data into the emulated S3 buckets:

```bash
aws configure
# Access key ID: test
# Secret access key: test
# Region: us-east-1
# Output: json
```

Or edit the config/credentials files directly. Always include `--endpoint-url=http://localhost:4566` when running S3 commands. Example:

```bash
aws s3 ls --endpoint-url=http://localhost:4566
```

## 5. Running the backend locally (optional)

`just up` runs the API inside Docker, but you can also start it on your host for a tighter edit/refresh loop:

```bash
uv run uvicorn certus_ask.main:app --reload
```

Leave the other services (OpenSearch, LocalStack, MLflow) in Docker; only the FastAPI process runs locally.

## 6. Handy companion commands

- `./scripts/preflight.sh` – smoke test ingestion + query flows; run before committing changes that touch guardrails, LLM configs, or dependencies.
- `just docs-serve` – start the MkDocs live-reload server for documentation edits.
- `docker compose logs -f localstack` / `... opensearch` – useful when debugging ingestion issues.

Once the stack is running you can proceed to `docs/installation/verify.md` for health checks and `docs/Learn/*` tutorials to exercise ingestion pipelines.
