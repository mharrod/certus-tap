# Non-Repudiation Sample Data

This directory contains comprehensive, production-grade sample data for all non-repudiation tutorials. Use these files to learn, test, and verify the complete security scanning pipeline without needing to run all services.

**START HERE:** Read [CASE_STUDY.md](CASE_STUDY.md) to understand how all samples fit together in a cohesive fictional application narrative.

## Directory Structure

```
non-repudation/
├── CASE_STUDY.md               # ⭐ START HERE: Complete narrative & vulnerability chains
│
├── scan-artifacts/              # Mock Certus-Assurance scan outputs
│   ├── scan.json               # Scan metadata with inner signatures
│   ├── trivy.sarif.json        # SAST findings (dependency vulnerabilities)
│   ├── semgrep.sarif.json      # SAST findings (pattern-based code issues)
│   ├── bandit.sarif.json       # SAST findings (Python-specific security)
│   ├── syft.spdx.json          # Software Bill of Materials (SPDX)
│   ├── presidio-privacy.sarif.json  # Privacy findings (PII/credentials)
│   ├── zap-dast.sarif.json     # DAST findings (runtime vulnerabilities)
│   └── checkov-iac.sarif.json  # IaC findings (infrastructure misconfigurations)
│
├── verification-proofs/        # Mock Certus-Trust verification outputs
│   └── verification-proof.json # Dual-signature proof with Sigstore entry
│
├── neo4j-queries/              # Sample Neo4j forensic queries and results
│   └── forensic-queries.cypher # 8 practical Cypher queries with expected outputs
│
├── compliance-reports/         # Generated compliance report samples
│   ├── compliance-report.json  # Structured compliance data (JSON)
│   └── compliance-report.html  # Professional compliance report (HTML)
│
├── oras-artifacts/            # OCI artifact examples
│   └── (generated during OCI tutorial)
│
├── signatures/                # Cosign signature examples
│   └── (generated during signing tutorial)
│
├── CASE_STUDY.md              # Complete narrative of assessed application
├── README.md                  # This file
│
└── scan-artifacts/
    ├── SCANNERS.md            # Scanner comparison (Trivy, Semgrep, Bandit)
    ├── PRIVACY_SCANNING.md    # Privacy scanning guide (Presidio)
    └── DAST_AND_IAC.md        # DAST & IaC guide (ZAP, Checkov)
```

## Files and Their Purpose

### 1. Scan Artifacts

#### `scan.json` - Certus-Assurance Scan Metadata

**Size:** ~2 KB | **Format:** JSON | **Location:** Root of scan bundle

Contains complete provenance and inner signature data from Certus-Assurance:

- Scan ID, git URL, branch, commit hash
- Timestamps: created, completed, duration
- Inner signature with full certificate chain
- Scanners invoked (Trivy, Syft, ZAP) with versions
- Links to all artifact files

**Usage:**

- Tutorial 2: Understand provenance metadata
- Tutorial 4: Extract inner signature for verification
- Tutorial 5: Document scan source in compliance report

**Key Fields:**

```json
{
  "scan_id": "scan_550e8400e29b41d4a716446655440000",
  "inner_signature": {
    "signer": "certus-assurance@certus.cloud",
    "signature": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQ...",
    "algorithm": "SHA256-RSA"
  }
}
```

#### `trivy.sarif.json` - Security Findings (SARIF 2.1)

**Size:** ~5 KB | **Format:** JSON | **Standard:** OASIS SARIF

Contains 6 realistic security findings:

- 1 CRITICAL (CVE-2024-1086)
- 2 HIGH (CWE-89, CWE-78)
- 2 MEDIUM (CWE-295, CWE-798)
- 1 LOW (CWE-327)

Each finding includes:

- Rule ID, severity, title, description
- CWE/CVE identifiers
- File location with line/column numbers
- Detailed vulnerability metadata
- Remediation guidance

**Usage:**

- Tutorial 2: Examine SARIF structure and findings
- Tutorial 3: Extract findings for verification
- Tutorial 5: Populate compliance report
- Tutorial 6: Analyze findings in compliance context

**Example Finding:**

```json
{
  "ruleId": "CVE-2024-1086",
  "level": "error",
  "message": "HTTP response smuggling in requests library",
  "properties": {
    "vulnerability": {
      "cveId": "CVE-2024-1086",
      "severity": "CRITICAL",
      "affectedComponent": "requests",
      "affectedVersionRange": "< 2.31.0",
      "fixedVersionRange": ">= 2.32.0"
    }
  }
}
```

#### `syft.spdx.json` - Software Bill of Materials (SPDX 2.3)

**Size:** ~4 KB | **Format:** JSON | **Standard:** SPDX 2.3

Complete dependency inventory:

- 8 packages with versions and licenses
- Dependency relationships (DEPENDS_ON)
- License compliance information
- Package URLs (PURL) for each component

Packages:

- certus-TAP (MIT)
- fastapi@0.104.1 (MIT)
- requests@2.31.0 (Apache-2.0) ← Vulnerable!
- pydantic@2.5.0 (MIT)
- neo4j@5.14.0 (Apache-2.0)
- cryptography@41.0.7 (Apache-2.0 OR BSD-3-Clause)
- PyYAML@6.0.1 (MIT)
- boto3@1.29.7 (Apache-2.0)

