# Sample Data for Provenance Tutorials

All tutorials in the provenance section use the same canonical sample security scan data for consistency and reproducibility.

## Purpose

Using consistent sample data across tutorials ensures:

- ✅ **Predictable results** - Same vulnerabilities appear in every tutorial
- ✅ **Easy troubleshooting** - If your results differ, something is misconfigured
- ✅ **Tutorial chaining** - Can follow tutorials in sequence with same data
- ✅ **Educational clarity** - Focus on the workflow, not random variations in scan results

## Sample Data Location

**Canonical Source**: `samples/non-repudiation/scan-artifacts/`

This directory contains pre-generated security scan results that represent a realistic security assessment.

## What's Consistent (Predictable)

### Repository Being Scanned

- **URL**: `https://github.com/mharrod/certus-TAP.git`
- **Branch**: `main`
- **Purpose**: The Certus TAP platform itself (dogfooding)

### Security Findings (Always the Same)

| File                          | Tool      | Count         | Description                              |
| ----------------------------- | --------- | ------------- | ---------------------------------------- |
| `trivy.sarif.json`            | Trivy     | 6 findings    | Container and dependency vulnerabilities |
| `syft.spdx.json`              | Syft      | 45 components | Software Bill of Materials (SBOM)        |
| `bandit.sarif.json`           | Bandit    | 8 findings    | Python security issues                   |
| `semgrep.sarif.json`          | Semgrep   | 7 findings    | Code pattern vulnerabilities             |
| `zap-dast.sarif.json`         | OWASP ZAP | 10 findings   | Dynamic application security testing     |
| `checkov-iac.sarif.json`      | Checkov   | 10 findings   | Infrastructure as Code issues            |
| `presidio-privacy.sarif.json` | Presidio  | 8 findings    | Privacy/PII detection                    |

### File Structure (Predictable)

After a scan, files are always stored in:

```
s3://raw/security-scans/<SCAN_ID>/
├── quarantine/
│   ├── trivy.sarif.json       # ← Always same content
│   ├── syft.spdx.json          # ← Always same content
│   ├── cosign.attestation.jsonl
│   ├── zap-report.json
│   └── ...
├── <SCAN_ID>/
│   ├── verification-proof.json
│   └── scan.json
└── privacy-scan-report.txt
```

The **filenames and structure** are predictable. The **scan ID** is dynamic.

## What's Dynamic (Unique Per Run)

### Generated Values

- ✅ **Scan ID**: Uniquely generated (e.g., `scan_73c5ff9a4478`)
- ✅ **Assessment ID**: Set from scan ID
- ✅ **Timestamps**: Reflect when you run the tutorial
- ✅ **S3 paths**: Include the dynamic scan ID
- ✅ **Neo4j node IDs**: Generated during ingestion

### How Scan IDs Work

Each time you initiate a scan, a unique ID is generated:

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

echo "Your scan ID: $SCAN_ID"
# Output: test_a1b2c3d4 (unique each time)
```

This ID is used throughout the tutorial for:

- S3 paths: `s3://raw/security-scans/$SCAN_ID/`
- API calls: All reference `$SCAN_ID`
- Neo4j queries: `MATCH (s:SecurityScan {assessment_id: $SCAN_ID})`

## How Each Tutorial Uses Sample Data

### sign-attestations.md

**Source**: Copies from `samples/non-repudiation/scan-artifacts/`
**Method**: `just attestations-workflow` copies trivy.sarif.json, syft.spdx.json
**Then**: Signs the copied files with cosign
**Result**: Same findings, signed artifacts in `samples/oci-attestations/`

### verify-trust.md

**Source**: Loads from `samples/non-repudiation/scan-artifacts/`
**Method**: Certus-Assurance mock service returns these files
**Then**: Trust service verifies and promotes to golden bucket
**Result**: Same findings, dynamic scan ID, verification proof created

### vendor-review.md

**Source**: Pulls signed artifacts from OCI registry
**Method**: ORAS pull from registry (contains signed oci-attestations data)
**Then**: Re-verifies signatures and ingests
**Result**: Reviews same findings that were signed in sign-attestations

### security-scans.md

**Source**: Direct upload of sample files
**Method**: Uses files from `samples/security-scans/` or `samples/non-repudiation/`
**Then**: Ingests directly into OpenSearch/Neo4j
**Result**: Same findings, no provenance workflow

### audit-queries.md

**Source**: Queries data from verify-trust ingestion
**Method**: Cypher queries against Neo4j
**Then**: Analyzes findings that were ingested
**Result**: Consistent query results (49 findings, 45 components)

## Case Study Context

The sample data represents a **realistic security assessment scenario** documented in:

📄 [Case Study: Security Scan Non-Repudiation](./case_study.md)

