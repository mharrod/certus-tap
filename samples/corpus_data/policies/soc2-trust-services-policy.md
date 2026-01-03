# SOC 2 Trust Services Criteria Control Policy

## Purpose
Translate SOC 2 Trust Services Criteria (Security, Availability, Confidentiality, Processing Integrity, Privacy) into actionable controls for TAP services and supporting infrastructure.

## Mapping Overview
| TSC | Control Category | Examples |
| --- | --- | --- |
| CC1/CC2 | Governance & Communication | Weekly leadership sync, risk register, security awareness campaigns. |
| CC3 | Risk Management | Threat modeling for pipelines, third-party risk reviews, vendor scorecards. |
| CC4 | Monitoring | OpenSearch detection rules, LocalStack smoke tests, centralized logging. |
| CC5 | Control Activities | Access reviews, zero-trust network segmentation, tamper-evident logging. |
| CC6 | Logical Access | SSO enforced on all services, MFA on privileged accounts, per-repo secrets management. |
| CC7 | Change & Incident Mgmt | Git change control, blameless postmortems, incident response plans for ingestion failures. |
| CC8 | Availability | High-availability FastAPI deployment, automated backups, DR playbooks tested twice per year. |

## Control Requirements
1. **Evidence Capture:** Every production change must include `preflight.sh` output, peer review sign-off, and automated test evidence. Evidence stored for 24 months.
2. **Access Control Reviews:** Quarterly automated review of IAM roles in cloud, OpenSearch, and TAP ingestion service accounts. Remediation window is 10 business days.
3. **Vendor Management:** All third-party data sources undergo SOC 2 Type II or equivalent review. Data sharing agreements must include breach notification clauses.
4. **Incident Response:** IR plan includes ingestion-specific runbooks, containment of malicious documents, and reporting timeline aligned with CC7.3.
5. **Availability Testing:** Perform failover tests on LocalStack/OpenSearch at least semi-annually and capture DR metrics within 15% of RTO/RPO targets.
6. **Confidentiality Handling:** Documents processed through scraping pipelines inherit classification labels and encryption requirements (at rest/in transit).
7. **Privacy Controls:** Personal data ingestion requires privacy impact assessments and data minimization review before enabling source connectors.

## Monitoring & Reporting
- SOC 2 metrics published monthly to leadership portal.
- Nonconformities require corrective action plans with owners and due dates.
- Independent auditor access to configuration baselines and IaC repos provided under NDA.

## Enforcement
Failure to maintain SOC 2 controls may lead to suspension of releases and leadership review. Intentional noncompliance may result in termination.
