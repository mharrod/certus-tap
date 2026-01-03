# Change Management & Release Policy

## Purpose
Ensure production changes are evaluated, tested, approved, and documented to protect availability, integrity, and compliance obligations.

## Scope
Applies to application code, infrastructure-as-code, ingestion connectors, configuration changes, and data pipeline modifications deployed to production or customer environments.

## Change Categories
- **Standard Changes:** Low-risk, pre-approved procedures (e.g., nightly reindex) documented in runbooks.
- **Normal Changes:** Require risk assessment, peer review, testing evidence, and change approval.
- **Emergency Changes:** Used for critical incidents; still require retrospective review within 48 hours.

## Requirements
1. All changes tracked in ticketing system with description, risk rating, rollback plan, and verification steps.
2. CI/CD pipelines must run tests, security scans, and `preflight.sh` (when ingestion is affected) before deployment.
3. Production deployments require at least one approver independent from the implementer.
4. Maintain change calendar with blackout windows for peak business periods.
5. Post-change validation includes monitoring dashboards, log review, and stakeholder sign-off.

## Documentation & Evidence
- Store approvals, test results, and deployment logs for at least 24 months.
- Tag Git commits/releases with change IDs for traceability.

## Enforcement
Unapproved changes may result in immediate rollback and disciplinary action. Repeated violations escalate to the Security Leadership Council.
