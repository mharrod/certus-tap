# Data Retention & Destruction Policy

## Purpose
Define retention timelines and secure disposal procedures for corporate and customer data to meet contractual, regulatory, SOC 2, and ISO 27001 requirements.

## Retention Schedule
| Data Type | Retention | Notes |
| --- | --- | --- |
| Audit & ingestion logs | 24 months minimum | Supports SOC 2 evidence and incident investigations. |
| Customer deliverables | Contract term + 1 year | Deletion upon request or contract termination. |
| HR/employee records | Per legal jurisdiction (typically 7 years) | Coordinate with HR/legal for specifics. |
| Source datasets from customers | Per data processing agreement | Document lawful basis and re-certify annually. |

## Secure Storage & Disposal
1. Store data only in approved systems with encryption and access controls.
2. Destruction methods: cryptographic erase for cloud storage, shredding for physical media, and log evidence of deletion.
3. Backup data follows same retention; expired backups removed via lifecycle policies.
4. Support "right to be forgotten" by enabling targeted deletion in OpenSearch and downstream caches.

## Responsibilities
- **Data Owners:** Define retention requirements and approve destruction requests.
- **IT/Operations:** Implement lifecycle rules, monitor storage compliance, document destruction certificates.
- **Security & Privacy:** Review retention schedule annually and during major product changes.

## Enforcement
Noncompliance may trigger regulatory fines and disciplinary action. Deviations require VP-level exception with compensating controls.
