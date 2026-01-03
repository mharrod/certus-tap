# Tutorial 4: End-to-End Security Workflow

**Time:** 20 minutes
**Prerequisites:** Docker, Docker Compose, completed [Quick Start](quick-start-cli-scan.md)
**What you'll learn:** Complete Certus workflow from scanning to querying findings

## Overview

This tutorial demonstrates the full Certus security workflow:

1. **Assurance** - Generate security scan artifacts
2. **Trust** - Verify and permit artifact upload
3. **Transform** - Upload artifacts to S3
4. **Ask** - Ingest and query findings using multiple strategies

This is the verification-first workflow that makes Certus unique: artifacts are cryptographically verified before being trusted for analysis.

## What Makes This Different?

Unlike typical security platforms, Certus:

- **Verifies provenance** before trusting artifacts
- **Stores immutable artifacts** in content-addressed storage
- **Enables multi-modal queries** (keyword, semantic, knowledge graph, hybrid)
- **Maintains audit trails** with cryptographic signatures

## Prerequisites

Ensure you have the sample data:

```bash
# Check for trust sample repository
ls samples/trust-smoke-repo.git/

# Check for scan artifacts
ls samples/non-repudiation/scan-artifacts/
```

Both should exist from the trust tutorials. If not, clone the sample repository:

```bash
git clone --bare https://github.com/certus-tech/trust-sample-repo.git \
  samples/trust-smoke-repo.git
```

**Clear Dagger cache** (recommended to avoid timeout issues during scans):

```bash
pkill -f dagger
rm -rf ~/.cache/dagger
```

This prevents the Dagger engine from timing out during cleanup, especially when generating SBOMs or running multiple scans.

## Step 1: Start All Services

Start the complete Certus stack:

```bash
# Start all services
just up
```

Verify all services are running:

```bash
just preflight
```

You should see:

- `certus-assurance` (port 8056)
- `certus-trust` (port 8057)
- `certus-transform` (port 8100)
- `ask-certus-backend` (port 8000)
- `postgres` (database)
- `qdrant` (vector database)
- `localstack` (S3 storage)

Check health:

```bash
# Check each service
curl http://localhost:8056/health | jq .        # Assurance
curl http://localhost:8057/v1/health | jq .    # Trust
curl http://localhost:8100/health | jq .       # Transform
curl http://localhost:8000/health | jq .       # Ask
```

**Verify scanning mode:**

```bash
# Check current mode
curl -s http://localhost:8056/health | jq -r '.scanning_mode'
```

**Expected:** `sample` for fast tutorial with pre-generated data
**If you see:** `production` - real scanners will run (slower, requires security tools)

**To switch to sample mode (if needed):**

```bash
sed -i.bak 's/CERTUS_ASSURANCE_USE_SAMPLE_MODE=false/CERTUS_ASSURANCE_USE_SAMPLE_MODE=true/' certus_assurance/deploy/docker-compose.yml && just assurance-down && just assurance-up
```

**To switch to production mode:**

```bash
sed -i.bak 's/CERTUS_ASSURANCE_USE_SAMPLE_MODE=true/CERTUS_ASSURANCE_USE_SAMPLE_MODE=false/' certus_assurance/deploy/docker-compose.yml && just assurance-down && just assurance-up
```

**Note:** Mode changes require restarting the assurance service (included in commands above).

## Step 2: Generate Security Artifacts

For this tutorial, we'll use **sample mode** with pre-generated artifacts. This provides:

- ✓ **Fast scans** - Complete in seconds instead of minutes
- ✓ **Rich findings** - Pre-generated artifacts have comprehensive security issues to explore
- ✓ **Predictable results** - Same findings every time, perfect for learning
- ✓ **No scanner dependencies** - Works offline without installing security tools

**Note:** This tutorial differs from the other Assurance tutorials (CLI, Managed Service, Custom Manifests) which use production mode with real scanners. The end-to-end workflow benefits from sample mode because it demonstrates the complete Trust → Transform → Ask pipeline with rich, predictable data for query examples.

