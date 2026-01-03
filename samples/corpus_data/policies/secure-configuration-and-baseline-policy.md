# Secure Configuration & Baseline Policy

## Purpose
Ensure all systems, containers, and services operate with hardened configurations aligned to CIS benchmarks, SOC 2 CC5, and ISO 27001 A.12.

## Baseline Management
1. Establish baseline configurations for operating systems, Docker images, FastAPI services, OpenSearch clusters, and LocalStack environments.
2. Version-control baselines in Git with change history and approvals.
3. Apply automated configuration management (IaC, Ansible, etc.) to enforce baselines across environments.

## Hardening Requirements
- Disable unused services and ports.
- Implement logging, auditing, and secure time synchronization.
- Enforce automatic security updates or documented patch schedules.
- Use least privilege for service accounts and container runtime permissions.

## Configuration Drift Detection
- Run continuous compliance scans and alert on drift from approved baselines.
- Investigate deviations within 5 business days; remediate or document exceptions.

## Secure Build Pipeline
- Build images using trusted sources, verify checksums, and sign artifacts.
- Scan base images for vulnerabilities and rebuild upon critical CVE disclosures.

## Documentation & Evidence
Maintain baseline definitions, scan reports, remediation tickets, and approvals for at least 24 months.

## Enforcement
Systems failing to meet baseline requirements may be quarantined or removed from production until compliant.
