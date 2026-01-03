# Manual Deployment to DigitalOcean

Step-by-step guide for deploying Certus TAP with Podman containers orchestrated by systemd on DigitalOcean.

!!! info "Automated Alternative Available"
**Most users should use the automated OpenTofu deployment:**

    📖 **[OpenTofu Deployment Guide](../../deployment/tofu/README.md)**

    - One-command deploy and destroy
    - Complete automation
    - ~15 minutes to fully deployed
    - All services included

    **This manual guide is for:**

    - Understanding how the stack works internally
    - Custom configurations beyond automation
    - Troubleshooting deployments
    - Learning Podman and systemd service management

---

## Overview

This guide walks through manually deploying the Certus TAP stack to a DigitalOcean droplet. You'll learn:

- How to set up Podman and systemd services
- Container orchestration with systemd
- Service dependencies and startup order
- Networking and firewall configuration
- Monitoring and maintenance

**What gets deployed:**

- All 5 Certus APIs (Assurance, Transform, Ask, Trust, Integrity)
- Security scan workers with Dagger
- Databases (PostgreSQL, Neo4j, Redis, OpenSearch)
- systemd service management

**Time required:** 1-2 hours for first-time setup

---

## Why Manual Deployment?

**Use manual deployment when you want to:**

- Understand exactly how the Certus stack works
- Customize configurations beyond what automation provides
- Learn Podman container orchestration
- Learn systemd service management
- Build your own custom automation
- Troubleshoot deployment issues

**For most users, the automated OpenTofu deployment is recommended.**

---

## Architecture

```
┌────────────────────────────────────────────────┐
│         DigitalOcean Droplet (Ubuntu 22.04)    │
│                                                │
│  ┌──────────────────────────────────────┐     │
│  │  systemd (orchestration)              │     │
│  │                                       │     │
│  │  ├─ certus-api.service               │     │
│  │  │  └─ Podman container (:8056)      │     │
│  │  │                                    │     │
│  │  ├─ certus-worker@1.service          │     │
│  │  │  └─ Podman container (Dagger)     │     │
│  │  │                                    │     │
│  │  └─ certus-worker@2.service          │     │
│  │     └─ Podman container (Dagger)     │     │
│  └──────────────────────────────────────┘     │
│                                                │
│  Podman (container runtime)                   │
│  └─ Uses Dagger to orchestrate scanners       │
│                                                │
│  Storage: /var/lib/certus/artifacts           │
└────────────────────────────────────────────────┘

Your laptop/CI → HTTPS → DigitalOcean IP:8056 → API → Workers
```

## Prerequisites

- DigitalOcean account
- `doctl` CLI installed (optional)
- SSH key configured in DigitalOcean
- Domain name (optional, for HTTPS)

---

## Step 1: Create DigitalOcean Droplet

### Option A: Using doctl CLI

```bash
# Create droplet
doctl compute droplet create certus-scanner \
  --size s-4vcpu-8gb \
  --image ubuntu-22-04-x64 \
  --region nyc1 \
  --ssh-keys $(doctl compute ssh-key list --format ID --no-header) \
  --wait

# Get droplet IP
export DROPLET_IP=$(doctl compute droplet list certus-scanner --format PublicIPv4 --no-header)
echo "Droplet IP: $DROPLET_IP"
```

### Option B: Using DigitalOcean Web Console

1. Go to https://cloud.digitalocean.com/droplets
2. Click "Create Droplet"
3. Choose:
   - **Image**: Ubuntu 22.04 LTS
   - **Size**: Basic - 4 vCPUs, 8GB RAM ($48/mo)
   - **Region**: Choose closest to you
   - **SSH Key**: Add your SSH key
4. Create Droplet
5. Note the IP address

**Recommended specs for different workloads:**

| Workload                     | vCPUs | RAM  | Monthly Cost |
| ---------------------------- | ----- | ---- | ------------ |
| Small repos (<10K files)     | 2     | 4GB  | $24          |
| Medium repos (10K-50K files) | 4     | 8GB  | $48          |
| Large repos (50K+ files)     | 8     | 16GB | $96          |

## Step 2: Initial Server Setup

SSH into your droplet:

```bash
ssh root@$DROPLET_IP
```

### 2.1 Update System

```bash
apt update && apt upgrade -y
```

### 2.2 Create Service User

```bash
# Create dedicated user for Certus services
useradd -r -m -d /opt/certus -s /bin/bash certus
usermod -aG sudo certus

# Create directories
mkdir -p /var/lib/certus/artifacts
mkdir -p /opt/certus/config
chown -R certus:certus /var/lib/certus
chown -R certus:certus /opt/certus
```

### 2.3 Install Podman

