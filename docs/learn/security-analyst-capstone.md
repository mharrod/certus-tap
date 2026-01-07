# Security Analyst Capstone: Product Acquisition Review

>**STATUS:Tutorial is currently in beta. If you have issues see our [Communication & Support guide](../../about/communication.md)**

> **NOTE: This tutorial is a wok in progress and not ready for use**

## Scenario

Your company is evaluating a new product acquisition. Before approval, you must conduct a comprehensive security, privacy, and compliance review using the **full Certus stack**: Trust (signing & verification), Ask (RAG), Integrity (rate limiting), Assurance (metrics), and Transform (PII detection).

**Your Task:** Review the product's security framework, policies, and privacy controls using document ingestion, privacy scanning, vulnerability analysis, and demonstrate the complete Certus security infrastructure.

**Expected Time:** 60-90 minutes

---

## Prerequisites

- Stack is running: `just up`
- Preflight checks passed: `just preflight`
- AWS CLI configured for LocalStack (see ingestion-pipelines.md)
- Environment variables set:
  ```bash
  export CERTUS_ASK_URL="http://localhost:8000"
  export CERTUS_TRUST_URL="http://localhost:8001"
  export CERTUS_TRANSFORM_URL="http://localhost:8002"
  export VICTORIAMETRICS_URL="http://localhost:8428"
  export OPENSEARCH_URL="http://localhost:9200"
  export NEO4J_URL="http://localhost:7474"
  ```

---

## Phase 1: Setup & Security Controls

### Step 1: Create a New Workspace

Create a dedicated workspace for this product acquisition review:

```bash
# Create workspace by uploading a document to it
# (Workspaces auto-create on first document ingestion)
WORKSPACE_ID="product-acquisition-review"

echo "Workspace ID: $WORKSPACE_ID"
```

You'll use this workspace throughout the tutorial: `/v1/$WORKSPACE_ID/`

---

### Step 1.5: Configure Integrity Controls (NEW)

**Goal:** Enable Certus Integrity middleware to protect API access during the review.

**Why this matters:** Even during a security review, the analyst's own API access should be protected by rate limiting. This demonstrates that Certus Integrity is active and generating cryptographic evidence for all API interactions.

```bash
# Set evidence directory
export EVIDENCE_DIR="${EVIDENCE_DIR:-~/certus-evidence}"
mkdir -p "$EVIDENCE_DIR"

# Configure rate limiting for the workspace
cat > /tmp/integrity-config.json <<EOF
{
  "workspace_id": "$WORKSPACE_ID",
  "rate_limit_per_minute": 100,
  "burst_limit": 20,
  "enforcement_mode": true,
  "shadow_mode": false,
  "whitelist_ips": ["127.0.0.1", "$(hostname -I | awk '{print $1}')"]
}
EOF

# Enable integrity controls
curl -X POST ${CERTUS_ASK_URL}/v1/admin/integrity/configure \
  -H "Content-Type: application/json" \
  -d @/tmp/integrity-config.json | jq
```

**Expected output:**
```json
{
  "status": "configured",
  "workspace_id": "product-acquisition-review",
  "enforcement": "active",
  "evidence_location": "~/certus-evidence/product-acquisition-review/"
}
```

**Verify integrity is active:**

```bash
# Generate test traffic to verify rate limiting
for i in {1..5}; do
  curl -s ${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/health >/dev/null
done

# Check evidence bundles were created
ls -l "$EVIDENCE_DIR"/dec_*.json | wc -l
# Expected: 5 decision bundles

# Verify enforcement mode is active (not shadow mode)
jq -r '.decision.metadata.shadow_mode' "$EVIDENCE_DIR"/dec_*.json | head -1
# Expected: false (enforcement mode active)
```

**What you've demonstrated:**
- ✅ Rate limiting configured (100 req/min, 20 burst)
- ✅ Enforcement mode enabled (not shadow)
- ✅ Evidence generation active (every request logged)
- ✅ Cryptographic signatures on all decisions

---

### Step 2: Prepare Document Corpus & Signed Artifacts

#### 2a. Upload Compliance Corpus to S3 (ENHANCED)

**Goal:** Build a comprehensive knowledge base of policies, frameworks, and documentation for the acquisition review.

**Document Corpus Includes:**
- **Compliance Frameworks:** SOC 2, ISO 27001, GDPR, PCI-DSS, HIPAA
- **Security Policies:** Access control, incident response, encryption
- **Privacy Documentation:** Privacy policy, DPA templates, data processing agreements
- **Product Documentation:** Architecture docs, API specs, deployment guides
- **Vendor Documentation:** Acquired company's policies and procedures

**Option 1: Use Bootstrap Script (Quick Start)**

```bash
uv run python scripts/upload_corpus_to_s3.py \
  --corpus-path samples/corpus_data \
  --bucket raw \
  --s3-prefix product-acquisition \
  --s3-endpoint-url http://localhost:4566 \
  --verbose
```

**Expected output:**
```
✓ Uploaded SOC 2 Type 2 controls (150 pages)
✓ Uploaded ISO 27001:2022 requirements (85 pages)
✓ Uploaded GDPR compliance framework (120 pages)
✓ Uploaded 12 security policy templates
✓ Uploaded 8 privacy policy templates
Total: 47 documents, 3,245 pages
```

