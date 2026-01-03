# Dynamic Application Security Testing (DAST) & Infrastructure as Code (IaC) Scanning

This guide demonstrates comprehensive DAST and IaC scanning samples using OWASP ZAP and Checkov to identify runtime vulnerabilities and infrastructure misconfigurations.

## Overview

### DAST (Dynamic Application Security Testing)
- **Purpose:** Find runtime vulnerabilities in running applications
- **Tool:** OWASP ZAP (Zed Attack Proxy)
- **Focus:** Web application security, OWASP Top 10, authentication, session management
- **Sample:** `zap-dast.sarif.json` with 10 realistic vulnerabilities

### IaC (Infrastructure as Code) Scanning
- **Purpose:** Detect misconfigurations in cloud/container infrastructure
- **Tool:** Checkov
- **Focus:** AWS, Terraform, Docker, Kubernetes security best practices
- **Sample:** `checkov-iac.sarif.json` with 10 infrastructure violations

## DAST: OWASP ZAP Sample

### Overview
The `zap-dast.sarif.json` sample contains 10 findings simulating a real web application security assessment:

| Finding | Type | Severity | Vulnerability |
|---------|------|----------|----------------|
| SQLi in /api/users/search | Injection | CRITICAL | User input concatenated into SQL query |
| XSS in /post/comments | Injection | HIGH | User input reflected without encoding |
| Auth bypass in /admin | Access Control | CRITICAL | Predictable session tokens |
| Insecure cookies | Session Mgmt | HIGH | Missing HttpOnly, Secure, SameSite |
| Missing CSRF tokens | CSRF | HIGH | Password change without validation |
| Java deserialization | Deserialization | CRITICAL | Gadget chain RCE vulnerability |
| Broken access control | Access Control | HIGH | IDOR in /api/orders/{id} |
| HTTP transmission | Encryption | CRITICAL | Password sent over HTTP |
| Weak password policy | Authentication | MEDIUM | Single character passwords allowed |
| Missing headers | Config | MEDIUM | CSP, HSTS, X-Frame-Options missing |

### OWASP ZAP Architecture

```
Target Application
      ↓
┌─────────────────────────────────┐
│  OWASP ZAP Scanner              │
├─────────────────────────────────┤
│  Passive Scanning:              │
│  - Response analysis            │
│  - Security header detection    │
│  - Cookie inspection            │
│                                 │
│  Active Scanning:               │
│  - SQL injection testing        │
│  - XSS payload injection        │
│  - Parameter fuzzing            │
│  - Authentication bypass tests  │
│                                 │
│  Spider:                        │
│  - Discover URLs                │
│  - Crawl application            │
└─────────────────────────────────┘
      ↓
Vulnerability Report (SARIF)
```

### Running ZAP

#### Docker Installation
```bash
# Run ZAP in Docker
docker run -t owasp/zap2docker-stable \
  zap-baseline.py \
  -t http://target:8080 \
  -r report.html

# For active scanning (more thorough)
docker run -t owasp/zap2docker-stable \
  zap-full-scan.py \
  -t http://target:8080 \
  -r report.html
```

#### CLI Usage
```bash
# Baseline scan (passive)
zap.sh -cmd \
  -quickurl http://localhost:8080 \
  -quickout report.html

# Full scan (active)
zap.sh -cmd \
  -quickurl http://localhost:8080 \
  -quickout report.html \
  -quickness slow
```

#### SARIF Output
```bash
# Generate SARIF report
zap.sh -cmd \
  -quickurl http://target:8080 \
  -f sarif \
  -r results.sarif
```

### Finding Details

#### SQL Injection (CWE-89)
**Severity:** CRITICAL (CVSS 9.8)
**OWASP:** A03:2021 - Injection
**Test Payload:** `' OR '1'='1`
**Impact:** Full database read/write access
**Remediation:** Use parameterized queries or ORM

#### Cross-Site Scripting (CWE-79)
**Severity:** HIGH (CVSS 6.1)
**OWASP:** A03:2021 - Injection
**Test Payload:** `<script>alert('XSS')</script>`
**Impact:** Session hijacking, credential theft
**Remediation:** HTML-encode all user input

#### Authentication Bypass (CWE-287)
**Severity:** CRITICAL (CVSS 9.1)
**OWASP:** A01:2021 - Broken Access Control
**Vulnerability:** Predictable session tokens (1000, 1001, 1002)
**Impact:** Impersonate any user
**Remediation:** Cryptographically secure random tokens

#### Insecure Cookies (CKE-614)
**Severity:** HIGH (CVSS 6.5)
**OWASP:** A02:2021 - Cryptographic Failures
**Missing Flags:** HttpOnly, Secure, SameSite
**Impact:** XSS cookie theft, CSRF attacks
**Remediation:** Set all three flags

#### Missing CSRF Protection (CWE-352)
**Severity:** HIGH (CVSS 6.5)
**OWASP:** A01:2021 - Broken Access Control
**Attack:** Trick user into changing own password
**Remediation:** Implement CSRF tokens on state-changing operations

