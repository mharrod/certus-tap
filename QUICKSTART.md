# Certus Quick Start Guide

Get up and running with Certus in under 10 minutes.

## Choose Your Environment

### 🚀 Local Development (Recommended for First Time)

**What you get:** All services running on your machine

**Prerequisites:**

- Docker Desktop
- 10 minutes

**Steps:**

```bash
# 1. Install direnv
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc

# 2. Clone and setup
git clone https://github.com/mharrod/certus-tap.git certus-TAP
cd certus-TAP
direnv allow

# 3. Install dependencies
brew install just
curl -LsSf https://astral.sh/uv/install.sh | sh
uv sync

# 4. Start services
just dev-up

# 5. Verify
just preflight-dev
```

**Done!** Services running at:

- Ask API: http://localhost:8000
- Assurance API: http://localhost:8056
- Trust API: http://localhost:8057

**Next:** Try the tutorials in `docs/learn/`

---

### ☁️ Single-Node Cloud Deployment

**What you get:** -Deployment on DigitalOcean

**Prerequisites:**

- DigitalOcean account ($48/month or ~$11 if you run 8hrs/day)
- Tailscale account (free)
- 15 minutes

**Steps:**

```bash
# 1. Install tools
brew install direnv opentofu
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc

# 2. Navigate to deployment
cd ~/src/certus/certus-TAP/deployment/tofu/environments/single-node
direnv allow

# 3. Generate secrets
../../shared/scripts/generate-secrets.sh

# 4. Edit secrets.tfvars
# Add your Tailscale auth key from: https://login.tailscale.com/admin/settings/keys
vim secrets.tfvars

# 5. Set DigitalOcean token
export DIGITALOCEAN_TOKEN="dop_v1_xxxxx"

# 6. Deploy
tf-init
tf-plan
tf-apply  # Type 'yes'

# Wait 10-15 minutes for deployment...

# 7. Get connection info
tf-output
```

**Done!** Install Tailscale on your laptop, then:

```bash
ssh root@certus-staging
curl http://certus-staging:8056/health
```

**Next:** Run security scans from anywhere via Tailscale

---

## What's the Difference?

| Feature              | Local             | Single-Node Cloud      |
| -------------------- | ----------------- | ---------------------- |
| **Cost**             | Free              | ~$11/month (8hrs/day)  |
| **Setup Time**       | 10 minutes        | 15 minutes             |
| **Use Case**         | Development       | Staging/Production     |
| **Access**           | Localhost only    | Anywhere via Tailscale |
| **Performance**      | Depends on laptop | 4 vCPU, 8GB RAM        |
| **Hot Reload**       | ✅ Yes            | ❌ No                  |
| **Production-Ready** | ❌ No             | ✅ Yes                 |

## direnv Quick Reference

Once you have direnv installed, it automatically loads environment variables when you `cd`:

```bash
# Local development
cd ~/src/certus/certus-TAP
# Loads: CERTUS_ENV=local, Python virtualenv, local URLs
# Aliases: dev, dev-stop, dev-logs

# Cloud deployment
cd deployment/tofu/environments/single-node
# Loads: CERTUS_ENV=staging, OpenTofu vars
# Aliases: tf-plan, tf-apply, ssh-droplet
```

**First time in directory:** Run `direnv allow`

## Common Commands

### Local Development

```bash
just up              # Start all services
just down            # Stop all services
just test-fast           # Run tests
just test-security-smoke # Quick security scan
dev-logs                 # View logs (via direnv alias)
```

### Cloud Deployment

```bash
tf-plan                  # Preview changes
tf-apply                 # Deploy
tf-destroy               # Remove deployment
ssh-droplet              # SSH to server (via direnv alias)
get-ip                   # Get droplet IP (via direnv alias)
```

## Troubleshooting

### direnv not working

```bash
# Check installation
which direnv

# Add to shell config
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc

# Manually allow
direnv allow
```

### Docker services won't start

```bash
# Check Docker is running
docker ps

# Clean slate
just dev-down
docker system prune -a
just dev-up
```

### OpenTofu deployment fails

```bash
# Check token is set
echo $DIGITALOCEAN_TOKEN

# Reinitialize
tf-init -reconfigure

# View detailed logs
tf-apply -auto-approve -verbose
```

## Next Steps

**After Local Setup:**

1. ✅ Services running
2. Follow tutorials: `docs/learn/ask/`, `docs/learn/assurance/`, etc.
3. Make changes, tests run automatically
4. Ready to deploy? Set up cloud environment

**After Cloud Setup:**

1. ✅ Deployment complete
2. Install Tailscale on all your devices
3. Test from anywhere: `curl http://certus-staging:8056/health`
4. Set up automated spin-up/down for cost savings
5. Configure CI/CD with self-hosted runner

**Welcome to Certus!** 🎉
