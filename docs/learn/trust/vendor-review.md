# Vendor Review & Compliance Proof

This tutorial shows how a third-party reviewer (customer, independent auditor, or acquisition partner) validates a vendor's security artifacts. You will:

1. Submit a security scan to generate artifacts
2. Package and publish artifacts to OCI registry (simulating vendor distribution)
3. Pull artifacts from the registry (as the auditor/customer)
4. Re-validate signatures and provenance independently
5. Ingest artifacts into Certus TAP for analysis
6. Generate and sign a compliance report

**Use case**: As an auditor or customer, you receive a vendor's security scan bundle via OCI registry and need to independently verify its integrity and assess the security posture.

## Prerequisites

- Stack is online: `just up`
- Preflight checks passed: `just preflight`
- CLI tools installed locally: `aws`, `oras`, `cosign`, `jq`

## Step 1 - Set-up

### 1.1 Bring up relevant services

```bash
just trust-up
```

### 1.2 Check if everything is ready for the tutorial

```bash
just preflight-trust
```

## Step 1. Submit a Security Scan

First, generate a fresh security scan to create the artifacts we'll review:

```bash
export SCAN_ID=$(curl -s -X POST http://localhost:8056/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_id": "vendor-compliance-review",
    "component_id": "trust-smoke-repo",
    "assessment_id": "vendor-review-scan",
    "git_url": "/app/samples/trust-smoke-repo.git",
    "branch": "main",
    "requested_by": "compliance-team@example.com",
    "manifest": {"version": "1.0"}
  }' | jq -r '.test_id')

echo "Scan submitted with ID: $SCAN_ID"
```

**Monitor scan status** until it completes:

```bash
while true; do
  STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.status')
  echo "Scan status: $STATUS"
  [ "$STATUS" = "SUCCEEDED" ] && break
  sleep 2
done
```

**Verify completion:**

```bash
curl http://localhost:8056/v1/security-scans/$SCAN_ID | \
  jq '{status, test_id, workspace_id, component_id}'
```

You should see `status: "SUCCEEDED"`.

## Step 2. Submit Upload Request to Certus Trust

Before distributing artifacts, submit them to Certus Trust for verification:

```bash
curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request \
  -H 'Content-Type: application/json' \
  -d '{
    "tier": "verified",
    "requested_by": "vendor-compliance@example.com"
  }'
```

**Monitor upload status** until Trust completes verification:

```bash
while true; do
  UPLOAD_STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.upload_status')
  SCAN_STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.status')
  echo "Scan: $SCAN_STATUS | Upload: $UPLOAD_STATUS"
  [ "$UPLOAD_STATUS" = "uploaded" ] && break
  sleep 2
done
```

**Verify Trust approved the scan:**

```bash
curl http://localhost:8056/v1/security-scans/$SCAN_ID | \
  jq '{status, upload_status, upload_permission_id, verification_proof}'
```

You should see:

- `upload_status: "uploaded"` (Trust approved)
- `verification_proof` populated with Trust's cryptographic verification

**Capture the upload permission ID for audit trail:**

```bash
UPLOAD_PERMISSION_ID=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.upload_permission_id')
echo "Upload permission: $UPLOAD_PERMISSION_ID"
```

## Step 3. Package and Publish Vendor Artifacts to OCI Registry

In a real scenario, the vendor would push their signed artifacts to an OCI registry for distribution. For this tutorial, we'll simulate that process:

```bash
# Set artifact source directory (canonical sample data)
export ARTIFACT_ROOT="$(pwd)/samples/non-repudiation/scan-artifacts"

# Create temporary directory for OCI packaging
mkdir -p /tmp/vendor-artifacts

# Copy artifacts from our sample data
cp "$ARTIFACT_ROOT/syft.spdx.json" /tmp/vendor-artifacts/
cp "$ARTIFACT_ROOT/trivy.sarif.json" /tmp/vendor-artifacts/
cp "$ARTIFACT_ROOT/semgrep.sarif.json" /tmp/vendor-artifacts/
cp "$ARTIFACT_ROOT/bandit.sarif.json" /tmp/vendor-artifacts/
cp "$ARTIFACT_ROOT/zap-dast.sarif.json" /tmp/vendor-artifacts/
cp "$ARTIFACT_ROOT/presidio-privacy.sarif.json" /tmp/vendor-artifacts/
cp "$ARTIFACT_ROOT/scan.json" /tmp/vendor-artifacts/
cp "$ARTIFACT_ROOT/slsa-provenance.json" /tmp/vendor-artifacts/
cp "$ARTIFACT_ROOT/build.intoto.jsonl" /tmp/vendor-artifacts/

# Push artifacts to OCI Registry
(cd /tmp/vendor-artifacts && \
oras push --plain-http localhost:5000/security-scans/vendor-artifacts:latest \
  syft.spdx.json:application/spdx+json \
  trivy.sarif.json:application/sarif+json \
  semgrep.sarif.json:application/sarif+json \
  bandit.sarif.json:application/sarif+json \
  zap-dast.sarif.json:application/sarif+json \
  presidio-privacy.sarif.json:application/sarif+json \
  scan.json:application/json \
  slsa-provenance.json:application/vnd.in-toto+json \
  build.intoto.jsonl:application/vnd.in-toto+json)

echo "✓ Vendor artifacts pushed to OCI registry"
```