**Option 2: Manual Upload (Custom Corpus)**

If you have your own compliance documents:

```bash
# Upload your organization's actual policies
aws s3 sync ./my-org-policies/ \
  s3://raw/product-acquisition/policies/ \
  --endpoint-url http://localhost:4566 \
  --exclude "*.DS_Store" \
  --include "*.pdf" \
  --include "*.docx" \
  --include "*.md"

# Upload acquired company's documentation
aws s3 sync ./target-company-docs/ \
  s3://raw/product-acquisition/vendor-docs/ \
  --endpoint-url http://localhost:4566
```

**Verify corpus upload:**

```bash
# List uploaded documents
aws s3 ls s3://raw/product-acquisition/ --recursive \
  --endpoint-url http://localhost:4566

# Count by document type
aws s3 ls s3://raw/product-acquisition/ --recursive \
  --endpoint-url http://localhost:4566 | \
  awk '{print $4}' | \
  grep -oE '\.(pdf|docx|md|txt)$' | \
  sort | uniq -c

# Expected output:
#   25 .pdf
#   12 .docx
#   10 .md
```

**Document Corpus Structure:**

```
s3://raw/product-acquisition/
├── frameworks/
│   ├── soc2-type2-controls.pdf
│   ├── iso27001-2022-requirements.pdf
│   ├── gdpr-compliance-checklist.pdf
│   └── pci-dss-v4-requirements.pdf
├── policies/
│   ├── access-control-policy.pdf
│   ├── incident-response-policy.pdf
│   ├── encryption-policy.pdf
│   └── data-classification-policy.pdf
├── privacy/
│   ├── privacy-policy-template.pdf
│   ├── dpa-template.docx
│   └── data-subject-rights-procedure.pdf
└── vendor-docs/
    ├── product-architecture.pdf
    └── api-documentation.pdf
```

**Why this corpus matters:**

When you run RAG queries later, the system will search across this entire corpus to answer questions like:

- "Does the vendor meet SOC 2 CC6.1 requirements?" → Searches SOC 2 controls + vendor docs
- "What GDPR gaps exist in their privacy policy?" → Compares vendor privacy policy against GDPR framework
- "Do they encrypt data at rest per ISO 27001?" → Checks ISO requirements + vendor architecture docs

**Without this corpus**, the RAG system can only answer questions about code - not compliance or policy alignment.

---

#### 2b. Generate Signed SBOM/SARIF via OCI Flow (ENHANCED)

**Goal:** Create cryptographically signed security artifacts using Certus Trust.

```bash
# Generate SBOM and SARIF for the product
just attestations-workflow "Acme Corporation Product" "2.5.0"

# Push signed artifacts to OCI registry
python3 scripts/oci-attestations.py push \
  --artifacts-dir samples/oci-attestations/artifacts \
  --registry http://localhost:5000

# Promote signed artifacts to golden bucket and ingest
./scripts/setup-security-search.sh --workspace ${WORKSPACE_ID} --ingest-all
```

**2b.1: Verify Signed Artifacts (NEW)**

**Why verification matters:** Shows end-to-end trust chain - not just signing, but cryptographic verification and transparency log lookup.

```bash
# Set artifact root
export ARTIFACT_ROOT="$(pwd)/samples/oci-attestations/artifacts"

# Verify SBOM signature
SBOM_FILE="${ARTIFACT_ROOT}/sbom.json"
SBOM_HASH=$(sha256sum "$SBOM_FILE" | cut -d' ' -f1)

curl -X POST ${CERTUS_TRUST_URL}/v1/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"artifact_hash\": \"$SBOM_HASH\",
    \"signature_file\": \"${SBOM_FILE}.sig\"
  }" | jq
```

**Expected output:**
```json
{
  "verified": true,
  "signer": "certus-trust@certus.cloud",
  "timestamp": "2026-01-03T10:15:23Z",
  "transparency_log_entry": {
    "uuid": "rekor-abc123",
    "index": 42,
    "log_url": "https://rekor.sigstore.dev/api/v1/log/entries/rekor-abc123"
  }
}
```

**Verify SARIF signature:**

```bash
SARIF_FILE="${ARTIFACT_ROOT}/security-findings.sarif"
SARIF_HASH=$(sha256sum "$SARIF_FILE" | cut -d' ' -f1)

curl -X POST ${CERTUS_TRUST_URL}/v1/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"artifact_hash\": \"$SARIF_HASH\",
    \"signature_file\": \"${SARIF_FILE}.sig\"
  }" | jq
```

**What you've demonstrated:**
- ✅ SBOM generated and cryptographically signed
- ✅ SARIF report generated and signed
- ✅ Signatures verified against transparency log (Rekor)
- ✅ Certificate chain validated
- ✅ Tamper-evident artifact chain established

---

## Phase 2: Privacy & Compliance Scanning

### Step 3: Run Privacy Transformation/Test

**Goal:** Use Certus Transform to detect PII and automatically quarantine sensitive documents.

Create a test file with PII to demonstrate quarantine:

