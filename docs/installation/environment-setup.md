# Environment Setup Guide

Understanding and configuring your Certus TAP environment using direnv and environment variables.

!!! tip "Quick Start"
For step-by-step installation instructions, see the [Installation Guide](index.md). For a condensed overview, see [QUICKSTART.md](../../QUICKSTART.md).

## Overview

Certus TAP uses a combination of **direnv** and **`.env` files** to manage environment configuration:

- **direnv** - Automatically loads environment variables when you `cd` into the project directory
- **`.env` file** - Contains environment-specific configuration (service URLs, credentials, feature flags)
- **`.envrc` file** - Configures direnv behavior, activates Python virtual environment, sets aliases

### How They Work Together

1. **Clone project** → `.envrc` exists in repository
2. **Run `direnv allow`** → direnv is now active for this directory
3. **Copy `.env.example` to `.env`** → Your local configuration
4. **`cd` into project** → direnv automatically:
   - Activates Python virtual environment
   - Loads variables from `.env`
   - Sets up helpful aliases (`dev`, `dev-stop`)
   - Configures `PYTHONPATH` and other development settings

### Benefits

- **No manual activation** - Virtual environment activates automatically
- **No forgetting exports** - Environment variables load automatically
- **Consistent environments** - Same setup across all developers
- **Secure secrets** - `.env` is gitignored, never committed
- **Easy switching** - Different `.envrc` files for different deployment environments

---

## Environment Types

Certus TAP supports multiple deployment environments, each with different configuration needs:

### Local Development (Docker Compose)

**Purpose:** Development on your local machine
**Services:** All services run in Docker containers
**Configuration:** `.env` in project root
**Managed by:** `docker-compose.full-dev.yml`

**Start:** `just dev-up` or `dev` (direnv alias)
**Stop:** `just dev-down` or `dev-stop` (direnv alias)

**Key settings in `.env`:**

```bash
CERTUS_ENV=local
OPENSEARCH_HOST=http://localhost:9200
LOCALSTACK_ENDPOINT=http://localhost:4566
LLM_URL=http://localhost:11434
MLFLOW_TRACKING_URI=http://localhost:5001
```

