# Secure Engineering and DevOps Policy

## Purpose
Define engineering practices that embed security across planning, coding, CI/CD, operations, and incident response for TAP.

## Core Principles
- **Shift Left:** Security requirements captured during backlog grooming and architecture reviews.
- **Automation First:** Use repeatable scripts (`just up`, `preflight.sh`) for environment parity and auditable evidence.
- **Defense in Depth:** Combine application, infrastructure, and data-layer controls to reduce blast radius.
- **Continuous Feedback:** Use metrics from OpenSearch, CI, and runtime monitoring to refine processes.

## Engineering Requirements
1. **Source Control:** All code resides in approved Git repos with branch protection and signed commits for privileged branches.
2. **Dependency Hygiene:** Dependabot or equivalent scanning kept active; engineers must run `uv lock` before merging dependency changes and update Dockerfiles accordingly.
3. **Code Reviews:** Peer review required for every pull request; reviewers verify security impact, tests, and compliance mapping (SOC 2, ISO 27001, OWASP).
4. **CI/CD Pipeline:** Pipelines enforce unit tests, security scans (SAST, container scanning, IaC linting), and artifact signing. Build results retained for 12 months.
5. **Infrastructure as Code:** Terraform/CloudFormation templates version-controlled; changes tested in isolated environments before production deployment.
6. **Secrets Management:** Secrets stored in centralized vault; never committed to source control; rotation automated every 90 days.
7. **Logging & Telemetry:** Service owners instrument structured logs and emit key metrics to centralized monitoring; alerts must include runbooks.
8. **Resilience Engineering:** Chaos tests on ingestion stack quarterly; DR drills ensure RTO 4 hours, RPO 1 hour.
9. **Change Management:** Production deployments require change record with impact analysis, rollback plan, and verification steps.

## Secure Operations
- **Access Reviews:** SRE leads monthly review of production access, including TAP ingestion identities.
- **Patch Management:** Operating systems patched within 7 days (critical) / 30 days (high) / 60 days (medium).
- **Monitoring:** Alerts for ingestion failures, abnormal data volume, unauthorized scraping attempts.
- **Incident Response:** Follow IR playbook; communication templates include customer notification guidelines and regulator contact timelines.

## Engineering Team Responsibilities
| Role | Responsibilities |
| --- | --- |
| Engineering Managers | Enforce secure SDLC, ensure teams meet policy requirements, track remediation tasks. |
| Staff Engineers | Lead threat modeling sesssions, mentor on secure coding, validate pipeline hardening. |
| DevOps/SRE | Maintain CI/CD, secrets, observability, and backup/restore workflows. |
| QA | Automate regression/security test suites and integrate results into release criteria. |

## Training & Awareness
- New engineers complete secure coding onboarding within 30 days.
- Annual tabletop exercises for incident response and DR.
- Quarterly lunch-and-learn series on SOC 2, ISO 27001, OWASP updates, and supply chain threats.

## Enforcement
Policy adherence measured via quarterly audits; violations may lead to revocation of deploy rights and HR action for repeated offenses.