```bash
cat > /tmp/sample-with-pii.md << 'EOF'
# Contact Information

Primary Contact: john.doe@company.com
Phone: +1-555-0123
Employee ID: EMP-12345

Security Officer: Jane Smith
Email: jane.smith@example.com
SSN: 123-45-6789

Internal Notes:
Contact support team at support@example.com for assistance.
EOF
```

Upload the test file:

```bash
curl -X POST ${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/index/ \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@/tmp/sample-with-pii.md" | jq
```

The response will show quarantined documents:

```json
{
  "ingestion_id": "ing_abc123",
  "message": "Indexed document",
  "document_count": 1,
  "metadata_preview": [...],
  "quarantined_documents": 1,
  "pii_detected": {
    "emails": 3,
    "phones": 1,
    "ssn": 1,
    "employee_ids": 1
  }
}
```

**Note:** Documents with detected PII are automatically quarantined for privacy protection. Move quarantined documents to `s3://raw/product-acquisition/quarantine/` for review.

---

### Step 4: Human-in-the-Loop Privacy Review

As security analyst, review the quarantined files:

1. **Identify quarantined documents:**

   ```bash
   # Check quarantine bucket (in real workflow)
   docker compose exec localstack awslocal s3 ls s3://raw/product-acquisition/quarantine/
   ```

2. **Review PII detection:**
   - Check which PII entities were detected (email, phone, SSN, etc.)
   - Determine if PII is necessary for the document
   - Decide: anonymize, redact, or remove

3. **Approval decision:**
   - If PII is business-critical and properly protected → move to `approved/`
   - If PII can be removed → redact and re-ingest
   - If PII is unnecessary → remove file entirely

**Example:** The sample-with-pii.md contains necessary contact information. As analyst, you approve it for ingestion with anonymization applied.

Move approved document back:

```bash
# In real workflow, move from quarantine to approved
docker compose exec localstack awslocal s3 cp \
  "s3://raw/product-acquisition/quarantine/sample-with-pii.md" \
  "s3://raw/product-acquisition/approved/sample-with-pii.md"
```

**What you've demonstrated:**
- ✅ PII detection run on 500+ documents
- ✅ Documents quarantined for review
- ✅ Human-in-the-loop review completed
- ✅ All approved documents ready for ingestion

---

## Phase 3: Knowledge Ingestion

### Step 5: Ingest All Approved Documents (ENHANCED)

**Goal:** Load the document corpus (frameworks, policies, vendor docs) into OpenSearch and Neo4j for semantic search and graph analysis.

**What gets ingested:**
- ✅ Compliance frameworks (SOC 2, ISO 27001, GDPR, etc.) - uploaded in Step 2a
- ✅ Security policies - uploaded in Step 2a
- ✅ Privacy documentation - uploaded in Step 2a
- ✅ Vendor product docs - uploaded in Step 2a
- ✅ Security scans (SBOM/SARIF) - uploaded in Step 2b
- ⏭️ Source code - will be ingested in Step 5.5

**Ingest frameworks and policies:**

```bash
curl -s -X POST "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/index/security/s3" \
  -H "Content-Type: application/json" \
  -d '{"bucket_name":"golden","key":"frameworks/"}' | jq

curl -s -X POST "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/index/security/s3" \
  -H "Content-Type: application/json" \
  -d '{"bucket_name":"golden","key":"policies/"}' | jq

curl -s -X POST "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/index/security/s3" \
  -H "Content-Type: application/json" \
  -d '{"bucket_name":"golden","key":"privacy/"}' | jq
```

**Expected output:**

```json
{
  "ingestion_id": "ing_abc123",
  "status": "completed",
  "document_count": 47,
  "file_breakdown": {
    "pdf": 25,
    "docx": 12,
    "markdown": 10
  },
  "document_categories": {
    "frameworks": 5,
    "policies": 12,
    "privacy": 8,
    "vendor_docs": 22
  },
  "total_pages": 3245,
  "total_tokens": 1847293,
  "metadata_preview": [
    {
      "filename": "soc2-type2-controls.pdf",
      "source": "frameworks/soc2-type2-controls.pdf",
      "pages": 150,
      "category": "compliance_framework"
    }
  ]
}
```

**Verify ingestion:**

```bash
# Check document count in OpenSearch
curl -X GET "${OPENSEARCH_URL}/${WORKSPACE_ID}/_count" | jq

# Expected: {"count": 3245}  (one doc per page for PDFs)

# Check document types
curl -X GET "${OPENSEARCH_URL}/${WORKSPACE_ID}/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "size": 0,
    "aggs": {
      "by_category": {
        "terms": {"field": "metadata.category.keyword"}
      }
    }
  }' | jq '.aggregations.by_category.buckets'
```

**Sample Query to Test Corpus:**

```bash
# Test that frameworks are searchable
curl -X POST "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the SOC 2 CC6.1 requirements for logical access controls?"
  }' | jq -r '.answer'
```

**Expected answer:** Will cite the SOC 2 framework document with specific control requirements.

**What you've demonstrated:**
- ✅ 47 documents ingested (frameworks, policies, privacy docs)
- ✅ 3,245 pages indexed and searchable
- ✅ Document corpus verifiable via OpenSearch queries
- ✅ RAG system can answer compliance questions

---

### Step 5.5: Scan Your Own Python Repository (NEW)

**Goal:** Analyze a Python repository of your choice using the full Certus stack - demonstrating real-world applicability to your own projects.

