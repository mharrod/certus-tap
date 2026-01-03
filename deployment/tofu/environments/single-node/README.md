# Single-Node DigitalOcean Deployment

Deploy the entire Certus stack to a single DigitalOcean droplet using OpenTofu, systemd, Podman, and Tailscale.

## Overview

This deployment creates:

- One DigitalOcean droplet (4 vCPU, 8GB RAM)
- All Certus services running via systemd + Podman
- Tailscale mesh networking for secure access
- Automatic SSL/TLS via Tailscale
- SSH with 2FA (Google Authenticator)
- Optional GitHub Actions self-hosted runner

**Cost:** ~$11/month (running 8hrs/day, 5 days/week on s-4vcpu-8gb droplet)

## Prerequisites

### 1. Install OpenTofu

```bash
# macOS
brew install opentofu

# Linux
snap install --classic opentofu

# Verify
tofu version
```

### 2. DigitalOcean API Token

1. Go to: https://cloud.digitalocean.com/account/api/tokens
2. Click "Generate New Token"
3. Name it "Certus Deployment"
4. Copy the token (starts with `dop_v1_`)

### 3. Tailscale Account

1. Sign up at: https://tailscale.com
2. Go to: https://login.tailscale.com/admin/settings/keys
3. Generate auth key:
   - Check "Reusable"
   - Set expiration (90 days recommended)
   - Copy the key (starts with `tskey-auth-`)

### 4. SSH Key

```bash
# Generate if you don't have one
ssh-keygen -t ed25519 -C "your-email@example.com"

# Location: ~/.ssh/id_ed25519.pub (default)
```

### 5. Install direnv

```bash
brew install direnv
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc
```

## Quick Start

### 1. Navigate to Environment

```bash
cd ~/src/certus/certus-TAP/deployment/tofu/environments/single-node
```

### 2. Allow direnv (First Time)

```bash
direnv allow
```

You should see:

```
🚀 Certus Single-Node Deployment Environment
   Environment: staging
   Deployment Type: single-node
   Region: nyc3
   Droplet Size: s-4vcpu-8gb
```

### 3. Generate Secrets

```bash
../../shared/scripts/generate-secrets.sh
```

This creates `secrets.tfvars` with random passwords.

### 4. Edit Secrets

```bash
vim secrets.tfvars
```

**Add your Tailscale auth key:**

```hcl
tailscale_auth_key = "tskey-auth-xxxxx"
```

**Optional: Add GitHub runner token:**

```hcl
github_runner_token = "AAAA..."
```

Everything else is auto-generated.

### 5. Set DigitalOcean Token

**Option A: Environment variable (temporary)**

```bash
export DIGITALOCEAN_TOKEN="dop_v1_xxxxx"
```

**Option B: Add to .envrc (persistent)**

```bash
# Edit .envrc (at the top of this directory)
vim .envrc

# Add line:
export DIGITALOCEAN_TOKEN="dop_v1_xxxxx"

# Reload
direnv allow
```

**Option C: Use 1Password (most secure)**

```bash
# Edit .envrc
vim .envrc

# Change the line to:
export DIGITALOCEAN_TOKEN=$(op read "op://certus/staging/do-token")

# Reload
direnv allow
```

### 6. Initialize OpenTofu

```bash
tf-init
```

### 7. Review Plan

```bash
tf-plan
```

This shows what will be created (droplet, firewall, etc).

### 8. Deploy

```bash
tf-apply
```

Type `yes` when prompted. Deployment takes **10-15 minutes**.

### 9. Get Access Information

```bash
tf-output
```

Shows:

- Droplet IP address
- Tailscale hostname
- SSH commands
- API URLs
- API key (save this!)

## Accessing Your Deployment

### Via Tailscale (Recommended)

**1. Install Tailscale on your laptop:**

```bash
# macOS
brew install tailscale
sudo tailscale up

# Linux
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up
```

**2. Access services:**

