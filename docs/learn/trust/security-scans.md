# Running a Security Scan with Provenance

This guide walks you through running your first security scan with Certus-Assurance and understanding provenance metadata.

## ⚠️ Important: Scanning Modes

**Certus-Assurance supports two scanning modes:**

### Sample Mode (Default for Tutorials)

- ✓ Loads pre-generated sample findings from `samples/non-repudiation/scan-artifacts/`
- ✓ Demonstrates the provenance and non-repudiation workflow
- ✓ Works offline without external scanner dependencies
- ✓ Provides deterministic, reproducible results
- ✓ Fast and suitable for tutorials/demos

**This tutorial uses sample mode** (configured via `CERTUS_ASSURANCE_USE_SAMPLE_MODE=true` in docker-compose).

### Production Mode (Real Scanning)

- ✓ Runs actual security tools (Trivy, Semgrep, Bandit, Syft, OWASP ZAP, Checkov, Presidio)
- ✓ Scans real repositories and generates fresh findings
- ✓ Requires `security_module` installed: `pip install -e dagger_modules/security`
- ✓ Use for actual security assessments

**Check your mode:**

```bash
curl http://localhost:8056/health | jq .scanning_mode
# Returns: "sample" or "production"
```

For the complete security assessment narrative using sample data, see [Case Study: Certus-TAP Security Findings](case_study.md) which contains 57 real findings.

## Overview

In this tutorial, you'll:

1. Set up Certus-Assurance mock scanning service
2. Run a scan that returns pre-generated case study findings
3. Examine SARIF output with provenance
4. Understand inner signatures
5. View scan artifacts and metadata

## Prerequisites

## Step 1 - Set-up

### 1.1 Bring up relevant services

```bash
just trust-up
```

### 1.2 Check if everything is ready for the tutorial

```bash
just preflight-trust
```

## Step 2 - Understanding the Scan Request

### 2.1 Scan Request Structure

Create a file `scan_request.json`:

```json
{
  "workspace_id": "security-demo",
  "component_id": "trust-smoke-repo",
  "assessment_id": "initial-scan",
  "git_url": "/app/samples/trust-smoke-repo.git",
  "branch": "main",
  "requested_by": "security-team@example.com",
  "manifest": {
    "version": "1.0"
  }
}
```

**Fields:**

- `workspace_id`: Workspace identifier for organizing scans
- `component_id`: Component being scanned (application/service name)
- `assessment_id`: Assessment identifier for tracking scan series
- `git_url`: Repository to scan (public or private with credentials)
- `branch`: Git branch to scan (optional, defaults to HEAD)
- `requested_by`: Who initiated the scan (for audit trail)
- `manifest`: Manifest JSON defining the scan configuration (required)

## Step 3 - Submitting Your First Scan

```bash
export SCAN_ID=$(curl -s -X POST http://localhost:8056/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_id": "security-demo",
    "component_id": "trust-smoke-repo",
    "assessment_id": "initial-scan",
    "git_url": "/app/samples/trust-smoke-repo.git",
    "branch": "main",
    "requested_by": "tutorial@example.com",
    "manifest": {"version": "1.0"}
  }' | jq -r '.test_id')

echo "Scan submitted with ID: $SCAN_ID"
```

This submits the scan and captures the `$SCAN_ID` from the response for use in subsequent commands.

### 3.1 Monitor Scan Status

Check the scan status:

```bash
curl http://localhost:8056/v1/security-scans/$SCAN_ID \
  -s | jq '{
    test_id,
    status,
    upload_status,
    upload_permission_id
  }'
```

**Upload status values:**

- `"pending"` - Waiting for Trust verification
- `"permitted"` - Trust approved, Transform is uploading
- `"failed"` - Trust denied or error occurred

### 3.2 Human-in-the-Loop: Review Scan Results

Before submitting an upload request, a human reviewer should examine the scan results to ensure they're acceptable:

```bash
# View the scan artifacts
ls -la ./certus-assurance-artifacts/$SCAN_ID/reports/

# Review SAST findings
cat ./certus-assurance-artifacts/$SCAN_ID/reports/sast/trivy.sarif.json | jq '.runs[0].results[] | {ruleId, message, severity}'

# Review SBOM
cat ./certus-assurance-artifacts/$SCAN_ID/reports/sbom/syft.spdx.json | jq '.packages | length'
```

After reviewing the findings, the human approver can decide whether to:

- ✅ **Approve**: Submit upload request to proceed with verification
- ❌ **Reject**: Decline upload if findings are unacceptable
- 🔄 **Request Changes**: Require fixes before resubmitting

