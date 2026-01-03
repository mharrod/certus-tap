#!/usr/bin/env bash
#
# Generate secure random secrets for Certus deployment
#
# Usage: ./generate-secrets.sh [output-file]
#
# Default output: deployment/tofu/secrets.tfvars

set -euo pipefail

OUTPUT_FILE="${1:-deployment/tofu/secrets.tfvars}"

echo "Generating secrets for Certus deployment..."
echo ""

# Generate random secrets
DB_PASSWORD=$(openssl rand -base64 32)
NEO4J_PASSWORD=$(openssl rand -base64 32)
REDIS_PASSWORD=$(openssl rand -base64 32)
JWT_SECRET=$(openssl rand -base64 64)

# Create secrets file
cat > "$OUTPUT_FILE" <<EOF
# Certus Deployment Secrets
# Generated: $(date)
# KEEP THIS FILE SECURE - DO NOT COMMIT TO GIT

# ==============================================================================
# Tailscale Configuration
# ==============================================================================
# Get auth key from: https://login.tailscale.com/admin/settings/keys
tailscale_auth_key = "YOUR_TAILSCALE_AUTH_KEY_HERE"

# ==============================================================================
# Database Passwords (Auto-generated)
# ==============================================================================
db_password    = "$DB_PASSWORD"
neo4j_password = "$NEO4J_PASSWORD"
redis_password = "$REDIS_PASSWORD"

# ==============================================================================
# Application Secrets (Auto-generated)
# ==============================================================================
jwt_secret = "$JWT_SECRET"

# ==============================================================================
# GitHub Actions (Optional)
# ==============================================================================
# Get runner token from:
# https://github.com/YOUR_ORG/YOUR_REPO/settings/actions/runners/new
github_runner_token = ""

# ==============================================================================
# Configuration (Optional Overrides)
# ==============================================================================
# environment = "staging"
# region = "nyc3"
# droplet_size = "s-4vcpu-8gb"
# worker_count = 2
EOF

# Set restrictive permissions
chmod 600 "$OUTPUT_FILE"

echo "✓ Secrets generated and saved to: $OUTPUT_FILE"
echo ""
echo "Next steps:"
echo "  1. Edit $OUTPUT_FILE"
echo "  2. Add your Tailscale auth key"
echo "  3. (Optional) Add GitHub runner token"
echo "  4. Deploy: cd deployment/tofu && tofu apply -var-file=secrets.tfvars"
echo ""
echo "⚠️  Keep this file secure - it contains sensitive credentials!"