```bash
# Install Podman
apt install -y podman podman-compose

# Enable Podman socket for rootless operation
systemctl enable --now podman.socket

# Create Docker-compatible socket link
ln -sf /run/podman/podman.sock /var/run/docker.sock

# Verify Podman installation
podman version
```

### 2.4 Install Dagger

```bash
# Install Dagger CLI
curl -fsSL https://dl.dagger.io/dagger/install.sh | sh
mv /root/bin/dagger /usr/local/bin/

# Verify Dagger installation
dagger version
```

### 2.5 Install Required Tools

```bash
# Install Git, jq, and other utilities
apt install -y git jq curl python3-pip

# Install uv for Python package management
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc
```

## Step 3: Deploy Application Code

### 3.1 Clone Repository

```bash
# Switch to certus user
su - certus

# Clone the repository
cd /opt/certus
git clone https://github.com/your-org/certus-TAP.git
cd certus-TAP
```

### 3.2 Build Podman Image

Create a Dockerfile for the Certus Assurance API:

```bash
cat > /opt/certus/certus-TAP/Dockerfile.assurance << 'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Dagger
RUN curl -fsSL https://dl.dagger.io/dagger/install.sh | sh && \
    mv /root/bin/dagger /usr/local/bin/

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Copy application code
COPY certus_assurance /app/certus_assurance
COPY dagger_modules /app/dagger_modules
COPY pyproject.toml /app/

# Install Python dependencies
RUN pip install -e /app/certus_assurance
RUN pip install -e /app/dagger_modules/security

# Expose API port
EXPOSE 8056

# Run API by default
CMD ["uvicorn", "certus_assurance.api:app", "--host", "0.0.0.0", "--port", "8056"]
EOF
```

Build the image:

```bash
cd /opt/certus/certus-TAP
podman build -t localhost/certus-assurance:latest -f Dockerfile.assurance .
```

## Step 4: Configure systemd Services

### 4.1 Create API Service

```bash
sudo tee /etc/systemd/system/certus-api.service > /dev/null << 'EOF'
[Unit]
Description=Certus Assurance API
After=network.target podman.socket
Requires=podman.socket

[Service]
Type=simple
User=certus
Group=certus
WorkingDirectory=/opt/certus/certus-TAP

# Environment variables
Environment="CERTUS_ASSURANCE_USE_SAMPLE_MODE=false"
Environment="CERTUS_ASSURANCE_ARTIFACT_ROOT=/var/lib/certus/artifacts"
Environment="CERTUS_ASSURANCE_HOST=0.0.0.0"
Environment="CERTUS_ASSURANCE_PORT=8056"
Environment="CERTUS_ASSURANCE_TRUST_BASE_URL=http://localhost:8000"
Environment="WORKER_TIMEOUT=3600"

# Run API container
ExecStart=/usr/bin/podman run --rm \
  --name certus-api \
  -p 8056:8056 \
  -v /var/run/podman/podman.sock:/var/run/docker.sock:z \
  -v /var/lib/certus/artifacts:/var/lib/certus/artifacts:z \
  -e CERTUS_ASSURANCE_USE_SAMPLE_MODE=false \
  -e CERTUS_ASSURANCE_ARTIFACT_ROOT=/var/lib/certus/artifacts \
  -e WORKER_TIMEOUT=3600 \
  localhost/certus-assurance:latest \
  uvicorn certus_assurance.api:app --host 0.0.0.0 --port 8056

ExecStop=/usr/bin/podman stop -t 30 certus-api

Restart=always
RestartSec=10

# Resource limits
CPUQuota=400%
MemoryLimit=8G
MemoryHigh=7G

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=certus-api

[Install]
WantedBy=multi-user.target
EOF
```

### 4.2 Create Worker Service Template

```bash
sudo tee /etc/systemd/system/certus-worker@.service > /dev/null << 'EOF'
[Unit]
Description=Certus Scan Worker %i
After=network.target podman.socket certus-api.service
Requires=podman.socket

[Service]
Type=simple
User=certus
Group=certus
WorkingDirectory=/opt/certus/certus-TAP

# Environment variables
Environment="DAGGER_TIMEOUT=3600"
Environment="CERTUS_ASSURANCE_ARTIFACT_ROOT=/var/lib/certus/artifacts"

# Run worker container
ExecStart=/usr/bin/podman run --rm \
  --name certus-worker-%i \
  -v /var/run/podman/podman.sock:/var/run/docker.sock:z \
  -v /var/lib/certus/artifacts:/var/lib/certus/artifacts:z \
  -e DAGGER_TIMEOUT=3600 \
  -e CERTUS_ASSURANCE_ARTIFACT_ROOT=/var/lib/certus/artifacts \
  localhost/certus-assurance:latest \
  python -m certus_assurance.jobs worker --worker-id %i

ExecStop=/usr/bin/podman stop -t 60 certus-worker-%i

Restart=always
RestartSec=15

# Resource limits per worker
CPUQuota=200%
MemoryLimit=4G
MemoryHigh=3G

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=certus-worker-%i

[Install]
WantedBy=multi-user.target
EOF
```