### 3.3 Submit Upload Request to Trust

Once human approval is obtained, submit the upload request:

```bash
curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request \
  -H 'Content-Type: application/json' \
  -d '{
    "tier": "verified"
  }'
```

### 3.4 Poll Until Upload Complete

```bash
while true; do
  STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.upload_status')
  SCAN_STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.status')
  echo "Scan: $SCAN_STATUS | Upload: $STATUS"
  [ "$STATUS" != "pending" ] && break
  sleep 2
done
```

Once `upload_status` shows `"permitted"`, artifacts are being uploaded to storage via the verification-first workflow.

## Step 4 - Examining Scan Artifacts

### 4.1 Where Artifacts Are Stored

Artifacts are stored locally in your project directory under `certus-assurance-artifacts/`:

```
certus-assurance-artifacts/
└── test_a1b2c3d4e5f6/           # Test ID directory
    ├── scan.json                 # Provenance metadata
    ├── build.intoto.jsonl        # In-toto attestations for each build step
    ├── slsa-provenance.json      # SLSA provenance metadata
    ├── logs/
    │   └── runner.log            # Execution log
    ├── artifacts/
    │   ├── image.digest          # Container image digest
    │   └── image.txt             # Image reference
    └── reports/
        ├── sbom/syft.spdx.json            # Software bill of materials (from case study)
        ├── sast/trivy.sarif.json          # Security findings (from case study)
        ├── dast/zap-report.json           # Dynamic analysis findings (from case study)
        └── signing/                       # (empty - for future use)
```

> **Note**: All findings are loaded from `samples/non-repudiation/scan-artifacts/` (case study data).
> These artifacts are generated locally and excluded from git (see `.gitignore`).

### 4.2 View the Metadata

```bash
# Assumes $SCAN_ID was set as variable
cat ./certus-assurance-artifacts/$SCAN_ID/scan.json | jq
```

Example `scan.json`:

```json
{
  "scan_id": "scan_a1b2c3d4e5f6",
  "status": "SUCCEEDED",
  "git_url": "https://github.com/mharrod/certus-TAP.git",
  "git_commit": "abc123def456789def456abc123def456",
  "branch": "main",
  "requested_by": "security-team@example.com",
  "started_at": "2024-01-15T14:30:00Z",
  "completed_at": "2024-01-15T14:32:45Z",
  "artifacts": {
    "sarif": "reports/sast/trivy.sarif.json",
    "sbom": "reports/sbom/syft.spdx.json",
    "dast_json": "reports/dast/zap-report.json"
  },
  "warnings": [],
  "errors": []
}
```

**Key fields:**

- `status`: "SUCCEEDED" when using mock service
- `started_at`: When scan started
- `completed_at`: When scan finished
- `artifacts`: Paths to all report files (loaded from case study samples)

### 4.3 View SARIF Findings (Case Study Data)

```bash
# Assumes $SCAN_ID was set as variable
cat ./certus-assurance-artifacts/$SCAN_ID/reports/sast/trivy.sarif.json | jq '.runs[0].results[] | {ruleId, message}'
```

These findings come from `samples/non-repudiation/scan-artifacts/trivy.sarif.json` and are part of the case study analysis. See [Case Study](case_study.md) for detailed narrative.

Example output (from case study):

```json
{
  "ruleId": "CASE-STUDY-001",
  "message": {
    "text": "Security finding from comprehensive assessment of Certus-TAP"
  }
}
```

### 4.4 View SBOM (Case Study Data)

```bash
# Assumes $SCAN_ID was set as variable
cat ./certus-assurance-artifacts/$SCAN_ID/reports/sbom/syft.spdx.json | jq '.packages[] | {name, versionInfo}'
```

These packages are from `samples/non-repudiation/scan-artifacts/syft.spdx.json` (case study SBOM).

Example output:

```json
{
  "name": "certus-tap",
  "versionInfo": "0.1.0"
}
{
  "name": "fastapi",
  "versionInfo": "0.104.1"
}
```

### 4.5 View Attestations and Signing

Each scan includes in-toto attestations documenting what was scanned and when:

```bash
# Assumes $SCAN_ID was set as variable
cat ./certus-assurance-artifacts/$SCAN_ID/build.intoto.jsonl | jq -s '.'
```

Example attestation:

```json
{
  "_type": "https://in-toto.io/Statement/v0.1",
  "predicateType": "https://slsa.dev/provenance/v1",
  "subject": [
    {
      "name": "registry.example.com/certus-assurance/certus-TAP:abc123def456",
      "digest": {
        "sha256": "abc123def456789def456abc123def456"
      }
    }
  ],
  "predicate": {
    "builder": {
      "id": "certus-assurance-mock-service"
    }
  }
}
```

**What this attestation means:**

- `_type`: Follows the in-toto Statement v0.1 specification (standard for software provenance)
- `predicateType`: Uses SLSA provenance v1 predicate (Software supply chain Levels for Secure software Artifacts)
- `subject`: The container image being attested (name and digest)
- `predicate.builder`: Identifies Certus-Assurance as the builder

**Note:** Certus-Assurance creates these attestations to document the scan provenance. For cryptographic signing with Cosign/Sigstore, see the [Verify Trust](verify-trust.md) tutorial which covers the full verification workflow with Certus-Trust.

## Step 5 - Analyze Findings inside Certus TAP

Once you trust the artifacts on disk, push them through the standard TAP pipelines so you can interrogate the findings alongside provenance metadata.

### 5.1 Ingest security artifacts into a workspace

Pick or create a workspace and post both the SARIF report and SBOM that Certus-Assurance produced:

```bash
export WORKSPACE_ID=security-provenance-demo

# Ingest SARIF security findings
curl -s -X POST "http://localhost:8000/v1/${WORKSPACE_ID}/index/security" \
  -F "uploaded_file=@./certus-assurance-artifacts/${SCAN_ID}/reports/sast/trivy.sarif.json" \
  | jq '{ingestion_id, document_count, neo4j_scan_id}'

# Ingest SBOM (Software Bill of Materials)
curl -s -X POST "http://localhost:8000/v1/${WORKSPACE_ID}/index/security" \
  -F "uploaded_file=@./certus-assurance-artifacts/${SCAN_ID}/reports/sbom/syft.spdx.json" \
  | jq '{ingestion_id, document_count, neo4j_sbom_id}'
```

The responses include `ingestion_id`, `document_count`, and (if Neo4j integration is enabled) `neo4j_scan_id` or `neo4j_sbom_id`.

### 5.2 Ask questions about security findings and dependencies

Now you can ask natural language questions about the ingested security data:

```bash
# Ask about security vulnerabilities
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What security vulnerabilities were found in the scanning results?"}' \
  | jq -r '.answer'

# Ask about specific vulnerability types
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Are there any SQL injection or command injection vulnerabilities?"}' \
  | jq -r '.answer'

# Ask about packages and dependencies
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What packages and dependencies are listed in the software bill of materials?"}' \
  | jq -r '.answer'

# Ask about high severity issues
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the high or critical severity findings that need immediate attention?"}' \
  | jq -r '.answer'

# Ask about specific files
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What security issues were found in Python files?"}' \
  | jq -r '.answer'
```

These questions work because both SARIF findings and SBOM packages have been ingested and indexed for semantic search.

### 5.3 Query OpenSearch for provenance-aware findings

Query the workspace-specific index to inspect findings and their provenance metadata:

```bash
curl -s -X POST "http://localhost:9200/ask_certus_${WORKSPACE_ID}/_search" \
  -H 'Content-Type: application/json' \
  -d "{
        \"query\": {
          \"bool\": {
            \"filter\": [
              {\"term\": {\"record_type\": \"finding\"}},
              {\"term\": {\"workspace_id\": \"${WORKSPACE_ID}\"}}
            ]
          }
        },
        \"_source\": [\"rule_id\",\"severity\",\"finding_title\",\"neo4j_scan_id\",\"chain_verified\",\"signer_outer\"],
        \"size\": 20
      }" | jq '.hits.hits[] | ._source'
```

Example output:

```json
{
  "rule_id": "CVE-2024-1086",
  "severity": "HIGH",
  "finding_title": "Package requests is vulnerable to HTTP/HTTPS Smuggling attack (CVE-2024-1086)",
  "neo4j_scan_id": "neo4j-security-provenance-demo-scan",
  "chain_verified": null,
  "signer_outer": null
}
```

This highlights how provenance properties (`chain_verified`, `signer_outer`, etc.) travel with every finding document.

**Note:** The index name is `ask_certus_<workspace_id>` (e.g., `ask_certus_security-provenance-demo`). Each workspace has its own dedicated index.

### 5.4 Run a Neo4j query to correlate provenance and locations

If you enabled graph loading, the SARIF ingestion response contains `neo4j_scan_id`. The scan ID follows the pattern `neo4j-<workspace_id>-scan`:

```bash
export NEO4J_SCAN_ID=neo4j-${WORKSPACE_ID}-scan
```

Or extract it from the ingestion response:

```bash
export NEO4J_SCAN_ID=$(curl -s -X POST "http://localhost:9200/ask_certus_${WORKSPACE_ID}/_search" \
  -H 'Content-Type: application/json' \
  -d '{
        "query": {"term": {"record_type": "scan_report"}},
        "_source": ["neo4j_scan_id"],
        "size": 1
      }' | jq -r '.hits.hits[0]._source.neo4j_scan_id')

echo "Neo4j Scan ID: $NEO4J_SCAN_ID"
```

Then query Neo4j:

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (scan:SecurityScan {id: '${NEO4J_SCAN_ID}'})-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
   RETURN scan.chain_verified AS chain_verified,
          scan.signer_outer   AS signer,
          f.rule_id           AS rule,
          f.severity          AS severity,
          loc.uri             AS file,
          loc.line            AS line
   ORDER BY severity DESC, rule
   LIMIT 15;"
```

Example output:

```
chain_verified, signer, rule, severity, file, line
NULL, NULL, "CWE-295", "warning", "src/api/client.py", 67
NULL, NULL, "CWE-798", "warning", "config.py", 12
NULL, NULL, "CWE-327", "note", "src/security/crypto.py", 34
NULL, NULL, "CVE-2024-1086", "error", "requirements.txt", 0
NULL, NULL, "CWE-78", "error", "src/utils/shell_runner.py", 23
NULL, NULL, "CWE-89", "error", "src/api/handlers.py", 45
```

Now you can prove which signer produced the scan, which files were implicated, and whether the verification chain succeeded—all from a single query. The `chain_verified` and `signer` fields will be populated when using premium tier verification.

## Step 6 - Understanding Provenance Metadata

### What is Provenance?

Provenance is metadata about how the scan was created:

```
┌─ Who ran it?        → requested_by
├─ When was it run?   → timestamp_created
├─ What code?         → git_url, branch, commit
├─ What found issues? → scanner version (Trivy 0.45.0)
├─ How was it signed? → inner_signature
└─ Can we trust it?   → signer, signature, algorithm
```

### Inner Signature Fields

```json
{
  "signer": "certus-assurance@certus.cloud",
  "timestamp": "2024-01-15T14:32:45Z",
  "signature": "base64-encoded-signature",
  "algorithm": "SHA256-RSA",
  "certificate": "-----BEGIN CERTIFICATE-----..."
}
```

**What this means:**

- `signer`: Identity claiming to have run the scan
- `timestamp`: When signature was created
- `signature`: Cryptographic proof of authenticity
- `algorithm`: How signature was created
- `certificate`: Public key to verify signature

### 6.1 Why Provenance Matters

Without provenance, you can't answer:

- ❌ "Did we actually scan this code?"
- ❌ "When was the scan done?"
- ❌ "Who can we blame if the scan is wrong?"

With provenance, you can:

- ✅ Prove scan happened at specific time
- ✅ Prove specific person/service initiated scan
- ✅ Verify scan wasn't modified after creation
- ✅ Create audit trail for compliance

## Step 7 - Scanning Different Repositories

### 7.1 Public Repository

```bash
curl -X POST http://localhost:8056/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_id": "k8s-security",
    "component_id": "kubernetes",
    "assessment_id": "release-1.28-scan",
    "git_url": "https://github.com/kubernetes/kubernetes.git",
    "branch": "release-1.28",
    "requested_by": "devops@example.com",
    "manifest": {"version": "1.0"}
  }'
```

### 7.2 Local Repository

You can scan a local directory path:

```bash
curl -X POST http://localhost:8056/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_id": "local-dev",
    "component_id": "my-app",
    "assessment_id": "local-scan",
    "git_url": "/path/to/local/repo",
    "requested_by": "developer@example.com",
    "manifest": {"version": "1.0"}
  }'
```

### 7.3 Specific Commit

```bash
curl -X POST http://localhost:8056/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_id": "security-demo",
    "component_id": "trust-smoke-repo",
    "assessment_id": "commit-scan",
    "git_url": "/app/samples/trust-smoke-repo.git",
    "branch": "main",
    "requested_by": "security@example.com",
    "manifest": {"version": "1.0"}
  }'
```

## Step 8 - Cleaning Up

```bash
just down          # stop containers, keep volumes
just cleanup       # stop + remove containers, keep volumes
just destroy       # full tear-down (volumes removed)
```
