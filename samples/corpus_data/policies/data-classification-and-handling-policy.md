# Data Classification & Handling Policy

## Purpose
Provide a consistent framework for classifying and protecting organizational data in line with ISO 27001 A.8 and SOC 2 CC6 requirements.

## Classification Levels
| Level | Description | Examples | Handling |
| --- | --- | --- | --- |
| Public | Approved for public disclosure. | Marketing site, published docs. | No restrictions, but must maintain integrity. |
| Internal | Non-public operational data. | Runbooks, internal metrics. | Share within company; store in approved drives. |
| Confidential | Sensitive business/customer data; unauthorized disclosure could harm company. | Customer contracts, ingestion configs. | Encryption in transit/at rest, role-based access, logging of access. |
| Restricted | Highly sensitive data with legal/regulatory controls. | PII, PHI, credentials. | MFA, least privilege, data masking, stricter retention and tracking. |

## Responsibilities
- **Data Owners:** Assign classification, approve access, define retention.
- **Data Custodians:** Implement controls (encryption, backups, logging).
- **Users:** Handle data per classification and report deviations.

## Handling Requirements
1. Apply labels in document metadata, repository folders, and ingestion manifests.
2. Encrypt Confidential/Restricted data in transit (TLS 1.2+) and at rest (AES-256 or equivalent).
3. Use secure transfer mechanisms (SFTP, HTTPS, signed URLs) for Confidential/Restricted data exchange.
4. Implement data minimization before ingesting external corpora; remove unused fields.
5. Retain Restricted data only for approved business purposes with documented lawful basis.

## Verification
Quarterly audits sample ingestion outputs to confirm classification tags propagate into OpenSearch indexes and downstream analytics.