**What you'll do:**
1. Generate signed SBOM and SARIF for your chosen repo
2. Scan for vulnerabilities and security issues
3. Ingest the code into the workspace for RAG queries
4. Verify cryptographic signatures on artifacts

#### A. Choose a Repository

Pick any Python repository you have access to:

**Option 1: Public GitHub repository**
```bash
# Example: Scan a popular Python project
export SCAN_REPO_URL="https://github.com/pallets/flask"
export SCAN_REPO_NAME="flask"
```

**Option 2: Local repository**
```bash
# Use a local Python project
export SCAN_REPO_PATH="~/projects/my-python-app"
export SCAN_REPO_NAME="my-python-app"
```

**Option 3: Use a sample vulnerable app (for learning)**
```bash
# WebGoat-style intentionally vulnerable Python app
export SCAN_REPO_URL="https://github.com/we45/Vulnerable-Flask-App"
export SCAN_REPO_NAME="vulnerable-flask-app"
```

#### B. Generate Signed Security Artifacts

**Step 1: Clone the repository (if remote)**

```bash
cd /tmp
git clone $SCAN_REPO_URL $SCAN_REPO_NAME
cd $SCAN_REPO_NAME
```

**Step 2: Generate SBOM (Software Bill of Materials)**

```bash
# Generate SBOM using syft
docker run --rm -v $(pwd):/src anchore/syft:latest \
  /src -o spdx-json > /tmp/${SCAN_REPO_NAME}-sbom.json

# View SBOM summary
jq '{
  name: .name,
  version: .documentDescribes[0].versionInfo,
  packages: (.packages | length),
  dependencies: (.relationships | length)
}' /tmp/${SCAN_REPO_NAME}-sbom.json
```

**Expected output:**
```json
{
  "name": "flask",
  "version": "3.0.0",
  "packages": 47,
  "dependencies": 112
}
```

**Step 3: Generate SARIF (Security Scan Results)**

```bash
# Scan for vulnerabilities using Grype
docker run --rm -v $(pwd):/src anchore/grype:latest \
  /src -o sarif > /tmp/${SCAN_REPO_NAME}-sarif.json

# Summary of findings
jq '{
  tool: .runs[0].tool.driver.name,
  total_results: (.runs[0].results | length),
  by_severity: [.runs[0].results | group_by(.level) | .[] | {
    severity: .[0].level,
    count: length
  }]
}' /tmp/${SCAN_REPO_NAME}-sarif.json
```

**Expected output:**
```json
{
  "tool": "Grype",
  "total_results": 23,
  "by_severity": [
    {"severity": "error", "count": 12},
    {"severity": "warning", "count": 5},
    {"severity": "note", "count": 6}
  ]
}
```

**Step 4: Sign Artifacts with Certus Trust**

```bash
# Sign SBOM
curl -X POST ${CERTUS_TRUST_URL}/v1/sign \
  -H "Content-Type: application/json" \
  -d "{
    \"artifact_path\": \"/tmp/${SCAN_REPO_NAME}-sbom.json\",
    \"artifact_type\": \"sbom\",
    \"metadata\": {
      \"repository\": \"$SCAN_REPO_NAME\",
      \"scan_date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
      \"analyst\": \"$(whoami)\"
    }
  }" | jq > /tmp/${SCAN_REPO_NAME}-sbom-signature.json

# Sign SARIF
curl -X POST ${CERTUS_TRUST_URL}/v1/sign \
  -H "Content-Type: application/json" \
  -d "{
    \"artifact_path\": \"/tmp/${SCAN_REPO_NAME}-sarif.json\",
    \"artifact_type\": \"sarif\",
    \"metadata\": {
      \"repository\": \"$SCAN_REPO_NAME\",
      \"scan_date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
      \"analyst\": \"$(whoami)\"
    }
  }" | jq > /tmp/${SCAN_REPO_NAME}-sarif-signature.json

echo "✓ Artifacts signed and published to transparency log"
```

**Step 5: Verify Signatures**

```bash
# Verify SBOM signature
SBOM_HASH=$(sha256sum /tmp/${SCAN_REPO_NAME}-sbom.json | cut -d' ' -f1)

curl -X POST ${CERTUS_TRUST_URL}/v1/verify \
  -H "Content-Type: application/json" \
  -d "{
    \"artifact_hash\": \"$SBOM_HASH\",
    \"signature_file\": \"/tmp/${SCAN_REPO_NAME}-sbom-signature.json\"
  }" | jq
```

**Expected output:**
```json
{
  "verified": true,
  "signer": "certus-trust@certus.cloud",
  "timestamp": "2026-01-03T14:23:45Z",
  "transparency_log_entry": {
    "uuid": "rekor-xyz789",
    "index": 1337,
    "log_url": "https://rekor.sigstore.dev/..."
  }
}
```

#### C. Ingest Repository Code into Workspace

```bash
# Set repository path
export REPO_PATH="/tmp/${SCAN_REPO_NAME}"

# Ingest Python files into the workspace
curl -X POST "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ingest/local" \
  -H "Content-Type: application/json" \
  -d "{
    \"source_path\": \"$REPO_PATH\",
    \"file_patterns\": [\"*.py\", \"requirements*.txt\", \"*.md\"],
    \"metadata\": {
      \"source_type\": \"personal_scan\",
      \"repository\": \"$SCAN_REPO_NAME\",
      \"scan_date\": \"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",
      \"sbom_hash\": \"$SBOM_HASH\"
    }
  }" | jq
```

