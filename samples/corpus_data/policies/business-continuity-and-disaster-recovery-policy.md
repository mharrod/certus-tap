# Business Continuity & Disaster Recovery Policy

## Purpose
Ensure the organization can sustain critical operations during disruptive events and recover TAP services within acceptable RTO/RPO targets.

## Scope
Covers FastAPI backend, ingestion pipelines, OpenSearch clusters, LocalStack emulations, build systems, and supporting infrastructure.

## Objectives
- RTO: 4 hours for customer-facing ingestion/query APIs.
- RPO: 1 hour for indexed data and configuration stores.
- Maintain critical business processes (support, compliance reporting, audits) during incidents.

## Continuity Planning
1. Identify critical processes, owners, and dependencies; document in BCP register.
2. Maintain alternate work locations and remote access plans for staff.
3. Establish redundancy for compute, storage, and network components (multi-region when feasible).

## Disaster Recovery Procedures
1. Nightly OpenSearch snapshots with cross-region replication; test restores quarterly.
2. Infrastructure-as-code templates stored in Git for rapid redeployments (`just up` as baseline).
3. DR runbooks include authentication bootstrap, secrets restoration, DNS updates, and validation scripts.
4. Communication plan ensures stakeholders receive status at least hourly during SEV1 events.

## Testing & Maintenance
- Semiannual DR exercises covering loss of primary region and data corruption scenarios.
- Update BCP/DR documents after major architecture changes and post-mortems.

## Compliance & Records
Keep evidence of BCP/DR tests, issues discovered, remediation steps, and approvals for a minimum of 3 years.