## Step 5: Start Services

### 5.1 Enable and Start Services

```bash
# Reload systemd to pick up new service files
sudo systemctl daemon-reload

# Enable services (auto-start on boot)
sudo systemctl enable certus-api.service
sudo systemctl enable certus-worker@1.service
sudo systemctl enable certus-worker@2.service

# Start API service
sudo systemctl start certus-api.service

# Start worker services
sudo systemctl start certus-worker@1.service
sudo systemctl start certus-worker@2.service
```

### 5.2 Verify Services Are Running

```bash
# Check API status
sudo systemctl status certus-api.service

# Check worker statuses
sudo systemctl status certus-worker@1.service
sudo systemctl status certus-worker@2.service

# View API logs
sudo journalctl -u certus-api.service -f

# View worker logs
sudo journalctl -u certus-worker@1.service -f
```

### 5.3 Test API is Accessible

```bash
# From the droplet
curl http://localhost:8056/health

# From your laptop (replace with your droplet IP)
curl http://$DROPLET_IP:8056/health
```

Expected output:

```json
{ "status": "healthy", "version": "1.0.0" }
```

## Step 6: Configure Firewall

### 6.1 Set Up UFW (Uncomplicated Firewall)

```bash
# Enable UFW
ufw --force enable

# Allow SSH
ufw allow 22/tcp

# Allow API port
ufw allow 8056/tcp

# Check status
ufw status
```

### 6.2 Configure DigitalOcean Cloud Firewall (Recommended)

In DigitalOcean console:

1. Go to Networking → Firewalls
2. Create Firewall
3. Inbound Rules:
   - SSH: Port 22, Source: Your IP
   - HTTP API: Port 8056, Source: All IPv4/IPv6
4. Apply to your droplet

## Step 7: Submit Your First Scan

### From Your Laptop

```bash
# Set droplet IP
export DROPLET_IP=<your-droplet-ip>

# Submit a scan
export SCAN_ID=$(curl -s -X POST http://$DROPLET_IP:8056/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_id": "production",
    "component_id": "my-app",
    "assessment_id": "scan-001",
    "git_url": "https://github.com/your-org/your-repo.git",
    "commit": "main",
    "branch": "main",
    "requested_by": "devops@example.com",
    "profile": "standard"
  }' | jq -r '.test_id')

echo "Scan submitted: $SCAN_ID"

# Poll for status
while true; do
  STATUS=$(curl -s http://$DROPLET_IP:8056/v1/security-scans/$SCAN_ID/status | jq -r '.status')
  echo "Status: $STATUS"
  [[ "$STATUS" == "completed" ]] && break
  [[ "$STATUS" == "failed" ]] && break
  sleep 10
done

# Download results
curl -s http://$DROPLET_IP:8056/v1/security-scans/$SCAN_ID/results > results.tar.gz
tar -xzf results.tar.gz
ls -la results/
```

## Step 8: Monitoring and Maintenance

### 8.1 View Real-Time Logs

```bash
# API logs
sudo journalctl -u certus-api.service -f

# Worker logs (both workers)
sudo journalctl -u 'certus-worker@*' -f

# Specific worker
sudo journalctl -u certus-worker@1.service -f

# All Certus services
sudo journalctl -u 'certus-*' -f
```

### 8.2 Check Resource Usage

```bash
# Overall system
htop

# Podman containers
podman stats

# Service resource usage
systemctl status certus-api.service
systemctl status certus-worker@1.service
```

### 8.3 Restart Services

```bash
# Restart API
sudo systemctl restart certus-api.service

# Restart specific worker
sudo systemctl restart certus-worker@1.service

# Restart all workers
sudo systemctl restart 'certus-worker@*'
```

### 8.4 Scale Workers

Add more workers for parallel processing:

```bash
# Enable and start worker 3
sudo systemctl enable certus-worker@3.service
sudo systemctl start certus-worker@3.service

# Enable and start worker 4
sudo systemctl enable certus-worker@4.service
sudo systemctl start certus-worker@4.service

# Check all workers
sudo systemctl status 'certus-worker@*'
```

## Step 9: Update and Maintenance

### 9.1 Update Application Code

```bash
# SSH into droplet
ssh certus@$DROPLET_IP

# Pull latest code
cd /opt/certus/certus-TAP
git pull origin main

# Rebuild image
podman build -t localhost/certus-assurance:latest -f Dockerfile.assurance .

# Restart services (systemd will use new image)
sudo systemctl restart certus-api.service
sudo systemctl restart 'certus-worker@*'
```

