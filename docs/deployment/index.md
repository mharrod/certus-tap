# Deployment Guide

Choose your deployment method based on your needs and environment.

---

## Automated Deployment (Recommended)

### OpenTofu + DigitalOcean + Tailscale

Complete automated deployment of the entire Certus TAP stack with infrastructure-as-code.

📖 **[OpenTofu Deployment Guide](../../deployment/tofu/README.md)**

**What you get:**
- Single DigitalOcean droplet with all services
- All 5 APIs (Assurance, Transform, Ask, Trust, Integrity)
- Security scan workers with Dagger
- All databases (PostgreSQL, Neo4j, Redis, OpenSearch)
- Tailscale private mesh networking
- SSH with Google Authenticator 2FA
- Optional GitHub Actions self-hosted runner

**One-command deployment:**
```bash
cd deployment/tofu
tofu apply -var-file=secrets.tfvars
```

**One-command teardown:**
```bash
tofu destroy -var-file=secrets.tfvars
```

**Cost:** ~$11/month (running 8 hours/day, 5 days/week)

**Best for:**
- ✅ Testing and staging environments
- ✅ Frequent spin up/down workflows
- ✅ Development
- ✅ Learning the platform
- ✅ Cost optimization

**Time to deploy:** 15 minutes (mostly automated)

---

## Manual Deployment

### Step-by-Step DigitalOcean Setup

Detailed manual installation guide for understanding how everything works.

📖 **[Manual Deployment Guide](manual.md)**

**What you'll learn:**
- How to set up Podman and systemd services
- Container orchestration details
- Service dependencies and configuration
- Networking and firewall setup
- Troubleshooting and maintenance

**Best for:**
- ✅ Learning how the stack works
- ✅ Custom configurations beyond automation
- ✅ Troubleshooting deployments
- ✅ Understanding systemd service management
- ✅ Building your own automation

**Time to deploy:** 1-2 hours (hands-on)

---

## Production Deployment

### Multi-Droplet High-Availability Setup

Coming soon: Production-ready architecture with:

- Separate droplets for APIs, workers, and databases
- DigitalOcean managed databases
- Load balancing
- High availability
- Advanced monitoring and alerting
- Automated backups
- Multi-region support

**Status:** Planned for future release

---

## Comparison

| Feature | Automated (OpenTofu) | Manual | Production |
|---------|---------------------|--------|------------|
| **Setup Time** | 15 min | 1-2 hours | TBD |
| **Skill Level** | Beginner | Intermediate | Advanced |
| **Cost (8hr/day)** | ~$11/mo | ~$11/mo | ~$80+/mo |
| **Infrastructure** | Single droplet | Single droplet | Multi-droplet |
| **Best For** | Testing/Staging | Learning | Production |
| **Teardown** | One command | Manual | Managed |
| **Reproducible** | ✅ Yes | ❌ No | ✅ Yes |

---

## Quick Decision Guide

**Choose Automated OpenTofu if:**
- You want to get started quickly
- You'll spin up/down frequently
- You're testing or developing
- You want reproducible infrastructure

**Choose Manual if:**
- You want to understand the internals
- You need custom configurations
- You're learning systemd/Podman
- You're building your own automation

**Wait for Production if:**
- You need high availability
- You're deploying to production
- You need managed databases
- You require SLAs and uptime guarantees

---

## Prerequisites (All Methods)

Regardless of deployment method, you'll need:

1. **DigitalOcean Account**
   - Sign up at https://digitalocean.com
   - Add payment method
   - Generate API token (for automated deployment)

2. **Tailscale Account** (Automated deployment)
   - Sign up at https://tailscale.com (free tier)
   - Generate auth key

3. **SSH Keys**
   - Generate if needed: `ssh-keygen -t ed25519`

4. **Local Tools**
   - OpenTofu/Terraform (automated)
   - `doctl` CLI (optional)
   - SSH client

---

## Next Steps

1. **Choose your deployment method** above
2. **Follow the guide** for your chosen method
3. **Verify deployment** by running health checks
4. **Explore tutorials** in the [Learn section](../learn/index.md)
5. **Read architecture docs** in the [Reference section](../reference/index.md)

---

## Support

- **Deployment Issues:** See troubleshooting sections in each guide
- **General Questions:** Check the [FAQ](../reference/troubleshooting/index.md)
- **Bug Reports:** https://github.com/mharrod/certus_doc_ops/issues