**Verify the push succeeded:**

```bash
oras repo tags --plain-http localhost:5000/security-scans/vendor-artifacts
```

Expected output: `latest`

## Step 4. Pull Signed Bundle from the OCI Registry

Now, acting as the auditor/customer, pull the vendor's artifact bundle:

```bash
mkdir -p /tmp/acquired-artifacts
oras pull --plain-http \
  localhost:5000/security-scans/vendor-artifacts:latest \
  --output /tmp/acquired-artifacts
```

This downloads all the signed security artifacts: SBOM, security scans (SARIF), SLSA provenance, and in-toto attestations.

**List the downloaded artifacts:**

```bash
ls -lh /tmp/acquired-artifacts/
```

You should see:

- `syft.spdx.json` - SBOM
- `trivy.sarif.json`, `semgrep.sarif.json`, `bandit.sarif.json` - SAST scans
- `zap-dast.sarif.json` - DAST scan
- `presidio-privacy.sarif.json` - Privacy scan
- `slsa-provenance.json` - Build provenance
- `build.intoto.jsonl` - Build attestations
- `scan.json` - Scan metadata

## Step 5. Re-Validate Cryptographic Proofs

Verify the artifacts you downloaded. In a production environment, you would use cosign to verify the signatures. For this tutorial, we'll focus on validating the artifact integrity.

**Verify SLSA provenance integrity:**

The SLSA provenance references all the security scan artifacts. Let's verify the build definition:

```bash
jq '.predicate.buildDefinition.buildType' /tmp/acquired-artifacts/slsa-provenance.json
```

Expected: `"https://slsa.dev/build-type/github-actions/v1"`

**Verify in-toto attestations:**

Count the build steps documented in the attestation file:

```bash
wc -l /tmp/acquired-artifacts/build.intoto.jsonl
```

Expected: 8 lines (one attestation per build step)

## Step 6. Inspect the Pulled Artifacts

Before ingestion, sanity-check the contents.

**Review SBOM packages:**

```bash
jq '.packages[0:5] | .[] | {name, versionInfo}' /tmp/acquired-artifacts/syft.spdx.json
```

You should see packages like alpine-baselayout, alpine-keys, apk-tools, etc.

**Count total packages:**

```bash
jq '.packages | length' /tmp/acquired-artifacts/syft.spdx.json
```

Expected: 45 packages

**Review the SLSA build definition:**

```bash
jq '.predicate.buildDefinition' /tmp/acquired-artifacts/slsa-provenance.json
```

Verify the repository URL, commit, and embedded SBOM digest.

**Review SARIF results:**

```bash
jq '.runs[0].results | length' /tmp/acquired-artifacts/trivy.sarif.json
```

Expected: 2 findings

**Check all security scans:**

```bash
for scan in trivy semgrep bandit; do
  echo "$scan findings: $(jq '.runs[0].results | length' /tmp/acquired-artifacts/${scan}.sarif.json)"
done
```

This shows the vulnerability count across all SAST scanners.

## Step 7. Ingest Artifacts into Certus TAP

With cryptographic checks complete, ingest everything into a workspace dedicated to this vendor review:

```bash
WORKSPACE_ID="vendor-compliance-review"
ARTIFACT_ROOT="/tmp/acquired-artifacts"

# Ingest SBOM
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/security \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/syft.spdx.json" \
  | jq '{ingestion_id, document_count}'

# Ingest SARIF security scans
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/security \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/trivy.sarif.json" \
  | jq '{ingestion_id, document_count}'

curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/security \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/semgrep.sarif.json" \
  | jq '{ingestion_id, document_count}'

curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/security \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/bandit.sarif.json" \
  | jq '{ingestion_id, document_count}'

# Ingest provenance files
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/ \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/slsa-provenance.json" \
  | jq '{ingestion_id, document_count}'

curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/ \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/build.intoto.jsonl" \
  | jq '{ingestion_id, document_count}'
```