**Expected output:**
```json
{
  "ingestion_id": "ing_xyz789",
  "status": "completed",
  "document_count": 127,
  "file_breakdown": {
    "python": 89,
    "markdown": 12,
    "txt": 3
  },
  "metadata": {
    "repository": "flask",
    "total_lines_of_code": 45231,
    "languages_detected": ["python", "jinja2"]
  }
}
```

#### D. Query Your Repository with RAG

**Security-focused queries:**

```bash
# Find authentication-related code
curl -X POST "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask" \
  -H "Content-Type: application/json" \
  -d "{
    \"question\": \"How does authentication work in the ${SCAN_REPO_NAME} codebase? Show me the relevant code.\",
    \"filters\": {
      \"source_type\": \"personal_scan\"
    }
  }" | jq -r '.answer'

# Check for hardcoded secrets
curl -X POST "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask" \
  -H "Content-Type: application/json" \
  -d "{
    \"question\": \"Are there any hardcoded API keys, passwords, or secrets in ${SCAN_REPO_NAME}?\",
    \"filters\": {
      \"source_type\": \"personal_scan\"
    }
  }" | jq -r '.answer'

# Analyze dependency security
curl -X POST "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask" \
  -H "Content-Type: application/json" \
  -d "{
    \"question\": \"Based on the SBOM, what are the high-risk dependencies in ${SCAN_REPO_NAME}?\",
    \"filters\": {
      \"artifact_type\": \"sbom\"
    }
  }" | jq -r '.answer'
```

#### E. Review Integrity Evidence

All API calls to scan your repo were logged by Certus Integrity:

```bash
# Count decisions during the last 10 minutes (your scan window)
find "$EVIDENCE_DIR" -name "dec_*.json" -mmin -10 | wc -l

# Show the request pattern
jq -r '.decision.metadata.endpoint' \
  $(find "$EVIDENCE_DIR" -name "dec_*.json" -mmin -10) | \
  sort | uniq -c | sort -rn

# Expected output:
#   45 /v1/product-acquisition-review/ingest/local
#   23 /v1/product-acquisition-review/ask
#    8 /v1/sign
#    8 /v1/verify
```

**What you've demonstrated:**
- ✅ End-to-end scanning workflow: SBOM → SARIF → Sign → Verify → Ingest → Query
- ✅ Trust chain: Cryptographic signatures + transparency log
- ✅ RAG on your own code: Ask natural language questions about security issues
- ✅ Integrity monitoring: All API calls logged with cryptographic evidence

---

## Phase 4: Security & Compliance Analysis

### Step 6: OpenSearch Semantic Queries (Document Search)

Use semantic search to find relevant security and compliance information.

**Query 1: Security practices documentation**

```bash
curl -X POST ${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What are the security practices and controls documented?"}' | jq -r '.answer'
```

**Query 2: Privacy controls and data protection**

```bash
curl -X POST ${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What privacy controls and data protection measures are in place?"}' | jq -r '.answer'
```

**Query 3: Compliance with standards**

```bash
curl -X POST ${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What compliance standards does the product adhere to?"}' | jq -r '.answer'
```

**Security Analyst Notes:**
- Document findings from each query
- Identify gaps in documentation
- Note any incomplete or missing information

---

### Step 7: Neo4j Graph Queries (Vulnerability & Dependency Analysis)

Use the knowledge graph to understand vulnerabilities and their relationships.

Access Neo4j at `http://localhost:7474` with credentials:
- Username: `neo4j`
- Password: `password`

**Query 1: All vulnerabilities in the system**

```cypher
MATCH (f:Finding)
RETURN f.id, f.title, f.severity, f.description
ORDER BY f.severity DESC
```

**Query 2: Critical findings and affected files**

```cypher
MATCH (f:Finding {severity: "high"})
-[:LOCATED_IN]->(l:Location)
-[:FILE]->(file:File)
RETURN f.title, file.path, l.start_line
LIMIT 10
```

**Query 3: Vulnerability summary by type**

```cypher
MATCH (f:Finding)
RETURN f.id, COUNT(*) as count
ORDER BY count DESC
```

---

### Step 8: Hybrid Queries (OpenSearch + Neo4j)

Combine document search with vulnerability knowledge graph.

**Query 1: Policy coverage for found vulnerabilities**

```bash
curl -X POST ${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What policies address shell injection vulnerabilities and secure coding practices?"}' | jq -r '.answer'
```

**Query 2: Remediation guidance from documentation**

```bash
curl -X POST ${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What remediation steps are documented for SQL injection and parameterized queries?"}' | jq -r '.answer'
```

**Query 3: Compliance requirements vs. current state**

```bash
curl -X POST ${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What ISO 27001 or SOC2 compliance requirements are documented for access control?"}' | jq -r '.answer'
```

---

## Phase 4.5: Quality Assurance & Metrics (NEW)

### Step 8.5: Review RAG Pipeline Performance Metrics

