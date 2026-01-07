# Getting Started with Certus TAP (Local Development)

>**STATUS:Tutorial is currently in beta. If you have issues see our [Communication & Support guide](../about/communication.md)**

This walkthrough takes you from a clean checkout to a working local development stack and your first RAG query.

This guide covers **local development** setup using Docker Compose. For more production/staging like deployments to DigitalOcean or other cloud providers, see the [deployment guides](https://github.com/mharrod/certus-tap/tree/main/deployment/tofu/environments).

## 1. Prerequisites

- **Docker**: Colima, Docker Desktop, or Rancher Desktop. Ensure `host.docker.internal` resolves inside containers.
- **Python 3.11+** with [`uv`](https://python-uv.org/docs/) installed: `pipx install uv`
- **[direnv](https://direnv.net/)**: For automatic environment management
  - macOS: `brew install direnv`
  - Linux: `sudo apt install direnv` or `sudo dnf install direnv`
  - Add to your shell: `eval "$(direnv hook bash)"` (or zsh/fish)
- **[Ollama](https://ollama.com/download)**: Running locally with a model pulled: `ollama run llama3.1:8b`
- **Git**

!!! tip "Quick Start"
For a condensed overview, see [QUICKSTART.md](https://github.com/mharrod/certus-tap/blob/main/QUICKSTART.md) in the repository root.

## 2. Clone and Configure

```bash
git clone https://github.com/mharrod/certus-tap.git
cd certus-tap

# direnv will prompt you to allow the environment
direnv allow

# Copy example environment file
cp .env.example .env
```

!!! tip "direnv Benefits"
Once you run `direnv allow`, direnv automatically:

    - Activates your Python virtual environment when you `cd` into the project
    - Loads environment variables from `.env`
    - Sets up helpful aliases like `dev` (starts stack + runs preflight)
    - Configures `PYTHONPATH` and other development settings

    See the [Installation Guide](../installation/) for more details.

Adjust `.env` if you're using custom ports or credentials.

## 3. Install Python Dependencies

```bash
uv lock
uv sync --group backend --dev
```

`uv lock` syncs `uv.lock` with `pyproject.toml`; `uv sync` installs the backend + dev dependencies in your virtual environment.

## 4. Build Containers and Start the Stack

The quickest way to get started is using the `dev` alias (configured by direnv):

```bash
dev
```

This runs `just up` followed by `just preflight`, starting all services and verifying they're healthy.

Alternatively, start services individually:

```bash
just up
```

If `just` is unavailable, run:

```bash
docker compose build
./scripts/start-up.sh
```

Either path launches OpenSearch, LocalStack, MLflow, Neo4j, and the FastAPI backend.

## 5. Run Preflight Checks

```bash
just preflight
```

Without `just`, run `./scripts/preflight.sh`.
The script checks:

- FastAPI health (`/v1/health`, `/v1/health/ingestion`, `/v1/health/evaluation`)
- OpenSearch, LocalStack, MLflow availability
- A smoke RAG query via `/v1/ask`

All checks must pass before continuing.

## 6. Explore the API

- **Swagger UI:** `http://localhost:8000/docs`
- **FastAPI health:** `curl http://localhost:8000/v1/health`

## 7. Ingest Documents

By default, documents are ingested into the `default` workspace. To learn about multi-workspace isolation, see [Multi-Workspace Isolation](../reference/core-reference/multi-workspace-isolation.md).

Single file (e.g. `docs/index.md`):

```bash
curl -X POST http://localhost:8000/v1/default/index/ \
  -F "uploaded_file=@docs/index.md"
```

Or specify a custom workspace:

```bash
curl -X POST http://localhost:8000/v1/my-workspace/index/ \
  -F "uploaded_file=@docs/index.md"
```

Folder (recursively):

```bash
curl -X POST http://localhost:8000/v1/default/index_folder/ \
  -H "Content-Type: application/json" \
  -d '{"local_directory": "docs"}'
```

The backend runs the preprocessing pipeline (clean, split, embed) and writes chunks to OpenSearch with workspace isolation metadata.

## 8. Ask Questions

Once documents are indexed in a workspace, query that workspace with `/v1/{workspace_id}/ask`:

```bash
curl -X POST http://localhost:8000/v1/default/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Summarize Certus TAP objectives."}'
```

Responses include the model's answer plus retrieved context.

## 9. Multi-Workspace Isolation

The `default` workspace used above is the starting point. For managing multiple independent analyses, products, or clients with complete data separation, see [Multi-Workspace Isolation](../reference/core-reference/multi-workspace-isolation.md).

## 10. Supporting UIs

- **OpenSearch Dashboards:** `http://localhost:5601`
- **MLflow UI:** `http://localhost:5001`
- **Swagger UI:** `http://localhost:8000/docs`
- **Streamlit UI:** `http://localhost:8501`
- **Neo4j:** `http://localhost:7474`

## 11. Maintenance Commands

- **Stop containers, keep volumes:** `just down`
- **Stop + remove containers, keep volumes:** `just cleanup`
- **Full teardown (containers + volumes):** `just destroy`

Without `just`, run the underlying scripts in `./scripts`. Re-run `just up` (or `./scripts/start-up.sh`) whenever you want to bring the stack back.

!!! tip "Development Workflow"
With direnv configured, your typical workflow is:

    1. `cd certus-tap` - environment auto-loads
    2. `just up` - starts the stack
    3. `just preflight` - verifies services are healthy
    4. Make code changes
    5. `just down` - stops the stack when done

    See [Local Development Guide](https://github.com/mharrod/certus-tap/blob/main/deployment/README.md) for advanced workflows.