To use production mode with real scanners, set `CERTUS_ASSURANCE_USE_SAMPLE_MODE=false` in docker-compose.yml.

Create a scan request:

```bash
# Generate a unique assessment ID
ASSESSMENT_ID="assess_$(date +%s)"

# Create the scan using local sample repository
SCAN_ID=$(curl -s -X POST http://localhost:8056/v1/security-scans \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "e2e-demo",
    "component_id": "sample-scan",
    "assessment_id": "'$ASSESSMENT_ID'",
    "git_url": "/app/samples/trust-smoke-repo.git",
    "branch": "main",
    "manifest": {
      "product": "sample-app",
      "version": "1.0",
      "profiles": [
        {
          "name": "light",
          "description": "Comprehensive security scan",
          "tools": []
        }
      ]
    }
  }' | jq -r '.test_id')

echo "Scan ID: $SCAN_ID"
echo "Assessment ID: $ASSESSMENT_ID"
```

**Note:** This uses the local sample repository at `/app/samples/trust-smoke-repo.git` which works offline and is faster than cloning remote repositories.

**What happens in sample mode:**

- Clones the repository (needed for metadata and context)
- Ignores actual scan results from security tools
- Copies pre-generated artifacts from `samples/non-repudiation/scan-artifacts/`
- Scan completes in seconds with rich, predictable findings
- Returns comprehensive security data for the tutorial workflow

**Response:**

```json
{
  "test_id": "test_abc123",
  "workspace_id": "e2e-demo",
  "component_id": "sample-scan",
  "assessment_id": "assess_1234567890",
  "status": "QUEUED"
}
```

**Note the `test_id` and `assessment_id`** - you'll use these to track the scan and artifacts throughout the workflow.

Monitor scan progress:

```bash
# Poll scan status
curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq '{status, profile, started_at}'
```

Wait for `"status": "SUCCEEDED"`.

## Step 3: Retrieve Scan Artifacts

Once complete, the artifacts are stored in the `certus-assurance-artifacts` directory:

```bash
# View the artifact directory (using the test_id from scan creation)
ls -lh certus-assurance-artifacts/$SCAN_ID/
```

You'll see:

- `manifest.json` - Scan configuration and metadata
- `summary.json` - High-level findings summary
- `scan.json` - Detailed scan execution information
- `*.sarif.json` - Tool-specific findings (SARIF format)
- `*.spdx.json` - Software Bill of Materials (if SBOM tools ran)
- `reports/` - Organized reports by category (sast, sbom, dast, signing)
- `artifacts/` - Additional scan artifacts like image digests
- `logs/` - Execution logs

## Step 4: Request Upload with Verification

Submit an upload request to trigger the Trust verification workflow:

```bash
# Submit for verification and upload (using "verified" tier for cryptographic proof)
curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request \
  -H 'Content-Type: application/json' \
  -d '{
    "tier": "verified",
    "requested_by": "tutorial@example.com"
  }' | jq .
```

**What happens:**

1. **Trust Service** receives the request and verifies:
   - Inner signature from Certus-Assurance
   - Artifact integrity (all files match declared hashes)
   - Policy compliance
2. **If verification passes**, Trust service:
   - Creates outer signature (dual-signature chain)
   - Records in Sigstore transparency log
   - Calls Transform service to upload to S3
3. **Transform Service** uploads artifacts to S3 raw bucket

**Monitor upload status:**

```bash
# Poll until upload completes
while true; do
  UPLOAD_STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.upload_status')
  echo "Upload status: $UPLOAD_STATUS"
  [ "$UPLOAD_STATUS" != "pending" ] && break
  sleep 2
done
```

**Possible statuses:**

- `pending` - Waiting for Trust verification
- `permitted` - Trust approved, Transform uploading to S3
- `uploaded` - Complete with verification proof
- `denied` - Trust rejected (workflow stops)

**Response when complete:**