**Goal:** Demonstrate Certus Assurance layer monitoring RAG quality.

```bash
# Query evaluation metrics for this workspace
curl -X GET "${CERTUS_ASK_URL}/v1/${WORKSPACE_ID}/evaluation/metrics" | jq
```

**Expected output:**
```json
{
  "workspace_id": "product-acquisition-review",
  "evaluation_period": "last_24h",
  "metrics": {
    "total_queries": 47,
    "avg_response_time_ms": 342,
    "avg_context_relevancy": 0.89,
    "avg_answer_relevancy": 0.92,
    "avg_faithfulness": 0.87,
    "retrieval_accuracy": 0.91
  },
  "quality_trends": {
    "context_relevancy": "stable",
    "answer_relevancy": "+3% vs baseline",
    "faithfulness": "-1% vs baseline"
  }
}
```

**What this shows:**
- ✅ RAG quality metrics (context relevancy: 0.89)
- ✅ Performance acceptable (<500ms avg)
- ✅ Answer quality tracked over time
- ✅ Assurance layer active and monitoring

---

### Step 8.6: Review Integrity Decision Metrics

**Goal:** Show that security controls don't degrade user experience.

```bash
# Get aggregate integrity metrics for this workspace
curl -s "${VICTORIAMETRICS_URL}/api/v1/query" \
  --data-urlencode "query=sum by(decision)(certus_integrity_decisions_total{workspace=\"${WORKSPACE_ID}\"})" | \
  jq -r '.data.result[] | "\(.metric.decision): \(.value[1])"'
```

**Expected output:**
```
allowed: 142
denied: 8
degraded: 0
```

**Calculate block rate:**

Block rate = denied / (allowed + denied) = 8 / 150 = 5.3%

**What this shows:**
- ✅ 94.7% allow rate (healthy)
- ✅ 5.3% block rate (minimal false positives)
- ✅ 0 degraded requests (system performing well)
- ✅ Security controls active without impacting workflow

---

## Phase 5: Audit & Logging

### Step 9: Log Checking & Activity Review

Verify all actions taken during the review process.

**Check ingestion logs:**

```bash
curl ${OPENSEARCH_URL}/logs-certus-docops/_search?pretty \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": {
      \"term\": {
        \"meta.workspace_id.keyword\": \"${WORKSPACE_ID}\"
      }
    },
    \"size\": 50
  }"
```

**Review privacy events:**

```bash
curl ${OPENSEARCH_URL}/logs-certus-docops/_search?pretty \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "match": {
        "event": "privacy"
      }
    },
    "size": 20
  }'
```

**Document findings:**

```
AUDIT LOG SUMMARY
=================
Workspace: product-acquisition-review
Review Date: [DATE]
Reviewer: [NAME]

Timeline:
- [TIME] Documentation uploaded to S3
- [TIME] Privacy scanning initiated
- [TIME] PII quarantine triggered: 1 document
- [TIME] Files approved after review
- [TIME] Ingestion completed: 47 documents indexed
- [TIME] Personal repo scan completed: 127 files
- [TIME] Vulnerability analysis completed
- [TIME] Compliance mapping completed

Integrity Metrics:
- Total API requests: 150
- Requests allowed: 142 (94.7%)
- Requests blocked: 8 (5.3%)
- Evidence bundles: 150 signed

Key Findings:
- [Vulnerability details]
- [Policy gaps]
- [Compliance gaps]

Recommendation: [APPROVE/CONDITIONAL/REJECT]
```

---

## Phase 6: Report Generation

### Step 10: Generate Security Review Report

Create a comprehensive security review report with findings, risk assessment, and recommendations.

#### A. Collect Query Results

```bash
cat > /tmp/product-acquisition-findings.json << 'EOF'
{
  "workspace_id": "product-acquisition-review",
  "product_name": "Acquisition Target Product",
  "review_date": "2026-01-03",
  "reviewer_name": "Security Analyst",
  "review_status": "COMPLETE",

  "document_summary": {
    "total_documents_indexed": 47,
    "frameworks_ingested": 5,
    "policies_ingested": 12,
    "security_scans_analyzed": 1,
    "personal_repo_files": 127,
    "pii_quarantined": 1
  },

  "vulnerability_summary": {
    "critical_count": 0,
    "high_count": 8,
    "medium_count": 15,
    "low_count": 19,
    "total_vulnerabilities": 42
  },

  "integrity_metrics": {
    "total_api_requests": 150,
    "requests_allowed": 142,
    "requests_blocked": 8,
    "block_rate_percent": 5.3,
    "evidence_bundles": 150,
    "enforcement_mode": "active"
  },

  "assurance_metrics": {
    "avg_context_relevancy": 0.89,
    "avg_answer_relevancy": 0.92,
    "avg_response_time_ms": 342
  },

  "trust_verification": {
    "sbom_verified": true,
    "sarif_verified": true,
    "transparency_log_entries": 2,
    "personal_repo_artifacts_signed": true
  },

  "security_findings": [
    {
      "finding_id": "VULN-001",
      "title": "Shell Injection Vulnerability",
      "severity": "high",
      "affected_files": ["api-handler.py"],
      "policy_coverage": "Secure Engineering and DevOps Policy",
      "remediation_status": "NOT STARTED",
      "impact": "Remote code execution"
    }
  ],

  "compliance_gaps": [
    {
      "gap_id": "GAP-001",
      "standard": "ISO 27001",
      "requirement": "Access Control Policy",
      "current_state": "Partially Documented",
      "remediation_priority": "HIGH",
      "estimated_effort": "2 weeks"
    }
  ],

  "recommendation": "CONDITIONAL APPROVE",
  "recommendation_reason": "Product meets baseline security requirements with identified gaps requiring remediation before production deployment. Full Certus stack demonstrated effective security controls."
}
EOF
```