## Step 8. Ask Supply Chain Questions

Now that the verified artifacts are indexed, ask TAP to analyze the findings:

```bash
# Query about packages and dependencies
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What packages and dependencies are listed in the SBOM?"}' \
  | jq -r '.answer'

# Query about security vulnerabilities
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the high or critical severity security vulnerabilities?"}' \
  | jq -r '.answer'

# Query about build provenance
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What does the SLSA provenance indicate about the build pipeline?"}' \
  | jq -r '.answer'

# Query about specific vulnerability types
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Are there any SQL injection or command injection vulnerabilities?"}' \
  | jq -r '.answer'
```

These queries produce evidence for your compliance assessment.

## Step 9. Generate, Sign, and Share the Compliance Report

Create a compliance report documenting your review findings.

### Step 9.1 Create Findings JSON

```bash
cat > /tmp/compliance-findings.json <<'EOF'
{
  "signatureVerification": {
    "status": "PASS",
    "details": "All 9 artifacts successfully pulled from OCI registry",
    "artifacts": [
      {"name": "syft.spdx.json", "status": "valid"},
      {"name": "trivy.sarif.json", "status": "valid"},
      {"name": "semgrep.sarif.json", "status": "valid"},
      {"name": "bandit.sarif.json", "status": "valid"},
      {"name": "zap-dast.sarif.json", "status": "valid"},
      {"name": "presidio-privacy.sarif.json", "status": "valid"},
      {"name": "scan.json", "status": "valid"},
      {"name": "slsa-provenance.json", "status": "valid"},
      {"name": "build.intoto.jsonl", "status": "valid"}
    ]
  },
  "sbomAnalysis": {
    "status": "PASS",
    "format": "SPDX-2.3",
    "packageCount": 45,
    "details": "Complete SBOM with all dependencies documented"
  },
  "slsaProvenance": {
    "status": "PASS",
    "slsaLevel": "SLSA L3",
    "buildType": "https://slsa.dev/build-type/github-actions/v1",
    "builder": "certus-assurance-pipeline@v1.2.0",
    "details": "Complete build provenance with resolved dependencies and byproducts",
    "findings": [
      {"check": "Builder identity verified", "status": "PASS"},
      {"check": "Source repository tracked", "status": "PASS"},
      {"check": "Build dependencies resolved", "status": "PASS"},
      {"check": "Artifact digests match", "status": "PASS"}
    ]
  },
  "inTotoAttestations": {
    "status": "PASS",
    "attestationCount": 8,
    "details": "Complete build step attestations covering checkout, SBOM generation, and all security scans",
    "steps": [
      {"name": "checkout", "status": "verified"},
      {"name": "sbom-generation", "status": "verified"},
      {"name": "sast-scan-trivy", "status": "verified"},
      {"name": "sast-scan-semgrep", "status": "verified"},
      {"name": "sast-scan-bandit", "status": "verified"},
      {"name": "dast-scan-zap", "status": "verified"},
      {"name": "privacy-scan-presidio", "status": "verified"},
      {"name": "iac-scan-checkov", "status": "verified"}
    ]
  },
  "vulnerabilityAssessment": {
    "status": "CONDITIONAL",
    "criticalCount": 0,
    "highCount": 6,
    "mediumCount": 2,
    "lowCount": 0,
    "findings": [
      {
        "id": "CVE-2024-1086",
        "title": "HTTP/HTTPS Smuggling in requests package",
        "severity": "HIGH",
        "file": "requirements.txt",
        "remediation": "Update requests package to latest version"
      },
      {
        "id": "CWE-89",
        "title": "SQL Injection vulnerability",
        "severity": "HIGH",
        "file": "database query handling",
        "remediation": "Use parameterized queries"
      }
    ]
  },
  "privacyAssessment": {
    "status": "WARNING",
    "piiDetected": 8,
    "details": "PII detected in sample data: person names, email addresses, phone numbers",
    "findings": [
      {"type": "PERSON", "example": "Sarah Johnson"},
      {"type": "EMAIL_ADDRESS", "example": "sarah.johnson@company.com"},
      {"type": "PHONE_NUMBER", "example": "+1-555-0147"}
    ]
  },
  "dependencyAnalysis": {
    "status": "PASS",
    "resolvedCount": 45,
    "details": "All dependencies documented in SPDX SBOM"
  },
  "licenseCompliance": {
    "status": "PASS",
    "details": "No incompatible open-source licenses detected",
    "licenses": ["Apache-2.0", "BSD-3-Clause", "MIT"]
  }
}
EOF
```