```json
{
  "test_id": "test_abc123",
  "upload_status": "uploaded",
  "verification_proof": {
    "chain_verified": true,
    "inner_signature_valid": true,
    "outer_signature_valid": true,
    "signer_inner": "certus-assurance@certus.cloud",
    "signer_outer": "certus-trust@certus.cloud",
    "sigstore_timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Key verification checks:**

- ✓ Inner signature (Assurance) is valid
- ✓ Outer signature (Trust) is valid
- ✓ All declared artifacts are present and unmodified
- ✓ Sigstore transparency log entry created

**If verification fails**, the upload is denied and the workflow stops here.

## Step 5: Promote Artifacts to Golden Bucket

After verification and upload to the raw bucket, promote artifacts to the golden bucket for ingestion:

```bash
# Promote from raw to golden bucket
./scripts/promote_security_scans.sh $SCAN_ID
```

**What the promotion script does:**

1. Verifies artifacts exist in S3 raw bucket
2. Checks for verification-proof.json
3. Copies SARIF findings to golden bucket
4. Copies SBOM to golden bucket
5. Copies verification proof to golden bucket
6. Makes artifacts ready for ingestion

**Verify artifacts in S3:**

```bash
# List artifacts in golden bucket (using AWS CLI with LocalStack)
aws s3 ls s3://golden/security-scans/$SCAN_ID/golden/ \
  --endpoint-url http://localhost:4566 \
  --recursive

# Check verification proof
aws s3 cp s3://golden/security-scans/$SCAN_ID/golden/verification-proof.json - \
  --endpoint-url http://localhost:4566 | jq .
```

## Step 6: Ingest into Certus Ask

Now that artifacts are verified and in the golden bucket, ingest them into Certus Ask for querying.

### Ingest SARIF (Security Findings)

```bash
# Ingest SARIF findings with Neo4j + OpenSearch indexing
curl -X POST "http://localhost:8000/v1/default/index/security/s3" \
  -H "Content-Type: application/json" \
  -d "{
    \"bucket_name\": \"golden\",
    \"key\": \"security-scans/${SCAN_ID}/golden/reports/sast/trivy.sarif.json\",
    \"format\": \"sarif\",
    \"tier\": \"premium\",
    \"assessment_id\": \"${SCAN_ID}\",
    \"signatures\": {
      \"signer_inner\": \"certus-assurance@certus.cloud\",
      \"signer_outer\": \"certus-trust@certus.cloud\"
    },
    \"artifact_locations\": {
      \"s3\": {
        \"bucket\": \"golden\",
        \"key\": \"security-scans/${SCAN_ID}/golden/reports/sast/trivy.sarif.json\"
      }
    }
  }" | jq .
```

**Response:**

```json
{
  "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "findings_indexed": 24,
  "neo4j_scan_id": "scan_420a8659eb4a",
  "status": "completed"
}
```

### Ingest SBOM (Software Bill of Materials)

```bash
# Ingest SPDX SBOM
curl -X POST "http://localhost:8000/v1/default/index/security/s3" \
  -H "Content-Type: application/json" \
  -d "{
    \"bucket_name\": \"golden\",
    \"key\": \"security-scans/${SCAN_ID}/golden/reports/sbom/syft.spdx.json\",
    \"format\": \"spdx\",
    \"tier\": \"premium\",
    \"assessment_id\": \"${SCAN_ID}\",
    \"signatures\": {
      \"signer_inner\": \"certus-assurance@certus.cloud\",
      \"signer_outer\": \"certus-trust@certus.cloud\"
    },
    \"artifact_locations\": {
      \"s3\": {
        \"bucket\": \"golden\",
        \"key\": \"security-scans/${SCAN_ID}/golden/reports/sbom/syft.spdx.json\"
      }
    }
  }" | jq .
