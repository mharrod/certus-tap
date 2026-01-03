# Infrastructure Secrets Management

**Status:** Draft v1.0
**Author:** System Architecture
**Date:** 2025-12-11
**Category:** Enhancement
## Executive Summary

As Certus TAP scales from development to production and introduces AI agents (AAIF), we need a **secure, centralized infrastructure for managing secrets** used by Certus services, agents, and automation. Currently, secrets (database passwords, API keys, cloud credentials) may be stored in configuration files, environment variables, or Kubernetes secrets without centralized management, rotation, or audit trails.

This enhancement proposes integrating **HashiCorp Vault** (or AWS Secrets Manager/Azure Key Vault as alternatives) to provide:

1. **Centralized Secret Storage** - Single source of truth for all infrastructure secrets
2. **Dynamic Secret Generation** - Generate short-lived credentials on-demand (database, cloud)
3. **Secret Rotation** - Automated rotation policies with zero-downtime
4. **Agent Authentication** - Secure credential access for AAIF agents and MCP servers
5. **Audit Logging** - Complete audit trail of secret access and usage
6. **Encryption at Rest & Transit** - Industry-standard encryption for all secrets

**Strategic Value:**

This is **foundational infrastructure** required for:
- Production deployment (cannot have secrets in `.env` files or config)
- AAIF agents (secure authentication to MCP servers and Certus APIs)
- Compliance (SOC2, HIPAA require secret management and rotation)
- Multi-tenancy (tenant-specific secrets with isolation)
- Security best practices (principle of least privilege, time-bound credentials)

**Business Impact:**

- **Security:** Eliminates hardcoded secrets, reduces breach surface area
- **Compliance:** Enables SOC2/HIPAA certification (required controls)
- **Operations:** Automated rotation reduces operational toil
- **Development:** Developers never handle production secrets directly
- **Audit:** Complete visibility into who accessed what secrets when

---

**Note:** This proposal does NOT cover:
- ❌ Secret scanning in user repositories (covered by [Dagger Proposal](../proposals/dagger-proposal.md))
- ❌ Git/registry credentials for scans (covered by [Certus-Assurance Proposal](../proposals/certus-assurance-proposal.md))

## Motivation

### Current State

**How secrets are likely managed today:**

```python
# Option 1: .env files (development)
DATABASE_URL=postgresql://user:password@localhost/certus
OPENAI_API_KEY=sk-abc123...
AWS_ACCESS_KEY_ID=AKIA...

# Option 2: Kubernetes secrets (production)
kubectl create secret generic certus-secrets \
  --from-literal=db-password=supersecret \
  --from-literal=openai-key=sk-abc123

# Option 3: Environment variables
export DATABASE_PASSWORD="hardcoded_password"
```

**Problems with current approach:**

1. **Secrets in Version Control Risk**
   - `.env` files might be accidentally committed
   - Difficult to rotate without redeploying everything
   - No audit trail of who accessed secrets

2. **No Centralization**
   - Secrets scattered across: `.env`, K8s secrets, CI/CD variables, developer machines
   - Hard to know where all copies of a secret exist
   - Rotation requires updating secrets in multiple places

3. **Static, Long-Lived Credentials**
   - Database passwords never rotate
   - API keys valid indefinitely
   - Increases blast radius if compromised

