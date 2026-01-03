# Local Development Environment

This guide covers setting up and using the local development environment for Certus.

## Overview

The local environment uses Docker Compose to run all services on your machine. It provides:

- Fast iteration with hot reload
- All services running locally
- Mock implementations for external services
- Isolated from production

## Prerequisites

### Required Tools

1. **Docker Desktop**
   ```bash
   # macOS
   brew install --cask docker

   # Or download from: https://www.docker.com/products/docker-desktop
   ```

2. **direnv**
   ```bash
   brew install direnv
   echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
   source ~/.zshrc
   ```

3. **uv** (Python package manager)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

4. **just** (command runner)
   ```bash
   brew install just
   ```

## Initial Setup

### 1. Clone Repository

```bash
cd ~/src/certus
git clone https://github.com/mharrod/certus_doc_ops.git certus-TAP
cd certus-TAP
```

### 2. Allow direnv

```bash
direnv allow
```

You should see output like:
```
🚀 Certus Local Development Environment
   Environment: local
   Python: Python 3.11.x

   Quick start:
     just dev-up          - Start all services
     just preflight-dev   - Check health
     just dev-down        - Stop all services
```

### 3. Create .env File

```bash
# Copy example
cp .env.example .env

# Edit if needed (defaults usually work)
vim .env
```

### 4. Install Python Dependencies

```bash
uv sync
```

### 5. Start Services

```bash
just dev-up
```

This will start:
- OpenSearch (search engine)
- LocalStack (mock AWS)
- Neo4j (graph database)
- Redis (cache)
- VictoriaMetrics (metrics)
- All Certus APIs (Ask, Trust, Assurance, Transform, Integrity)

### 6. Verify Everything Works

```bash
just preflight-dev
```

## Daily Workflow

### Morning: Start Environment

```bash
cd ~/src/certus/certus-TAP
# direnv auto-loads environment

dev  # Alias for: just dev-up && just preflight-dev
```

### During Development

**Run tests:**
```bash
just test-fast          # Quick tests
just test              # All tests with coverage
just test-assurance    # Specific service
```

**View logs:**
```bash
dev-logs                           # All services
docker compose logs ask-certus-backend -f  # Specific service
```

**Rebuild service:**
```bash
dev-rebuild                        # All services
docker compose build ask-certus-backend  # Specific service
docker compose up -d ask-certus-backend  # Restart it
```

**Check health:**
```bash
curl http://localhost:8000/health  # Ask API
curl http://localhost:8056/health  # Assurance API
curl http://localhost:8057/health  # Trust API
```

### Evening: Stop Services

```bash
dev-stop  # Alias for: just dev-down
```

## Available Services

### APIs

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| Ask | 8000 | http://localhost:8000 | RAG queries |
| Trust | 8057 | http://localhost:8057 | Attestations |
| Assurance | 8056 | http://localhost:8056 | Security scans |
| Transform | 8100 | http://localhost:8100 | Data pipelines |
| Integrity | 8060 | http://localhost:8060 | Guardrails |

### Infrastructure

| Service | Port | URL | Purpose |
|---------|------|-----|---------|
| OpenSearch | 9200 | http://localhost:9200 | Search/indexing |
| Neo4j | 7474, 7687 | http://localhost:7474 | Graph database |
| LocalStack | 4566 | http://localhost:4566 | Mock AWS |
| VictoriaMetrics | 8428 | http://localhost:8428 | Metrics |
| Redis | 6379 | localhost:6379 | Cache |

## Environment Variables

When you're in the project directory, direnv automatically sets:

```bash
export CERTUS_ENV=local
export PYTHONPATH="${PWD}:${PYTHONPATH}"
export OPENSEARCH_HOST=http://localhost:9200
export LOCALSTACK_ENDPOINT=http://localhost:4566
export NEO4J_URI=neo4j://localhost:7687
export VICTORIAMETRICS_URL=http://localhost:8428
# ... and more
```

View all variables:
```bash
printenv | grep CERTUS
```

## Useful Aliases

direnv sets up helpful aliases:

```bash
dev                    # Start services + health check
dev-stop               # Stop all services
dev-logs               # View all logs
dev-rebuild            # Rebuild and restart
```

## Tutorial Environments

For specific tutorials, use minimal stacks:

### Ask Tutorials (Search, RAG)
```bash
just ask-up            # Start Ask stack
just preflight-ask     # Verify
# Work on Ask features
just ask-down          # Stop
```

### Transform Tutorials (Data Pipelines)
```bash
just transform-up
just preflight-transform
# Work on Transform features
just transform-down
```

### Assurance Tutorials (Security Scanning)
```bash
just assurance-up
just preflight-assurance
# Work on Assurance features
just assurance-down
```

### Trust Tutorials (Attestations)
```bash
just trust-up
just preflight-trust
# Work on Trust features
just trust-down
```

## Testing

### Quick Tests (No Docker Required)
```bash
just test-fast
```

### Full Test Suite (Requires Docker)
```bash
just dev-up
just test
```

### Specific Test Categories
```bash
just test-assurance        # Assurance service
just test-services         # Service layer
just test-routers          # API endpoints
just test-dagger-security  # Security module
```

### Security Scans
```bash
just test-security-smoke     # Quick (20 seconds)
just test-security-fast      # Medium (2 minutes)
just test-security-standard  # Full (8 minutes)
```

## Troubleshooting

### Services won't start

**Check Docker:**
```bash
docker ps
docker compose ps
```

**Check logs:**
```bash
dev-logs
```

**Clean slate:**
```bash
just dev-down
docker compose down -v  # Remove volumes
docker system prune -a  # Clean all Docker
just dev-up
```

### direnv not loading

```bash
# Verify installation
which direnv

# Check shell config
cat ~/.zshrc | grep direnv

# Manually allow
direnv allow
```

### Port conflicts

If ports are already in use:

```bash
# Find what's using port 9200
lsof -i :9200

# Kill it or change port in docker-compose.full-dev.yml
```

### Python environment issues

```bash
# Remove virtual environment
rm -rf .venv

# Recreate
uv sync

# Verify
python --version
which python
```

### Database data persists

```bash
# Remove all volumes
just dev-down
docker compose down -v

# Restart fresh
just dev-up
```

## Advanced Usage

### Running Individual Services

```bash
# Start only infrastructure
just infrastructure-up

# Start only Ask service
just service-up ask

# Stop specific service
just service-down ask
```

### Custom Compose Files

```bash
# Use different compose file
docker compose -f certus_ask/deploy/docker-compose.yml up

# Combine multiple
docker compose -f certus_infrastructure/docker-compose.yml \
               -f certus_ask/deploy/docker-compose.yml up
```

### Debug Mode

```bash
# Set in .env
LOG_LEVEL=DEBUG
RELOAD=true

# Restart services
dev-rebuild
```

### Hot Reload

All services run with `--reload` flag by default. Changes to Python files automatically restart the service.

## Next Steps

1. ✅ Local environment running
2. Run through tutorials in `docs/learn/`
3. Make changes and test
4. Ready to deploy? See [Single-Node Deployment](single-node-deployment.md)

## Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [justfile Reference](../../justfile)
- [Contributing Guide](../contributing.md)
