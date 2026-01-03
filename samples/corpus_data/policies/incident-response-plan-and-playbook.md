# Incident Response Plan & Playbook

## Purpose
Provide a structured approach for detecting, responding to, and learning from security incidents, aligning with SOC 2 CC7 and ISO 27035.

## Incident Response Phases
1. **Preparation:** Maintain contact lists, tooling access, runbooks, and mandatory training.
2. **Identification:** Use monitoring, alerts, and user reports to detect events; classify severity (SEV1-SEV4).
3. **Containment:** Isolate affected services (e.g., disable ingestion connector, firewall rules, revoke credentials).
4. **Eradication:** Remove malware, patch vulnerabilities, reset accounts.
5. **Recovery:** Restore services, validate `preflight.sh` success, monitor for recurrence.
6. **Lessons Learned:** Conduct post-incident review within 5 business days and update policies/runbooks.

## Roles
| Role | Responsibilities |
| --- | --- |
| Incident Commander | Coordinates response, approves communications, tracks actions. |
| Communications Lead | Handles internal/external messaging, regulator notifications. |
| Forensics Lead | Collects evidence, maintains chain of custody, supports root cause analysis. |
| Engineering Leads | Execute containment/eradication steps for their services. |

## Communication Plan
- Escalate via paging system with severity-specific SLAs (SEV1 = acknowledge in <10 min).
- Notify Legal, Privacy, and affected business units when PII/PHI involved.
- Customer notification timeline defined per contract (typically 72 hours).

## Tooling & Evidence
- Central log platform, OpenSearch dashboards, ticketing system, and secure evidence storage.
- All actions recorded in incident tracker; artifacts retained for minimum 24 months.

## Testing
- Conduct semiannual tabletop exercises and annual live simulations (e.g., compromised ingestion credential) to validate response readiness.