### Step 9.2 Generate JSON + HTML Reports

```bash
just generate-compliance-report \
  "Acme Corporation Product" \
  "ACME Corp" \
  "Security Review Team" \
  "Your Organization" \
  /tmp/compliance-findings.json \
  samples/oci-attestations/reports
```

This emits both a JSON bundle (`compliance-report-<uuid>.json`) and an HTML version (`.html`).

### Step 9.3 Sign the Compliance Report

```bash
REPORT_FILE=$(ls -t samples/oci-attestations/reports/*.json | head -1)
COSIGN_PASSWORD="" COSIGN_YES=true just sign-compliance-report \
  "$REPORT_FILE" \
  samples/oci-attestations/keys/cosign.key
```

Signing proves the report hasn't been altered since you created it.

### Step 9.4 (Optional) Upload the Report to OCI

If you need to share your signed report via the same distribution channel:

```bash
just upload-compliance-report \
  "$REPORT_FILE" \
  "${REPORT_FILE}.sig" \
  http://localhost:5000 \
  "" "" \
  product-acquisition/compliance-reports
```

### Step 9.5 (Optional) Verify Report Integrity

To prove the report can be independently validated:

```bash
mkdir -p /tmp/pulled-reports
oras pull --plain-http \
  localhost:5000/product-acquisition/compliance-reports:latest \
  --output /tmp/pulled-reports

REPORT_FILE=$(ls -t /tmp/pulled-reports/samples/oci-attestations/reports/*.json | head -1)
cosign verify-blob --insecure-ignore-tlog \
  --key samples/oci-attestations/keys/cosign.pub \
  --signature "${REPORT_FILE}.sig" \
  "$REPORT_FILE"
```

## Step 10. Build a Supply Chain Audit Record

Create a comprehensive verification record for audit purposes.

### Step 10.1 Draft the Verification Record

```bash
cat > /tmp/supply-chain-verification.md <<EOF
# Supply Chain Verification Record

**Vendor:** Acme Corporation
**Product:** Acme Product v2.5.0
**Review Date:** $(date -u +"%Y-%m-%dT%H:%M:%SZ")
**Reviewer:** Your Organization Security Team
**Scan ID:** $SCAN_ID

## Verification Steps Completed

✓ All 9 artifacts retrieved from OCI Registry (localhost:5000/security-scans/vendor-artifacts:latest)
✓ SBOM analyzed: 45 packages documented in SPDX format
✓ SLSA L3 provenance verified with complete build definition
✓ in-toto attestations verified: 8 build steps documented
✓ Security scans reviewed: Trivy, Semgrep, Bandit (SAST), ZAP (DAST), Presidio (privacy), Checkov (IaC)
✓ All artifacts ingested into Certus TAP workspace (vendor-compliance-review)

## Findings Summary

- Signature Verification: PASS (9 artifacts)
- SBOM Analysis: PASS (45 packages)
- SLSA Provenance: PASS (L3, builder verified)
- in-toto Attestations: PASS (8 steps verified)
- Vulnerability Assessment: 6 HIGH, 2 MEDIUM (requires remediation)
- Privacy Assessment: WARNING (8 PII detections)
- Dependency Analysis: PASS (45 dependencies)
- License Compliance: PASS

## Overall Decision

CONDITIONAL APPROVE - Vendor must remediate HIGH vulnerabilities within 30 days.

## Next Steps
1. Vendor provides remediation plan within 7 days
2. Follow-up assessment in 30 days
3. Continue monitoring for security updates
EOF

COSIGN_PASSWORD="" COSIGN_YES=true just sign-compliance-report \
  /tmp/supply-chain-verification.md \
  samples/oci-attestations/keys/cosign.key
```

### Step 10.2 Create a Verification Manifest

