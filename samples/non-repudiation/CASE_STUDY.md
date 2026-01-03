# Case Study: TAP Security Assessment

## Executive Summary

This case study walks through a comprehensive security assessment of **Certus TAP v1.0.0**, a fictional enterprise document management and operations platform. The assessment uses all six sample scanner types (SAST, SBOM, DAST, IaC, Privacy, Signing) to demonstrate the complete non-repudiation security scanning pipeline.

The narrative shows how findings from different scanners relate to each other, how vulnerabilities manifest across the stack, and how the dual-signature non-repudiation model provides confidence in the assessment results.

---

## Part 1: The Application

### Certus TAP v1.0.0 Overview

**Application Type:** Enterprise Document Management System
**Tech Stack:** Python FastAPI backend + React frontend
**Deployment:** Kubernetes on AWS
**Critical Features:**
- Multi-tenant document storage and retrieval
- User authentication and role-based access control
- Full-text search across documents
- Automated compliance reporting
- Integration with external systems via REST APIs

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────┐
│  Certus TAP v1.0.0                                   │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────┐        ┌──────────────────┐     │
│  │  React Frontend  │◄──────►│ FastAPI Backend  │     │
│  │  :3000           │        │ :8080            │     │
│  └──────────────────┘        └──────────────────┘     │
│         ▲                             ▲                │
│         │                             │                │
│         └─────────────────┬───────────┘                │
│                           │                           │
│                    ┌──────▼──────┐                    │
│                    │ PostgreSQL   │                    │
│                    │ Database     │                    │
│                    │ :5432        │                    │
│                    └──────────────┘                    │
│                           ▲                            │
│                           │                            │
│                    ┌──────▼──────────┐                │
│                    │ S3 Document      │                │
│                    │ Storage          │                │
│                    └──────────────────┘                │
│                                                       │
│  External Integrations:                              │
│  - Elasticsearch (Full-text search)                  │
│  - Redis (Session cache)                            │
│  - Neo4j (Audit logs)                               │
└─────────────────────────────────────────────────────────┘
```

### Deployment Infrastructure

**Cloud Platform:** AWS
**Container Orchestration:** Kubernetes
**Database:** PostgreSQL 14
**Secrets Management:** AWS Secrets Manager
**Network:** VPC with public/private subnets
**Load Balancing:** AWS ALB
**Monitoring:** CloudWatch + ELK Stack

---

## Part 2: The Assessment

### Assessment Timeline

| Phase | Tool | Findings | Severity | Focus |
|-------|------|----------|----------|-------|
| 1. SAST Code Scanning | Trivy, Semgrep, Bandit | 21 findings | CRITICAL-LOW | Vulnerabilities in application code |
| 2. Dependency Analysis | Syft | 8 packages | 1 vulnerable | Known vulnerabilities in dependencies |
| 3. Privacy Scanning | Presidio | 8 findings | HIGH-LOW | PII/credentials in code/configs |
| 4. Dynamic Testing | OWASP ZAP | 10 findings | CRITICAL-MEDIUM | Runtime vulnerabilities in deployed app |
| 5. Infrastructure Review | Checkov | 10 findings | CRITICAL-MEDIUM | IaC misconfigurations in AWS/K8s |
| **TOTAL** | **All tools** | **57 findings** | Mix | Complete coverage |

### Assessment Date
**Started:** January 15, 2024 @ 10:00 UTC
**Completed:** January 15, 2024 @ 14:35 UTC
**Duration:** 4 hours 35 minutes

---

## Part 3: Scanner Findings & Cross-Scanner Narrative

### 1. SAST Phase: Code-Level Vulnerabilities

**Scanner:** Trivy, Semgrep, Bandit
**Purpose:** Find hardcoded secrets, unsafe patterns, and dependency vulnerabilities

#### Key Findings Connection

The SAST phase discovers foundational code vulnerabilities that cascade into runtime and infrastructure issues:

**Trivy - Dependency Vulnerabilities (6 findings)**
- **[CRITICAL] CVE-2024-1086** in `requests@2.31.0`
  - **Vulnerability:** HTTP response smuggling in requests library
  - **Impact:** Attacker can manipulate HTTP responses, bypass security controls
  - **Why it matters:** Used in authentication verification, credential validation
  - **Narrative link:** This vulnerable dependency enables the authentication bypass found in DAST testing
  - **Remediation:** Upgrade to `requests>=2.32.0`

**Bandit - Python Security Issues (8 findings)**
- **[CRITICAL] Hardcoded Password** in `config/database.py:42`
  ```python
  DB_PASSWORD = "SecureP@ssw0rd2024"  # ❌ VIOLATION
  ```
  - **Why it's here:** Developer left password in code during development
  - **Impact:** Anyone with code access can connect to production database
  - **Narrative link:** This hardcoded password is later deployed to production and exposed in the IaC configuration (Terraform variable)
  - **Root cause:** No `.gitignore` rules, no pre-commit hooks, developer workflow issue

- **[CRITICAL] Flask Debug Mode Enabled** in `app.py:201`
  ```python
  app.run(debug=True)  # ❌ VIOLATION - Enabled in production
  ```
  - **Why it's here:** Developer forgot to disable debug mode
  - **Impact:** Stack traces exposed, code execution possible via interactive debugger
  - **Narrative link:** ZAP DAST scan detects this in runtime, confirming the vulnerability is deployed

- **[HIGH] Unsafe Subprocess Shell=True** in `utils/document_processor.py:78`
  ```python
  subprocess.run(cmd, shell=True)  # ❌ VIOLATION - Command injection risk
  ```
  - **Why it's here:** Used for document conversion, developer took shortcut
  - **Impact:** Attacker can inject shell commands if document name is controlled
  - **Narrative link:** ZAP testing confirms command injection in `/api/documents/convert`

- **[MEDIUM] Insecure Hashing (MD5)** in `services/password_hashing.py:15`
  ```python
  import hashlib
  hash_obj = hashlib.md5(password.encode())  # ❌ VIOLATION - MD5 is broken
  ```
  - **Why it's here:** Legacy code from old password system
  - **Impact:** Passwords can be cracked offline if database is breached
  - **Narrative link:** IaC misconfiguration (unencrypted RDS) compounds this issue

**Semgrep - Pattern-Based Issues (7 findings)**
- **[CRITICAL] SQL Injection** in `routers/search.py:45`
  ```python
  query = f"SELECT * FROM documents WHERE title = '{user_input}'"  # ❌ VIOLATION
  ```
  - **Why it's here:** Developer used f-string instead of parameterized query
  - **Impact:** Complete database compromise
  - **Narrative link:** ZAP DAST confirms this with payload testing: `' OR '1'='1`

- **[CRITICAL] Pickle Deserialization** in `services/serializer.py:89`
  ```python
  data = pickle.loads(untrusted_data)  # ❌ VIOLATION - RCE vulnerability
  ```
  - **Why it's here:** Used for caching, developer unaware of pickle risks
  - **Impact:** Remote code execution if attacker controls serialized data
  - **Narrative link:** ZAP finds this exploitable in `/api/cache/load`

- **[HIGH] Unsafe YAML Loading** in `config/loader.py:22`
  ```python
  config = yaml.load(config_file)  # ❌ VIOLATION - Should use safe_load
  ```
  - **Why it's here:** Configuration loader from user-uploaded files
  - **Impact:** RCE through YAML gadget chains
  - **Narrative link:** Presidio privacy scan finds sensitive data in config files

#### Narrative Insight
The SAST phase reveals **developer workflow issues**: hardcoded secrets, debug modes left on, unsafe patterns. These are not sophisticated vulnerabilities but rather "left-hand-right-hand" mistakes. The findings suggest:
- **No code review process** (hardcoded password in production)
- **No automated linting** (SQL injection patterns missed)
- **No environment configuration** (Flask debug mode not environment-aware)

---

### 2. SBOM Phase: Dependency Inventory

**Scanner:** Syft
**Purpose:** Document complete dependency tree and identify known vulnerabilities

#### Key Finding

**Vulnerable Package:** `requests@2.31.0`
- **Vulnerability:** CVE-2024-1086 (HTTP response smuggling)
- **Used by:** Multiple components
  - Authentication verification in `auth/oauth.py`
  - API integrations in `integrations/external_apis.py`
  - Document fetching in `services/document_retriever.py`
- **Why it matters:** This single CVE affects multiple code paths and critical functions

#### Other Notable Dependencies

| Package | Version | License | Status | Note |
|---------|---------|---------|--------|------|
| fastapi | 0.104.1 | MIT | ✓ Secure | No known vulnerabilities |
| pydantic | 2.5.0 | MIT | ✓ Secure | Input validation library |
| neo4j | 5.14.0 | Apache-2.0 | ✓ Secure | Audit log driver |
| cryptography | 41.0.7 | Apache-2.0 OR BSD-3-Clause | ✓ Secure | Encryption library |
| PyYAML | 6.0.1 | MIT | ⚠️ Risky | Unsafe loading in code |
| boto3 | 1.29.7 | Apache-2.0 | ✓ Secure | AWS SDK |

#### Narrative Insight
The SBOM shows the application is using modern, well-maintained dependencies. However, **one outdated package (requests)** creates vulnerability cascade. This is the most common attack vector in real applications: not custom code flaws, but neglected dependency management.

---

### 3. Privacy Phase: Secrets & PII Detection

**Scanner:** Presidio
**Purpose:** Find hardcoded secrets, PII, and sensitive data in code

#### Key Findings Connection

**[CRITICAL] Hardcoded Database Password**
```python
# In config/database.py (same as Bandit finding)
DB_PASSWORD = "SecureP@ssw0rd2024"
```
- **Entity Type:** PASSWORD
- **Confidence:** 95%
- **Narrative link:**
  - Found by SAST (Bandit)
  - Stored in IaC (Terraform variables)
  - Deployed to production environment

**[CRITICAL] AWS Access Key in Environment Config**
```python
# In config/aws.py
AWS_ACCESS_KEY = "AKIA2HCTQRSABC12345"
AWS_SECRET_KEY = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
```
- **Entity Type:** AWS_CREDENTIALS
- **Confidence:** 98%
- **Impact:** Full AWS account access if compromised
- **Narrative link:** These credentials are baked into Docker image in IaC scan

**[HIGH] Personal Information in Test Data**
```python
# In tests/fixtures.py
TEST_USER = {
    "name": "John Smith",
    "email": "john.smith@company.com",
    "phone": "555-0142",
    "ssn": "123-45-6789"
}
```
- **Entity Types:** PERSON, EMAIL, PHONE_NUMBER, SOCIAL_SECURITY_NUMBER
- **Confidence:** 90%+
- **Narrative link:** These should be anonymized or synthetic data

**[HIGH] Credit Card Numbers in Documentation**
```markdown
# In docs/integration-examples.md
Example test card: 4532015112830366
CVC: 123
```
- **Entity Type:** CREDIT_CARD
- **Confidence:** 94%
- **Narrative link:** Documentation expose test credentials

**[MEDIUM] Database Connection String with Credentials**
```
# In docker-compose.yml
DATABASE_URL=postgresql://admin:SecureP@ssw0rd2024@db:5432/certus_tap
```

#### Narrative Insight
The privacy scan reveals **systemic credential management failures**:
- Secrets hardcoded in application code
- Credentials in configuration files
- Test data using real PII
- Documentation exposing sensitive examples

This suggests **no secrets management infrastructure** (no use of AWS Secrets Manager, HashiCorp Vault, or similar). Developers are managing secrets manually and making mistakes.

---

### 4. DAST Phase: Runtime Vulnerabilities

**Scanner:** OWASP ZAP
**Purpose:** Find vulnerabilities in the running application

#### Key Findings Connection

**[CRITICAL] SQL Injection** (CWE-89, CVSS 9.8)
- **Endpoint:** `POST /api/documents/search`
- **Parameter:** `query` parameter
- **Test Payload:** `' OR '1'='1`
- **Root Cause:** Semgrep finding in `routers/search.py:45` now confirmed in running code
- **Impact:** Complete database read/write
- **Narrative:** The hardcoded SQL string from SAST is vulnerable when user input reaches it

**[CRITICAL] Authentication Bypass** (CWE-287, CVSS 9.1)
- **Endpoint:** `GET /api/admin/users`
- **Vulnerability:** Session tokens are predictable (1000, 1001, 1002)
- **Root Cause:**
  - Hardcoded password in code (Bandit finding)
  - No strong authentication library used
  - Vulnerable requests library (CVE-2024-1086) used in auth verification
- **Impact:** Impersonate any user, access admin panel

**[CRITICAL] Java Deserialization RCE** (CWE-502, CVSS 9.8)
- **Endpoint:** `POST /api/cache/load`
- **Vulnerability:** Pickle.loads on untrusted data
- **Root Cause:** Semgrep finding `services/serializer.py:89` confirmed
- **Impact:** Remote code execution

**[CRITICAL] Unencrypted Password Transmission** (CWE-311, CVSS 8.1)
- **Endpoint:** `POST /api/auth/login`
- **Issue:** Password sent over HTTP (not HTTPS)
- **Root Cause:**
  - Flask debug mode enabled (Bandit finding)
  - No SSL/TLS enforcement in application
  - IaC misconfiguration in load balancer (no HTTPS redirect)
- **Impact:** Credential capture in transit

**[HIGH] Cross-Site Scripting (XSS)** (CWE-79, CVSS 6.1)
- **Endpoint:** `POST /api/documents/{id}/comments`
- **Vulnerability:** User comments reflected without encoding
- **Test Payload:** `<script>alert('XSS')</script>`
- **Impact:** Session hijacking, credential theft

**[HIGH] Insecure Cookies** (CWE-614, CVSS 6.5)
- **Issue:** Session cookies missing HttpOnly, Secure, SameSite flags
- **Impact:** XSS can steal cookies; CSRF attacks possible
- **Root Cause:** Flask session configuration not hardened

**[HIGH] Missing CSRF Protection** (CWE-352, CVSS 6.5)
- **Endpoint:** `POST /api/users/{id}/password`
- **Issue:** No CSRF tokens on state-changing operations
- **Narrative:** Attacker can trick logged-in user into changing their password

**[HIGH] Broken Access Control (IDOR)** (CWE-639, CVSS 6.1)
- **Endpoint:** `GET /api/documents/{id}`
- **Vulnerability:** Only checks if user is authenticated, not if they own document
- **Attack:** Request `/api/documents/1` then `/api/documents/2` to access others' documents

**[MEDIUM] Weak Password Policy** (CWE-521, CVSS 5.3)
- **Issue:** Single-character passwords accepted
- **Root Cause:** No password validation library used
- **Impact:** Weak credentials even for non-guessed accounts

**[MEDIUM] Missing Security Headers** (CWE-693, CVSS 4.2)
- **Missing:** Content-Security-Policy, X-Frame-Options, Strict-Transport-Security, X-Content-Type-Options
- **Impact:** Various client-side attacks enabled

#### Narrative Insight
**DAST findings confirm SAST findings in production.** The vulnerabilities discovered in code review are actually exploitable in the running system. This is critical: it proves the SAST findings aren't theoretical—they're real attack vectors.

Key observation: **Flask debug mode is enabled**, which explains why all of this is directly testable. In a locked-down production environment, some of these might be mitigated at the network level, but here they're fully exposed.

---

### 5. IaC Phase: Infrastructure Misconfigurations

**Scanner:** Checkov
**Purpose:** Find security misconfigurations in Terraform, Docker, and Kubernetes

#### Key Findings Connection

**[CRITICAL] Wildcard IAM Policy** (CKV_AWS_1)
- **Location:** `infrastructure/terraform/iam.tf:12`
- **Violation:**
  ```terraform
  resource "aws_iam_role_policy" "app_policy" {
    policy = jsonencode({
      Statement = [{
        Effect = "Allow"
        Action = "*"           # ❌ ALL ACTIONS
        Resource = "*"         # ❌ ALL RESOURCES
      }]
    })
  }
  ```
- **Impact:** Application has permission to do ANYTHING in AWS account
- **Narrative:** Coupled with hardcoded AWS credentials (from Privacy scan), this is catastrophic
- **Exploit Chain:**
  1. Hardcoded AWS credentials in code (Presidio finding)
  2. Deployed to production via Docker image
  3. Application assumes role with wildcard permissions
  4. Attacker who compromises app can destroy entire AWS infrastructure

**[CRITICAL] S3 Bucket Public Access** (CKV_AWS_34)
- **Location:** `infrastructure/terraform/storage.tf:45`
- **Violation:**
  ```terraform
  resource "aws_s3_bucket" "documents" {
    bucket = "certus-tap-documents"
    # ❌ NO public access blocking configured
  }
  ```
- **Impact:** All documents exposed publicly
- **Narrative:**
  - Combined with SQL injection vulnerability (DAST finding), attacker can list all document IDs
  - Then download them all from public S3
  - Privacy/GDPR/HIPAA violation

**[CRITICAL] RDS Database Unencrypted** (CKV_AWS_22)
- **Location:** `infrastructure/terraform/database.tf:8`
- **Violation:**
  ```terraform
  resource "aws_db_instance" "postgres" {
    allocated_storage = 100
    storage_encrypted = false  # ❌ VIOLATION
  }
  ```
- **Impact:** Database data unencrypted at rest
- **Narrative:**
  - Compounds the SQL injection vulnerability (DAST)
  - If attacker breaches database, data is in plaintext
  - Combines with MD5 password hashing (SAST) for complete compromise
  - GDPR/HIPAA violation

**[CRITICAL] Kubernetes Overpermissive RBAC** (CKV_AWS_1 adapted)
- **Location:** `infrastructure/kubernetes/rbac.yaml:15`
- **Violation:**
  ```yaml
  apiVersion: rbac.authorization.k8s.io/v1
  kind: ClusterRoleBinding
  metadata:
    name: app-admin
  roleRef:
    kind: ClusterRole
    name: cluster-admin  # ❌ TOO PERMISSIVE
  subjects:
  - kind: ServiceAccount
    name: app
  ```
- **Impact:** Application pod can control entire Kubernetes cluster
- **Narrative:**
  - Container breakout vulnerability (pickle RCE) can now compromise entire cluster
  - Attacker can steal other applications' secrets
  - Access all databases on shared infrastructure

**[HIGH] Missing S3 Encryption** (CKV_AWS_21)
- **Location:** `infrastructure/terraform/storage.tf:60`
- **Violation:** S3 bucket for logs has no encryption configuration
- **Impact:** Audit logs are in plaintext
- **Narrative:** Combined with unencrypted RDS, there's no encryption anywhere in the stack

**[HIGH] KMS Key Rotation Disabled** (CKV_AWS_33)
- **Location:** `infrastructure/terraform/encryption.tf:3`
- **Violation:**
  ```terraform
  resource "aws_kms_key" "main" {
    enable_key_rotation = false  # ❌ VIOLATION
  }
  ```
- **Impact:** Long-lived encryption keys aren't rotated
- **Narrative:** Keys used for sensitive data never change, increasing breach window

**[HIGH] CloudTrail Audit Logging Disabled** (CKV_AWS_45)
- **Violation:** No CloudTrail configured
- **Impact:** API calls aren't logged
- **Narrative:**
  - Combined with wildcard IAM role, attacker can destroy infrastructure with no trace
  - No audit trail for compliance investigations
  - GDPR/HIPAA violation

**[HIGH] Docker Ports Exposed** (CKV_DOCKER_2)
- **Location:** `infrastructure/docker/Dockerfile:8`
- **Violation:**
  ```dockerfile
  EXPOSE 80 443 22 3306 5432  # ❌ EXPOSES TOO MANY PORTS
  ```
- **Impact:** Unnecessary ports are accessible
- **Narrative:** SSH port exposed allows direct container access

**[MEDIUM] IAM Policy Attached to User** (CKV_AWS_40)
- **Location:** `infrastructure/terraform/iam.tf:35`
- **Violation:** Permission policy attached directly to IAM user instead of role
- **Impact:** Cannot be reused; violates AWS best practices
- **Narrative:** When employee leaves, their user account might be forgotten

**[MEDIUM] VPC Flow Logs Disabled** (CKV_AWS_17)
- **Violation:** No network logging configured
- **Impact:** Network traffic isn't monitored
- **Narrative:** No visibility into lateral movement attacks

#### Narrative Insight
**IaC findings show the "permission model is broken":**
- Application has more permissions than it needs (principle of least privilege violated)
- Data isn't encrypted
- Audit trails aren't enabled
- Network isn't monitored

Key observation: The hardcoded AWS credentials (Privacy scan) combined with wildcard IAM policy (IaC scan) create a catastrophic combination. An attacker with code access can compromise the entire AWS infrastructure.

---

## Part 4: Cross-Scanner Vulnerability Chains

### Chain 1: Complete Database Compromise

```
Code Vulnerability (SAST)
  ↓
  SQL Injection in search.py (Semgrep)
  ↓