This narrative explains:

- Why these specific vulnerabilities exist
- What the findings mean
- How they relate to each other
- The security implications

The case study makes the sample data **educational**, not just random test data.

## Sample Findings Summary

### High-Severity Issues (Across All Scanners)

- 13 error-level findings (high severity)
- 7 warning-level findings (medium severity)
- 1 note-level finding (low severity)
- Total: 21 SAST findings + 28 other findings = 49 total

### SBOM Components (From Syft)

- 45 total packages
- Includes: FastAPI, Pydantic, Neo4j, OpenSearch, Anthropic
- Covers: Web framework, databases, AI/LLM libraries, data processing
- Realistic production application dependencies

### Privacy Concerns (From Presidio)

- 4 email addresses detected
- 2 person names identified
- All flagged for review/redaction

## Why This Approach?

### Benefits of Canonical Sample Data

**For Learners**:

- Know what to expect (49 findings, 45 components)
- Easy to verify results match tutorial
- Can focus on workflow, not data variations

**For Tutorial Authors**:

- Write examples with specific findings
- Provide exact expected output
- Screenshots stay accurate

**For Platform Development**:

- Consistent test data
- Reproducible CI/CD runs
- Easier debugging

### Realistic Complexity

The sample data is not trivial:

- ❌ Not a "hello world" with 2 findings
- ✅ Realistic scale (49 vulnerabilities, 45 packages)
- ✅ Multiple tool types (SAST, SBOM, DAST, IAC, Privacy)
- ✅ Real-world scenarios (log4j, outdated deps, hardcoded secrets)

This teaches you to handle **production-scale** security data, not toy examples.

## Verifying Consistency

### Check Sample Files Exist

```bash
ls -la samples/non-repudiation/scan-artifacts/
```

Expected files:

```
trivy.sarif.json
syft.spdx.json
bandit.sarif.json
semgrep.sarif.json
zap-dast.sarif.json
checkov-iac.sarif.json
presidio-privacy.sarif.json
scan.json
```

### Verify Finding Count

```bash
# Count Trivy findings
cat samples/non-repudiation/scan-artifacts/trivy.sarif.json | \
  jq '.runs[0].results | length'
# Expected: 6

# Count SBOM components
cat samples/non-repudiation/scan-artifacts/syft.spdx.json | \
  jq '.packages | length'
# Expected: 45
```

### After Ingestion, Query Neo4j

```cypher
MATCH (s:SecurityScan {assessment_id: $SCAN_ID})-[:CONTAINS]->(f:Finding)
RETURN count(f) as finding_count
```

Expected: Total findings will vary based on which scanners were ingested (6-21 for SAST only, up to 49 if all scanners ingested)

## Customization (Advanced)

### Want Different Sample Data?

To use your own sample data:

1. **Replace canonical samples**:

   ```bash
   # Run your own scans
   trivy image myapp:latest -f sarif > samples/non-repudiation/scan-artifacts/trivy.sarif.json
   syft myapp:latest -o spdx-json > samples/non-repudiation/scan-artifacts/syft.spdx.json
   ```

2. **All tutorials will use your data**:
   - Certus-Assurance mock loads from this directory
   - sign-attestations copies from this directory
   - Results are consistent

### Keep Multiple Sample Sets

```bash
samples/
├── non-repudiation/
│   └── scan-artifacts/          # Default (Certus TAP)
├── sample-app-a/
│   └── scan-artifacts/          # Your app A
└── sample-app-b/
    └── scan-artifacts/          # Your app B
```

Then configure which to use in tutorial scripts.

## Summary

| Aspect               | Behavior                             |
| -------------------- | ------------------------------------ |
| **Findings content** | Consistent (same 49 vulnerabilities) |
| **SBOM components**  | Consistent (same 45 packages)        |
| **File structure**   | Consistent (quarantine/, metadata/)  |
| **Scan ID**          | Dynamic (unique per run)             |
| **Timestamps**       | Dynamic (when you run it)            |
| **S3 paths**         | Dynamic (include scan ID)            |

**Key Insight**: The **data is consistent**, but the **identifiers are dynamic**. This teaches realistic workflow while maintaining reproducibility.

---

**Next**: See individual tutorial files for workflow-specific details:

- [sign-attestations.md](sign-attestations.md) - Signing workflow
- [verify-trust.md](verify-trust.md) - Verification workflow
- [vendor-review.md](vendor-review.md) - Review workflow
- [security-scans.md](security-scans.md) - Direct ingestion
- [audit-queries.md](audit-queries.md) - Query and analysis

## Step 6: Cleaning Up

```bash
just down          # stop containers, keep volumes
just cleanup       # stop + remove containers, keep volumes
just destroy       # full tear-down (volumes removed)
```
