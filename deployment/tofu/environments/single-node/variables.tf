variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "Environment must be dev, staging, or prod."
  }
}

variable "region" {
  description = "DigitalOcean region"
  type        = string
  default     = "nyc3"

  validation {
    condition     = contains(["nyc1", "nyc3", "sfo3", "sgp1", "lon1", "fra1", "tor1", "blr1"], var.region)
    error_message = "Region must be a valid DigitalOcean region."
  }
}

variable "droplet_size" {
  description = "Droplet size (slug)"
  type        = string
  default     = "s-4vcpu-8gb"

  # Common sizes for testing/staging:
  # s-2vcpu-4gb    ($24/mo, ~$6/mo at 8hrs/day)  - Small testing
  # s-4vcpu-8gb    ($48/mo, ~$11/mo at 8hrs/day) - Recommended
  # s-8vcpu-16gb   ($96/mo, ~$22/mo at 8hrs/day) - Large codebases
}

variable "worker_count" {
  description = "Number of security scan workers"
  type        = number
  default     = 2

  validation {
    condition     = var.worker_count >= 1 && var.worker_count <= 8
    error_message = "Worker count must be between 1 and 8."
  }
}

# SSH Configuration
variable "ssh_public_key_path" {
  description = "Path to SSH public key"
  type        = string
  default     = "~/.ssh/id_rsa.pub"
}

# GitHub Configuration
variable "github_repo" {
  description = "GitHub repository (owner/repo)"
  type        = string
  default     = "mharrod/certus-tap"
}

variable "github_repo_url" {
  description = "GitHub repository URL"
  type        = string
  default     = "https://github.com/mharrod/certus-tap.git"
}

variable "github_branch" {
  description = "Git branch to deploy"
  type        = string
  default     = "main"
}

variable "github_runner_token" {
  description = "GitHub Actions runner registration token"
  type        = string
  sensitive   = true
  default     = ""

  # Get token from: https://github.com/YOUR_ORG/YOUR_REPO/settings/actions/runners/new
  # Or use GitHub API to generate programmatically
}

# Tailscale Configuration
variable "tailscale_auth_key" {
  description = "Tailscale authentication key (get from https://login.tailscale.com/admin/settings/keys)"
  type        = string
  sensitive   = true

  # Generate a reusable auth key:
  # 1. Go to https://login.tailscale.com/admin/settings/keys
  # 2. Generate auth key
  # 3. Make it reusable and set expiration
}

# Database Secrets
variable "db_password" {
  description = "PostgreSQL password"
  type        = string
  sensitive   = true

  # Generate: openssl rand -base64 32
}

variable "neo4j_password" {
  description = "Neo4j password"
  type        = string
  sensitive   = true

  # Generate: openssl rand -base64 32
}

variable "redis_password" {
  description = "Redis password"
  type        = string
  sensitive   = true

  # Generate: openssl rand -base64 32
}

# Application Secrets
variable "jwt_secret" {
  description = "JWT signing secret"
  type        = string
  sensitive   = true

  # Generate: openssl rand -base64 64
}
