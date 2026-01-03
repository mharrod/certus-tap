# Endpoint & Mobile Device Security Policy

## Purpose
Protect laptops, workstations, and mobile devices that access company resources, ensuring they meet compliance requirements and reduce risk of data loss.

## Device Enrollment & Management
- All corporate devices enrolled in MDM/endpoint management before accessing production resources.
- BYOD devices require security approval, device attestation, and containerized corporate workspace.

## Security Controls
1. Full disk encryption enabled (FileVault, BitLocker, mobile equivalents).
2. Screens lock automatically after 5 minutes of inactivity and require MFA-enabled authentication.
3. Up-to-date OS and security patches within 7 days of release for critical vulnerabilities.
4. Approved endpoint protection (EDR/anti-malware) installed and tamper-protected.
5. USB storage restricted unless explicitly approved; removable media encrypted.

## Network Access
- Use VPN or zero-trust access for internal systems.
- Public Wi-Fi requires VPN; avoid untrusted hotspots when handling Restricted data.

## Incident Handling
- Lost/stolen devices reported within 1 hour; remote wipe initiated immediately.
- Device tampering or jailbreaking results in access revocation.

## Monitoring & Compliance
- Endpoint compliance monitored continuously; non-compliant devices quarantined until remediated.
- Quarterly audits verify control effectiveness and MDM coverage.

## Enforcement
Policy violations may lead to disciplinary action up to termination and cost recovery for compromised devices.