### DAST Best Practices

1. **Baseline Scans** - Quick passive scanning for CI/CD
2. **Full Scans** - Thorough active scanning before release
3. **Authenticated Scans** - Test logged-in user workflows
4. **Context-Aware** - Focus on critical application flows
5. **Progressive Testing** - Start with baseline, escalate as needed

## IaC: Checkov Sample

### Overview
The `checkov-iac.sarif.json` sample contains 10 infrastructure violations across Terraform, Docker, and Kubernetes:

| Finding | Type | Severity | Issue |
|---------|------|----------|-------|
| Wildcard IAM policy | Access Control | CRITICAL | Resource: * on all actions |
| Missing S3 encryption | Encryption | CRITICAL | No server-side encryption |
| S3 public access | Public Access | CRITICAL | No access blocking enabled |
| Policy on user | Best Practice | MEDIUM | Should attach to group |
| KMS rotation disabled | Encryption | HIGH | Key rotation not enabled |
| No CloudTrail | Audit | HIGH | API calls not logged |
| RDS encryption off | Encryption | CRITICAL | Database not encrypted |
| No VPC Flow Logs | Logging | MEDIUM | Network traffic not monitored |
| Docker ports exposed | Port Security | HIGH | SSH, MySQL, PostgreSQL exposed |
| K8s cluster-admin | Access Control | CRITICAL | Overly permissive RBAC |

### Checkov Architecture

```
Infrastructure Code (Terraform, Docker, K8s)
      ↓
┌─────────────────────────────────┐
│  Checkov Scanner                │
├─────────────────────────────────┤
│  Policy Library:                │
│  - 450+ AWS checks              │
│  - 80+ Docker checks            │
│  - 100+ Kubernetes checks       │
│  - 60+ Terraform checks         │
│                                 │
│  Evaluation:                    │
│  - Parse IaC templates          │
│  - Apply policy rules           │
│  - Grade configurations         │
│  - Generate report              │
└─────────────────────────────────┘
      ↓
Violation Report (JSON/SARIF)
```

### Running Checkov

#### Installation
```bash
pip install checkov
```

#### Terraform Scanning
```bash
# Scan Terraform directory
checkov -d ./infrastructure/terraform

# Output as SARIF
checkov -d ./infrastructure/terraform \
  -o sarif > results.sarif

# Scan specific file
checkov -f ./infrastructure/terraform/main.tf
```

#### Docker Scanning
```bash
# Scan Dockerfile
checkov -f Dockerfile

# Scan all Dockerfiles
checkov -d . --framework dockerfile
```

#### Kubernetes Scanning
```bash
# Scan K8s manifests
checkov -d ./k8s \
  --framework kubernetes

# Scan specific manifest
checkov -f ./k8s/deployment.yaml
```

#### Policy Selection
```bash
# Use specific framework
checkov -d ./terraform --framework terraform

# Skip certain checks
checkov -d ./terraform --skip-check CKV_AWS_1

# Run only specific checks
checkov -d ./terraform --check CKV_AWS_21,CKV_AWS_22
```

### Finding Details

#### Wildcard IAM Policy (CKV_AWS_1)
**Severity:** CRITICAL
**Issue:** `Resource: "*"` grants access to all resources
**Code:**
```terraform
resource "aws_iam_role_policy" "lambda_execution" {
  policy = jsonencode({
    Statement = [{
      Resource = "*"  # ❌ VIOLATION
    }]
  })
}
```
**Fix:** Specify exact ARNs
```terraform
Resource = "arn:aws:s3:::my-bucket/*"
```

#### Missing S3 Encryption (CKV_AWS_21)
**Severity:** HIGH
**Issue:** S3 bucket has no encryption configuration
**Code:**
```terraform
resource "aws_s3_bucket" "data" {
  bucket = "app-data"
  # ❌ Missing encryption
}
```
**Fix:** Add encryption
```terraform
resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}
```

#### S3 Public Access (CKV_AWS_34)
**Severity:** CRITICAL
**Issue:** S3 bucket allows public access
**Code:**
```terraform
# ❌ VIOLATION - No public access blocking
resource "aws_s3_bucket" "uploads" {
  bucket = "user-uploads"
}
```
**Fix:** Block public access
```terraform
resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}
```

#### RDS Encryption (CKV_AWS_22)
**Severity:** CRITICAL
**Issue:** Database not encrypted at rest
**Code:**
```terraform
resource "aws_db_instance" "production" {
  storage_encrypted = false  # ❌ VIOLATION
}
```
**Fix:** Enable encryption
```terraform
resource "aws_db_instance" "production" {
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn
}
```