Dependency Vulnerability (SBOM)
  ↓
  requests library CVE-2024-1086
  ↓
Runtime Exploitation (DAST)
  ↓
  POST /api/documents/search with ' OR '1'='1
  ↓
Infrastructure Weakness (IaC)
  ↓
  Unencrypted RDS database (CKV_AWS_22)
  ↓
IMPACT: Complete plaintext database read/write, no encryption, no audit logs
```

**Remediation Priority:** CRITICAL
1. Apply SQL injection fix (parameterized queries)
2. Upgrade requests library
3. Enable RDS encryption
4. Enable CloudTrail logging

---

### Chain 2: Remote Code Execution via Deserialization

```
Code Vulnerability (SAST)
  ↓
  Pickle.loads on untrusted data (Semgrep)
  ↓
Runtime Exploitation (DAST)
  ↓
  POST /api/cache/load with malicious serialized object
  ↓
Infrastructure Weakness (IaC)
  ↓
  Overpermissive Kubernetes RBAC (cluster-admin)
  ↓
IMPACT: Container breakout → cluster takeover → access all databases
```

**Remediation Priority:** CRITICAL
1. Replace pickle with json (or use restrict deserialization)
2. Implement resource isolation in Kubernetes
3. Use network policies to limit lateral movement

---

### Chain 3: Complete AWS Infrastructure Compromise

```
Secrets in Code (Privacy Scan)
  ↓
  Hardcoded AWS credentials in config.py
  ↓