```bash
# SSH (no IP needed!)
ssh root@certus-staging

# Test API
curl http://certus-staging:8056/health

# With authentication
export CERTUS_API_KEY=$(tf-output -raw api_key)
curl -H "Authorization: Bearer $CERTUS_API_KEY" \
  http://certus-staging:8056/v1/security-scans
```

### Via Public IP (Emergency)

**First-time setup (2FA):**

```bash
# Get droplet IP
get-ip

# SSH to droplet
ssh root@$(get-ip)

# View 2FA QR code
cat /root/2fa-qr-code.txt

# Scan with Google Authenticator app on your phone
```

**Subsequent logins:**

```bash
ssh root@$(get-ip)
# Enter: SSH key passphrase (if set)
# Enter: 6-digit code from Google Authenticator
```

## Useful Commands

All these aliases are set by direnv when you're in this directory:

### OpenTofu Operations

```bash
tf-init          # Initialize OpenTofu
tf-plan          # Preview changes
tf-apply         # Deploy changes
tf-destroy       # Destroy infrastructure
tf-output        # Show outputs
tf-state         # List state resources
```

### Deployment Shortcuts

```bash
deploy           # Same as tf-apply
deploy-plan      # Same as tf-plan
get-ip           # Get droplet IP
ssh-droplet      # SSH to droplet
```

### Full Commands (Without Aliases)

```bash
tofu init
tofu plan -var-file=secrets.tfvars
tofu apply -var-file=secrets.tfvars
tofu destroy -var-file=secrets.tfvars
tofu output
ssh root@$(tofu output -raw droplet_ip)
```

## Managing Services

### Check Service Status

```bash
# SSH to droplet
ssh-droplet

# Check all services
systemctl status 'certus-*'

# Check specific service
systemctl status certus-assurance-api

# Run health check
certus-health-check
```

### View Logs

```bash
# All services
journalctl -u 'certus-*' -f

# Specific service
journalctl -u certus-assurance-api -f

# Last 100 lines
journalctl -u certus-assurance-api -n 100
```

### Restart Services

```bash
# Restart API
systemctl restart certus-assurance-api

# Restart all workers
systemctl restart 'certus-worker@*'

# Restart database
systemctl restart certus-postgres
```

## Updating Deployment

### Update Application Code

```bash
# SSH to droplet
ssh-droplet

# Pull latest code
cd /opt/certus/certus-TAP
git pull

# Rebuild container
podman build -t localhost/certus-assurance:latest \
  -f deployment/shared/dockerfiles/Dockerfile.assurance .

# Restart service
systemctl restart certus-assurance-api
```

### Update Infrastructure

```bash
# In single-node directory
cd deployment/tofu/environments/single-node

# Edit configuration
vim main.tf

# Review changes
tf-plan

# Apply changes
tf-apply
```

### Full Redeploy (Cleanest)

```bash
# Destroy existing
tf-destroy

# Recreate from scratch
tf-apply
```

## Configuration

### Environment Variables

Edit `secrets.tfvars` to customize:

```hcl
# Environment name (affects hostname)
environment = "staging"  # or "prod"

# DigitalOcean region
region = "nyc3"  # or "sfo3", "lon1", "fra1"

# Droplet size
droplet_size = "s-4vcpu-8gb"

# Number of scan workers
worker_count = 2

# GitHub configuration (optional)
github_repo = "your-org/your-repo"
github_runner_token = "AAAA..."

# Secrets (auto-generated)
db_password = "..."
tailscale_auth_key = "tskey-auth-..."
```

### Droplet Sizes

| Size         | vCPUs | RAM  | Cost/Month | Cost (8hrs/day) |
| ------------ | ----- | ---- | ---------- | --------------- |
| s-2vcpu-4gb  | 2     | 4GB  | $24        | ~$6             |
| s-4vcpu-8gb  | 4     | 8GB  | $48        | ~$11            |
| s-8vcpu-16gb | 8     | 16GB | $96        | ~$22            |