**See:** [Local Development Guide](../../deployment/README.md#local-development)

### Single-Node Deployment (DigitalOcean Droplet)

**Purpose:** Production deployment on a single server
**Services:** systemd + podman on one droplet
**Configuration:** `deployment/tofu/environments/single-node/.env` + `.envrc`
**Managed by:** OpenTofu + cloud-init

**Deploy:** `cd deployment/tofu/environments/single-node && tofu apply`

**Key settings:**

```bash
CERTUS_ENV=staging
DEPLOYMENT_TYPE=single-node
TF_VAR_environment=staging
TF_VAR_droplet_size=s-2vcpu-4gb
```

**See:** [Single-Node Deployment Guide](../../deployment/tofu/environments/single-node/README.md)

### Multi-Node Deployment (Multiple Droplets)

**Purpose:** Distributed production deployment
**Services:** systemd + podman across multiple servers
**Configuration:** `deployment/tofu/environments/multi-node/.env` + `.envrc`
**Managed by:** OpenTofu + Tailscale mesh networking

**Status:** Planned (not yet implemented)

### Managed Services (DigitalOcean/AWS)

**Purpose:** Cloud-native deployment with managed databases and storage
**Services:** Managed OpenSearch, S3, RDS, etc.
**Configuration:** `deployment/tofu/environments/managed/.env` + `.envrc`
**Managed by:** OpenTofu

**Status:** Planned (not yet implemented)

---

## Core Environment Variables

### Required Variables

These variables must be set for the application to start:

| Variable                | Purpose                  | Local Dev Example        | Production Example                 |
| ----------------------- | ------------------------ | ------------------------ | ---------------------------------- |
| `OPENSEARCH_HOST`       | OpenSearch endpoint      | `http://localhost:9200`  | `https://opensearch.internal:9200` |
| `OPENSEARCH_INDEX`      | Default index name       | `certus-docs`            | `certus-production`                |
| `AWS_ACCESS_KEY_ID`     | S3/LocalStack access key | `test`                   | `AKIA...` (from secrets)           |
| `AWS_SECRET_ACCESS_KEY` | S3/LocalStack secret     | `test`                   | (from secrets manager)             |
| `S3_ENDPOINT_URL`       | S3 endpoint              | `http://localhost:4566`  | `https://s3.amazonaws.com`         |
| `AWS_REGION`            | AWS region               | `us-east-1`              | `us-east-1`                        |
| `LLM_MODEL`             | Model identifier         | `llama3.1:8b`            | `llama3.1:70b`                     |
| `LLM_URL`               | LLM service URL          | `http://localhost:11434` | `http://ollama.internal:11434`     |
| `MLFLOW_TRACKING_URI`   | MLflow endpoint          | `http://localhost:5001`  | `http://mlflow.internal:5001`      |

### Optional Configuration

| Variable                  | Purpose                    | Default            | Notes                               |
| ------------------------- | -------------------------- | ------------------ | ----------------------------------- |
| `CERTUS_ENV`              | Environment identifier     | `local`            | Used for logging/metrics            |
| `LOG_LEVEL`               | Logging verbosity          | `INFO`             | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_JSON_OUTPUT`         | Structured logging         | `false`            | Set `true` for production           |
| `SEND_LOGS_TO_OPENSEARCH` | Log aggregation            | `false`            | Set `true` for production           |
| `EMBEDDING_MODEL`         | Sentence transformer model | `all-MiniLM-L6-v2` | Impacts vector search quality       |
| `CHUNK_SIZE`              | Document chunk size        | `500`              | Characters per chunk                |
| `CHUNK_OVERLAP`           | Chunk overlap              | `50`               | Characters of overlap               |

### Service-Specific Variables

**Data Lake (Transform)**

```bash
DATALAKE_RAW_BUCKET=raw
DATALAKE_GOLDEN_BUCKET=golden
DATALAKE_SAMPLE_FOLDER=samples
```

**Integrity Monitoring**

```bash
INTEGRITY_ENABLED=true
INTEGRITY_CHECK_INTERVAL=300
INTEGRITY_ALERT_THRESHOLD=0.8
```

**Neo4j (Knowledge Graph)**

```bash
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
```

**OpenTelemetry (Observability)**

```bash
OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
OTEL_SERVICE_NAME=certus-ask
```

---

## Customizing Your Environment

### When to Modify `.env`

**Change these values when:**

1. **Using different service URLs** - External OpenSearch, hosted Ollama, etc.
2. **Switching models** - Different LLM model sizes or providers
3. **Enabling features** - Turn on integrity monitoring, privacy filtering, etc.
4. **Performance tuning** - Adjust chunk sizes, batch sizes, timeout values
5. **Production deployment** - Enable structured logging, change log levels

**Never commit `.env` to git** - It may contain credentials or secrets

### Example: Using External OpenSearch

```bash
# .env - Connect to managed OpenSearch cluster
OPENSEARCH_HOST=https://vpc-certus-abc123.us-east-1.es.amazonaws.com
OPENSEARCH_HTTP_AUTH_USER=admin
OPENSEARCH_HTTP_AUTH_PASSWORD=${OPENSEARCH_PASSWORD}  # From secrets manager
OPENSEARCH_USE_SSL=true
OPENSEARCH_VERIFY_CERTS=true
```

### Example: Enabling Privacy Features

```bash
# .env - Enable PII detection and filtering
PRIVACY_ENABLED=true
PRIVACY_DETECTION_MODE=strict
PRIVACY_REDACTION_ENABLED=true
PII_DETECTION_THRESHOLD=0.8
```

### Example: Production Logging

```bash
# .env - Production logging configuration
LOG_LEVEL=INFO
LOG_JSON_OUTPUT=true
SEND_LOGS_TO_OPENSEARCH=true
OTEL_EXPORTER_OTLP_ENDPOINT=http://otel-collector:4317
OTEL_SERVICE_NAME=certus-ask-production
```

---

## Environment-Specific Configuration

### Local Development Best Practices

```bash
# .env for local development
CERTUS_ENV=local

# Use localhost for all services
OPENSEARCH_HOST=http://localhost:9200
LOCALSTACK_ENDPOINT=http://localhost:4566
LLM_URL=http://localhost:11434
MLFLOW_TRACKING_URI=http://localhost:5001

# Faster feedback during development
LOG_LEVEL=DEBUG
LOG_JSON_OUTPUT=false
SEND_LOGS_TO_OPENSEARCH=false

# Test credentials (LocalStack)
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test

# Smaller model for faster iteration
LLM_MODEL=llama3.1:8b
```

**Start development environment:**

```bash
dev  # direnv alias for 'just dev-up && just preflight-dev'
```

### Single-Node Deployment Configuration

Located in `deployment/tofu/environments/single-node/.envrc`:

```bash
# Inherits from root .envrc
source_up

# Deployment-specific settings
export CERTUS_ENV=staging
export DEPLOYMENT_TYPE=single-node

# OpenTofu variables
export TF_VAR_environment=staging
export TF_VAR_droplet_size=s-2vcpu-4gb
export TF_VAR_region=nyc3

# Helpful aliases
alias tf-plan='tofu plan -var-file=secrets.tfvars'
alias tf-apply='tofu apply -var-file=secrets.tfvars'
alias ssh-droplet='ssh root@$(tofu output -raw droplet_ip)'
```

**Deploy to DigitalOcean:**

```bash
cd deployment/tofu/environments/single-node
direnv allow  # Load deployment environment
tf-plan       # Preview changes
tf-apply      # Deploy infrastructure
```

---

## Networking Configuration

### Understanding Host vs Container Networking

**Problem:** Service URLs differ depending on where your code runs.

#### Running Application on Host (Local Development)

```bash
# .env - Application runs on your laptop
OPENSEARCH_HOST=http://localhost:9200      # ✓ Works
OPENSEARCH_HOST=http://opensearch:9200     # ✗ Fails (no DNS)
```

Services in Docker are accessible via `localhost` because of port mapping in `docker-compose.full-dev.yml`.

#### Running Application in Container (Docker Compose)

```bash
# .env - Application runs in Docker container
OPENSEARCH_HOST=http://opensearch:9200     # ✓ Works (Docker network)
OPENSEARCH_HOST=http://localhost:9200      # ✗ Fails (localhost = container itself)
```

Containers use Docker network DNS to resolve service names.

#### Special Case: Docker Desktop (macOS/Windows)

```bash
# .env - Works from both host AND container
OPENSEARCH_HOST=http://host.docker.internal:9200  # ✓ Universal
```

Docker Desktop provides `host.docker.internal` as a special DNS name that resolves correctly from both contexts.

### Networking by Environment

| Environment         | Application Location | Service URLs                | Example                  |
| ------------------- | -------------------- | --------------------------- | ------------------------ |
| Local Dev (Host)    | Host machine         | `localhost:PORT`            | `http://localhost:9200`  |
| Docker Compose      | Container            | Service names               | `http://opensearch:9200` |
| Single-Node Droplet | Systemd service      | `localhost` or internal IPs | `http://localhost:9200`  |
| Multi-Node          | Systemd across nodes | Tailscale IPs               | `http://100.64.1.2:9200` |

---

## Troubleshooting

### Configuration Validation Errors

**Symptom:** Application won't start, shows validation errors

```
[CRITICAL] opensearch_host: Missing required environment variable: OPENSEARCH_HOST
```

**Solution:**

```bash
# Check .env exists
ls -la .env

# Check variable is defined
grep OPENSEARCH_HOST .env

# If missing, add it
echo "OPENSEARCH_HOST=http://localhost:9200" >> .env
```

**Symptom:** Invalid URL format

```
[CRITICAL] llm_url: URL must start with http:// or https://
```

**Solution:**

```bash
# Wrong
LLM_URL=localhost:11434

# Correct
LLM_URL=http://localhost:11434
```

### Connection Refused Errors

**Symptom:** `ConnectionRefusedError: [Errno 111] Connection refused`

**Possible causes:**

1. **Service not running**

   ```bash
   # Check what's running
   docker ps

   # Start services
   just dev-up
   ```

2. **Wrong URL in .env**

   ```bash
   # Check configuration
   grep OPENSEARCH_HOST .env

   # Should be localhost for local dev
   OPENSEARCH_HOST=http://localhost:9200
   ```

3. **Service not ready yet**
   ```bash
   # Wait for services to be healthy
   just preflight-dev
   ```

### direnv Not Loading Environment

**Symptom:** Virtual environment doesn't activate, aliases not available

**Solution:**

```bash
# Check direnv is installed
direnv version

# Check shell hook is configured
grep direnv ~/.bashrc  # or ~/.zshrc

# Add hook if missing
echo 'eval "$(direnv hook bash)"' >> ~/.bashrc
source ~/.bashrc

# Allow direnv in this directory
direnv allow
```

**Symptom:** "direnv: error .envrc is blocked"

**Solution:**

```bash
# direnv blocks .envrc for security
# Review .envrc contents, then allow
cat .envrc
direnv allow
```

### Environment Variables Not Loading

**Symptom:** Variables from `.env` aren't available in shell

**Cause:** direnv loads `.env` automatically, but only when configured to do so in `.envrc`

**Check `.envrc` contains:**

```bash
dotenv_if_exists
```

**Manual reload:**

```bash
# Force direnv to reload
direnv reload
```

### Service DNS Resolution Failures

**Symptom:** `getaddrinfo failed: Name or service not known` for service names

**Cause:** Application running on host trying to use Docker service names

**Solution:**

```bash
# Use localhost for local development
OPENSEARCH_HOST=http://localhost:9200

# Or use host.docker.internal (Docker Desktop only)
OPENSEARCH_HOST=http://host.docker.internal:9200
```

---

## Security Best Practices

### Never Commit Secrets

**Always gitignored:**

- `.env` - Local configuration with potential secrets
- `secrets.tfvars` - OpenTofu secrets for deployment
- Any file with credentials, API keys, or passwords

**Check before committing:**

```bash
# Verify .env is not tracked
git status

# Double-check .gitignore
grep -E "^\.env$|secrets\.tfvars" .gitignore
```

### Use Secrets Management for Production

**Don't:**

```bash
# .env - NEVER do this in production
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
OPENSEARCH_PASSWORD=my-super-secret-password
```

**Do:**

```bash
# .env - Reference secrets manager
AWS_SECRET_ACCESS_KEY=${AWS_SECRET}  # Retrieved from secrets manager
OPENSEARCH_PASSWORD=${OPENSEARCH_PASS}  # Retrieved at runtime

# Or use IAM roles (no credentials needed)
# Application uses instance/pod IAM role automatically
```

**Best practices:**

- Use AWS Secrets Manager or DigitalOcean App Platform secrets
- Use IAM roles instead of access keys when possible
- Rotate credentials regularly
- Use different credentials per environment (dev/staging/prod)

### Restrict `.env` Permissions

```bash
# Make .env readable only by owner
chmod 600 .env

# Verify permissions
ls -la .env
# Should show: -rw------- (600)
```

### Use Environment-Specific Secrets

**Don't share secrets across environments:**

```bash
# deployment/tofu/environments/single-node/secrets.tfvars
do_token = "dop_v1_staging_token"
opensearch_password = "staging-password"

# deployment/tofu/environments/production/secrets.tfvars
do_token = "dop_v1_production_token"
opensearch_password = "production-password-different"
```

---

## Verification Checklist

Before starting development or deployment, verify:

### Local Development

- [ ] direnv installed and shell hook configured
- [ ] `direnv allow` has been run in project directory
- [ ] `.env` file exists (copied from `.env.example`)
- [ ] Virtual environment activates automatically when entering directory
- [ ] `dev` alias available (test with `type dev`)
- [ ] Services start with `just dev-up` or `dev`
- [ ] Preflight checks pass: `just preflight-dev`

### Deployment Environment

- [ ] Environment-specific `.envrc` exists and allowed
- [ ] `secrets.tfvars` created with deployment credentials (not committed)
- [ ] OpenTofu initialized: `tofu init`
- [ ] Can preview changes: `tf-plan` alias works
- [ ] Network connectivity verified to cloud provider
- [ ] Secrets stored in secrets manager (not in files)

---

## Next Steps

After configuring your environment:

1. **Start developing** - See [Getting Started Guide](../learn/getting-started.md)
2. **Run tutorials** - Try [Transform](../learn/transform/), [Ask](../learn/ask/), or [Assurance](../learn/assurance/) tutorials
3. **Deploy to cloud** - Follow [Single-Node Deployment Guide](../../deployment/tofu/environments/single-node/README.md)
4. **Set up monitoring** - Configure observability with OpenTelemetry and VictoriaMetrics

---

## See Also

- [Installation Guide](index.md) - Step-by-step setup from scratch
- [QUICKSTART.md](../../QUICKSTART.md) - Condensed quick reference
- [Getting Started](../learn/getting-started.md) - First steps with Certus TAP
- [Deployment Guides](../../deployment/) - Production deployment options
- [justfile Reference](../../justfile) - Available commands and workflows
