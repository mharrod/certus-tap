output "droplet_id" {
  description = "Droplet ID"
  value       = digitalocean_droplet.certus.id
}

output "droplet_ip" {
  description = "Public IP address"
  value       = digitalocean_droplet.certus.ipv4_address
}

output "ssh_command" {
  description = "SSH command (emergency access)"
  value       = "ssh root@${digitalocean_droplet.certus.ipv4_address}"
}

output "tailscale_access" {
  description = "Access via Tailscale (after droplet joins mesh)"
  value       = "ssh root@${var.environment == "staging" ? "certus-staging" : "certus-${var.environment}"}"
}

output "api_urls" {
  description = "API endpoints (accessible via Tailscale only)"
  value = {
    assurance = "http://certus-${var.environment}:8056"
    transform = "http://certus-${var.environment}:8057"
    ask       = "http://certus-${var.environment}:8058"
    trust     = "http://certus-${var.environment}:8059"
    integrity = "http://certus-${var.environment}:8060"
  }
}

output "api_key" {
  description = "API authentication key"
  value       = random_password.api_key.result
  sensitive   = true
}

output "database_connections" {
  description = "Database connection strings (internal)"
  value = {
    postgres   = "postgresql://certus:${var.db_password}@localhost:5432/certus"
    neo4j      = "neo4j://localhost:7687"
    redis      = "redis://:${var.redis_password}@localhost:6379"
    opensearch = "http://localhost:9200"
  }
  sensitive = true
}

output "cost_estimate" {
  description = "Estimated cost"
  value = {
    hourly_rate  = lookup(local.droplet_costs, var.droplet_size, "unknown")
    monthly_24_7 = lookup(local.droplet_costs_monthly, var.droplet_size, "unknown")
    monthly_8h_5d = "~${lookup(local.droplet_costs_8h, var.droplet_size, "unknown")}"
  }
}

output "next_steps" {
  description = "What to do next"
  value = <<-EOT

  ════════════════════════════════════════════════════════════════
  Certus ${upper(var.environment)} Deployment Complete!
  ════════════════════════════════════════════════════════════════

  📡 Droplet IP: ${digitalocean_droplet.certus.ipv4_address}

  🔐 Access Methods:

    1. Via Tailscale (Primary):
       - Wait 2-3 min for droplet to join Tailscale mesh
       - Access APIs: curl http://certus-${var.environment}:8056/health
       - SSH: ssh root@certus-${var.environment}

    2. Emergency SSH (Public IP + 2FA):
       - SSH: ssh root@${digitalocean_droplet.certus.ipv4_address}
       - Requires: SSH key + Google Authenticator code
       - Setup 2FA on first login (see docs)

  🔑 API Key (save this):
       export CERTUS_API_KEY="${random_password.api_key.result}"

  📊 Check Status:
       ssh root@certus-${var.environment}
       systemctl status 'certus-*'

  🧪 Test Services:
       curl -H "Authorization: Bearer $CERTUS_API_KEY" \
         http://certus-${var.environment}:8056/health

  💰 Cost (8 hrs/day, 5 days/week):
       ${lookup(local.droplet_costs_8h, var.droplet_size, "unknown")}/month

  📖 Full docs: deployment/tofu/README.md

  ════════════════════════════════════════════════════════════════
  EOT
}

locals {
  droplet_costs = {
    "s-1vcpu-1gb"    = "$0.007/hr"
    "s-2vcpu-2gb"    = "$0.018/hr"
    "s-2vcpu-4gb"    = "$0.036/hr"
    "s-4vcpu-8gb"    = "$0.071/hr"
    "s-8vcpu-16gb"   = "$0.143/hr"
    "s-16vcpu-32gb"  = "$0.286/hr"
  }

  droplet_costs_monthly = {
    "s-1vcpu-1gb"    = "$5/mo"
    "s-2vcpu-2gb"    = "$13/mo"
    "s-2vcpu-4gb"    = "$24/mo"
    "s-4vcpu-8gb"    = "$48/mo"
    "s-8vcpu-16gb"   = "$96/mo"
    "s-16vcpu-32gb"  = "$192/mo"
  }

  droplet_costs_8h = {
    "s-1vcpu-1gb"    = "$1"
    "s-2vcpu-2gb"    = "$3"
    "s-2vcpu-4gb"    = "$6"
    "s-4vcpu-8gb"    = "$11"
    "s-8vcpu-16gb"   = "$22"
    "s-16vcpu-32gb"  = "$44"
  }
}
