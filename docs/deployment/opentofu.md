# OpenTofu Automated Deployment

Complete automated deployment of the entire Certus TAP stack with infrastructure-as-code.

---

## 📖 Full Guide

The complete OpenTofu deployment documentation is located in the repository:

**[deployment/tofu/README.md](../../deployment/tofu/README.md)**

---

## Quick Start

```bash
# 1. Generate secrets
cd deployment
./scripts/generate-secrets.sh

# 2. Edit secrets file (add Tailscale auth key)
nano tofu/secrets.tfvars

# 3. Set DigitalOcean token
export DIGITALOCEAN_TOKEN="dop_v1_xxxxx"

# 4. Deploy
cd tofu
tofu init
tofu apply -var-file=secrets.tfvars
```

**Deployment time:** 10-15 minutes

---

## What You Get

Single DigitalOcean droplet with:

- ✅ All 5 Certus APIs (ports 8056-8060)
- ✅ Security scan workers with Dagger
- ✅ All databases (PostgreSQL, Neo4j, Redis, OpenSearch)
- ✅ Tailscale private mesh networking
- ✅ SSH with Google Authenticator 2FA
- ✅ Optional GitHub Actions self-hosted runner
- ✅ systemd service orchestration
- ✅ Podman container runtime

---

## Cost

**~$11/month** when running 8 hours/day, 5 days/week

- Droplet: s-4vcpu-8gb at $0.071/hour
- Tailscale: Free (personal tier)
- Total: 160 hours × $0.071 = $11.36/month

vs $48/month running 24/7

---

## Access

### Via Tailscale (Primary)

```bash
# Install Tailscale on your laptop
brew install tailscale  # macOS
sudo tailscale up

# Access services
ssh root@certus-staging
curl http://certus-staging:8056/health
```

### Emergency SSH (Public IP + 2FA)

```bash
# Get droplet IP
DROPLET_IP=$(cd tofu && tofu output -raw droplet_ip)

# SSH with 2FA
ssh root@$DROPLET_IP
# Prompts for SSH key + Google Authenticator code
```

---

## Daily Workflow

**Morning:**
```bash
cd deployment/tofu
tofu apply -var-file=secrets.tfvars
# Wait 10-15 min, get coffee ☕
```

**During day:**
```bash
# Access from anywhere via Tailscale
curl http://certus-staging:8056/v1/security-scans
```

**Evening:**
```bash
cd deployment/tofu
tofu destroy -var-file=secrets.tfvars
# Billing stops
```

---

## Prerequisites

1. **OpenTofu installed**
   ```bash
   brew install opentofu
   ```

2. **DigitalOcean API token**
   - Get from: https://cloud.digitalocean.com/account/api/tokens

3. **Tailscale account** (free)
   - Sign up: https://tailscale.com
   - Get auth key: https://login.tailscale.com/admin/settings/keys

4. **SSH keys**
   ```bash
   ssh-keygen -t ed25519
   ```

---

## Next Steps

1. **Read the full guide**: [deployment/tofu/README.md](../../deployment/tofu/README.md)
2. **Configure secrets**: See secrets.tfvars.example
3. **Deploy and test**
4. **Explore tutorials**: [Learn section](../learn/index.md)

---

## Support

- **Full documentation**: [deployment/tofu/README.md](../../deployment/tofu/README.md)
- **Troubleshooting**: See README troubleshooting section
- **Issues**: https://github.com/mharrod/certus_doc_ops/issues