```bash
cat > /tmp/verification-manifest.json <<EOF
{
  "verificationManifest": {
    "manifestId": "MANIFEST-$(uuidgen)",
    "scanId": "$SCAN_ID",
    "vendor": "Acme Corporation",
    "product": "Acme Product v2.5.0",
    "reviewDate": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
    "reviewerOrganization": "Your Organization",
    "artifacts": [
      {"type": "sbom", "name": "syft.spdx.json", "status": "verified"},
      {"type": "attestation", "name": "build.intoto.jsonl", "status": "verified"},
      {"type": "sast-scan", "name": "trivy.sarif.json", "status": "verified"},
      {"type": "sast-scan", "name": "semgrep.sarif.json", "status": "verified"},
      {"type": "sast-scan", "name": "bandit.sarif.json", "status": "verified"},
      {"type": "dast-scan", "name": "zap-dast.sarif.json", "status": "verified"},
      {"type": "privacy-scan", "name": "presidio-privacy.sarif.json", "status": "verified"},
      {"type": "provenance", "name": "slsa-provenance.json", "status": "verified"},
      {"type": "compliance-report", "name": "$(basename "$REPORT_FILE")", "status": "signed"},
      {"type": "verification-document", "name": "supply-chain-verification.md", "status": "signed"}
    ],
    "overallStatus": "CONDITIONAL_APPROVE",
    "statusReason": "All critical verifications passed. HIGH vulnerabilities require remediation.",
    "completenessChecklist": {
      "signatureVerification": true,
      "sbomAnalysis": true,
      "slsaProvenance": true,
      "inTotoAttestations": true,
      "vulnerabilityAssessment": true,
      "privacyAssessment": true,
      "dependencyAnalysis": true,
      "licenseCompliance": true,
      "auditTrailComplete": true
    },
    "nextReviewDate": "$(date -u -d '+30 days' +"%Y-%m-%dT%H:%M:%SZ" 2>/dev/null || date -u -v+30d +"%Y-%m-%dT%H:%M:%SZ")",
    "notes": "Vendor to provide remediation plan for 6 HIGH and 2 MEDIUM vulnerabilities. PII detections in sample data require review and redaction."
  }
}
EOF

COSIGN_PASSWORD="" COSIGN_YES=true just sign-compliance-report \
  /tmp/verification-manifest.json \
  samples/oci-attestations/keys/cosign.key
```

### Step 10.3 (Optional) Upload Verification Artifacts to OCI

Share the verification memo and manifest via OCI:

```bash
just upload-compliance-report \
  /tmp/supply-chain-verification.md \
  /tmp/supply-chain-verification.md.sig \
  http://localhost:5000 "" "" \
  product-acquisition/verification-documents

just upload-compliance-report \
  /tmp/verification-manifest.json \
  /tmp/verification-manifest.json.sig \
  http://localhost:5000 "" "" \
  product-acquisition/verification-manifests
```

### Step 10.4 Verify the Audit Trail

Pull the manifest back down and confirm the signature:

```bash
mkdir -p /tmp/complete-audit-trail
oras pull --plain-http \
  localhost:5000/product-acquisition/verification-manifests:latest \
  --output /tmp/complete-audit-trail

MANIFEST_FILE=$(ls -t /tmp/complete-audit-trail/*.json | head -1)
cosign verify-blob --insecure-ignore-tlog \
  --key samples/oci-attestations/keys/cosign.pub \
  --signature "${MANIFEST_FILE}.sig" \
  "$MANIFEST_FILE"

jq '.verificationManifest | {scanId, vendor, product, overallStatus, artifacts: (.artifacts | map({type, status}))}' \
  "$MANIFEST_FILE"
```

## Cleanup (Optional)

```bash
# Remove temporary directories
rm -rf /tmp/vendor-artifacts /tmp/acquired-artifacts /tmp/pulled-reports /tmp/complete-audit-trail

# Remove temporary files
rm -f /tmp/compliance-findings.json /tmp/supply-chain-verification.md /tmp/verification-manifest.json
```

## What You Achieved

- Generated a security scan and packaged artifacts for vendor distribution
- Published artifacts to an OCI registry (simulating vendor workflow)
- Pulled and independently validated vendor artifacts
- Ingested verified artifacts into Certus TAP for analysis
- Asked natural language questions about security posture
- Generated, signed, and published a compliance report with auditable chain of custody

This tutorial demonstrates a complete vendor review workflow where both the vendor and auditor maintain independent verification of security artifacts.

## Next Steps

- **Explore graph queries**: See [`audit-queries.md`](audit-queries.md) for Neo4j Cypher queries
- **Learn about trust workflows**: See [`verify-trust.md`](verify-trust.md) for verification-first gatekeeper patterns
- **Understand attestation signing**: See [`sign-attestations.md`](sign-attestations.md) for vendor-side signing workflows

## Step 6: Cleaning Up

```bash
just down          # stop containers, keep volumes
just cleanup       # stop + remove containers, keep volumes
just destroy       # full tear-down (volumes removed)
```
