# Access Control & Identity Management Policy

## Purpose
Define the controls for granting, reviewing, and revoking access to systems and data across TAP environments, aligning with SOC 2 CC6 and ISO 27001 A.9.

## Principles
- **Least Privilege:** Users receive the minimum access required to perform duties.
- **Separation of Duties:** Critical operations (code deployment, production database changes) require dual control.
- **Centralized Identity:** All workforce identities federate through SSO with MFA enforced.

## Access Lifecycle
1. **Provisioning:** Requires manager request, data owner approval, and ticket tracking. Production access requires security approval and completion of secure engineering training.
2. **Changes:** Role changes trigger access reviews; contractors receive time-bound accounts.
3. **Deprovisioning:** Access removed within 24 hours of departure. Service accounts rotated or disabled when no longer needed.

## Technical Controls
- PAM for privileged accounts.
- Automated sync to IAM, OpenSearch, LocalStack, and cloud providers.
- Secrets managed in centralized vault; usage logged and rotated every 90 days.

## Reviews & Monitoring
- Quarterly entitlement reviews documented in GRC system.
- Alerts for anomalous logins, excessive privilege grants, and stale accounts.

## Enforcement
Unauthorized access attempts investigated per incident response plan. Violations may lead to termination and legal action.