Infrastructure Configuration (IaC)
  ↓
  Credentials deployed to production Docker image
  ↓
IAM Permissions (IaC)
  ↓
  Application assumes role with wildcard permissions
  ↓
IMPACT: Attacker with code access can destroy entire AWS infrastructure
```

**Remediation Priority:** CRITICAL (IMMEDIATE)
1. Rotate AWS credentials immediately
2. Restrict IAM role to specific actions/resources
3. Implement secrets management (AWS Secrets Manager)
4. Remove credentials from Docker image

---

### Chain 4: Authentication Bypass + Unencrypted Transmission

```
Code Vulnerability (SAST)
  ↓
  Hardcoded password in config.py (Bandit)
  ↓
Runtime Vulnerability (DAST)
  ↓
  Predictable session tokens (CWE-287)
  ↓
Infrastructure Weakness (IaC)
  ↓
  Flask debug mode enabled (no HTTPS enforcement)
  ↓
IMPACT: Credentials in plaintext + predictable sessions = trivial auth bypass
```

**Remediation Priority:** CRITICAL
1. Implement cryptographically secure token generation
2. Enforce HTTPS at load balancer
3. Disable Flask debug mode in production
4. Implement secrets management for database password

---

## Part 5: Assessment Results Summary

### Risk Dashboard

```
CRITICAL FINDINGS:   11 findings across all scanners
HIGH FINDINGS:       16 findings
MEDIUM FINDINGS:      20 findings
LOW FINDINGS:        10 findings
─────────────────────────────────
TOTAL:              57 findings
```

### By Category

| Category | Count | Examples |
|----------|-------|----------|
| Injection | 3 | SQL Injection, Command Injection, YAML Deserialization |
| Cryptography | 8 | Unencrypted RDS, Unencrypted S3, MD5 hashing, No HTTPS |
| Access Control | 7 | IDOR, Authentication Bypass, Wildcard IAM, Overpermissive RBAC |
| Secrets Management | 4 | Hardcoded credentials, AWS keys in code, Secrets in Docker |
| Configuration | 9 | Debug mode enabled, Missing security headers, Exposed ports |
| Dependencies | 3 | Vulnerable requests library, Unsafe libraries used |
| Logging & Monitoring | 5 | No CloudTrail, No VPC Flow Logs, No audit logs |
| Other | 8 | XSS, CSRF, weak password policy, insecure cookies |

### OWASP Top 10 2021 Coverage

| Vulnerability | Scanner | Finding |
|---|---|---|
| A01:2021 – Broken Access Control | DAST, IaC | IDOR, Auth Bypass, Wildcard IAM, Overpermissive RBAC |
| A02:2021 – Cryptographic Failures | IaC, SAST, Privacy | Unencrypted DB, Unencrypted S3, MD5 hashing, Hardcoded creds |
| A03:2021 – Injection | DAST, SAST | SQL Injection, Command Injection, YAML Deserialization |
| A04:2021 – Insecure Design | IaC, DAST | Weak password policy, Missing CSRF tokens, No HTTPS |
| A05:2021 – Security Misconfiguration | IaC, SAST | Debug mode on, Exposed ports, Missing security headers, Wildcard IAM |
| A06:2021 – Vulnerable & Outdated Components | SBOM, SAST | requests@2.31.0 CVE-2024-1086 |
| A07:2021 – Identification & Authentication Failures | DAST, SAST | Hardcoded password, Predictable tokens, Weak password policy |
| A08:2021 – Software & Data Integrity Failures | SAST, Privacy | Pickle deserialization, No log integrity |
| A09:2021 – Logging & Monitoring Failures | IaC | No CloudTrail, No VPC Flow Logs, No audit logs |
| A10:2021 – SSRF | DAST | (Not found - good!) |

---

## Part 6: Non-Repudiation Assessment Value

### Why Non-Repudiation Matters for This Assessment

**Without Non-Repudiation:**
- Management could doubt assessment results
- Attackers could claim vulnerabilities were planted
- Auditors wouldn't trust findings
- No proof assessment was independent and thorough

**With Non-Repudiation (Dual-Signature Model):**

```
┌──────────────────────────────────────────┐
│ 1. Certus-Assurance Creates Scan         │
├──────────────────────────────────────────┤
│ Scans entire codebase (SAST)             │
│ Analyzes runtime (DAST)                  │
│ Reviews infrastructure (IaC)             │
│ Inner signature proof of scan creation   │
│ Inner signature timestamp: 2024-01-15 14:00 UTC │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│ 2. Results Stored in Neo4j               │
├──────────────────────────────────────────┤
│ All 57 findings recorded                 │
│ Linked to scan ID and assessment ID      │
│ Immutable chain of custody begins        │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│ 3. Certus-Trust Verifies & Signs         │
├──────────────────────────────────────────┤
│ Independent verification of findings     │
│ Validates inner signature is authentic   │
│ Creates outer signature                  │
│ Records in Sigstore/Rekor (immutable log)│
│ Outer signature timestamp: 2024-01-15 14:35 UTC │
└──────────────────────────────────────────┘
            ↓
