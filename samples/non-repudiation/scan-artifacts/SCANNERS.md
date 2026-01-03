# Scanner-Specific SARIF Examples

This directory contains comprehensive SARIF 2.1 output examples from three major Python security scanners: Trivy, Semgrep, and Bandit. Each demonstrates how different tools map their findings to the standardized SARIF format.

## Overview

| Scanner | File | Focus | Findings | Type |
|---------|------|-------|----------|------|
| **Trivy** | `trivy.sarif.json` | Multi-language dependency vulnerabilities | 6 | CVE/SBOM-based |
| **Semgrep** | `semgrep.sarif.json` | Code-level security patterns (Python-specific) | 7 | Pattern-based (SAST) |
| **Bandit** | `bandit.sarif.json` | Python-specific security issues | 8 | Test-based (SAST) |

## Scanner Comparison

### Trivy
- **Purpose:** Vulnerability scanning for container images, filesystems, code repos
- **Detection Method:** Database of known vulnerabilities (CVEs, advisories)
- **Language Coverage:** Multi-language (Python, Go, Java, Ruby, PHP, Node.js, etc.)
- **Findings Type:** CVE identifiers with CVSS scores
- **Strengths:** Fast, comprehensive dependency scanning, SBOM generation
- **Output Format:** SARIF with structured vulnerability metadata

**Sample Focus:**
- HTTP response smuggling in requests library (CVE-2024-1086)
- SQL injection vulnerability (CWE-89)
- Command injection via shell=True (CWE-78)
- Disabled SSL validation (CWE-295)
- Hardcoded credentials (CWE-798)
- Weak cryptography (CWE-327)

### Semgrep
- **Purpose:** Code pattern matching and custom rule enforcement
- **Detection Method:** Pattern-based rules (similar to grep but semantic-aware)
- **Language Coverage:** Python, JavaScript, Java, Go, Ruby, and more
- **Findings Type:** Security patterns, best practices, compliance rules
- **Strengths:** Custom rules, fast, no network dependency, excellent for internal policies
- **Output Format:** SARIF with rule configurations and pattern details

**Sample Focus:**
- Insecure deserialization with pickle (CWE-502)
- SQL injection in Django/Flask (CWE-89)
- Unsafe YAML loading (CWE-502)
- Unsafe pickle deserialization (CWE-502)
- Use of eval() function (CWE-95)
- Use of exec() function (CWE-95)
- Missing Django CSRF protection (CWE-352)

### Bandit
- **Purpose:** Python-specific security linter
- **Detection Method:** AST analysis of Python code
- **Language Coverage:** Python only
- **Findings Type:** Python security issues, code quality
- **Strengths:** Purpose-built for Python, high precision
- **Output Format:** SARIF with Bandit test IDs and severity levels

**Sample Focus:**
- Insecure Paramiko policy (AutoAddPolicy)
- Assert statements for validation
- Hardcoded passwords
- subprocess with shell=True
- Insecure hash functions (MD5, SHA1)
- Bare except clauses
- Flask debug mode enabled
- Insecure password hashing

## Using Scanner Samples in Tutorials

### Tutorial 2: Running a Security Scan with Provenance
**Use:** Compare output from different scanners
```bash
# View Trivy findings
cat samples/non-repudation/scan-artifacts/trivy.sarif.json | jq '.runs[0].results[] | {title: .message.text, severity: .level}'

# View Semgrep findings
cat samples/non-repudation/scan-artifacts/semgrep.sarif.json | jq '.runs[0].results[] | {title: .message.text, severity: .level}'

# View Bandit findings
cat samples/non-repudation/scan-artifacts/bandit.sarif.json | jq '.runs[0].results[] | {title: .message.text, severity: .level}'
```

### Tutorial 5: Compliance Reporting
**Use:** Show findings from multiple scanners in one report
```bash
# Combine findings from all scanners
jq -s 'add' trivy.sarif.json semgrep.sarif.json bandit.sarif.json | \
  jq '.runs[0].results | group_by(.level) | map({level: .[0].level, count: length})'
```

### Understanding Finding Severity Mapping

Different scanners use different severity conventions:

**Trivy** (follows CVSS):
- error = Critical/High severity
- warning = Medium/Low severity
- note = Informational

**Semgrep**:
- error = Security issue requiring action
- warning = Code quality/best practice
- note = Informational

**Bandit**:
- error = HIGH/CRITICAL issues
- warning = LOW/MEDIUM issues
- note = Informational

## Real-World Scenarios

### Scenario 1: Dependency Vulnerability (Trivy)
**Finding:** CVE-2024-1086 in requests library
**Scanner:** Trivy (dependency checker)
**Severity:** CRITICAL (9.8 CVSS)
**Timeline:** CVE published Jan 10, found in scan Jan 15

This demonstrates how Trivy quickly identifies known vulnerabilities in dependencies—critical for supply chain security.

### Scenario 2: Code Pattern Vulnerability (Semgrep)
**Finding:** SQL injection via f-string concatenation
**Scanner:** Semgrep (pattern matching)
**Severity:** CRITICAL (CWE-89)
**Code:** `query = f'SELECT * FROM users WHERE email = {email}'`

This shows how Semgrep catches code-level security issues before they reach production. Custom rules can enforce company-specific policies.

### Scenario 3: Python-Specific Issue (Bandit)
**Finding:** Flask debug=True in production code
**Scanner:** Bandit (Python AST analysis)
**Severity:** CRITICAL (CWE-434)
**Code:** `app.run(debug=True)`

Bandit specializes in catching Python-specific anti-patterns that static analysis can't easily detect.