**Usage:**

- Tutorial 2: Understand SBOM structure and dependencies
- Tutorial 5: Document package inventory in report
- Tutorial 6: Analyze license compliance
- Forensic queries: Track vulnerable dependencies

**Example Package:**

```json
{
  "name": "requests",
  "versionInfo": "2.31.0",
  "downloadLocation": "https://pypi.org/project/requests/2.31.0/",
  "licenseConcluded": "Apache-2.0",
  "externalRefs": [
    {
      "referenceType": "purl",
      "referenceLocator": "pkg:pypi/requests@2.31.0"
    }
  ]
}
```

### 2. Verification Proofs

#### `verification-proof.json` - Trust Verification Output

**Size:** ~6 KB | **Format:** JSON

Complete verification proof from Certus-Trust service showing:

- Verification status (all checks pass ✓)
- Inner and outer signatures valid
- Chain unbroken
- Signers: Assurance and Trust
- Artifact hashes (SHA256)
- Sigstore entry UUID and inclusion proof
- Policy compliance checks

**Key Sections:**

```json
{
  "verification_proof": {
    "chain_verified": true,
    "inner_signature_valid": true,
    "outer_signature_valid": true,
    "signer_inner": "certus-assurance@certus.cloud",
    "signer_outer": "certus-trust@certus.cloud",
    "sigstore_timestamp": "2024-01-15T14:35:23Z",
    "rekor_entry_uuid": "550e8400-e29b-41d4-a716-446655440001"
  }
}
```

**Usage:**

- Tutorial 4: Understand verification output structure
- Tutorial 5: Use verification_proof in compliance report
- Tutorial 6: Document Sigstore immutability

### 3. Neo4j Queries

#### `forensic-queries.cypher` - Forensic Analysis Examples

**File:** Cypher queries with expected results

Contains 8 practical queries for compliance and investigation:

1. **Find all verified scans** - List verified assessments with findings count
2. **Verify unbroken chain** - Confirm all signatures valid for specific assessment
3. **Timeline by severity** - Track findings across time
4. **Chain of custody** - Complete audit trail for investigation
5. **Incident investigation** - Who modified what and when
6. **Compliance findings** - All verified findings with remediation status
7. **Dependency analysis** - SBOM components with vulnerability counts
8. **Complete chain verification** - Prove non-repudiation from creation to storage

Each query includes:

- Cypher syntax
- Expected JSON results
- Realistic data matching sample artifacts

**Usage:**

- Tutorial 3: Run queries to audit verified findings
- Tutorial 5: Document chain of custody in report
- Compliance: Generate audit trails for regulators
- Investigation: Track scan through complete pipeline

**Example Query Result:**

```json
{
  "assessment_id": "assessment-20240115-001",
  "verified_by": "certus-trust@certus.cloud",
  "verified_at": "2024-01-15T14:35:25Z",
  "findings_count": 6
}
```

### 4. Compliance Reports

#### `compliance-report.json` - Structured Compliance Data

**Size:** ~25 KB | **Format:** JSON

Comprehensive compliance assessment including:

- Report metadata (ID, assessment ID, signatures)
- Executive summary with conditional approve decision
- Verification chain proof
- Risk summary (critical, high, medium, low counts)
- 6 detailed findings with remediation
- OWASP Top 10 2021 compliance assessment
- SBOM analysis with license compliance
- Complete audit trail
- Next steps and follow-up date

**Key Sections:**

```json
{
  "report_metadata": {
    "report_id": "report_550e8400e29b41d4a716446655440002",
    "assessment_id": "assessment-20240115-001",
    "verified": true,
    "signature": {
      "signer": "certus-trust@certus.cloud",
      "timestamp": "2024-01-15T14:35:32Z"
    }
  },
  "executive_summary": {
    "overall_status": "CONDITIONAL_APPROVE",
    "risk_posture": "MEDIUM",
    "confidence_level": 95
  },
  "risk_summary": {
    "statistics": {
      "critical": 1,
      "high": 2,
      "medium": 2,
      "low": 1,
      "total": 6
    }
  }
}
```

**Usage:**

- Tutorial 5: Reference complete compliance structure
- Automation: Template for compliance report generation
- Dashboards: Parse JSON for visualization
- Archival: Store for long-term compliance records

#### `compliance-report.html` - Professional Report

**Size:** ~20 KB | **Format:** HTML5 + CSS3

Production-grade HTML report with:

- Professional header with product info
- Color-coded severity badges
- Risk summary with statistics
- Detailed finding cards with remediation
- OWASP compliance checklist
- Interactive timeline of events
- Action items with due dates
- Footer with verification links

**Styling Features:**

- Responsive design (mobile-friendly)
- Print-optimized (page breaks)
- Color accessibility
- Section-level page breaks for printing
- Professional typography

**Usage:**

- Tutorial 5: Generate compliance reports for stakeholders
- Printing: Output to PDF for archival
- Email: Send to leadership/auditors
- Web: Serve from compliance dashboard