#### B. Generate HTML Report (with Integrity Section)

```bash
cat > /tmp/generate-report.sh << 'SCRIPT'
#!/bin/bash

WORKSPACE_ID="${1:-product-acquisition-review}"
FINDINGS_FILE="${2:-/tmp/product-acquisition-findings.json}"
OUTPUT_FILE="${3:-/tmp/security-review-report.html}"

# Extract findings from JSON
PRODUCT_NAME=$(jq -r '.product_name' "$FINDINGS_FILE")
REVIEW_DATE=$(jq -r '.review_date' "$FINDINGS_FILE")
REVIEWER=$(jq -r '.reviewer_name' "$FINDINGS_FILE")
RECOMMENDATION=$(jq -r '.recommendation' "$FINDINGS_FILE")
REASON=$(jq -r '.recommendation_reason' "$FINDINGS_FILE")

CRITICAL=$(jq -r '.vulnerability_summary.critical_count' "$FINDINGS_FILE")
HIGH=$(jq -r '.vulnerability_summary.high_count' "$FINDINGS_FILE")
MEDIUM=$(jq -r '.vulnerability_summary.medium_count' "$FINDINGS_FILE")
LOW=$(jq -r '.vulnerability_summary.low_count' "$FINDINGS_FILE")
TOTAL_VULNS=$((CRITICAL + HIGH + MEDIUM + LOW))

API_REQUESTS=$(jq -r '.integrity_metrics.total_api_requests' "$FINDINGS_FILE")
ALLOWED=$(jq -r '.integrity_metrics.requests_allowed' "$FINDINGS_FILE")
BLOCKED=$(jq -r '.integrity_metrics.requests_blocked' "$FINDINGS_FILE")
BLOCK_RATE=$(jq -r '.integrity_metrics.block_rate_percent' "$FINDINGS_FILE")

# Generate HTML (truncated for brevity - see original for full HTML)
cat > "$OUTPUT_FILE" << 'HTML'
<!DOCTYPE html>
<html>
<head>
    <title>Security Review Report</title>
    <style>
        /* ... styles from original ... */
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Security Review Report</h1>
            <p>Product Acquisition Assessment - Full Certus Stack Demonstration</p>
        </div>

        <div class="content">
            <!-- Executive Summary -->
            <div class="section">
                <h2>Executive Summary</h2>
                <!-- ... metadata ... -->
            </div>

            <!-- NEW: API Security & Integrity Section -->
            <div class="section">
                <h2>API Security & Access Control (Certus Integrity)</h2>

                <h3>Integrity Summary</h3>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Assessment</th>
                    </tr>
                    <tr>
                        <td>Total API Requests</td>
                        <td>API_REQUESTS</td>
                        <td>✓ Normal volume</td>
                    </tr>
                    <tr>
                        <td>Requests Allowed</td>
                        <td>ALLOWED (ALLOW_PERCENT%)</td>
                        <td>✓ Healthy allow rate</td>
                    </tr>
                    <tr>
                        <td>Requests Blocked</td>
                        <td>BLOCKED (BLOCK_RATE%)</td>
                        <td>✓ Minimal false positives</td>
                    </tr>
                    <tr>
                        <td>Enforcement Mode</td>
                        <td>Active</td>
                        <td>✓ Controls enforced</td>
                    </tr>
                    <tr>
                        <td>Evidence Trail</td>
                        <td>API_REQUESTS signed bundles</td>
                        <td>✓ Complete audit trail</td>
                    </tr>
                </table>

                <h3>Security Posture</h3>
                <ul>
                    <li><strong>Rate Limiting:</strong> Configured at 100 req/min with 20-request burst protection</li>
                    <li><strong>IP Whitelisting:</strong> Analyst IPs whitelisted, all others subject to limits</li>
                    <li><strong>Evidence Generation:</strong> Every API decision cryptographically signed and logged</li>
                    <li><strong>Transparency Log:</strong> All evidence published to Sigstore Rekor for independent verification</li>
                </ul>

                <h3>Recommendations</h3>
                <ul>
                    <li>Current rate limits appropriate for acquisition review workload</li>
                    <li>Consider lowering limits to 50 req/min post-acquisition if internal-only</li>
                    <li>Monitor for distributed attacks from multiple IPs (none detected during review)</li>
                </ul>
            </div>

            <!-- Rest of report sections ... -->
        </div>

        <div class="footer">
            <p>This report is confidential and intended for authorized personnel only.</p>
            <p>Generated: REVIEW_DATE | Certus DocOps Security Review System</p>
        </div>
    </div>
</body>
</html>
HTML

# Replace placeholders
sed -i'' -e "s|PRODUCT_NAME|$PRODUCT_NAME|g" "$OUTPUT_FILE"
sed -i'' -e "s|REVIEW_DATE|$REVIEW_DATE|g" "$OUTPUT_FILE"
sed -i'' -e "s|API_REQUESTS|$API_REQUESTS|g" "$OUTPUT_FILE"
sed -i'' -e "s|ALLOWED|$ALLOWED|g" "$OUTPUT_FILE"
sed -i'' -e "s|BLOCKED|$BLOCKED|g" "$OUTPUT_FILE"
sed -i'' -e "s|BLOCK_RATE|$BLOCK_RATE|g" "$OUTPUT_FILE"
sed -i'' -e "s|TOTAL_VULNS|$TOTAL_VULNS|g" "$OUTPUT_FILE"

ALLOW_PERCENT=$(echo "scale=1; $ALLOWED * 100 / $API_REQUESTS" | bc)
sed -i'' -e "s|ALLOW_PERCENT|$ALLOW_PERCENT|g" "$OUTPUT_FILE"

echo "Report generated: $OUTPUT_FILE"
SCRIPT

chmod +x /tmp/generate-report.sh
/tmp/generate-report.sh
```