### Regions

Common DigitalOcean regions:

- `nyc3` - New York
- `sfo3` - San Francisco
- `lon1` - London
- `fra1` - Frankfurt
- `sgp1` - Singapore
- `tor1` - Toronto

## Cost Management

### Automated Spin Up/Down

**Using cron on your laptop:**

```bash
# Edit crontab
crontab -e

# Add lines:
# Spin up weekdays at 9 AM
0 9 * * 1-5 cd /path/to/certus/deployment/tofu/environments/single-node && tofu apply -var-file=secrets.tfvars -auto-approve

# Tear down weekdays at 6 PM
0 18 * * 1-5 cd /path/to/certus/deployment/tofu/environments/single-node && tofu destroy -var-file=secrets.tfvars -auto-approve
```

### Manual Management

```bash
# Morning
cd deployment/tofu/environments/single-node
tf-apply

# Work all day...

# Evening
tf-destroy
```

## Troubleshooting

### Deployment Fails

```bash
# Check cloud-init progress
ssh-droplet
tail -f /var/log/cloud-init-output.log

# Check status
cloud-init status
```

### Services Not Starting

```bash
ssh-droplet

# Check service
systemctl status certus-assurance-api

# View errors
journalctl -u certus-assurance-api -n 100

# Common issues:
# - Container image not built: check cloud-init logs
# - Database not ready: wait a minute, restart service
# - Environment variables: check /opt/certus/.env
```

### Tailscale Not Working

```bash
ssh-droplet

# Check status
tailscale status

# Rejoin network
tailscale up --authkey=YOUR_KEY --hostname=certus-staging --force-reauth
```

### Can't SSH (2FA Issues)

```bash
# Use DigitalOcean console (emergency access)
# Or reset 2FA:
ssh root@$(get-ip) "google-authenticator --time-based --force"
```

### State Lock Issues

```bash
# Force unlock (use carefully)
tofu force-unlock <lock-id>

# Or delete lock file and reinit
rm -rf .terraform
tf-init
```

## Security Best Practices

1. **Rotate secrets regularly**

   ```bash
   ../../shared/scripts/generate-secrets.sh
   # Edit secrets.tfvars
   tf-apply
   ```

2. **Keep 2FA enabled**
   - Don't disable Google Authenticator
   - Keep backup codes safe

3. **Use Tailscale**
   - Don't expose services to public internet
   - Only SSH via Tailscale when possible

4. **Review firewall rules**

   ```bash
   ssh-droplet
   ufw status
   ```

5. **Monitor access logs**
   ```bash
   ssh-droplet
   journalctl -u sshd | grep -i failed
   ```

## GitHub Actions Integration

### Setup

1. Get runner token:
   - Go to: `https://github.com/YOUR_ORG/YOUR_REPO/settings/actions/runners/new`
   - Copy token

2. Add to secrets.tfvars:

   ```hcl
   github_runner_token = "AAAA..."
   ```

3. Deploy:
   ```bash
   tf-apply
   ```

### Using the Runner

```yaml
# .github/workflows/security-scan.yml
jobs:
  scan:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - name: Security Scan
        run: |
          security-scan --runtime dagger --profile smoke
```

## Cleanup

### Temporary Teardown

```bash
# Remove droplet, keep configuration
tf-destroy
```

### Complete Removal

```bash
# Remove everything including state
tf-destroy
rm -rf .terraform terraform.tfstate*
```

## Next Steps

1. ✅ Deployment successful
2. Install Tailscale on all devices
3. Test security scans
4. Set up automated spin up/down
5. Document workflows for your team
6. Plan multi-node architecture when ready

## Support

- **Documentation:** [Main Deployment README](../../README.md)
- **Issues:** https://github.com/mharrod/certus_doc_ops/issues
- **Tailscale Help:** https://tailscale.com/kb/
- **DigitalOcean Help:** https://docs.digitalocean.com/