## SARIF Structure Comparison

### Common Elements
All three tools produce SARIF 2.1 with:
- `version`: "2.1.0"
- `runs[].tool.driver.name`: Scanner name
- `runs[].tool.driver.version`: Scanner version
- `runs[].results[]`: Array of findings
- `locations[]`: Where finding was detected
- `ruleId`: Identifier for the issue

### Tool-Specific Properties

**Trivy**:
```json
{
  "properties": {
    "vulnerability": {
      "cveId": "CVE-2024-1086",
      "severity": "CRITICAL",
      "publishedDate": "2024-01-10T00:00:00Z",
      "affectedComponent": "requests",
      "affectedVersionRange": "< 2.31.0"
    }
  }
}
```

**Semgrep**:
```json
{
  "properties": {
    "vulnerability": {
      "cweId": "CWE-502",
      "severity": "CRITICAL",
      "remediation": "Use json.loads() or implement restricted unpickler"
    }
  }
}
```

**Bandit**:
```json
{
  "properties": {
    "vulnerability": {
      "testId": "B602",
      "severity": "HIGH",
      "remediation": "Use paramiko.WarningPolicy() or manage known_hosts explicitly"
    }
  }
}
```

## Combining Scanner Results

In a real CI/CD pipeline, you'd run multiple scanners and combine results:

```bash
#!/bin/bash
# Run all scanners
trivy fs --format sarif . > trivy-results.sarif
semgrep --json . | semgrep-to-sarif > semgrep-results.sarif
bandit -f json -o bandit-json.json . && \
  bandit-to-sarif bandit-json.json > bandit-results.sarif

# Merge results
jq -s '.[0] | .runs += ([.[1], .[2]].runs | add)' \
  trivy-results.sarif \
  semgrep-results.sarif \
  bandit-results.sarif > combined-results.sarif

# Analyze combined
echo "Total findings: $(jq '.runs[].results | length' combined-results.sarif | paste -sd+ | bc)"
echo "By severity:"
jq -r '.runs[].results[].level' combined-results.sarif | sort | uniq -c
```

## Remediation by Scanner Type

### Trivy Findings
**Type:** Dependency vulnerabilities
**Remediation:** Upgrade or patch libraries
**Example:** `requests` 2.31.0 → 2.32.0
**Timeline:** Often available within days of CVE publication

### Semgrep Findings
**Type:** Code-level security patterns
**Remediation:** Refactor code to use safe patterns
**Example:** SQL injection → use parameterized queries
**Timeline:** Code review, testing, deployment cycle

### Bandit Findings
**Type:** Python-specific anti-patterns
**Remediation:** Change Python practices
**Example:** `debug=True` → environment-based control
**Timeline:** Configuration change or code refactor

## Scanner Configuration

### Trivy
```bash
trivy image --severity CRITICAL,HIGH \
  --vuln-type os,library \
  --scanners secret,config \
  alpine:latest
```

### Semgrep
```bash
semgrep --config=p/security-audit \
  --config=p/owasp-top-ten \
  --json src/
```

### Bandit
```bash
bandit -r src/ \
  --severity-level medium \
  --format json \
  -ll  # Confidence level: low, medium, high
```

## Converting Other Formats to SARIF

If using other scanners, tools exist to convert to SARIF:

- **npm audit** → `npm-audit-to-sarif`
- **Go gosec** → Built-in SARIF output
- **Java Checkmarx** → SARIF plugin available
- **Generic JSON** → Custom conversion scripts

## Testing with Samples

### Validate SARIF Schema
```bash
# Install sarif-lint
npm install -g @microsoft/sarif-lint

# Validate each file
sarif-lint trivy.sarif.json
sarif-lint semgrep.sarif.json
sarif-lint bandit.sarif.json
```

### Parse and Analyze
```bash
# Count findings by severity
jq '[.runs[0].results[] | .level] | group_by(.) | map({level: .[0], count: length})' trivy.sarif.json

# List all rule IDs
jq -r '.runs[0].results[].ruleId' semgrep.sarif.json | sort | uniq

# Extract remediation advice
jq -r '.runs[0].results[] | "\(.message.text): \(.properties.vulnerability.remediation)"' bandit.sarif.json
```

## References

- [SARIF 2.1.0 Specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
- [Trivy Documentation](https://aquasecurity.github.io/trivy/)
- [Semgrep Documentation](https://semgrep.dev/docs)
- [Bandit Documentation](https://bandit.readthedocs.io)
- [CWE Top 25](https://cwe.mitre.org/top25/)
- [CVSS Calculator](https://www.first.org/cvss/calculator/3.1)

## Key Insights

1. **Defense in Depth:** Run multiple scanners for comprehensive coverage
   - Trivy catches known vulnerabilities
   - Semgrep catches code-level patterns
   - Bandit catches Python-specific issues

2. **Severity Varies:** CRITICAL in Trivy may be different from CRITICAL in Bandit
   - Always normalize severity levels
   - Consider context (what framework? what tier?)

3. **Finding Overlap:** Same vulnerability detected by multiple scanners
   - SQL injection detected by Semgrep AND Bandit patterns
   - Helpful for confirmation but increases noise

4. **Custom Rules:** Only Semgrep offers custom pattern rules
   - Enforce company security policies
   - Reference internal security libraries
   - Block known-bad patterns specific to your codebase

5. **Language Focus:** Choose scanners for your tech stack
   - Trivy: Universal (all languages)
   - Semgrep: Multi-language but strongest in Python/JS
   - Bandit: Python-only but very precise