```

**What happens during ingestion:**

1. **Download** - Fetch artifacts from golden S3 bucket
2. **Parse** - Extract findings from SARIF and components from SBOM
3. **Link Verification** - Attach verification metadata to each finding
4. **Neo4j** - Store as graph (SecurityScan → Finding → Location nodes)
5. **OpenSearch** - Index for full-text and semantic search
6. **Embeddings** - Generate vectors for AI-powered queries

## Step 7: Query Findings with Natural Language

Now you can ask questions about the security findings using natural language.

**Sample data contains findings from:**

- SQL Injection (CWE-89)
- Command Injection (CWE-78)
- CVE vulnerabilities (CVE-2024-1086)
- Certificate validation issues (CWE-295)
- Hardcoded credentials (CWE-798)
- Weak cryptography (CWE-327)

### Query Injection Vulnerabilities

```bash
# Find SQL injection risks
curl -X POST "http://localhost:8000/v1/default/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What SQL injection vulnerabilities were found?"}' | jq .
```

**Response includes:**

- Relevant findings from SARIF
- Context about the vulnerability
- File locations and line numbers
- Severity ratings
- Verification status (who signed the scan)

### Query Command Injection Issues

```bash
# Find command injection and shell execution risks
curl -X POST "http://localhost:8000/v1/default/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "Are there any command injection or shell execution risks?"}' | jq .
```

### Query CVE Vulnerabilities

```bash
# Find known CVE vulnerabilities in dependencies
curl -X POST "http://localhost:8000/v1/default/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What CVE vulnerabilities exist in our dependencies?"}' | jq .
```

### Query Authentication and Credential Issues

```bash
# Search for authentication and credential management problems
curl -X POST "http://localhost:8000/v1/default/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What authentication and credential management issues were found?"}' | jq .
```

### Query Cryptography Issues

```bash
# Find cryptographic vulnerabilities
curl -X POST "http://localhost:8000/v1/default/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What cryptographic vulnerabilities or weak algorithms were detected?"}' | jq .
```

### Query High Severity Issues

```bash
# Get all high severity findings
curl -X POST "http://localhost:8000/v1/default/ask" \
  -H "Content-Type: application/json" \
  -d '{"question": "What are all the high severity security issues found?"}' | jq .
```

### How Queries Work

Behind the scenes, Certus Ask:

1. **Semantic Search** - Converts your question to embeddings
2. **Vector Search** - Finds relevant chunks in OpenSearch
3. **Graph Traversal** - Queries Neo4j for related findings
4. **RAG (Retrieval Augmented Generation)** - Combines results with LLM
5. **Returns** - Natural language answer with sources

**Note:** This tutorial demonstrates semantic queries using the `/ask` endpoint. For other query methods including keyword search, graph queries, and hybrid search, see the [Ask tutorials](../ask/README.md):

- [Keyword Search](../ask/keyword-search.md) - Direct text matching in findings
- [Semantic Search](../ask/semantic-search.md) - AI-powered natural language queries
- [Graph Queries](../ask/graph-queries.md) - Cypher queries in Neo4j
- [Hybrid Search](../ask/hybrid-search.md) - Combining multiple search strategies

## Step 8: Query Verification Proof in Neo4j

Verify that the scan metadata includes cryptographic verification.

**Note:** If you don't have the SCAN_ID from Step 2, retrieve it from Neo4j:

```bash
# Get the most recent scan ID
SCAN_ID=$(docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:SecurityScan) RETURN s.assessment_id ORDER BY s.created_at DESC LIMIT 1" \
  | tail -1 | tr -d '"')
echo "SCAN_ID: $SCAN_ID"
```

Now query the verification details:

```bash
# Query Neo4j for verification details
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:SecurityScan {assessment_id: '$SCAN_ID'})
   RETURN s.chain_verified AS verified,
          s.signer_inner AS inner_signer,
          s.signer_outer AS outer_signer,
          s.sigstore_timestamp AS timestamp"
```

**Expected output:**

```
verified | inner_signer                    | outer_signer                | timestamp
TRUE     | "certus-assurance@certus.cloud" | "certus-trust@certus.cloud" | "2025-01-15T10:30:00Z"
```

### Query Findings with Verification Metadata

```bash
# Show findings with their verification chain
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:SecurityScan {assessment_id: '$SCAN_ID'})-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
   RETURN s.chain_verified AS verified,
          s.signer_outer AS signer,
          f.rule_id AS rule,
          f.severity AS severity,
          loc.uri AS file,
          loc.line AS line
   ORDER BY severity DESC, rule
   LIMIT 10"
