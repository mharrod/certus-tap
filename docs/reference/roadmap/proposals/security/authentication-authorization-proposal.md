# Authentication & Authorization Modernization

**Status:** Draft
**Author:** DevOps/RAG Agent
**Date:** 2025-12-07
## Executive Summary

Certus TAP currently relies on basic auth or network isolation for many internal services (Assurance, Trust, Insight, MCP gateway). As the platform evolves, we need a consistent authentication/authorization layer that supports API clients, IDE agents, and managed deployments. This proposal describes how we introduce token-based auth, role-based access control (RBAC), and secrets management so all services share a cohesive security model.

## Motivation

### Current Gaps

- Services (Assurance, Trust, Ask) often lack API auth or use ad-hoc tokens.
- No central identity provider or RBAC; workspace-level permissions are manual.
- MCP/ACP gateways need user-level authentication to trigger actions safely.
- Secrets (API keys, cosign keys) are stored per service without a unified strategy.

### Goals

1. Introduce a unified auth layer (API keys + OIDC) across all services.
2. Implement RBAC for workspaces, features, and roles (admin, analyst, viewer).
3. Provide secrets management and rotation guidelines (Vault, AWS SSM, etc.).
4. Integrate auth with MCP/ACP proxies and CLI tools.

## Proposed Solution

### Architecture

```
Identity Layer
└── Auth Provider (Keycloak/OIDC)
└── API Gateway Middleware (FastAPI dependencies)
└── RBAC Policies (per workspace/service)
└── Secret Store (Vault/SSM)
```

- Use Keycloak or equivalent as OIDC provider (aligned with Certus-Trust).
- Provide API key support for automation with scoped permissions.
- Inject auth middleware into each FastAPI service (Assurance, Trust, Insight, Ask, MCP gateway).
- Centralize secret management and rotation.

## Dependencies

- Certus-Trust integration with Keycloak (for keyless signing).
- Observability (audit logs for auth events).

## Phased Roadmap

### Phase 0 – Auth Foundations (Weeks 0-1)

- Set up identity provider (Keycloak) and define client registrations for each service.
- Provide API key format and rotation policy.

### Phase 1 – API Integration (Weeks 2-3)

- Add auth middleware to services; enforce required scopes per endpoint.
- Update CLI/MCP clients to include tokens.

### Phase 2 – RBAC & Workspace Policies (Weeks 4-5)

- Define roles (admin, analyst, viewer) and workspace scope mapping.
- Enforce policies in services (e.g., ingestion actions limited to workspace admins).

### Phase 3 – Secrets & Audit (Weeks 6-7)

- Move secrets to Vault/SSM; document rotation and access controls.
- Log auth events and expose to Insight dashboards.

## Deliverables

- Auth provider configuration (Keycloak) and client credentials.
- Service-level middleware enforcing auth and RBAC.
- Documentation for tokens, scopes, secret management.

## Success Metrics

1. **Coverage:** 100% of services require authenticated requests.
2. **RBAC Compliance:** Workspace-level permissions enforced across features.
3. **Secrets Management:** All sensitive keys managed via Vault/SSM with rotation.
4. **Auditability:** Auth events logged and visible in dashboards.

## Next Steps

1. Approve this proposal and coordinate with the Certus-Trust team for Keycloak rollout.
2. Create implementation issues per service for auth integration and RBAC mapping.
3. Begin Phase 0 by configuring the identity provider and drafting API key specs.
