# Certus Deployment Guide

This directory contains all deployment configurations for Certus across multiple environments.

## Directory Structure

```
deployment/
├── shared/                           # Shared across all deployments
│   ├── systemd/                      # systemd service units
│   ├── dockerfiles/                  # Container definitions
│   └── scripts/                      # Deployment scripts
│
└── tofu/                             # OpenTofu infrastructure as code
    └── environments/
        └── single-node/              # Single DigitalOcean droplet
            ├── .envrc                # Auto-loads deployment context
            ├── .envrc.example        # Template
            ├── main.tf               # Infrastructure definition
            ├── variables.tf          # Configuration variables
            ├── outputs.tf            # Deployment outputs
            ├── cloud-init.yaml       # Bootstrap script
            ├── secrets.tfvars        # Secrets (gitignored)
            ├── secrets.tfvars.example # Template
            └── README.md             # Deployment docs
```

## Available Environments

### 1. Local Development
- **Location:** Project root
- **Technology:** Docker Compose
- **Command:** `just up`
- **Use Case:** Development, testing, iteration

### 2. Single-Node DigitalOcean
- **Location:** `deployment/tofu/environments/single-node/`
- **Technology:** OpenTofu + systemd + Podman + Tailscale
- **Command:** `tofu apply -var-file=secrets.tfvars`
- **Use Case:** Staging, small production, cost-effective testing

## Getting Started

### Prerequisites

1. **Install direnv**
   ```bash
   brew install direnv
   echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
   source ~/.zshrc
   ```

2. **Install OpenTofu** (for cloud deployments)
   ```bash
   brew install opentofu
   ```

3. **Install uv** (for Python)
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

### Local Development Setup

1. Navigate to project root:
   ```bash
   cd ~/src/certus/certus-TAP
   ```

2. Allow direnv (first time only):
   ```bash
   direnv allow
   ```

3. Install dependencies:
   ```bash
   uv sync
   ```

4. Start development environment:
   ```bash
   just up
   ```

5. Verify services:
   ```bash
   just preflight
   ```

### Single-Node Deployment Setup

1. Navigate to single-node environment:
   ```bash
   cd deployment/tofu/environments/single-node
   ```

2. Allow direnv (first time only):
   ```bash
   direnv allow
   ```

3. Generate secrets:
   ```bash
   ../../shared/scripts/generate-secrets.sh
   ```

4. Edit secrets file:
   ```bash
   # Add your Tailscale auth key
   vim secrets.tfvars
   ```

5. Initialize OpenTofu:
   ```bash
   tf-init
   ```

6. Review plan:
   ```bash
   tf-plan
   ```

7. Deploy:
   ```bash
   tf-apply
   ```

8. Get connection info:
   ```bash
   tf-output
   ```

## Environment Variables with direnv

### How It Works

When you `cd` into a directory with a `.envrc` file, direnv automatically:
- Loads environment variables
- Activates Python virtual environment
- Sets up helpful aliases
- Shows you relevant information

### Local Environment

When in project root (`~/src/certus/certus-TAP`):
- `CERTUS_ENV=local`
- Python virtualenv activated
- Local service URLs set
- Shell prints quick-start commands (`just up/preflight/down`)

### Deployment Environment

When in `deployment/tofu/environments/single-node/`:
- `CERTUS_ENV=staging`
- OpenTofu variables prefixed with `TF_VAR_*`
- Aliases like `tf-plan`, `tf-apply`, `ssh-droplet`
- Deployment context clearly indicated

## Shared Resources

### systemd Services

Located in `shared/systemd/`, used by all droplet deployments:

- `certus-assurance-api.service` - Security scanning API
- `certus-transform-api.service` - Data transformation API
- `certus-ask-api.service` - RAG query API
- `certus-trust-api.service` - Attestation API
- `certus-integrity-api.service` - Guardrails API
- `certus-worker@.service` - Background workers (templated)
- `certus-postgres.service` - PostgreSQL database
- `certus-neo4j.service` - Neo4j graph database
- `certus-redis.service` - Redis cache
- `certus-opensearch.service` - OpenSearch

### Dockerfiles

Located in `shared/dockerfiles/`, built on droplets via cloud-init:

- `Dockerfile.assurance`
- `Dockerfile.transform`
- `Dockerfile.ask`
- `Dockerfile.trust`
- `Dockerfile.integrity`

### Scripts

Located in `shared/scripts/`:

- `generate-secrets.sh` - Generate secure random secrets
- `deploy-to-digitalocean.sh` - Legacy manual deployment script

## Secrets Management

### What's Gitignored

- `.env` (local environment file)
- `secrets.tfvars` (OpenTofu secrets)
- `.terraform/` (OpenTofu state)
- All `*.tfvars` except `*.tfvars.example`

### What's Committed

- `.envrc.example` (templates)
- `secrets.tfvars.example` (templates)
- Configuration files (no secrets)

### Secret Storage Options

**Simple (current):**
```bash
# secrets.tfvars (gitignored)
tailscale_auth_key = "tskey-auth-xxxxx"
db_password = "generated-secret"
```

**Enhanced (optional):**
```bash
# .envrc loads from 1Password
export TF_VAR_db_password=$(op read "op://certus/staging/db-password")
export DIGITALOCEAN_TOKEN=$(op read "op://certus/staging/do-token")
```

## Common Workflows

### Daily Local Development

```bash
cd ~/src/certus/certus-TAP
# direnv auto-loads local environment

dev                    # Start all services
just test-fast         # Run tests
dev-logs               # View logs
dev-stop               # Stop services
```

### Deploy to Staging

```bash
cd deployment/tofu/environments/single-node
# direnv auto-loads staging environment

tf-plan                # Review changes
tf-apply               # Deploy
ssh-droplet            # SSH to droplet
```

### Update Deployment

```bash
cd deployment/tofu/environments/single-node

# Update code on droplet
ssh-droplet "cd /opt/certus/certus-TAP && git pull"

# Rebuild containers
ssh-droplet "systemctl restart certus-assurance-api"

# Or recreate entire droplet
tf-apply -replace=digitalocean_droplet.certus
```

### Destroy Staging

```bash
cd deployment/tofu/environments/single-node
tf-destroy             # Type 'yes' to confirm
```

## Troubleshooting

### direnv not loading

```bash
# Check if direnv is installed
which direnv

# Check if hook is in shell config
grep direnv ~/.zshrc

# Manually allow
direnv allow
```

### OpenTofu state issues

```bash
# Reinitialize
tf-init -reconfigure

# View current state
tf-state

# Import existing resource
tofu import digitalocean_droplet.certus <droplet-id>
```

### Service not starting on droplet

```bash
# SSH to droplet
ssh-droplet

# Check service status
systemctl status certus-assurance-api

# View logs
journalctl -u certus-assurance-api -f

# Check cloud-init progress
tail -f /var/log/cloud-init-output.log
```

## Next Steps

1. **Local Development:** Follow [Local Development Guide](../../docs/deployment/local-development.md)
2. **Single-Node Deploy:** Follow [Single-Node Deployment Guide](tofu/environments/single-node/README.md)
3. **CI/CD Setup:** Configure GitHub Actions with self-hosted runner

## Additional Resources

- [OpenTofu Documentation](https://opentofu.org/docs/)
- [Tailscale Documentation](https://tailscale.com/kb/)
- [systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [direnv Documentation](https://direnv.net/)