```

This shows that every finding is linked to its verification proof.

## Step 9: Track Artifact Lineage

View the complete audit trail by checking the scan status:

```bash
# Get scan details with upload status
curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq '{
  test_id,
  status,
  upload_status,
  workspace_id,
  component_id,
  assessment_id,
  started_at,
  completed_at
}'
```

**This shows the complete workflow:**

1. **Scan initiated** - When the scan was submitted
2. **Artifacts generated** - When security tools completed
3. **Verification requested** - When upload was requested
4. **Trust verification** - Cryptographic signature verification
5. **Upload to S3** - Artifacts stored in raw bucket
6. **Promotion to golden** - Manual approval and promotion
7. **Ingestion to Ask** - Indexed in Neo4j and OpenSearch

**The verification proof in Neo4j proves:**

- Who signed the scan (Assurance + Trust dual signatures)
- When artifacts were verified
- That artifacts haven't been tampered with
- Complete chain of custody from scan to query

## What You Learned

You've completed the full Certus workflow:

1. **Assurance** - Generated security artifacts with inner signature
2. **Trust** - Verified artifacts and added outer signature (dual-signature chain)
3. **Transform** - Uploaded to S3 raw bucket
4. **Promotion** - Moved verified artifacts to golden bucket
5. **Ask** - Ingested into Neo4j + OpenSearch for querying
6. **Query** - Asked natural language questions about findings

**Key concepts:**

- **Verification-first** - Trust service acts as cryptographic gatekeeper
- **Dual signatures** - Inner (Assurance) + Outer (Trust) = non-repudiation
- **Immutable audit trail** - Verification metadata travels with every finding
- **Semantic search** - AI-powered queries understand intent, not just keywords
- **Graph storage** - Findings linked to verification proof in Neo4j

## Next Steps

1. **Production scanning** - Try tutorials 1-3 with real security tools
2. **Custom compliance** - Create your own compliance frameworks
3. **CI/CD integration** - Add Certus to your pipeline
4. **Policy enforcement** - Use Trust policies to gate deployments

## Troubleshooting

For common issues across all components, see the [Troubleshooting Guide](../../reference/troubleshooting/README.md).

**Component-specific guides:**

- **[Certus Assurance](../../reference/troubleshooting/certus_assurance.md)** - Scanning issues
- **[Certus Trust](../../reference/troubleshooting/certus_trust.md)** - Verification and upload issues
- **[Certus Transform](../../reference/troubleshooting/certus_transform.md)** - S3 storage issues
- **[Certus Ask](../../reference/troubleshooting/certus_ask.md)** - Ingestion and query issues

**Quick fixes for this tutorial:**

- **Services won't start** - [General troubleshooting](../../reference/troubleshooting/README.md#service-wont-start)
- **Scan fails or stays QUEUED** - [Assurance troubleshooting](../../reference/troubleshooting/certus_assurance.md#scan-stuck-in-queued)
- **Upload request denied** - [Trust troubleshooting](../../reference/troubleshooting/certus_trust.md)
- **S3 buckets don't exist** - [Transform troubleshooting](../../reference/troubleshooting/certus_transform.md)
- **Ingestion fails** - [Ask troubleshooting](../../reference/troubleshooting/certus_ask.md)
- **No query results** - [Ask troubleshooting](../../reference/troubleshooting/certus_ask.md)

## Clean Up

Stop all services:

```bash
docker compose down

# Remove volumes (optional - deletes all data)
docker compose down -v
```

## Learn More

- [Quick Start CLI Scan](quick-start-cli-scan.md) - Scan local projects
- [Custom Manifests](custom-manifests.md) - Create scanning profiles
- [Managed Service API](managed-service-api-scanning.md) - Scan remote repositories
- [Assurance Reference](../../reference/core-reference/README.md) - API documentation