┌──────────────────────────────────────────┐
│ 4. Non-Repudiation Proof                 │
├──────────────────────────────────────────┤
│ ✓ Assessment definitely occurred         │
│ ✓ Findings definitely found on this date │
│ ✓ Assurance independently created it     │
│ ✓ Trust independently verified it        │
│ ✓ Both signed with cryptographic proof   │
│ ✓ Sigstore records it immutably          │
│ ✓ Can't be denied, deleted, or altered   │
└──────────────────────────────────────────┘
```

### Legal & Compliance Implications

**Scenario:** Application owner claims findings are fake

**Without Non-Repudiation:**
- No proof the assessment happened
- No way to verify findings are authentic
- Could be disputed in court

**With Non-Repudiation:**
- Dual signatures prove assessment happened
- Sigstore immutable log proves timing
- Assurance and Trust both signed
- Hash chain proves findings unchanged
- Legal evidence holds up in litigation

---

## Part 7: Remediation Roadmap

### Phase 1: Emergency (Day 1)
**Goal:** Stop active exploitation

- [ ] Rotate AWS credentials immediately
- [ ] Restrict IAM policy to least privilege
- [ ] Disable Flask debug mode
- [ ] Enforce HTTPS at load balancer
- [ ] Block public access to S3 bucket
- **Impact:** Closes wildcard IAM + hardcoded credentials chain

### Phase 2: Critical (Week 1)
**Goal:** Fix exploitable vulnerabilities

- [ ] Fix SQL injection (parameterized queries)
- [ ] Fix pickle deserialization (use json)
- [ ] Fix authentication (cryptographically secure tokens)
- [ ] Upgrade requests library
- [ ] Implement CSRF tokens
- [ ] Enable RDS encryption
- **Impact:** Closes injection, deserialization, and auth chains

### Phase 3: Important (Week 2)
**Goal:** Harden configuration

- [ ] Fix IDOR vulnerabilities (ownership checks)
- [ ] Implement secure cookie flags
- [ ] Add security headers (CSP, HSTS)
- [ ] Enable CloudTrail logging
- [ ] Fix Kubernetes RBAC (least privilege)
- [ ] Remove SSH port from Docker
- **Impact:** Reduces attack surface

### Phase 4: Improvement (Month 1)
**Goal:** Long-term hardening

- [ ] Implement secrets management (AWS Secrets Manager)
- [ ] Enable KMS key rotation
- [ ] Add VPC Flow Logs
- [ ] Fix weak password policy
- [ ] Implement code review process
- [ ] Add SAST to CI/CD pipeline
- [ ] Enable container scanning
- **Impact:** Prevents future vulnerabilities

---

## Part 8: Using This Case Study with Tutorials

### Tutorial 1: Non-Repudiation Overview
Reference this case study to explain why non-repudiation matters. Show how 57 findings need defensible proof.

### Tutorial 2: Running a Security Scan
Use Certus TAP as the example application. Walk through what each scanner found.

### Tutorial 3: Passing Scans Through Trust Verification
Show the dual-signature proof from this assessment. Explain how it proves the findings authentic.

### Tutorial 4: Forensic Queries & Audit Trail
Query the findings from this assessment in Neo4j. Show the chain of custody.

### Tutorial 5: Publishing Compliance Reports
Generate a compliance report for Certus TAP findings. Explain the risk posture.

### Tutorial 6: Supply Chain Distribution
Distribute scan artifacts using OCI Registry. Link to this case study for provenance.

---

## Part 9: Key Learnings

### For Development Teams
1. **Secrets don't belong in code** - Use secrets management infrastructure
2. **Dependency updates matter** - One outdated package = full compromise
3. **Configuration is security** - Debug mode, HTTPS, authentication all matter
4. **Code review catches everything** - The SAST tools found all of this

### For DevOps/Infrastructure Teams
1. **Principle of least privilege** - Wildcard IAM is dangerous
2. **Encryption everywhere** - Unencrypted databases violate compliance
3. **Audit trails are essential** - Can't investigate without logs
4. **Network isolation** - Overpermissive RBAC = cluster compromise

### For Security Teams
1. **Multi-layer scanning works** - SAST + DAST + IaC together catch everything
2. **Non-repudiation is valuable** - Dual signatures prove assessment authenticity
3. **Vulnerability chains matter** - Individual findings less dangerous than combinations
4. **Risk prioritization is key** - 11 critical findings but some more dangerous than others

### For Management
1. **Security is not binary** - Risk can be quantified and managed
2. **Non-repudiation has business value** - Protects against disputes and litigation
3. **Remediation is achievable** - Phased approach makes problems manageable
4. **Prevention is cheaper** - Fixing before production is less costly

---

## Conclusion

This comprehensive assessment of Certus TAP demonstrates:
- **57 findings** across the entire stack (code, runtime, infrastructure)
- **Multiple vulnerability chains** showing how issues compound
- **Complete OWASP Top 10 2021 coverage** including all critical areas
- **Non-repudiation proof** that the assessment is authentic and defensible

The dual-signature model (Assurance + Trust) provides cryptographic proof that:
- ✓ Assessment definitely occurred on this date
- ✓ Findings are authentic and unchanged
- ✓ Results can't be disputed or denied
- ✓ Chain of custody is complete and auditable

This case study is the foundation for understanding why comprehensive, verifiable security assessments matter in enterprise environments.

---

## References

- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [CWE/CVSS Database](https://cwe.mitre.org/)
- [Sigstore Documentation](https://docs.sigstore.dev/)
- [SARIF Specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