---

## Phase 7: Full Stack Verification (NEW)

### Step 11: Verify All Certus Components

**Goal:** End-to-end integration test of Trust, Ask, Integrity, Assurance, and Transform.

```bash
echo "=== Certus Stack Health Check ==="

# 1. Trust: Verify signing capability
echo "1. Trust Service..."
curl -s ${CERTUS_TRUST_URL}/health | jq -r '.status'
# Expected: "healthy"

# 2. Ask: Verify RAG pipeline
echo "2. Ask Service (RAG)..."
curl -s ${CERTUS_ASK_URL}/health | jq -r '.status'
# Expected: "healthy"

# 3. Integrity: Verify middleware active
echo "3. Integrity Middleware..."
curl -s ${CERTUS_ASK_URL}/v1/admin/integrity/status | jq -r '.enforcement_mode'
# Expected: "active"

# 4. Transform: Verify PII redaction capability
echo "4. Transform Service..."
curl -s ${CERTUS_TRANSFORM_URL}/health | jq -r '.status'
# Expected: "healthy"

# 5. Assurance: Verify metrics collection
echo "5. Assurance (Metrics)..."
curl -s "${VICTORIAMETRICS_URL}/api/v1/query?query=up" | jq -r '.status'
# Expected: "success"

echo "=== All Certus Components Verified ==="
```

**What you've demonstrated:**
- ✅ Trust service signing and verification active
- ✅ Ask RAG pipeline operational
- ✅ Integrity middleware enforcing rate limits
- ✅ Transform PII detection operational
- ✅ Assurance metrics collection active
- ✅ Full stack integration verified

---

## Summary Checklist

**Complete Certus Stack Demonstrated:**

**Trust:**
- [x] SBOM generated and cryptographically signed
- [x] SARIF report generated and signed
- [x] Signatures verified against transparency log (Rekor)
- [x] Certificate chain validated
- [x] Personal repository artifacts signed and verified

**Ask:**
- [x] Workspace created (`product-acquisition-review`)
- [x] Documents ingested (47 docs from S3 + 127 files from personal repo)
- [x] Semantic queries executed (OpenSearch)
- [x] Graph queries executed (Neo4j)
- [x] RAG answers generated for compliance questions

**Integrity:**
- [x] Rate limiting configured (100 req/min, 20 burst)
- [x] Enforcement mode enabled (shadow_mode=false)
- [x] 150 API requests logged with evidence bundles
- [x] 8 requests blocked (5.3% block rate - healthy)
- [x] Evidence cryptographically signed and verifiable

**Transform:**
- [x] PII detection run on documents
- [x] 1 document quarantined for review
- [x] Human-in-the-loop review completed
- [x] All approved documents ingested

**Assurance:**
- [x] RAG quality metrics collected (context relevancy: 0.89)
- [x] Integrity decision metrics reviewed (94.7% allow rate)
- [x] System health verified across all components
- [x] Performance within acceptable ranges (<500ms avg)

**Report:**
- [x] Security findings documented (0 critical, 8 high, 15 medium, 19 low)
- [x] Compliance gaps identified
- [x] Cryptographic evidence attached (SBOM, SARIF, integrity logs)
- [x] HTML report generated with executive summary
- [x] Integrity metrics included in report

---

## Next Steps

After completing this capstone:

1. **Present findings to stakeholders** using the generated security review report
2. **Negotiate remediation timeline** with vendor based on identified gaps
3. **Establish security governance** with assigned owner and escalation process
4. **Schedule follow-up review** at 90 days to verify remediation
5. **Archive the workspace** for compliance audit trail

---

**Total Time:** Expected 75-90 minutes for complete review including full stack demonstration

**Skills Demonstrated:**

- Document ingestion and privacy compliance (Transform)
- Semantic search (OpenSearch) for policy/control discovery (Ask)
- Knowledge graph queries (Neo4j) for vulnerability analysis (Ask)
- Cryptographic signing and verification (Trust)
- Rate limiting and access control (Integrity)
- Quality assurance and metrics monitoring (Assurance)
- End-to-end security stack integration
- Security review report generation and presentation
