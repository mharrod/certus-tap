# Runtime Policy Engine

**Status:** Draft
**Author:** DevOps/RAG Agent
**Date:** 2025-12-11
## Executive Summary

The Runtime Policy Engine provides centralized, declarative policy-as-code for runtime authorization decisions across all Certus TAP services. While the Assurance Manifest governs build-time compliance and testing policies, the Runtime Policy Engine governs who can do what at runtime: API access control, data governance, agent behavior boundaries, resource quotas, and cross-service authorization.

Using **Open Policy Agent (OPA)** as the policy evaluation engine, Certus TAP services, AAIF agents, and infrastructure components query the policy engine for authorization decisions. Policies are written in **Rego** (OPA's declarative language), versioned in Git, and distributed to services via OPA's bundle mechanism. The engine integrates with:

- **Certus TAP Services** (Assurance, Trust, Insight, Ask, Transform): API-level authorization
- **AAIF Agents**: Agent behavior policies (which MCP servers/tools agents can access)
- **Vault**: Secret access policies (who can read which secrets)
- **Data Layer**: Data governance policies (PII handling, retention, classification)
- **Multi-tenancy**: Tenant isolation and resource quota enforcement
- **Assurance Manifest**: Compliance-driven policies (e.g., "if HIPAA manifest, enforce data classification")

The Runtime Policy Engine provides:
- **Fine-grained authorization**: Beyond role-based access control (RBAC) to attribute-based (ABAC)
- **Centralized policy management**: Single source of truth for all authorization logic
- **Audit trails**: Every policy decision is logged for compliance
- **Dynamic policy updates**: Policy changes deploy without service restarts
- **Policy testing**: Unit test policies before deployment

## Motivation

### Current State Challenges

1. **Scattered Authorization Logic**
   - Each Certus service implements its own authorization checks
   - Inconsistent enforcement across services
   - Hard to audit "who can access what" across the platform
   - Code changes required for policy updates

2. **Agent Security Gaps**
   - AAIF agents need bounded permissions (principle of least privilege)
   - No centralized way to control which MCP servers/tools agents can access
   - Risk of agent escalation or lateral movement

3. **Data Governance Needs**
   - HIPAA/SOC2 require data classification and access controls
   - No unified way to enforce "PII cannot leave certain boundaries"
   - Compliance requirements vary by tenant/customer

4. **Multi-Tenancy Isolation**
   - Tenant data must be strictly isolated
   - Resource quotas need enforcement (API rate limits, storage)
   - Cross-tenant access must be explicitly allowed (not default-deny)

5. **Compliance Integration**
   - Assurance Manifest declares compliance requirements
   - But no runtime enforcement of compliance-driven policies
   - Example: If manifest declares HIPAA, all data access should be logged and classified

### Why Open Policy Agent (OPA)?

**Selected over alternatives** (AWS Cedar, Casbin, custom):

| Capability | OPA | Cedar | Casbin | Custom |
|------------|-----|-------|--------|--------|
| Cloud-neutral | ✅ | ❌ (AWS-centric) | ✅ | ✅ |
| Declarative language | ✅ Rego | ✅ Cedar | ⚠️ Config-based | ❌ Code |
| Policy testing | ✅ Built-in | ✅ Built-in | ⚠️ Limited | ❌ Manual |
| Community/ecosystem | ✅ CNCF | ⚠️ New | ⚠️ Smaller | ❌ None |
| Performance | ✅ High | ✅ High | ✅ High | ⚠️ Varies |
| Learning curve | ⚠️ Moderate | ⚠️ Moderate | ✅ Low | ❌ High |
| Integration maturity | ✅ Kubernetes, Envoy, etc. | ⚠️ Growing | ⚠️ Limited | ❌ DIY |

**OPA chosen because:**
- CNCF graduated project with strong community
- Vendor-neutral (aligns with Certus positioning)
- Rich ecosystem (Kubernetes admission control, service mesh, API gateways)
- Powerful Rego language for complex policies
- Built-in policy testing and validation
- Battle-tested at scale (Netflix, Pinterest, Chef)

## Goals & Non-Goals

| Goals | Non-Goals |
|-------|-----------|
| Centralized runtime authorization for all Certus services | Replace Assurance Manifest (build-time policies) |
| Fine-grained access control (RBAC, ABAC, relationship-based) | Implement authentication (handled by Auth proposal) |
| Agent behavior policies (AAIF agents → MCP servers) | Replace Vault ACLs (integrate with, not replace) |
| Data governance (PII classification, retention, redaction) | Build a policy authoring UI (Git-based workflow) |
| Multi-tenant isolation and resource quotas | Enforce policies in application code (externalize) |
| Compliance-driven policies (manifest integration) | Support non-OPA policy languages |
| Audit logging of all authorization decisions | Replace API gateway functionality |
| Policy versioning, testing, and rollback | Implement rate limiting (use existing tools) |

## Proposed Solution

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Policy Repository (Git)                   │
│  ├─ policies/                                                    │
│  │  ├─ api/          (Service API authorization)                │
│  │  ├─ agents/       (AAIF agent behavior policies)             │
│  │  ├─ data/         (Data governance, PII, retention)          │
│  │  ├─ secrets/      (Vault integration policies)               │
│  │  ├─ tenancy/      (Multi-tenant isolation, quotas)           │
│  │  └─ compliance/   (Manifest-driven policies)                 │
│  ├─ tests/           (Policy unit tests)                        │
│  └─ bundles/         (Compiled policy bundles)                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ CI/CD (build bundles, test)
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                    OPA Bundle Distribution                       │
│  (S3/OCI Registry/HTTP Server)                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Pull bundles (polling/webhooks)
                              ↓
┌──────────────────┬──────────────────┬──────────────────────────┐
│  OPA Sidecar     │  OPA Sidecar     │  OPA Sidecar            │
│  (Assurance)     │  (Trust)         │  (Insight)              │
├──────────────────┼──────────────────┼──────────────────────────┤
│  Certus          │  Certus          │  Certus                 │
│  Assurance       │  Trust           │  Insight                │
│  Service         │  Service         │  Service                │
└──────────────────┴──────────────────┴──────────────────────────┘
         ↑                  ↑                    ↑
         │                  │                    │
         │ Authorization queries (HTTP/gRPC)     │
         │                  │                    │
┌────────┴──────────────────┴────────────────────┴───────────────┐
│                       API Clients                               │
│  ├─ AAIF Agents (Goose, SK, AutoGen)                           │
│  ├─ Web UI (Conversational Interface)                          │
│  ├─ CLI (certus-cli)                                           │
│  └─ External Services (Partner integrations)                   │
└─────────────────────────────────────────────────────────────────┘
```

### Deployment Model

**OPA Sidecar Pattern** (recommended for Kubernetes):
- Each Certus service pod includes an OPA sidecar container
- Service calls `localhost:8181/v1/data/<policy>` for authorization decisions
- Low latency (<5ms), high availability (local evaluation)
- Policies cached in-memory, updated via bundle pulls

**Alternative: Centralized OPA Cluster** (for non-K8s or shared policy server):
- Dedicated OPA cluster behind load balancer
- Services call centralized OPA via HTTP/gRPC
- Higher latency (~20-50ms), but simpler deployment
- Useful for legacy services or serverless functions

### Policy Structure

Policies organized by domain in Git repository:

```
policies/
├── api/
│   ├── assurance.rego          # Certus Assurance API policies
│   ├── trust.rego              # Certus Trust API policies
│   ├── insight.rego            # Certus Insight API policies
│   ├── ask.rego                # Certus Ask API policies
│   └── transform.rego          # Certus Transform API policies
├── agents/
│   ├── mcp_access.rego         # Which agents can access which MCP servers
│   ├── tool_permissions.rego   # Which tools agents can invoke
│   └── resource_limits.rego    # Agent resource quotas
├── data/
│   ├── classification.rego     # Data classification (PII, PHI, sensitive)
│   ├── retention.rego          # Data retention policies
│   └── redaction.rego          # PII redaction rules
├── secrets/
│   ├── vault_integration.rego  # Vault policy integration
│   └── secret_access.rego      # Who can access which secrets
├── tenancy/
│   ├── isolation.rego          # Tenant data isolation
│   ├── quotas.rego             # Resource quotas per tenant
│   └── cross_tenant.rego       # Cross-tenant access rules
└── compliance/
    ├── manifest_driven.rego    # Policies derived from Assurance Manifest
    ├── hipaa.rego              # HIPAA-specific policies
    └── soc2.rego               # SOC2-specific policies
```

### Policy Examples

#### Example 1: Service API Authorization

**File:** `policies/api/assurance.rego`

```rego
package certus.api.assurance

import future.keywords.if
import future.keywords.in

# Default deny
default allow = false

# Allow admins full access
allow if {
    input.user.role == "admin"
}

# Allow users to read their own scan results
allow if {
    input.method == "GET"
    input.path == ["scans", scan_id]
    input.user.tenant == data.scans[scan_id].tenant
}

# Allow users to create scans for their own repositories
allow if {
    input.method == "POST"
    input.path == ["scans"]
    input.body.repository.owner == input.user.username
}

# Allow users with "security-reviewer" role to read all scans in their tenant
allow if {
    input.method == "GET"
    startswith(input.path[0], "scans")
    "security-reviewer" in input.user.roles
    input.tenant == input.user.tenant
}

# Audit all denied requests
deny_reason[msg] if {
    not allow
    msg := sprintf("User %s denied access to %s %s", [
        input.user.username,
        input.method,
        concat("/", input.path)
    ])
}
```

#### Example 2: AAIF Agent MCP Access Control

**File:** `policies/agents/mcp_access.rego`

```rego
package certus.agents.mcp

import future.keywords.if
import future.keywords.in

# Default deny
default allow_mcp_access = false

# Agent metadata structure expected:
# {
#   "agent": {
#     "id": "goose-instance-123",
#     "type": "goose",
#     "user": "alice@example.com",
#     "tenant": "acme-corp"
#   },
#   "mcp_server": "certus-assurance",
#   "tool": "scan_repository",
#   "context": {...}
# }

# Allow agents to access Assurance MCP if user has scanning permissions
allow_mcp_access if {
    input.mcp_server == "certus-assurance"
    user_has_permission(input.agent.user, "scan:create")
}

# Allow agents to access Trust MCP only for their own tenant's artifacts
allow_mcp_access if {
    input.mcp_server == "certus-trust"
    input.tool in ["verify_attestation", "get_provenance"]
    input.context.artifact.tenant == input.agent.tenant
}

# Allow agents to access Insight MCP for querying vulnerability data
allow_mcp_access if {
    input.mcp_server == "certus-insight"
    input.tool in ["query_vulnerabilities", "get_remediation"]
    user_has_permission(input.agent.user, "vulnerability:read")
}

# Deny access to Transform MCP for agents (only direct API access allowed)
allow_mcp_access = false if {
    input.mcp_server == "certus-transform"
}

# Helper function to check user permissions
user_has_permission(user, permission) if {
    user_data := data.users[user]
    permission in user_data.permissions
}

# Audit all MCP access attempts
audit_log[entry] if {
    entry := {
        "timestamp": time.now_ns(),
        "agent": input.agent,
        "mcp_server": input.mcp_server,
        "tool": input.tool,
        "allowed": allow_mcp_access,
        "policy_version": data.policy_metadata.version
    }
}
```

#### Example 3: Data Classification & PII Handling

**File:** `policies/data/classification.rego`

```rego
package certus.data.classification

import future.keywords.if
import future.keywords.in

# Classify data based on content and context
classification[result] if {
    # Check for PII patterns
    contains_pii := detect_pii(input.data)

    # Check for PHI (Protected Health Information) if HIPAA manifest
    contains_phi := detect_phi(input.data)
    has_hipaa_manifest := manifest_requires_hipaa(input.context.manifest)

    # Determine classification level
    level := classification_level(contains_pii, contains_phi, has_hipaa_manifest)

    result := {
        "level": level,
        "requires_encryption": requires_encryption(level),
        "retention_days": retention_days(level),
        "allowed_regions": allowed_regions(level, input.context.tenant),
        "redaction_required": redaction_required(level, input.context.purpose)
    }
}

# Detect PII patterns
detect_pii(data) if {
    # Email addresses
    regex.match(`\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`, data)
}

detect_pii(data) if {
    # SSN patterns
    regex.match(`\b\d{3}-\d{2}-\d{4}\b`, data)
}

detect_pii(data) if {
    # Credit card numbers
    regex.match(`\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b`, data)
}

# Detect PHI patterns
detect_phi(data) if {
    # Medical record numbers
    regex.match(`\bMRN[-:]?\s*\d+\b`, data)
}

detect_phi(data) if {
    # ICD codes
    regex.match(`\b[A-Z]\d{2}(\.\d{1,2})?\b`, data)
}

# Check if manifest requires HIPAA compliance
manifest_requires_hipaa(manifest_digest) if {
    manifest := data.manifests[manifest_digest]
    some outcome in manifest.compliance
    some control in outcome.controls
    control.framework == "HIPAA"
}

# Determine classification level
classification_level(pii, phi, hipaa) := "restricted" if {
    phi
    hipaa
}

classification_level(pii, phi, hipaa) := "confidential" if {
    pii
    not phi
}

classification_level(pii, phi, hipaa) := "internal" if {
    not pii
    not phi
}

# Encryption requirements
requires_encryption(level) := true if level in ["restricted", "confidential"]
requires_encryption(level) := false if level == "internal"

# Retention policies
retention_days("restricted") := 2555  # 7 years (HIPAA requirement)
retention_days("confidential") := 1825  # 5 years
retention_days("internal") := 365  # 1 year

# Allowed regions for data storage
allowed_regions("restricted", tenant) := regions if {
    tenant_config := data.tenants[tenant]
    regions := tenant_config.data_residency.allowed_regions
}

allowed_regions(level, _) := ["us-east-1", "us-west-2", "eu-west-1"] if {
    level != "restricted"
}

# Redaction requirements
redaction_required("restricted", purpose) := true if {
    purpose != "authorized_audit"
}

redaction_required("confidential", purpose) := true if {
    purpose == "analytics"
}

redaction_required(_, _) := false
```

#### Example 4: Manifest-Driven Compliance Policies

**File:** `policies/compliance/manifest_driven.rego`

```rego
package certus.compliance.manifest

import future.keywords.if
import future.keywords.in

# Enforce policies based on Assurance Manifest declarations

# If manifest declares HIPAA, all data access must be logged
require_audit_logging if {
    manifest := data.manifests[input.manifest_digest]
    some outcome in manifest.compliance
    some control in outcome.controls
    control.framework == "HIPAA"
}

# If manifest declares SOC2 CC7.2 (access control), enforce MFA
require_mfa if {
    manifest := data.manifests[input.manifest_digest]
    some outcome in manifest.compliance
    some control in outcome.controls
    control.framework == "SOC2"
    control.controlId == "CC7.2"
}

# If manifest includes privacy tests, enforce data minimization
require_data_minimization if {
    manifest := data.manifests[input.manifest_digest]
    some profile in manifest.profiles
    some tool in profile.tools
    tool.id == "privacySample"
}

# Enforce encryption for restricted data based on manifest
enforce_encryption_policy[decision] if {
    require_audit_logging

    decision := {
        "encrypt_at_rest": true,
        "encrypt_in_transit": true,
        "key_rotation_days": 90,
        "audit_all_access": true,
        "mfa_required": require_mfa
    }
}

# Validate that scan bundles meet manifest thresholds
bundle_meets_thresholds if {
    manifest := data.manifests[input.bundle.manifest_digest]
    profile := [p | p := manifest.profiles[_]; p.name == input.bundle.profile][0]

    # Check critical findings
    input.bundle.findings.critical <= profile.thresholds.critical

    # Check high findings
    input.bundle.findings.high <= profile.thresholds.high

    # Check medium findings
    input.bundle.findings.medium <= profile.thresholds.medium
}

# Determine required evidence based on manifest
required_evidence[evidence] if {
    manifest := data.manifests[input.manifest_digest]
    some outcome in manifest.compliance
    some control in outcome.controls
    some test in control.tests
    some evidence_type in test.evidence

    evidence := {
        "framework": control.framework,
        "control_id": control.controlId,
        "test_name": test.name,
        "evidence_type": evidence_type,
        "linked_profile": test.linkedProfile
    }
}
```

#### Example 5: Multi-Tenant Isolation & Quotas

**File:** `policies/tenancy/isolation.rego`

```rego
package certus.tenancy.isolation

import future.keywords.if
import future.keywords.in

# Default deny cross-tenant access
default allow_cross_tenant = false

# Allow cross-tenant access only if explicitly permitted
allow_cross_tenant if {
    # Check if source tenant has permission to access target tenant
    source_tenant := input.source.tenant
    target_tenant := input.target.tenant

    tenant_config := data.tenants[source_tenant]
    target_tenant in tenant_config.cross_tenant_access.allowed_tenants
}

# Allow cross-tenant access for shared artifacts (e.g., public SBOM)
allow_cross_tenant if {
    input.target.resource_type == "artifact"
    artifact := data.artifacts[input.target.resource_id]
    artifact.visibility == "public"
}

# Enforce tenant data isolation for database queries
enforce_tenant_filter[filter] if {
    filter := {
        "tenant_id": input.user.tenant,
        "required": true,
        "error_if_missing": "Tenant isolation violation"
    }
}

# Resource quotas per tenant
quota_exceeded(resource_type) if {
    tenant := input.user.tenant
    tenant_config := data.tenants[tenant]

    current_usage := data.usage[tenant][resource_type]
    quota := tenant_config.quotas[resource_type]

    current_usage >= quota
}

# Check specific quota types
scans_quota_exceeded if quota_exceeded("scans_per_month")
storage_quota_exceeded if quota_exceeded("storage_gb")
api_calls_quota_exceeded if quota_exceeded("api_calls_per_day")

# Allow action if quotas not exceeded
allow_within_quota if {
    not scans_quota_exceeded
    not storage_quota_exceeded
    not api_calls_quota_exceeded
}

# Quota enforcement response
quota_enforcement[response] if {
    response := {
        "allowed": allow_within_quota,
        "quotas": {
            "scans": {
                "exceeded": scans_quota_exceeded,
                "current": data.usage[input.user.tenant].scans_per_month,
                "limit": data.tenants[input.user.tenant].quotas.scans_per_month
            },
            "storage": {
                "exceeded": storage_quota_exceeded,
                "current": data.usage[input.user.tenant].storage_gb,
                "limit": data.tenants[input.user.tenant].quotas.storage_gb
            },
            "api_calls": {
                "exceeded": api_calls_quota_exceeded,
                "current": data.usage[input.user.tenant].api_calls_per_day,
                "limit": data.tenants[input.user.tenant].quotas.api_calls_per_day
            }
        }
    }
}
```

### Service Integration

#### Python SDK for Certus Services

**File:** `certus_common/policy/opa_client.py`

```python
from typing import Dict, Any, Optional
import httpx
import structlog

logger = structlog.get_logger()


class OPAClient:
    """Client for querying OPA for authorization decisions."""

    def __init__(
        self,
        opa_url: str = "http://localhost:8181",
        timeout: float = 5.0,
        cache_ttl: int = 300
    ):
        self.opa_url = opa_url
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)
        self._cache: Dict[str, Any] = {}

    async def query(
        self,
        policy_path: str,
        input_data: Dict[str, Any],
        use_cache: bool = True
    ) -> Dict[str, Any]:
        """
        Query OPA for a policy decision.

        Args:
            policy_path: Policy path (e.g., "certus/api/assurance/allow")
            input_data: Input data for policy evaluation
            use_cache: Whether to use cached results

        Returns:
            Policy decision result
        """
        cache_key = f"{policy_path}:{hash(str(input_data))}"

        if use_cache and cache_key in self._cache:
            logger.debug("opa.cache_hit", policy_path=policy_path)
            return self._cache[cache_key]

        try:
            response = await self.client.post(
                f"{self.opa_url}/v1/data/{policy_path.replace('.', '/')}",
                json={"input": input_data}
            )
            response.raise_for_status()

            result = response.json()["result"]

            if use_cache:
                self._cache[cache_key] = result

            logger.info(
                "opa.query",
                policy_path=policy_path,
                allowed=result.get("allow", False)
            )

            return result

        except httpx.HTTPError as e:
            logger.error(
                "opa.query_failed",
                policy_path=policy_path,
                error=str(e)
            )
            # Fail closed: deny by default
            return {"allow": False, "error": str(e)}

    async def allow(
        self,
        policy_path: str,
        input_data: Dict[str, Any]
    ) -> bool:
        """
        Check if action is allowed by policy.

        Args:
            policy_path: Policy path
            input_data: Input data for policy evaluation

        Returns:
            True if allowed, False otherwise
        """
        result = await self.query(policy_path, input_data)
        return result.get("allow", False)

    async def classify_data(
        self,
        data: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Classify data using data classification policy.

        Args:
            data: Data to classify
            context: Context (manifest, tenant, purpose, etc.)

        Returns:
            Classification result with level, encryption, retention, etc.
        """
        result = await self.query(
            "certus.data.classification.classification",
            {"data": data, "context": context}
        )
        return result

    async def check_quota(
        self,
        user: Dict[str, Any],
        resource_type: str
    ) -> Dict[str, Any]:
        """
        Check if user is within quota for resource type.

        Args:
            user: User information (tenant, username, etc.)
            resource_type: Resource type (scans, storage, api_calls)

        Returns:
            Quota enforcement result
        """
        result = await self.query(
            "certus.tenancy.isolation.quota_enforcement",
            {"user": user, "resource_type": resource_type}
        )
        return result

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# FastAPI dependency for OPA client
async def get_opa_client() -> OPAClient:
    """FastAPI dependency to get OPA client."""
    return OPAClient()
```

#### FastAPI Middleware for Authorization

**File:** `certus_common/middleware/authorization.py`

```python
from fastapi import Request, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any, Optional
import structlog

from certus_common.policy.opa_client import OPAClient, get_opa_client

logger = structlog.get_logger()
security = HTTPBearer()


async def authorize_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    opa: OPAClient = Depends(get_opa_client)
) -> Dict[str, Any]:
    """
    Authorize incoming request using OPA.

    Returns user context if authorized, raises HTTPException otherwise.
    """
    # Extract user from JWT (assuming auth middleware already validated)
    user = request.state.user

    # Build OPA input
    input_data = {
        "method": request.method,
        "path": request.url.path.strip("/").split("/"),
        "user": {
            "username": user.username,
            "tenant": user.tenant,
            "role": user.role,
            "roles": user.roles,
        },
        "tenant": user.tenant,
    }

    # Add request body for POST/PUT/PATCH
    if request.method in ["POST", "PUT", "PATCH"]:
        try:
            body = await request.json()
            input_data["body"] = body
        except Exception:
            pass

    # Determine policy path based on service
    service = request.app.title.lower().replace("certus ", "")
    policy_path = f"certus.api.{service}.allow"

    # Query OPA
    allowed = await opa.allow(policy_path, input_data)

    if not allowed:
        logger.warning(
            "authorization.denied",
            user=user.username,
            tenant=user.tenant,
            method=request.method,
            path=request.url.path
        )
        raise HTTPException(
            status_code=403,
            detail="Access denied by policy"
        )

    logger.info(
        "authorization.allowed",
        user=user.username,
        tenant=user.tenant,
        method=request.method,
        path=request.url.path
    )

    return user


# Example usage in FastAPI route
from fastapi import APIRouter, Depends

router = APIRouter()


@router.post("/scans")
async def create_scan(
    scan_request: ScanRequest,
    user: Dict = Depends(authorize_request),
    opa: OPAClient = Depends(get_opa_client)
):
    """Create a new scan (policy-enforced)."""

    # Check quota before creating scan
    quota_result = await opa.check_quota(
        user=user,
        resource_type="scans_per_month"
    )

    if not quota_result.get("allowed", False):
        raise HTTPException(
            status_code=429,
            detail="Scan quota exceeded",
            headers={"X-Quota-Info": str(quota_result["quotas"])}
        )

    # Proceed with scan creation
    # ...
```

#### AAIF Agent Integration

**File:** `certus_agents/policy/mcp_policy_enforcer.py`

```python
from typing import Dict, Any, Optional
import structlog

from certus_common.policy.opa_client import OPAClient

logger = structlog.get_logger()


class MCPPolicyEnforcer:
    """Enforce OPA policies for AAIF agent MCP access."""

    def __init__(self, opa_client: OPAClient):
        self.opa = opa_client

    async def authorize_mcp_call(
        self,
        agent_id: str,
        agent_type: str,
        user: str,
        tenant: str,
        mcp_server: str,
        tool: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Authorize AAIF agent MCP server access.

        Args:
            agent_id: Unique agent instance ID
            agent_type: Agent type (goose, semantic-kernel, autogen)
            user: User who invoked the agent
            tenant: Tenant context
            mcp_server: MCP server name (certus-assurance, certus-trust, etc.)
            tool: Tool/method being called
            context: Additional context (artifact info, etc.)

        Returns:
            True if allowed, False otherwise
        """
        input_data = {
            "agent": {
                "id": agent_id,
                "type": agent_type,
                "user": user,
                "tenant": tenant,
            },
            "mcp_server": mcp_server,
            "tool": tool,
            "context": context or {}
        }

        allowed = await self.opa.allow(
            "certus.agents.mcp.allow_mcp_access",
            input_data
        )

        if not allowed:
            logger.warning(
                "mcp.access_denied",
                agent_id=agent_id,
                agent_type=agent_type,
                user=user,
                mcp_server=mcp_server,
                tool=tool
            )

        return allowed


# Goose agent integration example
# (Integration point in Goose runtime or MCP client wrapper)

class PolicyEnforcedMCPClient:
    """MCP client wrapper with OPA policy enforcement."""

    def __init__(
        self,
        mcp_client,
        policy_enforcer: MCPPolicyEnforcer,
        agent_id: str,
        agent_type: str,
        user: str,
        tenant: str
    ):
        self.mcp_client = mcp_client
        self.enforcer = policy_enforcer
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.user = user
        self.tenant = tenant

    async def call_tool(
        self,
        server: str,
        tool: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """Call MCP tool with policy enforcement."""

        # Check policy before calling
        allowed = await self.enforcer.authorize_mcp_call(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            user=self.user,
            tenant=self.tenant,
            mcp_server=server,
            tool=tool,
            context={"arguments": arguments}
        )

        if not allowed:
            raise PermissionError(
                f"Policy denied {self.agent_type} agent access to "
                f"{server}/{tool}"
            )

        # Call underlying MCP client
        return await self.mcp_client.call_tool(server, tool, arguments)
```

### Policy Bundle Management

#### CI/CD Pipeline for Policies

**File:** `.github/workflows/opa-policies.yml`

```yaml
name: OPA Policy CI/CD

on:
  push:
    branches: [main, develop]
    paths:
      - 'policies/**'
      - 'tests/policies/**'
  pull_request:
    paths:
      - 'policies/**'
      - 'tests/policies/**'

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install OPA
        run: |
          curl -L -o opa https://openpolicyagent.org/downloads/latest/opa_linux_amd64
          chmod +x opa
          sudo mv opa /usr/local/bin/

      - name: Run policy tests
        run: |
          cd policies
          opa test . -v

      - name: Validate policies
        run: |
          cd policies
          opa check .

      - name: Build policy bundle
        if: github.ref == 'refs/heads/main'
        run: |
          opa build -b policies/ -o bundles/bundle.tar.gz

      - name: Upload bundle to S3
        if: github.ref == 'refs/heads/main'
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
        run: |
          aws s3 cp bundles/bundle.tar.gz \
            s3://certus-opa-bundles/production/bundle-$(date +%s).tar.gz

          # Update latest pointer
          aws s3 cp bundles/bundle.tar.gz \
            s3://certus-opa-bundles/production/bundle-latest.tar.gz

      - name: Notify deployment
        if: github.ref == 'refs/heads/main'
        run: |
          # Trigger OPA sidecar bundle refresh via webhook
          # (OPA sidecars poll S3 every 60s, or use webhook for immediate update)
          curl -X POST https://opa-webhook.certus.internal/refresh
```

#### Policy Testing Example

**File:** `tests/policies/api/assurance_test.rego`

```rego
package certus.api.assurance

import future.keywords.if

# Test admin access
test_admin_full_access if {
    allow with input as {
        "user": {"role": "admin", "username": "admin"},
        "method": "GET",
        "path": ["scans", "123"]
    }
}

# Test user can read their own scans
test_user_read_own_scan if {
    allow with input as {
        "user": {"role": "user", "username": "alice", "tenant": "acme"},
        "method": "GET",
        "path": ["scans", "scan-456"],
        "tenant": "acme"
    } with data.scans as {
        "scan-456": {"tenant": "acme", "owner": "alice"}
    }
}

# Test user cannot read other tenant's scans
test_user_cannot_read_other_tenant if {
    not allow with input as {
        "user": {"role": "user", "username": "alice", "tenant": "acme"},
        "method": "GET",
        "path": ["scans", "scan-789"],
        "tenant": "acme"
    } with data.scans as {
        "scan-789": {"tenant": "widgetco", "owner": "bob"}
    }
}

# Test security-reviewer role can read all scans in tenant
test_reviewer_read_all_tenant_scans if {
    allow with input as {
        "user": {
            "role": "user",
            "roles": ["security-reviewer"],
            "username": "reviewer",
            "tenant": "acme"
        },
        "method": "GET",
        "path": ["scans"],
        "tenant": "acme"
    }
}

# Test user can create scans for their own repos
test_user_create_own_repo_scan if {
    allow with input as {
        "user": {"role": "user", "username": "alice", "tenant": "acme"},
        "method": "POST",
        "path": ["scans"],
        "body": {
            "repository": {"owner": "alice", "name": "my-repo"}
        }
    }
}

# Test user cannot create scans for other users' repos
test_user_cannot_create_other_repo_scan if {
    not allow with input as {
        "user": {"role": "user", "username": "alice", "tenant": "acme"},
        "method": "POST",
        "path": ["scans"],
        "body": {
            "repository": {"owner": "bob", "name": "bobs-repo"}
        }
    }
}
```

### OPA Deployment Configuration

#### Kubernetes Deployment (Sidecar Pattern)

**File:** `k8s/certus-assurance-deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: certus-assurance
  namespace: certus
spec:
  replicas: 3
  selector:
    matchLabels:
      app: certus-assurance
  template:
    metadata:
      labels:
        app: certus-assurance
    spec:
      serviceAccountName: certus-assurance

      containers:
      # Main Certus Assurance service
      - name: assurance
        image: certus/assurance:latest
        ports:
          - containerPort: 8000
        env:
          - name: OPA_URL
            value: "http://localhost:8181"
          - name: DATABASE_URL
            valueFrom:
              secretKeyRef:
                name: certus-db-credentials
                key: url
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"

      # OPA sidecar
      - name: opa
        image: openpolicyagent/opa:latest
        ports:
          - containerPort: 8181
        args:
          - "run"
          - "--server"
          - "--addr=0.0.0.0:8181"
          - "--config-file=/config/opa-config.yaml"
        volumeMounts:
          - name: opa-config
            mountPath: /config
          - name: opa-policies
            mountPath: /policies
        resources:
          requests:
            memory: "256Mi"
            cpu: "100m"
          limits:
            memory: "512Mi"
            cpu: "500m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8181
          initialDelaySeconds: 10
          periodSeconds: 10
        readinessProbe:
          httpGet:
            path: /health?bundle=true
            port: 8181
          initialDelaySeconds: 5
          periodSeconds: 5

      volumes:
      - name: opa-config
        configMap:
          name: opa-config
      - name: opa-policies
        emptyDir: {}

---
apiVersion: v1
kind: ConfigMap
metadata:
  name: opa-config
  namespace: certus
data:
  opa-config.yaml: |
    services:
      s3:
        url: https://s3.us-east-1.amazonaws.com
        credentials:
          s3_signing:
            environment_credentials: {}

    bundles:
      certus:
        service: s3
        resource: certus-opa-bundles/production/bundle-latest.tar.gz
        polling:
          min_delay_seconds: 60
          max_delay_seconds: 120

    decision_logs:
      service: s3
      resource: certus-opa-logs/decisions/
      reporting:
        min_delay_seconds: 300
        max_delay_seconds: 600

    status:
      service: s3
      resource: certus-opa-status/

    plugins:
      envoy_ext_authz_grpc:
        addr: :9191
        path: certus/api/authz
```

### Data Management

OPA needs access to runtime data for policy evaluation:

1. **User/Tenant Data** (PostgreSQL → OPA data sync):
   - Periodic sync of user permissions, tenant configs, quotas
   - Use OPA's data API (`PUT /v1/data/users`, `PUT /v1/data/tenants`)

2. **Manifest Data** (Certus Assurance → OPA):
   - When manifest uploaded, push to OPA data store
   - Include manifest digest, compliance metadata, profiles

3. **Usage Data** (Real-time counters → OPA):
   - Quota enforcement requires current usage data
   - Options: Redis counters + periodic sync, or query during policy eval

**Data sync job example:**

```python
# certus_common/policy/data_sync.py
import asyncio
from certus_common.policy.opa_client import OPAClient
from certus_common.db import get_db_session


async def sync_users_to_opa(opa: OPAClient):
    """Sync user/tenant data from PostgreSQL to OPA."""
    async with get_db_session() as db:
        # Get all users with permissions
        users = await db.fetch("""
            SELECT
                u.username,
                u.tenant_id,
                u.role,
                array_agg(p.permission) as permissions
            FROM users u
            LEFT JOIN user_permissions up ON u.id = up.user_id
            LEFT JOIN permissions p ON up.permission_id = p.id
            GROUP BY u.username, u.tenant_id, u.role
        """)

        # Build OPA data structure
        user_data = {}
        for user in users:
            user_data[user["username"]] = {
                "tenant": user["tenant_id"],
                "role": user["role"],
                "permissions": user["permissions"] or []
            }

        # Push to OPA
        await opa.client.put(
            f"{opa.opa_url}/v1/data/users",
            json=user_data
        )

    logger.info("opa.data_sync", type="users", count=len(user_data))


async def sync_tenants_to_opa(opa: OPAClient):
    """Sync tenant configs and quotas to OPA."""
    async with get_db_session() as db:
        tenants = await db.fetch("""
            SELECT
                t.id,
                t.name,
                t.quotas,
                t.cross_tenant_access,
                t.data_residency
            FROM tenants t
        """)

        tenant_data = {
            tenant["id"]: {
                "name": tenant["name"],
                "quotas": tenant["quotas"],
                "cross_tenant_access": tenant["cross_tenant_access"],
                "data_residency": tenant["data_residency"]
            }
            for tenant in tenants
        }

        await opa.client.put(
            f"{opa.opa_url}/v1/data/tenants",
            json=tenant_data
        )

    logger.info("opa.data_sync", type="tenants", count=len(tenant_data))


# Scheduled job (run every 5 minutes)
async def sync_all_data():
    """Sync all data to OPA."""
    opa = OPAClient()
    try:
        await sync_users_to_opa(opa)
        await sync_tenants_to_opa(opa)
        # Add more sync functions as needed
    finally:
        await opa.close()


if __name__ == "__main__":
    asyncio.run(sync_all_data())
```

### Audit Logging

All policy decisions should be logged for compliance:

1. **OPA Decision Logs** (built-in):
   - OPA automatically logs all policy queries and decisions
   - Configure decision log plugin to ship to S3/CloudWatch/Elasticsearch

2. **Certus Service Logs** (application-level):
   - Log authorization decisions in service logs
   - Include user, action, resource, allowed/denied, policy version

3. **Audit Dashboard**:
   - Visualize policy decisions in Grafana/Kibana
   - Alerts for suspicious patterns (repeated denials, quota violations)

### Performance Considerations

1. **OPA Performance**:
   - OPA evaluates policies in <1ms for most queries
   - Sidecar pattern: localhost network (~5ms total latency)
   - Centralized OPA: network overhead (~20-50ms)

2. **Caching**:
   - OPA client SDK includes optional caching
   - Cache policy decisions for non-sensitive queries
   - Cache TTL: 5 minutes (configurable)

3. **Bundle Size**:
   - Keep policy bundles < 10MB for fast loading
   - Split policies into multiple bundles if needed
   - OPA supports incremental bundle updates

4. **Data Sync**:
   - Sync user/tenant data every 5 minutes (eventual consistency)
   - For real-time decisions, query database during policy eval (slower)
   - Hybrid: cache frequently accessed data, query for real-time

## Dependencies & Integration Points

| Component | Integration Type | Purpose |
|-----------|------------------|---------|
| **Assurance Manifest** | Data provider | Policies consume manifest metadata for compliance-driven rules |
| **Infrastructure Secrets** | Policy enforcement | Vault policies enforced via OPA (who can access which secrets) |
| **Authentication/Authorization** | Policy enforcement | OPA extends authn with fine-grained authz |
| **AAIF Agents** | Policy enforcement | Agent behavior boundaries, MCP access control |
| **All Certus Services** | Policy client | Every service queries OPA for authorization |
| **PostgreSQL** | Data provider | User/tenant data synced to OPA |
| **Redis** | Data provider | Usage counters for quota enforcement |
| **Kubernetes** | Deployment platform | OPA deployed as sidecar containers |

## Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| **OPA Sidecar Failure** | Service cannot authorize requests | Fail-closed (deny by default), health checks, automatic restart |
| **Policy Bundle Corruption** | Incorrect authorization decisions | Bundle signing, version pinning, automated testing, rollback |
| **Data Sync Lag** | Policies use stale user/tenant data | Hybrid approach: cache + real-time queries for critical decisions |
| **Performance Overhead** | Added latency to every request | Sidecar pattern (<5ms), caching, policy optimization |
| **Policy Complexity** | Hard to understand/maintain | Policy testing, documentation, preset libraries |
| **Learning Curve** | Teams unfamiliar with Rego | Training, examples, policy templates, pair programming |
| **Policy Drift** | Policies diverge from requirements | Git-based versioning, PR reviews, automated validation |

## Phased Roadmap

### Phase 0: Foundation (Weeks 1-2)

**Goals:**
- Set up OPA infrastructure
- Define policy structure and repository
- Deploy OPA sidecars to development environment

**Tasks:**
1. Create `certus-policies` Git repository
2. Define directory structure (`policies/`, `tests/`, `bundles/`)
3. Set up OPA bundle build pipeline (GitHub Actions)
4. Deploy OPA to development K8s cluster (sidecar pattern)
5. Configure bundle distribution (S3 bucket)
6. Write initial policy examples (API authorization)
7. Set up policy testing framework

**Deliverables:**
- OPA deployed to dev environment
- Sample policies for Certus Assurance API
- CI/CD pipeline for policy testing and bundling

### Phase 1: Service API Authorization (Weeks 3-5)

**Goals:**
- Implement policy enforcement for all Certus service APIs
- Migrate from hardcoded authorization to policy-based

**Tasks:**
1. Write policies for all Certus services:
   - `policies/api/assurance.rego`
   - `policies/api/trust.rego`
   - `policies/api/insight.rego`
   - `policies/api/ask.rego`
   - `policies/api/transform.rego`
2. Implement Python OPA client SDK (`certus_common/policy/opa_client.py`)
3. Add FastAPI authorization middleware
4. Integrate OPA client into all services
5. User/tenant data sync job (PostgreSQL → OPA)
6. Write comprehensive policy tests
7. Deploy to staging environment

**Deliverables:**
- All Certus service APIs using OPA for authorization
- User/tenant data synced to OPA
- 80%+ test coverage for policies

### Phase 2: Agent Behavior Policies (Weeks 6-7)

**Goals:**
- Enforce AAIF agent MCP access control
- Implement agent resource quotas

**Tasks:**
1. Write agent MCP access policies (`policies/agents/mcp_access.rego`)
2. Implement MCP policy enforcer (`certus_agents/policy/mcp_policy_enforcer.py`)
3. Integrate policy enforcement into Goose runtime
4. Add policy enforcement to Semantic Kernel/AutoGen wrappers (if used)
5. Define agent resource limits (CPU, memory, runtime duration)
6. Write agent policy tests
7. Document agent policy authoring for users

**Deliverables:**
- AAIF agents query OPA before MCP calls
- Agent behavior constrained by policies
- Documentation for writing agent policies

### Phase 3: Data Governance & Compliance (Weeks 8-10)

**Goals:**
- Implement data classification and PII handling policies
- Integrate Assurance Manifest with runtime policies

**Tasks:**
1. Write data classification policies (`policies/data/classification.rego`)
2. Implement PII detection patterns (regex, ML-based)
3. Write manifest-driven compliance policies (`policies/compliance/manifest_driven.rego`)
4. Integrate manifest data into OPA (Assurance → OPA sync)
5. Enforce encryption/retention based on classification
6. Implement audit logging for all data access
7. Write compliance policy tests (HIPAA, SOC2 scenarios)

**Deliverables:**
- Data automatically classified based on content
- Assurance Manifest drives runtime policies
- Audit logs for all data access decisions

### Phase 4: Multi-Tenancy & Quotas (Weeks 11-12)

**Goals:**
- Enforce tenant isolation
- Implement resource quota enforcement

**Tasks:**
1. Write tenant isolation policies (`policies/tenancy/isolation.rego`)
2. Implement quota enforcement (`policies/tenancy/quotas.rego`)
3. Usage tracking integration (Redis counters → OPA)
4. Cross-tenant access policies (explicit allowlist)
5. Tenant data residency enforcement (geo-restrictions)
6. Write multi-tenancy policy tests
7. Deploy quota monitoring dashboard

**Deliverables:**
- Strict tenant data isolation
- Resource quotas enforced per tenant
- Quota monitoring and alerting

### Phase 5: Production Deployment & Monitoring (Weeks 13-14)

**Goals:**
- Deploy OPA to production
- Set up monitoring and alerting

**Tasks:**
1. Deploy OPA sidecars to production K8s cluster
2. Configure production bundle distribution (S3 replication)
3. Set up decision log shipping (S3/CloudWatch)
4. Create Grafana dashboards for policy metrics:
   - Authorization decisions (allow/deny rates)
   - Policy evaluation latency
   - Quota violations
   - Tenant isolation violations
5. Configure alerts:
   - OPA sidecar failures
   - High denial rates (potential security issue)
   - Quota threshold warnings
6. Write operational runbooks
7. Conduct security review of all policies

**Deliverables:**
- OPA running in production
- Monitoring and alerting operational
- Security review completed

### Phase 6: Advanced Features (Weeks 15+)

**Goals:**
- Policy as a product (self-service)
- Advanced policy patterns

**Tasks:**
1. Policy library for common patterns (presets)
2. Policy authoring documentation and training
3. Self-service policy authoring (GitOps workflow)
4. Advanced agent policies:
   - Time-based restrictions (business hours only)
   - Anomaly detection (unusual agent behavior)
   - Progressive permissions (trust increases over time)
5. Integration with external policy sources:
   - Import compliance frameworks (NIST, CIS)
   - Partner organization policies
6. Policy impact analysis tools (what-if simulator)
7. Policy versioning and rollback automation

**Deliverables:**
- Self-service policy authoring workflow
- Advanced policy patterns library
- Policy impact analysis tooling

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| **Policy Coverage** | 100% of API endpoints | Automated endpoint inventory vs policy coverage |
| **Authorization Latency** | <10ms p95 | OPA query duration metrics |
| **Policy Test Coverage** | >80% | `opa test` coverage report |
| **Audit Completeness** | 100% of decisions logged | Decision log volume vs request volume |
| **Incident Reduction** | 50% fewer authz bugs | Support ticket categorization |
| **Compliance Readiness** | Pass SOC2/HIPAA audits | Auditor feedback on policy controls |
| **Team Velocity** | Policy updates in <1 day | Time from PR to production deployment |

## Alternatives Considered

### 1. AWS Cedar
**Pros:** Purpose-built for authorization, formal verification
**Cons:** AWS-centric, smaller ecosystem, less Kubernetes integration
**Decision:** OPA chosen for cloud-neutrality and CNCF ecosystem

### 2. Casbin
**Pros:** Simpler learning curve, multiple language support
**Cons:** Less expressive than Rego, weaker policy testing, smaller community
**Decision:** OPA chosen for expressiveness and testing capabilities

### 3. Custom Authorization Framework
**Pros:** Full control, tailored to Certus needs
**Cons:** High maintenance burden, no ecosystem, hard to hire for
**Decision:** OPA chosen to leverage existing tools and community

### 4. Embedded in Services (Status Quo)
**Pros:** No new infrastructure, familiar to developers
**Cons:** Scattered logic, inconsistent enforcement, hard to audit
**Decision:** OPA chosen for centralization and auditability

## Appendix: Policy Authoring Guidelines

### Policy Writing Best Practices

1. **Default Deny**: Always start with `default allow = false`
2. **Explicit Rules**: Write explicit allow rules, not deny rules (easier to reason about)
3. **Descriptive Names**: Use clear function/rule names (`user_has_permission`, not `uhp`)
4. **Comments**: Document complex logic and business rules
5. **Testing**: Write at least 3 test cases per rule (happy path, boundary, denial)
6. **Modularity**: Break complex policies into helper functions
7. **Performance**: Avoid nested loops, use indexed lookups

### Policy Review Checklist

- [ ] Default deny present?
- [ ] All paths covered by tests?
- [ ] No hardcoded credentials or sensitive data?
- [ ] Policy version updated?
- [ ] Documentation updated?
- [ ] Security team reviewed?
- [ ] Performance impact assessed?

### Common Patterns

**Pattern 1: Role-Based Access Control (RBAC)**
```rego
allow if {
    input.user.role == "admin"
}

allow if {
    input.user.role == "editor"
    input.method in ["GET", "POST"]
}
```

**Pattern 2: Attribute-Based Access Control (ABAC)**
```rego
allow if {
    input.user.department == input.resource.department
    input.user.clearance_level >= input.resource.classification_level
}
```

**Pattern 3: Relationship-Based Access Control (ReBAC)**
```rego
allow if {
    # User owns the resource
    input.resource.owner == input.user.id
}

allow if {
    # User is a team member
    input.user.id in data.teams[input.resource.team_id].members
}
```

**Pattern 4: Time-Based Access**
```rego
allow if {
    # Only during business hours
    hour := time.clock(time.now_ns())[0]
    hour >= 9
    hour < 17
}
```

## Appendix: Integration with Vault

OPA can enforce policies for Vault secret access:

```rego
package certus.secrets.vault

# Allow service to read database credentials
allow if {
    input.service == "certus-assurance"
    input.path == "database/creds/assurance-ro"
    input.operation == "read"
}

# Allow AAIF agent to read MCP credentials
allow if {
    input.agent.type in ["goose", "semantic-kernel"]
    input.path == "mcp/creds/certus-assurance"
    input.operation == "read"
    # Agent user must have scan permissions
    user_has_permission(input.agent.user, "scan:create")
}
```

Vault can query OPA via its [external auth plugin](https://developer.hashicorp.com/vault/docs/auth/external).

## Appendix: AGENTS.md Integration

The Assurance Manifest generates `AGENTS.md` files. OPA can parse and enforce these:

```rego
package certus.agents.agents_md

import future.keywords.if

# Parse AGENTS.md allowed_apis
allow_api(agent_type, api) if {
    agents_md := data.repositories[input.repository].agents_md
    some allowed in agents_md.allowed_apis
    allowed.name == api
    agent_type in allowed.agent_types
}

# Enforce AGENTS.md policies
allow if {
    allow_api(input.agent.type, input.mcp_server)
}
```

This creates a three-layer policy system:
1. **AGENTS.md**: Repository-level agent policies (what agents can do in this repo)
2. **Assurance Manifest**: Compliance-driven policies (what tests must pass)
3. **Runtime Policies**: System-wide authorization (who can access what)

All three layers integrate via OPA as the central policy engine.