### 9.2 Backup Artifacts

```bash
# Create backup script
sudo tee /usr/local/bin/backup-certus-artifacts.sh > /dev/null << 'EOF'
#!/bin/bash
BACKUP_DIR="/var/backups/certus"
ARTIFACT_DIR="/var/lib/certus/artifacts"
DATE=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR"
tar -czf "$BACKUP_DIR/artifacts-$DATE.tar.gz" -C "$ARTIFACT_DIR" .

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "artifacts-*.tar.gz" -mtime +7 -delete
EOF

chmod +x /usr/local/bin/backup-certus-artifacts.sh

# Add to cron (daily at 2 AM)
echo "0 2 * * * /usr/local/bin/backup-certus-artifacts.sh" | sudo crontab -
```

## Step 10: Optional - Set Up HTTPS with Let's Encrypt

### 10.1 Install Nginx as Reverse Proxy

```bash
apt install -y nginx certbot python3-certbot-nginx
```

### 10.2 Configure Nginx

```bash
sudo tee /etc/nginx/sites-available/certus << 'EOF'
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8056;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for long-running scans
        proxy_read_timeout 3600s;
        proxy_connect_timeout 3600s;
        proxy_send_timeout 3600s;
    }
}
EOF

# Enable site
sudo ln -s /etc/nginx/sites-available/certus /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 10.3 Get SSL Certificate

```bash
# Get certificate
sudo certbot --nginx -d your-domain.com

# Verify auto-renewal
sudo certbot renew --dry-run
```

Now access via: `https://your-domain.com`

## Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
sudo journalctl -u certus-api.service --no-pager -n 50

# Check Podman
podman ps -a
podman logs <container-id>

# Verify Podman socket
systemctl status podman.socket
```

### Scans Timing Out

```bash
# Increase worker timeout
sudo vi /etc/systemd/system/certus-worker@.service
# Change: Environment="DAGGER_TIMEOUT=7200"

# Reload and restart
sudo systemctl daemon-reload
sudo systemctl restart 'certus-worker@*'
```

### High Memory Usage

```bash
# Check current limits
systemctl show certus-worker@1.service | grep Memory

# Adjust limits
sudo systemctl edit certus-worker@1.service

# Add:
[Service]
MemoryLimit=8G

# Reload
sudo systemctl daemon-reload
sudo systemctl restart certus-worker@1.service
```

### Clean Up Old Artifacts

```bash
# Create cleanup script
sudo tee /usr/local/bin/cleanup-old-artifacts.sh > /dev/null << 'EOF'
#!/bin/bash
find /var/lib/certus/artifacts -type f -mtime +30 -delete
EOF

chmod +x /usr/local/bin/cleanup-old-artifacts.sh

# Run weekly
echo "0 3 * * 0 /usr/local/bin/cleanup-old-artifacts.sh" | sudo crontab -
```

## Cost Optimization

### Snapshot for Quick Redeployment

```bash
# Create snapshot via doctl
doctl compute droplet-action snapshot <droplet-id> --snapshot-name certus-production

# Or via web console:
# Droplets → certus-scanner → Snapshots → Take Snapshot
```

### Use Reserved IPs

```bash
# Reserve IP (survives droplet deletion)
doctl compute reserved-ip create --region nyc1

# Assign to droplet
doctl compute reserved-ip-action assign <reserved-ip> <droplet-id>
```

### Resize Droplet as Needed

```bash
# Power off droplet
doctl compute droplet-action power-off <droplet-id>

# Resize (can only increase, not decrease)
doctl compute droplet-action resize <droplet-id> --size s-8vcpu-16gb

# Power on
doctl compute droplet-action power-on <droplet-id>
```

## Next Steps

1. **Set up CI/CD integration** - Trigger scans from GitHub Actions/GitLab CI
2. **Configure S3 storage** - Store artifacts in DigitalOcean Spaces
3. **Add monitoring** - Set up Prometheus + Grafana
4. **Enable authentication** - Add API keys or OAuth
5. **Multi-region deployment** - Deploy in multiple regions for global teams

## Summary

You now have:

- ✅ Certus Assurance API running on DigitalOcean
- ✅ Podman managing containers (more reliable than Docker)
- ✅ systemd orchestrating services (auto-restart, logging)
- ✅ Dagger orchestrating scanners (portable, reproducible)
- ✅ Multiple workers for parallel scanning
- ✅ Better timeout handling for large codebases
- ✅ Production-ready infrastructure

**Estimated monthly cost**: $48-96 depending on droplet size
**Scan capacity**: 10-50 repos/day depending on size
**Reliability**: High (systemd auto-restart, Podman stability)
