#!/usr/bin/env bash
#
# Deploy Certus Assurance to DigitalOcean with Podman + systemd
#
# Usage:
#   ./deploy-to-digitalocean.sh <droplet-ip>
#
# Example:
#   ./deploy-to-digitalocean.sh 164.90.155.123
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check arguments
if [ $# -lt 1 ]; then
    error "Usage: $0 <droplet-ip>"
fi

DROPLET_IP=$1
DEPLOY_USER="certus"
REPO_DIR="/opt/certus/certus-TAP"

info "Deploying Certus Assurance to $DROPLET_IP"

# Test SSH connection
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes root@$DROPLET_IP exit 2>/dev/null; then
    error "Cannot connect to $DROPLET_IP via SSH. Check your SSH keys and network."
fi

info "SSH connection successful"

# Step 1: Initial setup
info "Step 1/7: Installing system dependencies..."
ssh root@$DROPLET_IP << 'ENDSSH'
    set -e
    apt-get update
    apt-get install -y podman git jq curl python3-pip

    # Install Dagger
    if ! command -v dagger &> /dev/null; then
        curl -fsSL https://dl.dagger.io/dagger/install.sh | sh
        mv /root/bin/dagger /usr/local/bin/
    fi

    # Enable Podman socket
    systemctl enable --now podman.socket
    ln -sf /run/podman/podman.sock /var/run/docker.sock || true

    echo "System dependencies installed"
ENDSSH

# Step 2: Create service user
info "Step 2/7: Creating service user..."
ssh root@$DROPLET_IP << 'ENDSSH'
    set -e
    if ! id -u certus &> /dev/null; then
        useradd -r -m -d /opt/certus -s /bin/bash certus
        usermod -aG sudo certus
    fi

    # Create directories
    mkdir -p /var/lib/certus/artifacts
    mkdir -p /opt/certus
    chown -R certus:certus /var/lib/certus
    chown -R certus:certus /opt/certus

    echo "Service user created"
ENDSSH

# Step 3: Clone/update repository
info "Step 3/7: Deploying application code..."
ssh root@$DROPLET_IP << ENDSSH
    set -e
    if [ -d "$REPO_DIR" ]; then
        cd $REPO_DIR
        git fetch origin
        git reset --hard origin/main
    else
        git clone https://github.com/your-org/certus-TAP.git $REPO_DIR
    fi
    chown -R certus:certus $REPO_DIR
    echo "Application code deployed"
ENDSSH

# Step 4: Build container image
info "Step 4/7: Building Podman image..."
ssh certus@$DROPLET_IP << ENDSSH
    set -e
    cd $REPO_DIR
    podman build -t localhost/certus-assurance:latest -f deployment/Dockerfile.assurance .
    echo "Container image built"
ENDSSH

# Step 5: Install systemd service files
info "Step 5/7: Installing systemd services..."
ssh root@$DROPLET_IP << ENDSSH
    set -e
    cp $REPO_DIR/deployment/systemd/certus-api.service /etc/systemd/system/
    cp $REPO_DIR/deployment/systemd/certus-worker@.service /etc/systemd/system/
    systemctl daemon-reload
    echo "Systemd services installed"
ENDSSH

# Step 6: Enable and start services
info "Step 6/7: Starting services..."
ssh root@$DROPLET_IP << 'ENDSSH'
    set -e

    # Enable services
    systemctl enable certus-api.service
    systemctl enable certus-worker@1.service
    systemctl enable certus-worker@2.service

    # Start or restart services
    systemctl restart certus-api.service
    systemctl restart certus-worker@1.service
    systemctl restart certus-worker@2.service

    # Wait for services to start
    sleep 5

    # Check service status
    if systemctl is-active --quiet certus-api.service; then
        echo "✓ API service is running"
    else
        echo "✗ API service failed to start"
        systemctl status certus-api.service --no-pager || true
        exit 1
    fi

    if systemctl is-active --quiet certus-worker@1.service; then
        echo "✓ Worker 1 is running"
    else
        echo "✗ Worker 1 failed to start"
        systemctl status certus-worker@1.service --no-pager || true
    fi

    if systemctl is-active --quiet certus-worker@2.service; then
        echo "✓ Worker 2 is running"
    else
        echo "✗ Worker 2 failed to start"
        systemctl status certus-worker@2.service --no-pager || true
    fi
ENDSSH

# Step 7: Configure firewall
info "Step 7/7: Configuring firewall..."
ssh root@$DROPLET_IP << 'ENDSSH'
    set -e
    if ! command -v ufw &> /dev/null; then
        apt-get install -y ufw
    fi

    ufw --force enable
    ufw allow 22/tcp
    ufw allow 8056/tcp
    echo "Firewall configured"
ENDSSH

# Test API endpoint
info "Testing API endpoint..."
sleep 3
if curl -sf http://$DROPLET_IP:8056/health > /dev/null; then
    info "✓ API is responding at http://$DROPLET_IP:8056"
else
    warn "API health check failed - service may still be starting up"
fi

info ""
info "════════════════════════════════════════════"
info "Deployment Complete!"
info "════════════════════════════════════════════"
info ""
info "API URL: http://$DROPLET_IP:8056"
info ""
info "Next steps:"
info "  1. Test the API: curl http://$DROPLET_IP:8056/health"
info "  2. Submit a scan: curl -X POST http://$DROPLET_IP:8056/v1/security-scans ..."
info "  3. View logs: ssh root@$DROPLET_IP journalctl -u certus-api.service -f"
info "  4. Check status: ssh root@$DROPLET_IP systemctl status certus-api.service"
info ""
info "Documentation: docs/deployment/digitalocean-podman-systemd.md"
info ""