### 5. OCI Artifacts (Generated During Tutorial)

During Tutorial 6, you'll create:

- `oras-artifacts/` - Pushed artifacts from OCI Registry
- `signatures/` - Cosign signatures for artifacts

## Using Sample Data in Tutorials

### Tutorial 1: Non-Repudiation Overview

**No samples needed** - Conceptual foundation

### Tutorial 2: Running a Security Scan with Provenance

**Use:** `scan-artifacts/scan.json`, `trivy.sarif.json`, `syft.spdx.json`

```bash
# Examine scan metadata
cat samples/non-repudation/scan-artifacts/scan.json | jq

# View SARIF findings
cat samples/non-repudation/scan-artifacts/trivy.sarif.json | jq '.runs[0].results'

# Check SBOM packages
cat samples/non-repudation/scan-artifacts/syft.spdx.json | jq '.packages[] | {name, version}'
```

### Tutorial 3: Passing Scans Through Certus-Trust

**Use:** `verification-proofs/verification-proof.json`

```bash
# View verification structure
cat samples/non-repudation/verification-proofs/verification-proof.json | jq '.verification_proof'

# Extract Sigstore entry
cat samples/non-repudation/verification-proofs/verification-proof.json | jq '.verification_proof.rekor_entry_uuid'
```

### Tutorial 4: Forensic Queries & Audit Trail

**Use:** `neo4j-queries/forensic-queries.cypher`

```bash
# Copy queries to run against your Neo4j instance
cat samples/non-repudation/neo4j-queries/forensic-queries.cypher
```

### Tutorial 5: Publishing Signed Compliance Reports

**Use:** `compliance-reports/compliance-report.json`, `compliance-report.html`

```bash
# Parse compliance report structure
cat samples/non-repudation/compliance-reports/compliance-report.json | jq '.risk_summary'

# View HTML in browser
open samples/non-repudation/compliance-reports/compliance-report.html
```

### Tutorial 6: Supply Chain Distribution with OCI

**Generate:** OCI artifacts using sample data

```bash
# Push sample artifacts to OCI Registry
oras push localhost:5000/certus-samples:latest \
  samples/non-repudation/scan-artifacts/scan.json \
  samples/non-repudation/scan-artifacts/trivy.sarif.json \
  samples/non-repudation/scan-artifacts/syft.spdx.json
```

## Sample Data Characteristics

### Realism

- Uses real CVE identifiers and severity scores
- Realistic file paths and code snippets
- Proper SARIF format with line/column numbers
- Valid SPDX 2.3 structure
- Production-grade JSON/HTML

### Completeness

- 6 findings across severity levels
- 8 dependencies with licenses
- Full audit trail with timestamps
- Complete verification chain
- Comprehensive compliance assessment

### Consistency

- All IDs, UUIDs, and timestamps match across files
- Scan ID, assessment ID, and report ID linked throughout
- Findings referenced consistently in multiple files
- Signatures and hashes are consistent

### Extensibility

- Can modify finding severity/counts
- Can change product name/version
- Can update dates/times for your context
- Can add additional findings following the pattern

## Modifying Sample Data

### Change Product Name

```bash
# Update all references
sed -i 's/Certus TAP/Your Product/g' samples/non-repudation/**/*.json
sed -i 's/certus-TAP/your-product/g' samples/non-repudation/**/*.json
```

### Change Assessment Date

```bash
# Update all timestamps (macOS)
sed -i '' 's/2024-01-15/2024-02-20/g' samples/non-repudation/**/*.json
```

### Add New Finding

1. Add to `trivy.sarif.json` with CWE ID
2. Update risk_summary.statistics in `compliance-report.json`
3. Add finding card to `compliance-report.html`
4. Update findings query results in `forensic-queries.cypher`

## Key Insights from Sample Data

### Vulnerability Progression

- CVE-2024-1086: Dependency update available (easy fix)
- CWE-89, CWE-78: Code-level issues requiring refactoring
- CWE-295, CWE-798: Configuration issues with moderate effort
- CWE-327: Low-priority improvement

### Verification Chain

Shows complete non-repudiation:

1. Assurance creates scan + inner signature
2. Transform promotes to premium tier
3. Trust verifies + creates outer signature
4. Sigstore records immutably
5. Ask stores with verification metadata
6. Forensic queries prove chain

### Compliance Assessment

Demonstrates:

- OWASP Top 10 mapping
- Conditional approval decision
- Remediation timeline
- Action items with priorities
- Next review date

## References

- [OASIS SARIF Specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)
- [SPDX 2.3 Specification](https://spdx.github.io/spdx-spec/v2.3/)
- [OWASP Top 10 2021](https://owasp.org/Top10/)
- [Sigstore Documentation](https://docs.sigstore.dev/)
- [Cosign Signing Guide](https://docs.sigstore.dev/cosign/)

## Questions?

Refer to the tutorial documentation at `docs/learn/non-repudation/` for:

- Detailed explanations of each file format
- Step-by-step usage instructions
- Integration with live services
- Troubleshooting and FAQ