4. **No Access Control**
   - Anyone with K8s access can read all secrets
   - No granular permissions (can't restrict by service)
   - Developers have same access as production services

5. **No Audit Trail**
   - Can't answer: "Who accessed the production database password?"
   - No compliance evidence for auditors

6. **Agent Authentication Gap**
   - AAIF agents need credentials to call MCP servers
   - How do they get these securely?
   - How do we rotate agent credentials?

### Problems Addressed

| Problem | Impact | Current State | Desired State |
|---------|--------|---------------|---------------|
| **Hardcoded secrets** | Security breach if code leaked | In .env, configs | In Vault, injected at runtime |
| **No rotation** | Stale credentials, compliance violation | Manual, rare | Automated, frequent |
| **No audit trail** | Can't prove compliance | No logging | Complete audit logs |
| **Broad access** | Developers see prod secrets | K8s access = all secrets | Role-based, need-to-know |
| **Agent auth** | Agents can't securely authenticate | Manual token sharing | Dynamic, short-lived tokens |
| **Manual management** | High operational toil | kubectl create secret | Self-service secret injection |

### Why Infrastructure Secrets Management?

**Security Best Practices:**
- **Principle of Least Privilege** - Services only access secrets they need
- **Defense in Depth** - Secrets encrypted at rest, in transit, and in memory
- **Time-Bound Access** - Short-lived credentials limit blast radius
- **Zero Trust** - Every access is authenticated and authorized

**Compliance Requirements:**

For SOC2, HIPAA, ISO27001 certification, you need:
- ✅ Centralized secret management
- ✅ Secret rotation policies
- ✅ Audit logging of secret access
- ✅ Encryption at rest and in transit
- ✅ Access controls and least privilege

**Operational Benefits:**

- **Developers** never see production secrets (use dev secrets only)
- **Services** get secrets injected automatically at startup
- **Agents** authenticate using short-lived tokens
- **Security team** can rotate secrets centrally without redeployment

## Goals & Non-Goals

| Goals | Non-Goals |
|-------|-----------|
| Integrate HashiCorp Vault (or AWS/Azure alternative) for secret storage | Replace Kubernetes entirely (K8s still used for non-secret config) |
| Provide runtime secret injection for all Certus services | Manage secrets in user repositories (Dagger handles scanning) |
| Enable dynamic, short-lived credentials for databases and cloud services | Implement custom secret encryption (use proven solutions) |
| Implement automated secret rotation with zero downtime | Rotate every secret immediately (phased rotation) |
| Provide secure authentication for AAIF agents to MCP servers | Build a secrets manager from scratch (use existing tools) |
| Complete audit logging of all secret access | Store application logs in Vault (only secret access logs) |
| Support multiple environments (dev, staging, prod) with isolation | Share secrets across environments (strict isolation) |
| Enable self-service secret management for developers (dev/staging only) | Allow developers to access production secrets |

## Proposed Solution

### Architecture Overview

```
┌───────────────────────────────────────────────────────────────────────┐
│              Infrastructure Secrets Management Architecture           │
├───────────────────────────────────────────────────────────────────────┤
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              HashiCorp Vault (Central Secrets Store)        │    │
│  │                                                             │    │
│  │  Secret Engines:                                            │    │
│  │  ├─ KV Secrets v2 (static secrets)                         │    │
│  │  │   ├─ certus/prod/database/password                      │    │
│  │  │   ├─ certus/prod/openai/api-key                         │    │
│  │  │   ├─ certus/prod/aws/credentials                        │    │
│  │  │   └─ certus/mcp/server-tokens                           │    │
│  │  ├─ Database Secrets (dynamic)                             │    │
│  │  │   └─ Generate PostgreSQL credentials on-demand          │    │
│  │  ├─ AWS Secrets (dynamic)                                  │    │
│  │  │   └─ Generate IAM credentials with TTL                  │    │
│  │  └─ PKI Secrets (certificates)                             │    │
│  │      └─ Generate TLS certs for mTLS                        │    │
│  │                                                             │    │
│  │  Auth Methods:                                              │    │
│  │  ├─ Kubernetes Auth (for pods)                             │    │
│  │  ├─ AppRole (for services)                                 │    │
│  │  ├─ OIDC (for developers)                                  │    │
│  │  └─ Token (for agents)                                     │    │
│  │                                                             │    │
│  │  Policies (RBAC):                                          │    │
│  │  ├─ certus-assurance-policy (read: assurance/*)           │    │
│  │  ├─ certus-ask-policy (read: ask/*)                       │    │
│  │  ├─ certus-agent-policy (read: mcp/*, agents/*)           │    │
│  │  └─ developer-policy (read: dev/*, staging/*)             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↕                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Secret Injection Layer                         │    │
│  │                                                             │    │
│  │  Vault Agent Injector (Kubernetes)                          │    │
│  │  ├─ Sidecar containers inject secrets into pods            │    │
│  │  ├─ Secrets mounted as files or env vars                   │    │
│  │  └─ Auto-renewal of short-lived credentials                │    │
│  │                                                             │    │
│  │  Vault SDK (Python, for services)                          │    │
│  │  ├─ Services fetch secrets programmatically                │    │
│  │  ├─ Caching and renewal logic                              │    │
│  │  └─ Graceful fallback on errors                            │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↕                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Certus Services (Consumers)                    │    │
│  │                                                             │    │
│  │  Certus-Ask                                                 │    │
│  │  └─ Reads: database password, OpenAI key, OpenSearch creds │    │
│  │                                                             │    │
│  │  Certus-Assurance                                           │    │
│  │  └─ Reads: database password, S3 credentials, Neo4j creds  │    │
│  │                                                             │    │
│  │  Certus-Trust                                               │    │
│  │  └─ Reads: signing keys, verification credentials          │    │
│  │                                                             │    │
│  │  AAIF Agents (Goose)                                        │    │
│  │  └─ Reads: MCP server tokens, GitHub tokens, Certus API keys│   │
│  │                                                             │    │
│  │  Security SLM                                               │    │
│  │  └─ Reads: model storage credentials, API keys             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↕                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │              Audit & Monitoring                             │    │
│  │                                                             │    │
│  │  Vault Audit Logs                                           │    │
│  │  └─ All secret access logged (who, what, when)             │    │
│  │                                                             │    │
│  │  Certus-Insight Integration                                 │    │
│  │  └─ Audit logs streamed to Insight for alerting            │    │
│  │                                                             │    │
│  │  Alerts:                                                    │    │
│  │  ├─ Unusual secret access patterns                         │    │
│  │  ├─ Failed authentication attempts                         │    │
│  │  └─ Secrets nearing expiration                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────┘
```

### Key Components

#### 1. HashiCorp Vault Deployment

**Deployment Options:**

**Option A: Vault OSS (Self-Hosted)**
- Deploy in Kubernetes (Helm chart)
- Backend: Raft storage (integrated storage)
- HA: 3-5 node cluster

**Option B: Vault Enterprise (Self-Hosted)**
- Same as OSS + advanced features
- Namespaces (multi-tenancy)
- Replication (DR, performance)

**Option C: HCP Vault (Managed)**
- HashiCorp Cloud Platform
- Fully managed, zero ops
- Higher cost but simpler

**Recommendation: Start with Vault OSS**, upgrade to Enterprise if multi-tenancy needed.

**Deployment (Kubernetes):**

```yaml
# vault-values.yaml (Helm chart values)
global:
  enabled: true
  tlsDisable: false  # Enable TLS

server:
  # High availability
  ha:
    enabled: true
    replicas: 3
    raft:
      enabled: true
      setNodeId: true
      config: |
        ui = true

        listener "tcp" {
          tls_disable = 0
          address = "[::]:8200"
          cluster_address = "[::]:8201"
          tls_cert_file = "/vault/tls/tls.crt"
          tls_key_file = "/vault/tls/tls.key"
        }

        storage "raft" {
          path = "/vault/data"
        }

        service_registration "kubernetes" {}

  # Resources
  resources:
    requests:
      memory: 256Mi
      cpu: 250m
    limits:
      memory: 512Mi
      cpu: 500m

  # Persistence
  dataStorage:
    enabled: true
    size: 10Gi
    storageClass: fast-ssd

  # Audit logging
  auditStorage:
    enabled: true
    size: 10Gi

# Vault Agent Injector (for K8s secret injection)
injector:
  enabled: true
  replicas: 2
  resources:
    requests:
      memory: 128Mi
      cpu: 100m

ui:
  enabled: true
  serviceType: LoadBalancer
```

**Deploy:**

```bash
# Add Vault Helm repo
helm repo add hashicorp https://helm.releases.hashicorp.com
helm repo update

# Install Vault
helm install vault hashicorp/vault \
  --namespace vault \
  --create-namespace \
  --values vault-values.yaml

# Initialize Vault (first time only)
kubectl exec -n vault vault-0 -- vault operator init

# Save unseal keys and root token securely (1Password, etc.)

# Unseal Vault (3 of 5 keys required)
kubectl exec -n vault vault-0 -- vault operator unseal <key1>
kubectl exec -n vault vault-0 -- vault operator unseal <key2>
kubectl exec -n vault vault-0 -- vault operator unseal <key3>

# Repeat for vault-1, vault-2 if HA
```

#### 2. Secret Engines Configuration

**KV Secrets v2 (Static Secrets):**

```bash
# Enable KV secrets engine
vault secrets enable -path=certus kv-v2

# Store secrets
vault kv put certus/prod/database \
  username=certus_prod \
  password=<generated-strong-password>

vault kv put certus/prod/openai \
  api_key=sk-...

vault kv put certus/prod/aws \
  access_key_id=AKIA... \
  secret_access_key=...

vault kv put certus/mcp/assurance \
  server_token=<generated-token>

# Versioning (automatic)
vault kv get certus/prod/database
vault kv get -version=2 certus/prod/database  # Previous version
```

**Database Secrets Engine (Dynamic):**

```bash
# Enable database secrets engine
vault secrets enable database

# Configure PostgreSQL connection
vault write database/config/certus-postgres \
  plugin_name=postgresql-database-plugin \
  allowed_roles="certus-ask,certus-assurance" \
  connection_url="postgresql://{{username}}:{{password}}@postgres.certus:5432/certus" \
  username="vault_admin" \
  password="vault_admin_password"

# Define role for Certus-Ask (read-only)
vault write database/roles/certus-ask \
  db_name=certus-postgres \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT SELECT ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"

# Define role for Certus-Assurance (read-write)
vault write database/roles/certus-assurance \
  db_name=certus-postgres \
  creation_statements="CREATE ROLE \"{{name}}\" WITH LOGIN PASSWORD '{{password}}' VALID UNTIL '{{expiration}}'; \
    GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO \"{{name}}\";" \
  default_ttl="1h" \
  max_ttl="24h"

# Generate dynamic credentials (1 hour TTL)
vault read database/creds/certus-ask
# Output:
# Key                Value
# ---                -----
# lease_id          database/creds/certus-ask/abc123
# lease_duration    1h
# username          v-certus-ask-xyz789
# password          A1b2C3d4...
```

**AWS Secrets Engine (Dynamic):**

```bash
# Enable AWS secrets engine
vault secrets enable aws

# Configure AWS root credentials
vault write aws/config/root \
  access_key=<root_access_key> \
  secret_key=<root_secret_key> \
  region=us-west-2

# Define role for S3 access (for Certus-Assurance)
vault write aws/roles/certus-s3-access \
  credential_type=iam_user \
  policy_document=-<<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::certus-artifacts/*"
    }
  ]
}
EOF

# Generate dynamic AWS credentials (1 hour TTL)
vault read aws/creds/certus-s3-access
# Output:
# access_key        ASIA...
# secret_key        ...
# security_token    ... (if using STS)
# ttl               1h
```

#### 3. Authentication Methods

**Kubernetes Auth (for Pods):**

```bash
# Enable Kubernetes auth
vault auth enable kubernetes

# Configure Kubernetes auth
vault write auth/kubernetes/config \
  kubernetes_host="https://kubernetes.default.svc:443" \
  kubernetes_ca_cert=@/var/run/secrets/kubernetes.io/serviceaccount/ca.crt \
  token_reviewer_jwt=@/var/run/secrets/kubernetes.io/serviceaccount/token

# Create role for Certus-Ask pods
vault write auth/kubernetes/role/certus-ask \
  bound_service_account_names=certus-ask \
  bound_service_account_namespaces=certus-tap \
  policies=certus-ask-policy \
  ttl=1h

# Create role for AAIF agents
vault write auth/kubernetes/role/certus-agent \
  bound_service_account_names=certus-agent \
  bound_service_account_namespaces=certus-tap \
  policies=certus-agent-policy \
  ttl=15m  # Shorter TTL for agents
```

**AppRole (for Services outside K8s):**

```bash
# Enable AppRole auth
vault auth enable approle

# Create role for Certus services
vault write auth/approle/role/certus-service \
  secret_id_ttl=24h \
  token_ttl=1h \
  token_max_ttl=4h \
  policies=certus-service-policy

# Get role ID and secret ID
vault read auth/approle/role/certus-service/role-id
vault write -f auth/approle/role/certus-service/secret-id

# Use in application
# role_id: <from above>
# secret_id: <from above>
```

**OIDC (for Developers):**

```bash
# Enable OIDC auth
vault auth enable oidc

# Configure with Google Workspace (or Okta, Auth0, etc.)
vault write auth/oidc/config \
  oidc_discovery_url="https://accounts.google.com" \
  oidc_client_id="<google_client_id>" \
  oidc_client_secret="<google_client_secret>" \
  default_role="developer"

# Create role for developers (read-only on dev/staging)
vault write auth/oidc/role/developer \
  bound_audiences="<google_client_id>" \
  allowed_redirect_uris="http://localhost:8200/ui/vault/auth/oidc/oidc/callback" \
  user_claim="email" \
  policies=developer-policy
```

#### 4. Access Policies (RBAC)

```hcl
# certus-ask-policy.hcl
path "certus/data/prod/database" {
  capabilities = ["read"]
}

path "certus/data/prod/openai" {
  capabilities = ["read"]
}

path "certus/data/prod/opensearch" {
  capabilities = ["read"]
}

path "database/creds/certus-ask" {
  capabilities = ["read"]
}

# Deny access to other services' secrets
path "certus/data/prod/assurance/*" {
  capabilities = ["deny"]
}
```

```hcl
# certus-agent-policy.hcl
path "certus/data/mcp/*" {
  capabilities = ["read"]
}

path "certus/data/agents/*" {
  capabilities = ["read"]
}

path "certus/data/prod/github" {
  capabilities = ["read"]
}

# Short-lived tokens for MCP authentication
path "auth/token/create" {
  capabilities = ["create", "update"]
}
```

```hcl
# developer-policy.hcl
# Developers can only access dev/staging, never prod
path "certus/data/dev/*" {
  capabilities = ["read", "list"]
}

path "certus/data/staging/*" {
  capabilities = ["read", "list"]
}

path "certus/data/prod/*" {
  capabilities = ["deny"]
}
```

**Apply policies:**

```bash
vault policy write certus-ask-policy certus-ask-policy.hcl
vault policy write certus-agent-policy certus-agent-policy.hcl
vault policy write developer-policy developer-policy.hcl
```

#### 5. Secret Injection Methods

**Method 1: Vault Agent Injector (Kubernetes - Recommended)**

Automatically injects secrets into pods as files or environment variables.

**Example: Certus-Ask Deployment**

```yaml
# certus-ask-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: certus-ask
  namespace: certus-tap
spec:
  replicas: 3
  template:
    metadata:
      annotations:
        # Enable Vault injection
        vault.hashicorp.com/agent-inject: "true"
        vault.hashicorp.com/role: "certus-ask"

        # Inject database credentials
        vault.hashicorp.com/agent-inject-secret-database: "database/creds/certus-ask"
        vault.hashicorp.com/agent-inject-template-database: |
          {{- with secret "database/creds/certus-ask" -}}
          export DATABASE_USERNAME="{{ .Data.username }}"
          export DATABASE_PASSWORD="{{ .Data.password }}"
          {{- end -}}

        # Inject OpenAI key
        vault.hashicorp.com/agent-inject-secret-openai: "certus/data/prod/openai"
        vault.hashicorp.com/agent-inject-template-openai: |
          {{- with secret "certus/data/prod/openai" -}}
          export OPENAI_API_KEY="{{ .Data.data.api_key }}"
          {{- end -}}

    spec:
      serviceAccountName: certus-ask  # K8s service account for auth
      containers:
      - name: certus-ask
        image: certus/certus-ask:latest
        command: ["/bin/sh", "-c"]
        args:
          # Source secrets from injected files
          - source /vault/secrets/database &&
            source /vault/secrets/openai &&
            python -m certus_ask.main

        # Secrets mounted at /vault/secrets/
        volumeMounts:
        - name: vault-secrets
          mountPath: /vault/secrets
          readOnly: true
```

**How it works:**

1. Vault Agent Injector sees the annotations
2. Injects a sidecar container into the pod
3. Sidecar authenticates to Vault using K8s service account
4. Fetches secrets and writes to `/vault/secrets/`
5. Main container sources secrets from files
6. Sidecar auto-renews secrets before expiry

**Method 2: Vault SDK (Python)**

For services that need programmatic access or run outside Kubernetes.

```python
# certus_common/secrets/vault_client.py
import hvac
import os
from typing import Dict, Optional

class VaultClient:
    """
    Client for fetching secrets from HashiCorp Vault.
    """

    def __init__(
        self,
        vault_addr: str = None,
        auth_method: str = "kubernetes",
        role: str = None
    ):
        self.vault_addr = vault_addr or os.getenv("VAULT_ADDR", "https://vault.certus:8200")
        self.client = hvac.Client(url=self.vault_addr)
        self.auth_method = auth_method
        self.role = role

        self._authenticate()

    def _authenticate(self):
        """Authenticate to Vault based on auth method."""

        if self.auth_method == "kubernetes":
            # Read K8s service account token
            with open("/var/run/secrets/kubernetes.io/serviceaccount/token") as f:
                jwt = f.read()

            # Authenticate
            self.client.auth.kubernetes.login(
                role=self.role,
                jwt=jwt
            )

        elif self.auth_method == "approle":
            role_id = os.getenv("VAULT_ROLE_ID")
            secret_id = os.getenv("VAULT_SECRET_ID")

            self.client.auth.approle.login(
                role_id=role_id,
                secret_id=secret_id
            )

        elif self.auth_method == "token":
            # For development only
            token = os.getenv("VAULT_TOKEN")
            self.client.token = token

        else:
            raise ValueError(f"Unsupported auth method: {self.auth_method}")

    def get_secret(self, path: str, key: Optional[str] = None) -> Dict:
        """
        Get secret from KV v2 store.

        Args:
            path: Secret path (e.g., "certus/prod/database")
            key: Specific key to extract (optional)

        Returns:
            Secret data or specific key value
        """
        secret = self.client.secrets.kv.v2.read_secret_version(
            path=path,
            mount_point="certus"
        )

        data = secret["data"]["data"]

        if key:
            return data.get(key)
        return data

    def get_database_credentials(self, role: str) -> Dict:
        """
        Get dynamic database credentials.

        Args:
            role: Vault database role (e.g., "certus-ask")

        Returns:
            {"username": "...", "password": "...", "lease_id": "..."}
        """
        creds = self.client.secrets.database.generate_credentials(
            name=role
        )

        return {
            "username": creds["data"]["username"],
            "password": creds["data"]["password"],
            "lease_id": creds["lease_id"],
            "lease_duration": creds["lease_duration"]
        }

    def renew_lease(self, lease_id: str):
        """Renew a lease before it expires."""
        self.client.sys.renew_lease(lease_id=lease_id)

    def get_aws_credentials(self, role: str) -> Dict:
        """Get dynamic AWS credentials."""
        creds = self.client.secrets.aws.generate_credentials(
            name=role
        )

        return {
            "access_key": creds["data"]["access_key"],
            "secret_key": creds["data"]["secret_key"],
            "security_token": creds["data"].get("security_token"),
            "lease_id": creds["lease_id"]
        }

# Usage in Certus services
vault = VaultClient(auth_method="kubernetes", role="certus-ask")

# Get static secret
openai_key = vault.get_secret("prod/openai", key="api_key")

# Get dynamic database credentials
db_creds = vault.get_database_credentials(role="certus-ask")
connection_string = f"postgresql://{db_creds['username']}:{db_creds['password']}@postgres:5432/certus"

# Renew before expiry (background task)
vault.renew_lease(db_creds['lease_id'])
```

**Integration in Certus-Ask:**

```python
# certus_ask/config.py
from certus_common.secrets import VaultClient

class Settings:
    def __init__(self):
        # Initialize Vault client
        self.vault = VaultClient(auth_method="kubernetes", role="certus-ask")

        # Fetch secrets from Vault
        self._database_creds = self.vault.get_database_credentials("certus-ask")
        self._openai_key = self.vault.get_secret("prod/openai", key="api_key")
        self._opensearch_creds = self.vault.get_secret("prod/opensearch")

    @property
    def database_url(self) -> str:
        return (
            f"postgresql://{self._database_creds['username']}:"
            f"{self._database_creds['password']}@postgres.certus:5432/certus"
        )

    @property
    def openai_api_key(self) -> str:
        return self._openai_key

    @property
    def opensearch_url(self) -> str:
        creds = self._opensearch_creds
        return f"https://{creds['username']}:{creds['password']}@opensearch.certus:9200"

settings = Settings()
```

#### 6. Agent Authentication (AAIF)

**How Goose agents authenticate to MCP servers:**

```yaml
# Goose profile with Vault integration
# ~/.config/goose/profiles/certus-security.yaml

llm:
  provider: ollama
  model: llama3

mcp_servers:
  - name: certus-assurance
    command: certus-mcp-server
    args: [assurance]
    env:
      # Vault integration
      VAULT_ADDR: "https://vault.certus:8200"
      VAULT_ROLE: "certus-agent"
      # MCP token fetched from Vault at runtime
      MCP_SERVER_TOKEN: "${VAULT:certus/mcp/assurance/server_token}"

  - name: certus-trust
    command: certus-mcp-server
    args: [trust]
    env:
      VAULT_ADDR: "https://vault.certus:8200"
      VAULT_ROLE: "certus-agent"
      MCP_SERVER_TOKEN: "${VAULT:certus/mcp/trust/server_token}"
```

**MCP Server validates token from Vault:**

```python
# certus_mcp_servers/auth/vault_auth.py
from certus_common.secrets import VaultClient

class MCPServerAuth:
    """Authenticate MCP clients using Vault tokens."""

    def __init__(self):
        self.vault = VaultClient(auth_method="kubernetes", role="certus-mcp-server")
        # Load valid tokens from Vault
        self.valid_tokens = self._load_valid_tokens()

    def _load_valid_tokens(self) -> set:
        """Load all valid MCP tokens from Vault."""
        tokens = set()

        # Read token list from Vault
        token_list = self.vault.get_secret("mcp/assurance/valid_tokens")

        for token in token_list.get("tokens", []):
            tokens.add(token)

        return tokens

    def validate_token(self, token: str) -> bool:
        """Validate incoming MCP client token."""
        return token in self.valid_tokens

    async def rotate_tokens(self):
        """
        Rotate MCP server tokens (called by background job).

        Process:
        1. Generate new token
        2. Add to valid_tokens in Vault
        3. Notify clients to refresh
        4. After grace period, remove old token
        """
        # Generate new token
        new_token = secrets.token_urlsafe(32)

        # Add to Vault
        current_tokens = self.vault.get_secret("mcp/assurance/valid_tokens")
        current_tokens["tokens"].append(new_token)

        self.vault.client.secrets.kv.v2.create_or_update_secret(
            path="mcp/assurance/valid_tokens",
            secret=current_tokens
        )

        # Update in-memory cache
        self.valid_tokens.add(new_token)

        # Schedule old token removal (after grace period)
        # ... background job removes old token after 24 hours
```

#### 7. Secret Rotation

**Automated Rotation Policies:**

```python
# certus_ops/secret_rotation/rotator.py
import asyncio
from datetime import datetime, timedelta
from certus_common.secrets import VaultClient

class SecretRotator:
    """
    Automated secret rotation for static secrets.

    Dynamic secrets (database, AWS) auto-rotate via TTL.
    This handles static secrets (API keys, tokens).
    """

    def __init__(self):
        self.vault = VaultClient(auth_method="kubernetes", role="secret-rotator")
        self.rotation_policies = {
            "certus/prod/openai": {"interval_days": 90, "notify": ["security@certus.io"]},
            "certus/prod/aws": {"interval_days": 30, "notify": ["devops@certus.io"]},
            "certus/mcp/*/server_token": {"interval_days": 7, "notify": ["agents@certus.io"]},
        }

    async def check_and_rotate(self):
        """Check all secrets and rotate if needed."""

        for secret_path, policy in self.rotation_policies.items():
            # Get secret metadata
            metadata = self.vault.client.secrets.kv.v2.read_secret_metadata(
                path=secret_path.replace("certus/", "")
            )

            created_time = datetime.fromisoformat(
                metadata["data"]["created_time"].replace("Z", "+00:00")
            )

            age_days = (datetime.now() - created_time).days

            if age_days >= policy["interval_days"]:
                await self._rotate_secret(secret_path, policy)

    async def _rotate_secret(self, secret_path: str, policy: dict):
        """Rotate a specific secret."""

        # 1. Generate new secret value
        if "openai" in secret_path:
            # Manual: Admin must generate new API key from OpenAI dashboard
            await self._notify_manual_rotation(secret_path, policy["notify"])
            return

        elif "mcp" in secret_path:
            # Automatic: Generate new MCP token
            new_token = self._generate_token()

            # 2. Store new version in Vault
            self.vault.client.secrets.kv.v2.create_or_update_secret(
                path=secret_path.replace("certus/", ""),
                secret={"server_token": new_token}
            )

            # 3. Notify services to refresh
            await self._notify_services_refresh(secret_path)

            # 4. Log rotation
            logger.info(f"Rotated secret: {secret_path}")

            # 5. Send notification
            await self._notify_rotation_complete(secret_path, policy["notify"])

    async def _notify_manual_rotation(self, secret_path: str, recipients: list):
        """Notify admins that manual rotation is required."""
        # Send email/Slack notification
        pass

    async def _notify_services_refresh(self, secret_path: str):
        """Notify services to refresh their secrets from Vault."""
        # Could use Kubernetes rollout restart or pub/sub
        pass

# Run as CronJob in Kubernetes
# Schedule: Daily at 2am UTC
async def main():
    rotator = SecretRotator()
    await rotator.check_and_rotate()

if __name__ == "__main__":
    asyncio.run(main())
```

**CronJob for rotation:**

```yaml
# secret-rotation-cronjob.yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: secret-rotator
  namespace: certus-tap
spec:
  schedule: "0 2 * * *"  # Daily at 2am UTC
  jobTemplate:
    spec:
      template:
        spec:
          serviceAccountName: secret-rotator
          containers:
          - name: rotator
            image: certus/secret-rotator:latest
            env:
            - name: VAULT_ADDR
              value: "https://vault.certus:8200"
          restartPolicy: OnFailure
```

#### 8. Audit Logging

**Enable Vault audit logging:**

```bash
# Enable file audit backend
vault audit enable file file_path=/vault/audit/audit.log

# Enable syslog audit backend (for centralized logging)
vault audit enable syslog
```

**Audit log format (JSON):**

```json
{
  "time": "2025-12-11T10:30:00Z",
  "type": "response",
  "auth": {
    "client_token": "hmac-sha256:abc...",
    "display_name": "certus-ask",
    "policies": ["certus-ask-policy"],
    "metadata": {
      "role": "certus-ask",
      "service_account_name": "certus-ask",
      "service_account_namespace": "certus-tap"
    }
  },
  "request": {
    "path": "certus/data/prod/openai",
    "operation": "read"
  },
  "response": {
    "secret": {
      "lease_duration": 0
    }
  }
}
```

**Stream to Certus-Insight:**

```python
# certus_ops/audit/vault_audit_streamer.py
import json
from certus_insight.client import InsightClient

class VaultAuditStreamer:
    """Stream Vault audit logs to Certus-Insight."""

    def __init__(self):
        self.insight = InsightClient()

    async def stream_logs(self, audit_log_path: str):
        """Tail audit log and stream to Insight."""

        with open(audit_log_path, 'r') as f:
            # Seek to end
            f.seek(0, 2)

            while True:
                line = f.readline()
                if line:
                    try:
                        log = json.loads(line)
                        await self._process_log(log)
                    except json.JSONDecodeError:
                        continue
                else:
                    await asyncio.sleep(0.1)

    async def _process_log(self, log: dict):
        """Process and index audit log."""

        # Extract key fields
        event = {
            "timestamp": log["time"],
            "service": log["auth"]["display_name"],
            "secret_path": log["request"]["path"],
            "operation": log["request"]["operation"],
            "success": log["type"] == "response"
        }

        # Send to Insight
        await self.insight.index_event(
            index="vault-audit",
            event=event
        )

        # Check for suspicious patterns
        if self._is_suspicious(event):
            await self._alert_security_team(event)

    def _is_suspicious(self, event: dict) -> bool:
        """Detect suspicious access patterns."""

        # Example: Access to production secrets outside business hours
        if "prod" in event["secret_path"]:
            hour = datetime.fromisoformat(event["timestamp"]).hour
            if hour < 6 or hour > 18:  # Outside 6am-6pm
                return True

        return False
```

**Alerts:**

- Unusual access patterns (prod secrets at 3am)
- Failed authentication attempts (>5 in 5 minutes)
- Access from unexpected services
- Secrets nearing expiration

#### 9. Development Workflow

**For developers:**

```bash
# 1. Login to Vault (OIDC via Google Workspace)
vault login -method=oidc role=developer

# Opens browser for OAuth flow
# After auth, token saved to ~/.vault-token

# 2. Access dev/staging secrets
vault kv get certus/dev/database
# Key              Value
# ---              -----
# username         certus_dev
# password         dev_password

# 3. Cannot access production
vault kv get certus/prod/database
# Error: permission denied

# 4. Use secrets in local development
export DATABASE_PASSWORD=$(vault kv get -field=password certus/dev/database)
python -m certus_ask.main
```

**For CI/CD:**

```yaml
# .github/workflows/test.yml
name: Test

on: [push]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Import secrets from Vault
        uses: hashicorp/vault-action@v2
        with:
          url: https://vault.certus.io
          method: approle
          roleId: ${{ secrets.VAULT_ROLE_ID }}
          secretId: ${{ secrets.VAULT_SECRET_ID }}
          secrets: |
            certus/data/ci/database password | DATABASE_PASSWORD ;
            certus/data/ci/openai api_key | OPENAI_API_KEY

      - name: Run tests
        run: pytest
        env:
          DATABASE_PASSWORD: ${{ env.DATABASE_PASSWORD }}
          OPENAI_API_KEY: ${{ env.OPENAI_API_KEY }}
```

## Migration Path

### Phase 1: Vault Deployment (Week 1)

**Goals:**
- Deploy Vault in Kubernetes
- Initialize and unseal
- Enable basic auth methods (Kubernetes, AppRole)

**Tasks:**
1. Deploy Vault using Helm chart
2. Initialize Vault (save unseal keys securely)
3. Enable Kubernetes auth
4. Enable AppRole auth
5. Enable audit logging

**Success Criteria:**
- Vault cluster running (3 replicas)
- Can authenticate via K8s service account
- Audit logs flowing to file

---

### Phase 2: Migrate One Service (Certus-Ask) (Week 2)

**Goals:**
- Migrate Certus-Ask to use Vault for secrets
- Prove the pattern works

**Tasks:**
1. Create KV secrets for Certus-Ask (database, OpenAI, OpenSearch)
2. Enable database secrets engine
3. Create policy for Certus-Ask
4. Create Kubernetes auth role
5. Update Certus-Ask deployment with Vault annotations
6. Test secret injection
7. Verify Certus-Ask starts and functions correctly

**Success Criteria:**
- Certus-Ask runs with Vault-injected secrets
- No hardcoded secrets in deployment YAML
- Audit logs show secret access

---

### Phase 3: Migrate Remaining Services (Weeks 3-4)

**Goals:**
- Migrate all Certus services to Vault

**Services:**
- Certus-Assurance
- Certus-Trust
- Certus-Insight
- Certus-Transform

**Tasks:**
1. Create secrets in Vault for each service
2. Create policies for each service
3. Update deployments with Vault annotations
4. Test each service
5. Remove old secrets from Kubernetes/environment

**Success Criteria:**
- All services using Vault
- No secrets in K8s secrets or .env files

---

### Phase 4: Agent Authentication (Week 5)

**Goals:**
- Enable AAIF agents to authenticate via Vault

**Tasks:**
1. Create MCP server tokens in Vault
2. Create agent policy
3. Update Goose profiles to fetch tokens from Vault
4. Test agent → MCP server authentication
5. Implement token rotation

**Success Criteria:**
- Agents authenticate to MCP servers using Vault tokens
- Tokens rotate automatically

---

### Phase 5: Dynamic Credentials (Week 6)

**Goals:**
- Enable dynamic database and AWS credentials

**Tasks:**
1. Enable database secrets engine (already done in Phase 2, expand)
2. Enable AWS secrets engine
3. Update services to use dynamic credentials
4. Implement lease renewal
5. Test credential rotation (force rotation, verify zero downtime)

**Success Criteria:**
- Database credentials rotate every hour
- AWS credentials rotate every hour
- Zero downtime during rotation

---

### Phase 6: Developer Access & CI/CD (Week 7)

**Goals:**
- Enable developers to access dev/staging secrets
- CI/CD pipelines use Vault

**Tasks:**
1. Enable OIDC auth (Google Workspace)
2. Create developer policy (dev/staging only)
3. Document developer workflow
4. Update CI/CD pipelines (GitHub Actions, etc.)
5. Train developers on Vault usage

**Success Criteria:**
- Developers can access dev/staging secrets via Vault CLI/UI
- Developers cannot access production secrets
- CI/CD pipelines fetch secrets from Vault

---

### Phase 7: Rotation & Monitoring (Week 8)

**Goals:**
- Automated rotation
- Alerting on suspicious access

**Tasks:**
1. Implement SecretRotator (CronJob)
2. Stream audit logs to Certus-Insight
3. Create dashboards in Insight
4. Configure alerts (unusual access, failed auth)
5. Test rotation end-to-end

**Success Criteria:**
- Secrets rotate automatically per policy
- Alerts fire on suspicious access
- Dashboard shows all secret access in real-time

---

## Success Metrics

### Security Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Secrets in version control** | 0 | Git history scan |
| **Secrets in K8s manifests** | 0 | Kubectl get secrets review |
| **Services using Vault** | 100% | Deployment audit |
| **Dynamic credential usage** | 80%+ | Database/AWS credential type |
| **Rotation frequency** | Per policy | Vault audit logs |
| **Failed auth attempts** | <10/day | Vault audit logs |

### Compliance Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Audit log coverage** | 100% | All secret access logged |
| **Access violations detected** | 100% | Alerts on unauthorized access |
| **Secret rotation compliance** | 100% | All secrets rotated per policy |
| **Least privilege enforcement** | 100% | Policy review |

### Operational Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Vault uptime** | 99.9% | Monitoring |
| **Secret fetch latency (p95)** | <100ms | Application metrics |
| **Rotation downtime** | 0 seconds | Zero-downtime rotation |
| **Developer satisfaction** | 4.5/5 | Survey |

## Dependencies

### External Dependencies

- **HashiCorp Vault** (OSS or Enterprise)
- **Kubernetes** (for Vault Agent Injector)
- **Python hvac library** (Vault SDK)
- **PostgreSQL/MySQL** (database secrets engine)
- **AWS/Azure/GCP** (cloud secrets engine, optional)

### Internal Dependencies

- **Authentication & Authorization** - Required for user/service identity
- **Observability Platform** - For audit log streaming and alerting
- **Kubernetes Infrastructure** - For Vault deployment
- **All Certus Services** - Must be updated to use Vault

## Risks & Mitigations

### Risks

1. **Vault Becomes Single Point of Failure**
   - Risk: If Vault is down, services can't start
   - Impact: Complete outage
   - Mitigation: HA deployment (3-5 nodes), Raft storage
   - Mitigation: Cached credentials (services cache secrets for N minutes)
   - Mitigation: Graceful degradation (use last-known credentials)

2. **Unseal Key Management**
   - Risk: Losing unseal keys locks Vault permanently
   - Impact: Lose access to all secrets
   - Mitigation: Store unseal keys in multiple secure locations (1Password, hardware HSM)
   - Mitigation: Use auto-unseal with cloud KMS (AWS KMS, Azure Key Vault)

3. **Secret Sprawl in Vault**
   - Risk: Vault becomes dumping ground for all config (not just secrets)
   - Impact: Harder to manage, slower access
   - Mitigation: Clear policy: Only actual secrets in Vault (not general config)
   - Mitigation: Regular audits of Vault contents

4. **Learning Curve**
   - Risk: Developers unfamiliar with Vault
   - Impact: Slower development, mistakes
   - Mitigation: Training and documentation
   - Mitigation: Self-service tooling (`certus-vault` CLI wrapper)

5. **Migration Complexity**
   - Risk: Difficult to migrate existing secrets
   - Impact: Extended migration timeline
   - Mitigation: Phased migration (one service at a time)
   - Mitigation: Dual-read during migration (fall back to old secrets if Vault fails)

6. **Performance Overhead**
   - Risk: Vault lookups add latency
   - Impact: Slower application startup
   - Mitigation: Caching (services cache secrets for 1 hour)
   - Mitigation: Vault is fast (<10ms for KV reads)

### Non-Risks

- **Cost** - Vault OSS is free, hosting cost is minimal ($50-100/month)
- **Vendor lock-in** - Vault has competitors (AWS Secrets Manager, Azure Key Vault)
- **Data privacy** - Secrets stay in your infrastructure (not cloud)

## Cost Analysis

### Infrastructure Costs

| Component | Cost | Notes |
|-----------|------|-------|
| **Vault OSS (self-hosted)** | $0 | Free software |
| **Compute (K8s)** | ~$50/month | 3 pods × small instances |
| **Storage (Raft)** | ~$10/month | 30GB SSD |
| **Backup** | ~$5/month | S3/cloud backup |
| **Total Monthly** | **~$65/month** | |

**Vault Enterprise (if needed):**
- Namespaces (multi-tenancy): +$0 (price varies by contract)
- Replication: +$0 (price varies)

**HCP Vault (managed):**
- Starter: ~$200/month
- Standard: ~$500/month

**Recommendation:** Start with Vault OSS ($65/month), upgrade to Enterprise/HCP if needed.

### ROI

**Benefits:**
- **Security incidents avoided:** Priceless (one breach could cost $millions)
- **Compliance certification:** Required for SOC2/HIPAA (enables enterprise sales)
- **Developer productivity:** 2 hours/week saved per developer (no manual secret management)
- **Operational toil:** 5 hours/week saved (automated rotation vs. manual)

**Time savings:**
- 10 developers × 2 hours/week = 20 hours/week = $2,000/week (at $100/hr) = **$104K/year**

**ROI:** $104K saved / $780 cost per year = **133x ROI**

## Alternatives Considered

### Alternative 1: AWS Secrets Manager

**Pros:**
- Fully managed (zero ops)
- Native AWS integration
- Automatic rotation for RDS

**Cons:**
- AWS-only (vendor lock-in)
- More expensive ($0.40/secret/month)
- Less flexible than Vault

**Decision:** Vault chosen for vendor neutrality and flexibility

---

### Alternative 2: Azure Key Vault

**Pros:**
- Fully managed
- Native Azure integration
- HSM-backed

**Cons:**
- Azure-only (vendor lock-in)
- Complex pricing
- Less community support

**Decision:** Vault chosen for multi-cloud support

---

### Alternative 3: Kubernetes Secrets (Current)

**Pros:**
- Built-in, no extra infrastructure
- Simple to use

**Cons:**
- No audit logging
- No rotation
- No dynamic credentials
- Base64 encoding (not encryption by default)

**Decision:** Not suitable for production security requirements

---

### Alternative 4: SOPS (Secrets OPerationS)

**Pros:**
- Git-friendly (encrypted files in repo)
- Simple workflow

**Cons:**
- No dynamic credentials
- No audit logging
- Manual rotation
- Not designed for runtime secret injection

**Decision:** Good for GitOps config, not infrastructure secrets

---

**Final Decision: HashiCorp Vault** for centralized, auditable, dynamic secret management.

## Next Steps

### Immediate Actions (Week 1)

1. ✅ Review and approve this enhancement
2. ✅ Assign engineering owner (1 platform engineer)
3. ✅ Provision Kubernetes cluster resources for Vault
4. ✅ Decide: Vault OSS vs Enterprise vs HCP
5. ✅ Set up secure storage for unseal keys (1Password, HSM)

### Phase 1 Kickoff (Week 1)

1. Deploy Vault to Kubernetes (Helm chart)
2. Initialize and unseal Vault
3. Enable Kubernetes auth
4. Enable audit logging
5. Create first policy (certus-ask-policy)
6. Document Vault access procedures

### Communication Plan

1. **Internal:**
   - Present enhancement to engineering team
   - Training: "Vault 101" workshop for developers
   - Documentation: Developer guide, runbooks
   - Weekly updates during migration

2. **Security Team:**
   - Demo audit logging capabilities
   - Review rotation policies
   - Validate compliance controls

### Success Criteria for Approval

- [ ] Strategic alignment (foundational for production, AAIF, compliance)
- [ ] Architecture is sound (HA, secure, scalable)
- [ ] Migration path is realistic (8 weeks phased approach)
- [ ] ROI is compelling (133x based on time savings + security)
- [ ] Cost is acceptable (~$65/month for OSS)
- [ ] Risks are understood and mitigated
- [ ] Resource allocation approved (1 platform engineer, infrastructure)

---

## Appendix A: Vault Commands Cheat Sheet

### Administration

```bash
# Check Vault status
vault status

# Unseal Vault (requires 3 of 5 keys)
vault operator unseal <key>

# Enable audit logging
vault audit enable file file_path=/vault/audit/audit.log

# List auth methods
vault auth list

# List secrets engines
vault secrets list

# List policies
vault policy list
```

### Secret Operations

```bash
# Write secret (KV v2)
vault kv put certus/prod/database username=user password=pass

# Read secret
vault kv get certus/prod/database

# Read specific field
vault kv get -field=password certus/prod/database

# List secrets
vault kv list certus/prod

# Delete secret
vault kv delete certus/prod/database

# Get secret metadata (versions, timestamps)
vault kv metadata get certus/prod/database
```

### Dynamic Credentials

```bash
# Get database credentials (1 hour TTL)
vault read database/creds/certus-ask

# Get AWS credentials
vault read aws/creds/certus-s3-access

# Renew lease
vault lease renew database/creds/certus-ask/abc123

# Revoke lease
vault lease revoke database/creds/certus-ask/abc123
```

### Authentication

```bash
# Login with Kubernetes auth
vault write auth/kubernetes/login role=certus-ask jwt=<service-account-token>

# Login with AppRole
vault write auth/approle/login role_id=<id> secret_id=<secret>

# Login with OIDC (developer)
vault login -method=oidc role=developer

# Login with token (dev only)
vault login <token>
```

---

## Appendix B: Example Vault Policies

### Certus-Assurance Policy

```hcl
# certus-assurance-policy.hcl

# Read static secrets
path "certus/data/prod/database" {
  capabilities = ["read"]
}

path "certus/data/prod/aws" {
  capabilities = ["read"]
}

path "certus/data/prod/neo4j" {
  capabilities = ["read"]
}

# Generate dynamic database credentials
path "database/creds/certus-assurance" {
  capabilities = ["read"]
}

# Generate dynamic AWS credentials
path "aws/creds/certus-s3-access" {
  capabilities = ["read"]
}

# Renew leases
path "sys/leases/renew" {
  capabilities = ["update"]
}

# Deny access to other services
path "certus/data/prod/ask/*" {
  capabilities = ["deny"]
}

path "certus/data/prod/insight/*" {
  capabilities = ["deny"]
}
```

---

## Appendix C: Vault High Availability

### Raft Storage (Integrated Storage)

**Architecture:**

```
Vault Cluster (Raft)
├─ vault-0 (Leader)
├─ vault-1 (Follower)
└─ vault-2 (Follower)

Writes → Leader → Replicated to Followers
Reads → Any node
```

**Auto-failover:**
- If Leader fails, new Leader elected (seconds)
- No data loss (quorum-based)
- Clients automatically redirect to new Leader

**Backup:**

```bash
# Take snapshot (automated via CronJob)
vault operator raft snapshot save backup.snap

# Restore from snapshot
vault operator raft snapshot restore backup.snap
```

**Disaster Recovery:**
- Daily snapshots to S3/cloud storage
- Retention: 30 days
- Tested restore procedure (monthly DR drill)

---

**End of Enhancement Proposal**
