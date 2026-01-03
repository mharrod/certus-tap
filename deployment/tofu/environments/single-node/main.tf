terraform {
  required_version = ">= 1.6"

  required_providers {
    digitalocean = {
      source  = "digitalocean/digitalocean"
      version = "~> 2.0"
    }
  }
}

provider "digitalocean" {
  # Set via environment variable: DIGITALOCEAN_TOKEN
}

# Generate random API key for securing endpoints
resource "random_password" "api_key" {
  length  = 64
  special = false
}

# SSH key for droplet access
resource "digitalocean_ssh_key" "certus" {
  name       = "certus-${var.environment}"
  public_key = file(var.ssh_public_key_path)
}

# Main Certus droplet - all services on one machine
resource "digitalocean_droplet" "certus" {
  image    = "ubuntu-22-04-x64"
  name     = "certus-${var.environment}"
  region   = var.region
  size     = var.droplet_size
  ssh_keys = [digitalocean_ssh_key.certus.fingerprint]

  # Bootstrap script
  user_data = templatefile("${path.module}/cloud-init.yaml", {
    # Secrets
    db_password         = var.db_password
    neo4j_password      = var.neo4j_password
    redis_password      = var.redis_password
    jwt_secret          = var.jwt_secret
    api_key             = random_password.api_key.result
    tailscale_auth_key  = var.tailscale_auth_key
    github_runner_token = var.github_runner_token

    # Config
    github_repo         = var.github_repo
    github_repo_url     = var.github_repo_url
    github_branch       = var.github_branch
    worker_count        = var.worker_count
    environment         = var.environment
    certus_hostname     = "certus-${var.environment}"
  })

  tags = ["certus", var.environment, "ephemeral"]
}

# Firewall rules
resource "digitalocean_firewall" "certus" {
  name = "certus-${var.environment}-firewall"

  droplet_ids = [digitalocean_droplet.certus.id]

  # Emergency SSH with 2FA (Google Authenticator)
  inbound_rule {
    protocol         = "tcp"
    port_range       = "22"
    source_addresses = ["0.0.0.0/0"]  # Public, secured by key + 2FA
  }

  # Tailscale mesh coordination
  inbound_rule {
    protocol         = "udp"
    port_range       = "41641"
    source_addresses = ["0.0.0.0/0"]
  }

  # All API ports are NOT public - only accessible via Tailscale mesh
  # No inbound rules for 8056-8060

  # Allow all outbound
  outbound_rule {
    protocol              = "tcp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "udp"
    port_range            = "1-65535"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }

  outbound_rule {
    protocol              = "icmp"
    destination_addresses = ["0.0.0.0/0", "::/0"]
  }
}
