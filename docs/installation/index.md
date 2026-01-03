# Local Installation

These steps prepare a fresh workstation for Certus TAP local development using `just`, `uv`, `direnv`, and the default local LLM (Ollama).

> **Quick Start?** For a faster setup guide, see [QUICKSTART.md](../QUICKSTART.md) in the repository root.
>
> **Cloud Deployment?** This guide covers local development only. For deploying to DigitalOcean or production environments, see the deployment guides in the `deployment/` directory.

## 1. Install Ollama (local LLM runtime)

TAP defaults to a local LLM served by [Ollama](https://github.com/ollama/ollama) to keep data on your machine. Install and pull the default model:

```bash
curl -sSfL https://ollama.com/download | sh
ollama run llama3.1:8b
```

You can swap `llama3.1:8b` with any other installed model; just update `LLM_MODEL`/`LLM_URL` in your `.env`.

## 2. Install direnv, uv, and just

**Install direnv** for automatic environment configuration:

```bash
# macOS
brew install direnv

# Linux
sudo apt install direnv  # or your package manager

# Add to your shell (zsh example)
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc
```

**Install uv** using `pipx` so it stays isolated from system Python:

```bash
python3 -m pip install --user pipx
python3 -m pipx ensurepath
pipx install uv
```

**Install just** via your package manager (Homebrew, apt, etc.). We rely on it for repeatable recipes like `just install`, `just up`, and `just docs-serve`:

```bash
# macOS
brew install just

# Linux
cargo install just  # or via package manager
```

If you must export a `requirements.txt`, run:

```bash
uv export -f requirements.txt --output requirements.txt          # runtime only
uv export -f requirements.txt --dev --output requirements-dev.txt # dev + tooling
```

## 3. Clone the repository and bootstrap tooling

```bash
git clone https://github.com/mharrod/certus-tap.git
cd certus-tap

# Allow direnv to load environment (first time only)
direnv allow

# Install dependencies and pre-commit hooks
just install
```

When you `cd` into the project directory, direnv automatically:

- Activates the Python virtual environment
- Loads environment variables
- Sets up helpful aliases like `dev`, `dev-stop`, `dev-logs`

`just install` executes `uv sync`, installs dev dependencies, and attaches pre-commit hooks so your environment mirrors CI.

## 4. Configure environment variables

Copy the example file and adjust values as needed:

```bash
cp .env.example .env
```

Default values expect all services to run locally via Docker:

```bash
# OpenSearch
OPENSEARCH_HOST=http://localhost:9200
OPENSEARCH_INDEX=ask_certus
OPENSEARCH_HTTP_AUTH_USER=admin
OPENSEARCH_HTTP_AUTH_PASSWORD=admin

# LocalStack / AWS
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
S3_ENDPOINT_URL=http://localhost:4566
AWS_REGION=us-east-1

# LLM
LLM_MODEL=llama3.1:8b
LLM_URL=http://host.docker.internal:11434
```

If you change hosts/ports, remember to update the AWS CLI profile and any dependent scripts.

## 5. Build (optional) and start the stack

`just up` delegates to `./scripts/start-up.sh`, which ensures the Docker network exists and launches `docker compose up -d` for:

- `opensearch`
- `opensearch-dashboards`
- `localstack`
- `mlflow`
- `ask-certus-backend`

```bash
just up
```

If you change dependencies or Dockerfiles, rebuild via `docker compose build ask-certus-backend` (or the full stack) before running `just up`.

Use `just down`, `just cleanup`, or `just destroy` to stop the system, and `just docs-serve` / `./scripts/preflight.sh` as companion commands once services are live.

## 6. Configure AWS CLI for LocalStack

Install the [AWS CLI](https://aws.amazon.com/cli/) if necessary, then run:

```bash
aws configure
```

Use `test` for both the Access Key ID and Secret Access Key, `us-east-1` for the region, and `json` for output. Point S3 commands at LocalStack:

```bash
aws s3 ls --endpoint-url=http://localhost:4566
```

At this stage the environment is ready for ingestion (see `docs/installation/application.md`) and verification checks (`docs/installation/verify.md`).
