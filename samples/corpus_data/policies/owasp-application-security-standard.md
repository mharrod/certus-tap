# OWASP Application Security Standard

## Purpose
Provide actionable controls derived from OWASP Top 10 and OWASP ASVS level 2 for all application and pipeline development teams.

## Secure Development Lifecycle
1. **Design:** Perform threat modeling for every new connector or retrieval strategy; document assets, trust boundaries, and abuse cases.
2. **Implementation:** Follow secure coding guidelines, enforce linting/pre-commit hooks, and require code review for all merges.
3. **Verification:** Automated tests include dependency scanning, SAST, DAST for public endpoints, and ingestion-specific fuzz tests.
4. **Release:** Use signed container images and IaC templates; changes require change advisory approval when impacting critical services.

## OWASP Control Requirements
- **A01 Broken Access Control:** Enforce token-based auth on all ingestion endpoints; validate document ownership before indexing.
- **A02 Cryptographic Failures:** TLS 1.2+ required for all data in transit; secrets managed via centralized vault; customer data encrypted at rest.
- **A03 Injection:** Use parameterized queries and sanitized user inputs across pipelines and search queries.
- **A04 Insecure Design:** Reference architecture docs must be updated when new ingestion patterns are added; guardrails validated through DRIs.
- **A05 Security Misconfiguration:** Deploy hardened Docker images; disable default accounts; maintain infrastructure-as-code drift detection.
- **A06 Vulnerable Components:** Monitor CVEs; patch within 7 days for critical or 30 days for high severity issues; update `uv lock` when dependencies change.
- **A07 Identification & Authentication:** SSO + MFA enforced; service-to-service auth uses mutual TLS certificates rotated quarterly.
- **A08 Software Integrity Failures:** Enforce signed commits for privileged repos; verify checksums of ingestion artifacts.
- **A09 Security Logging:** Centralize logs; monitor for suspicious ingestion patterns; keep 12 months of searchable history.
- **A10 SSRF Prevention:** Restrict outbound traffic from scraping components; enforce allowlists and metadata service protections.

## Verification Activities
- Quarterly OWASP ASVS assessments led by AppSec.
- Mandatory OWASP Top 10 training for engineers and data scientists annually.
- Penetration tests on external APIs twice a year covering ingestion/auth/monitoring components.

## Enforcement
Noncompliance halts release approvals until remediation. Repeated violations escalate to the Security Leadership Council.
