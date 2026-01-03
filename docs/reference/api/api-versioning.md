# API Versioning Strategy

## Purpose
Ensure Certus TAP REST APIs evolve without breaking existing clients by defining how we version endpoints, document deprecations, and roll out changes.

## Audience & Prerequisites
- API owners and backend contributors planning endpoint changes.
- Release managers communicating API compatibility.
- Familiarity with FastAPI routing and the [API Documentation Standard](api-doc-standard.md).

## Overview
- Current major version is `v1`, exposed via the `/v1/` URL prefix.
- We follow semantic versioning semantics (MAJOR.MINOR.PATCH) for release planning.
- Backward-compatible changes (new optional fields, new endpoints) stay within v1.
- Breaking changes trigger a new major version plus a structured deprecation cycle.

## Key Concepts

### Current State
- **Version:** `v1` (stable since 2025‑11‑14).
- **Prefix:** All endpoints mount under `/v1/`.
- **Status:** Breaking changes require `v2`; none planned yet.

### Semantic Versioning
- **MAJOR** – Introduces breaking changes (requires `/v2/`).
- **MINOR** – Backward-compatible features within `/v1/`.
- **PATCH** – Backward-compatible fixes.

### URL Versioning
- Version lives in the path for clarity, e.g., `https://api.example.com/v1/index/`.
- When `v2` arrives, new endpoints appear at `/v2/...` while `/v1/...` remains available during deprecation.

### Compatibility Policy (Within v1)
| Stable Within v1                     | May Change Without Bump                     |
| ------------------------------------ | ------------------------------------------- |
| Endpoint URLs and HTTP verbs         | New optional request parameters             |
| Existing request fields              | New optional response fields                |
| Existing response fields             | New endpoints                               |
| Documented HTTP status codes         | Error message text (code remains the same)  |

Breaking actions that require `v2`: removing endpoints, renaming fields, changing types, removing error codes, or altering HTTP status semantics.

### Deprecation Policy
1. **Announce (T‑6 months):** Mark endpoint/field as deprecated in docs and responses.
   ```json
   {
     "deprecated": true,
     "deprecation_notice": "Removed on 2026-05-14. Use POST /v1/index/ instead.",
     "migration_guide": "https://docs.example.com/migrate-to-v2"
   }
   ```
2. **Support Window (6 months):** Endpoint continues to function; new clients should migrate.
3. **Removal:** After the window, drop the deprecated surface in the next major release.
4. **Sunset:** Keep migration guides and (optionally) maintenance branches for reference.

### Adding Backward-Compatible Features
- **New optional parameter:** Provide defaults so existing clients remain unaffected.
- **New response field:** Mark as optional in pydantic models so older clients can ignore it.
- **New endpoint:** Document it and leave existing endpoints untouched.

### When to Cut v2
- Multiple breaking changes accumulate (3+).
- Architectural shifts require different contracts (e.g., new `/ask` response shape).
- Deprecation windows have completed and stakeholders have been notified.

## Workflows / Operations
1. **Plan change** – Decide if the feature is backward compatible.
2. **Document** – Update endpoint docstrings plus this file if a new version or deprecation is planned.
3. **Communicate** – Post release notes and update API reference/roadmap.
4. **Implement** – For breaking changes, add `/v2/` routes while keeping `/v1/` in place during the deprecation window.
5. **Clean up** – After the window, remove deprecated `/v1/` features and note final removal in docs.

## Configuration / Interfaces
- FastAPI routers live under `/v1/` in `certus_ask/routers/*`.
- Release metadata (effective dates, status) should be tracked in CHANGELOG/release notes alongside this doc.
- Deprecation notices go into response payloads and documentation tables.

## Troubleshooting / Gotchas
- **Silent breaking change:** Removing a field without version bump will break clients—avoid.
- **Missing announcement:** Always document deprecations at least six months ahead.
- **Partial migrations:** Ensure both `/v1/` and `/v2/` endpoints share business logic to prevent divergence.

## Related Documents
- [API Documentation Standard](api-doc-standard.md)
- [Standardized Response Format](api-response.md)
- [API Error Codes](api-error-codes.md)
- [Architecture – Non-Repudiation Flow](../architecture/NON_REPUDIATION_FLOW.md)