#### CloudTrail Audit (CKV_AWS_45)
**Severity:** HIGH
**Issue:** No API call logging
**Code:**
```terraform
# ❌ VIOLATION - No CloudTrail configured
```
**Fix:** Add CloudTrail
```terraform
resource "aws_cloudtrail" "main" {
  name                          = "main"
  s3_bucket_name               = aws_s3_bucket.cloudtrail.id
  include_global_service_events = true
  is_multi_region_trail        = true
  enable_log_file_validation   = true
}
```

#### Docker Port Exposure (CKV_DOCKER_2)
**Severity:** HIGH
**Issue:** Exposes unnecessary ports
**Code:**
```dockerfile
EXPOSE 80 443 22 3306 5432  # ❌ VIOLATION
```
**Fix:** Only expose necessary ports
```dockerfile
EXPOSE 80 443
```

#### Kubernetes RBAC (CKV_AWS_1 adapted for K8s)
**Severity:** CRITICAL
**Issue:** Overly permissive cluster-admin binding
**Code:**
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: admin-binding
roleRef:
  kind: ClusterRole
  name: cluster-admin  # ❌ VIOLATION - Too permissive
```
**Fix:** Create minimal role
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: app-role
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: app-binding
roleRef:
  kind: Role
  name: app-role
```

### IaC Best Practices

1. **Scanning in CI/CD** - Fail build on critical violations
2. **Framework-Specific** - Run appropriate scanners per framework
3. **Policy-As-Code** - Enforce company standards
4. **Custom Rules** - Create checks for business requirements
5. **Baseline Remediation** - Fix critical issues before deployment

## Integration with Non-Repudiation Pipeline

Both DAST and IaC scanning integrate into the Assurance pipeline:

```
┌─────────────────────────────────────┐
│  Certus Assurance Pipeline          │
├─────────────────────────────────────┤
│                                     │
│  1. SAST (Code)                     │
│     ├─ Trivy                        │
│     ├─ Semgrep                      │
│     └─ Bandit                       │
│                                     │
│  2. DAST (Runtime) ← NEW            │
│     └─ OWASP ZAP                    │
│                                     │
│  3. IaC Scanning (Infrastructure)   │
│     └─ Checkov                      │
│                                     │
│  4. SBOM (Dependencies)             │
│     └─ Syft                         │
│                                     │
│  5. Privacy (PII Detection)         │
│     └─ Presidio                     │
│                                     │
│  6. Signing (Attestations)          │
│     └─ Cosign                       │
└─────────────────────────────────────┘
```

## Compliance Mapping

### DAST Findings
- **OWASP Top 10** - Direct mapping
- **CVSS Scoring** - Each finding scored
- **CWE References** - Root cause classification

### IaC Findings
- **AWS Security Best Practices**
- **CIS Benchmarks** - AWS, Docker, Kubernetes
- **Industry Standards** - PCI-DSS, HIPAA, SOC2

## Common Workflows

### Complete Security Assessment
```bash
# Run all scanners
trivy fs src/
semgrep --json src/ | semgrep-to-sarif > semgrep.sarif
bandit -r src/ -f json | bandit-to-sarif > bandit.sarif
zap-baseline.py -t http://app:8080
checkov -d infrastructure/

# Merge results
jq -s 'add' trivy.sarif semgrep.sarif bandit.sarif zap.sarif checkov.sarif > all-results.sarif
```

### CI/CD Integration (GitHub Actions)
```yaml
name: Security Scan

on: [push, pull_request]

jobs:
  dast:
    runs-on: ubuntu-latest
    services:
      app:
        image: myapp:latest
    steps:
      - uses: actions/checkout@v3
      - name: ZAP Baseline Scan
        uses: zaproxy/action-baseline@v0.7.0
        with:
          target: 'http://app:8080'
          rules_file_name: '.zap/rules.tsv'
          cmd_options: '-a'

  iac:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: bridgecrewio/checkov-action@master
        with:
          directory: infrastructure/
          framework: terraform
          output_format: sarif
```

## Performance Considerations

### DAST
- **Baseline Scan:** 5-10 minutes
- **Full Scan:** 30-60 minutes
- **Resources:** Can be CPU/network intensive
- **Scheduling:** Run in non-peak hours for production-like environments

### IaC
- **Scan Time:** 1-2 minutes for typical infrastructure
- **Resources:** Lightweight, minimal CPU/memory
- **Scheduling:** Can run on every commit

## References

- [OWASP ZAP Documentation](https://www.zaproxy.org/docs/)
- [Checkov Documentation](https://www.checkov.io/1.Welcome/What%20is%20Checkov.html)
- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [CIS Benchmarks](https://www.cisecurity.org/cis-benchmarks/)
- [CVSS Calculator](https://www.first.org/cvss/calculator/3.1)

## Summary

**DAST + IaC Scanning provides:**
- ✅ Runtime vulnerability detection (DAST)
- ✅ Infrastructure security validation (IaC)
- ✅ OWASP Top 10 coverage
- ✅ Cloud security compliance
- ✅ Configuration best practices
- ✅ Automated remediation guidance
- ✅ SARIF integration with other tools
- ✅ CI/CD pipeline integration
