# Forensic Queries & Audit Trail

This guide shows you how to leverage the non-repudiation audit trail in Neo4j for compliance, incident investigation, and forensic analysis.

This tutorial is standalone - follow the Quick Start section below to populate Neo4j with sample data, or use it after completing [`verify-trust.md`](verify-trust.md) or [`vendor-review.md`](vendor-review.md).

## Overview

When you ingest findings with premium tier non-repudiation, every scan is recorded in Neo4j with full verification metadata. This enables powerful forensic queries to answer critical questions:

- "Were we running security scans before the breach?"
- "Did we verify those scans?"
- "Who verified the scan?"
- "Can I prove we scanned this code?"

## Prerequisites

- Stack is running: `just up`
- Preflight checks passed: `just preflight`
- Neo4j Browser access at `http://localhost:7474`

## Step 1 - Set-up

### 1.1 Bring up relevant services

```bash
just trust-up
```

### 1.2 Check if everything is ready for the tutorial

```bash
just preflight-trust
```

## Quick Start: Populate Neo4j with Sample Data

If you're starting fresh or haven't run the other tutorials, use the real security scan artifacts to populate Neo4j:

**Step 1: Set up workspace and artifacts**

```bash
# Create a workspace for audit queries
export WORKSPACE_ID="audit-demo"
export ARTIFACT_ROOT="$(pwd)/samples/non-repudiation/scan-artifacts"

# Verify artifacts exist
ls -lh "$ARTIFACT_ROOT"
```

**Step 2: Ingest security scans into Neo4j**

```bash
# Generate a unique scan ID for this demo
export SCAN_ID="audit-demo-$(date +%s)"
export ASSESSMENT_ID="neo4j-${WORKSPACE_ID}-scan"

# Ingest SAST scans (creates Finding nodes in Neo4j)
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/security \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/trivy.sarif.json"

curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/security \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/semgrep.sarif.json"

curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/security \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/bandit.sarif.json"

# Ingest SBOM (creates Package nodes in Neo4j)
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/index/ \
  -H "Content-Type: multipart/form-data" \
  -F "uploaded_file=@${ARTIFACT_ROOT}/syft.spdx.json"
```

**Step 3: Verify Neo4j was populated**

```bash
# Check that SecurityScan node was created
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:SecurityScan {assessment_id: 'neo4j-audit-demo-scan'})
   RETURN s.assessment_id, s.timestamp;"

# Count findings by severity
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:SecurityScan {assessment_id: 'neo4j-audit-demo-scan'})-[:CONTAINS]->(f:Finding)
   RETURN f.severity, count(f) as count
   ORDER BY count DESC;"
```

Expected output:

```
"error"    6
"warning"  2
```

You're now ready to run the forensic queries below!

## Part 1: Understanding the Neo4j Graph Structure

### Scan Node with Verification Properties

When a premium tier scan is ingested, the Scan node includes verification metadata:

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan)
   RETURN
     s.id,
     s.chain_verified,
     s.signer_outer,
     s.sigstore_timestamp,
     s.verification_timestamp
   LIMIT 1;"
```

This returns a node like:

```
{
  id: "scan-assessment-123",
  chain_verified: true,
  inner_signature_valid: true,
  outer_signature_valid: true,
  chain_unbroken: true,
  signer_inner: "certus-assurance@certus.cloud",
  signer_outer: "certus-trust@certus.cloud",
  sigstore_timestamp: "2024-01-15T14:32:45Z",
  verification_timestamp: "2024-01-15T14:35:22Z",
  timestamp: "2024-01-15T14:30:00Z"
}
```

### Relationships to Findings

The graph structure is:

```
(Scan {chain_verified: true})
  └─[:CONTAINS]─→ (Finding)
       ├─[:VIOLATES]─→ (Rule)
       ├─[:HAS_SEVERITY]─→ (Severity)
       └─[:LOCATED_AT]─→ (Location)
```

## Part 2: Basic Forensic Queries

### Query 1: Find All Verified Scans

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {chain_verified: true})
   RETURN
     s.id as scan_id,
     s.timestamp as scan_time,
     s.verification_timestamp as verified_at,
     s.signer_outer as verified_by,
     s.sigstore_timestamp as timestamp_authority
   ORDER BY s.verification_timestamp DESC;"
```

**Use case:** Compliance audit - "Show me all scans that were independently verified"

**Expected output:**

```
scan_id              scan_time                verified_at              verified_by                    timestamp_authority
assessment-prod-001  2024-01-15T14:30:00Z    2024-01-15T14:35:22Z    certus-trust@certus.cloud     2024-01-15T14:32:45Z
assessment-prod-002  2024-01-15T13:15:00Z    2024-01-15T13:18:44Z    certus-trust@certus.cloud     2024-01-15T13:16:32Z
```

### Query 2: Find All Unverified Scans

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan)
   WHERE NOT EXISTS(s.chain_verified) OR s.chain_verified = false
   RETURN
     s.id as scan_id,
     s.timestamp as scan_time,
     'UNVERIFIED' as status
   ORDER BY s.timestamp DESC;"
```

**Use case:** Compliance gap analysis - "Which scans lack verification?"

### Query 3: Find Findings from Verified Scans

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {chain_verified: true})-[:CONTAINS]->(f:Finding)
   RETURN
     s.id as scan_id,
     f.id as finding_id,
     f.rule_id as rule,
     f.severity as severity,
     s.signer_outer as verified_by
   ORDER BY s.verification_timestamp DESC, f.severity DESC;"
```

**Use case:** Risk assessment - "Show me high-severity findings from verified scans"

## Part 3: Advanced Forensic Queries

### Query 4: Timeline of Scans (Incident Investigation)

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan)
   WHERE s.timestamp >= '2024-01-15T00:00:00Z'
     AND s.timestamp <= '2024-01-16T00:00:00Z'
   RETURN
     s.id as scan_id,
     s.timestamp as when_scanned,
     s.verification_timestamp as when_verified,
     s.chain_verified as was_verified,
     s.signer_outer as verified_by,
     COUNT(()-[:CONTAINS]->(s)) as finding_count
   ORDER BY s.timestamp DESC;"
```

**Use case:** Incident investigation - "What scans were we running on Jan 15-16?"

**Sample output:**

```
scan_id             when_scanned              when_verified             was_verified  verified_by
assessment-prod-05  2024-01-15T15:10:00Z      2024-01-15T15:15:34Z      true          certus-trust@certus.cloud
assessment-prod-04  2024-01-15T13:55:00Z      2024-01-15T13:58:12Z      true          certus-trust@certus.cloud
```

### Query 5: Findings by Severity Over Time

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {chain_verified: true})-[:CONTAINS]->(f:Finding)-[:HAS_SEVERITY]->(sev:Severity)
   WHERE s.verification_timestamp >= '2024-01-01T00:00:00Z'
   RETURN
     sev.level as severity,
     COUNT(f) as finding_count,
     COLLECT(DISTINCT s.id) as scans
   ORDER BY sev.level DESC;"
```

**Use case:** Metrics - "Show severity distribution across verified scans"

**Sample output:**

```
severity  finding_count  scans
ERROR     6              ["assessment-prod-01","assessment-prod-05"]
WARNING   11             ["assessment-prod-01","assessment-prod-02","assessment-prod-05"]
```

### Query 6: Chain of Custody for Specific Assessment

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {id: 'assessment-123'})
   RETURN
     s.id as assessment_id,
     s.timestamp as scan_created,
     s.signer_inner as scanned_by,
     s.verification_timestamp as verification_completed,
     s.signer_outer as verified_by,
     s.sigstore_timestamp as timestamp_authority,
     s.chain_unbroken as chain_intact,
     CASE
       WHEN s.chain_verified = true THEN '✓ VERIFIED'
       ELSE '✗ UNVERIFIED'
     END as status;"
```

**Use case:** Compliance report - "Show the complete chain of custody for assessment 123"

**Sample output:**

```
assessment_id       scan_created             scanned_by                     verification_completed     verified_by
assessment-prod-01  2024-01-15T14:30:00Z     certus-assurance@certus.cloud  2024-01-15T14:35:22Z      certus-trust@certus.cloud
status: ✓ VERIFIED (chain_unbroken=true)
```

### Query 7: Who Verified Our Scans?

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {chain_verified: true})
   RETURN
     s.signer_outer as verified_by,
     COUNT(s) as scan_count,
     MIN(s.verification_timestamp) as first_verified,
     MAX(s.verification_timestamp) as last_verified
   ORDER BY scan_count DESC;"
```

**Use case:** Access control audit - "Who has been verifying our scans?"

**Sample output:**

```
verified_by                    scan_count  first_verified           last_verified
certus-trust@certus.cloud      42          2024-01-02T10:15:00Z     2024-01-16T09:42:12Z
```

## Part 4: Compliance Report Queries

### Query 8: SOC 2 Compliance Report

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {chain_verified: true})-[:CONTAINS]->(f:Finding)
   WITH
     s.id as scan_id,
     COUNT(f) as finding_count,
     COLLECT(DISTINCT f.severity) as severities,
     s.verification_timestamp as verified_at
   RETURN
     scan_id,
     finding_count,
     severities,
     verified_at,
     'COMPLIANT' as status
   ORDER BY verified_at DESC
   LIMIT 10;"
```

**Report output:**

```
scan_id              finding_count  severities           verified_at              status
assessment-001       3              ["error","warning"]  2024-01-15T14:35:22Z    COMPLIANT
assessment-002       1              ["warning"]         2024-01-15T13:18:44Z    COMPLIANT
```

### Query 9: PCI-DSS Required Scanning Schedule

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan)
   WITH
     s,
     datetime(s.timestamp) as scan_date
   WHERE scan_date >= datetime() - duration('P30D')
   RETURN
     DATE(scan_date) as date,
     COUNT(s) as scans_performed,
     SUM(CASE WHEN s.chain_verified = true THEN 1 ELSE 0 END) as verified_scans,
     100.0 * SUM(CASE WHEN s.chain_verified = true THEN 1 ELSE 0 END) / COUNT(s) as verification_rate
   ORDER BY date DESC;"
```

**Report output:**

```
date         scans_performed  verified_scans  verification_rate
2024-01-15   5                5               100.0
2024-01-14   4                4               100.0
2024-01-13   3                2               66.7
```

## Part 5: Exporting Audit Trails

### Export Verified Scans to CSV

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {chain_verified: true})
   RETURN
     s.id as assessment_id,
     s.timestamp as scan_timestamp,
     s.verification_timestamp as verification_timestamp,
     s.signer_outer as verified_by,
     s.sigstore_timestamp as sigstore_timestamp,
     s.chain_unbroken as chain_intact
   ORDER BY s.verification_timestamp DESC;"
```

**In Neo4j Browser:**

1. Run the query
2. Click "Export" → "CSV"
3. Save for compliance audit

### Export Full Chain of Custody

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {chain_verified: true})-[:CONTAINS]->(f:Finding)
   RETURN
     s.id as scan_id,
     f.id as finding_id,
     f.rule_id as rule,
     f.severity as severity,
     s.signer_inner as scanned_by,
     s.signer_outer as verified_by,
     s.verification_timestamp as verification_time
   ORDER BY s.verification_timestamp DESC;"
```

## Part 6: Incident Investigation Scenario

### Scenario: Breach Occurred on Jan 15

**Question:** "Did we scan for CVE-2024-1234 before the breach?"

```bash
# Step 1: Find scans before Jan 15
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan)
   WHERE s.timestamp < '2024-01-15T00:00:00Z'
     AND s.chain_verified = true
   RETURN
     s.id as scan_id,
     s.timestamp as scan_time,
     s.signer_outer as verified_by,
     s.sigstore_timestamp as timestamp_proof
   ORDER BY s.timestamp DESC
   LIMIT 5;"
```

**Step 2: Check what was scanned in those assessments**

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan {id: 'assessment-123'})-[:CONTAINS]->(f:Finding)
   WHERE f.rule_id CONTAINS 'CVE-2024-1234'
   RETURN
     f.rule_id as vulnerability,
     f.severity as severity,
     s.timestamp as found_at,
     s.verification_timestamp as verified_at,
     s.sigstore_timestamp as timestamp_authority;"
```

**Result:** Shows proof that CVE was scanned and verified before breach

## Part 7: Accessing Sigstore Transparency Log

Each verified scan has a `sigstore_timestamp` and entry ID. To verify independently:

```bash
# Get the timestamp from Neo4j query
sigstore_timestamp="2024-01-15T14:32:45Z"

# Query Rekor transparency log
curl https://rekor.sigstore.dev/api/v1/log/entries \
  --data-urlencode "search=timestamp=$sigstore_timestamp"
```

> **Note:** Today’s dev environment uses a mock Sigstore/Rekor integration (same as described in [`verify-trust.md`](verify-trust.md)), so the timestamps/UUIDs can’t be queried against the public Rekor API yet. Treat this as a preview; once real Sigstore support arrives you can run the commands above.

## Part 8: Dashboard View (Ongoing Compliance)

### Real-Time Verification Rate

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan)
   WITH
     COUNT(s) as total_scans,
     SUM(CASE WHEN s.chain_verified = true THEN 1 ELSE 0 END) as verified
   RETURN
     total_scans,
     verified,
     ROUND(100.0 * verified / total_scans, 1) as verification_rate_percent,
     CASE
       WHEN 100.0 * verified / total_scans >= 95 THEN '✓ COMPLIANT'
       ELSE '✗ BELOW TARGET'
     END as compliance_status;"
```

### Scans Per Service

```bash
docker exec neo4j cypher-shell -u neo4j -p password \
  "MATCH (s:Scan)-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
   WITH DISTINCT s, loc
   RETURN
     SPLIT(loc.uri, '/')[0] as service,
     COUNT(DISTINCT s) as scan_count,
     SUM(CASE WHEN s.chain_verified = true THEN 1 ELSE 0 END) as verified,
     100.0 * SUM(CASE WHEN s.chain_verified = true THEN 1 ELSE 0 END) / COUNT(DISTINCT s) as verify_rate
   ORDER BY scan_count DESC;"
```

## Common Use Cases

| Use Case               | Query   | Purpose                           |
| ---------------------- | ------- | --------------------------------- |
| Compliance audit       | Query 1 | Prove scans are verified          |
| Incident investigation | Query 4 | Timeline of scanning              |
| Access audit           | Query 7 | Who verified scans                |
| Risk assessment        | Query 3 | Findings from trusted scans       |
| Report generation      | Query 8 | SOC 2 compliance proof            |
| Chain of custody       | Query 6 | Complete audit trail for one scan |

## Part 9: Cross-Checking with OpenSearch Logs

Neo4j captures structured provenance, while OpenSearch stores ingestion events and raw documents. Use both for complete forensic coverage.

### Query 10: Find Ingestion Events in OpenSearch

```bash
curl -s "http://localhost:9200/logs-certus-tap/_search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": {
      "term": {
        "meta.scan_id.keyword": "'$SCAN_ID'"
      }
    },
    "sort": [{"@timestamp": {"order": "desc"}}],
    "size": 10
  }' | jq '.hits.hits[] | {timestamp: ._source["@timestamp"], event: ._source.event, document: ._source.document_name}'
```

**Use case:** Correlate Neo4j `Scan` nodes with their ingestion events in OpenSearch.

### Query 11: Hybrid RAG Query

Use Certus Ask to pull SARIF/SBOM evidence from OpenSearch while referencing Neo4j verification data:

```bash
curl -X POST http://localhost:8000/v1/$WORKSPACE_ID/ask \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Summarize verified findings for scan '$SCAN_ID' and show the verification proof."
  }'
```

**Result:** The response cites SARIF documents stored in OpenSearch and includes Neo4j verification metadata, giving auditors both unstructured evidence and structured lineage.

### Visual Dashboards

Load the `logs-certus-tap` index into OpenSearch Dashboards/Kibana to visualize ingestion timelines or document activity, then pair it with Neo4j dashboards (NeoDash/Grafana) for a combined compliance view.

## Key Takeaways

✓ **Verified scans have immutable audit trails** - Every step is cryptographically signed and recorded in Sigstore

✓ **Forensic queries answer compliance questions** - "Did we really scan?" with proof

✓ **Independent verification** - Sigstore timestamp proves Trust didn't forge verification retroactively

✓ **Legal defensibility** - Complete chain of custody can be presented in audits or court

✓ **Real-time compliance monitoring** - Dashboard queries (Cypher, NeoDash, Grafana) plus OpenSearch/Kibana views keep verification trends visible

## Next Steps

- Explore queries in Neo4j Browser: `http://localhost:7474`
- Export audit trails to CSV for compliance reports
- Set up regular queries as compliance monitoring dashboards
- Integrate with your compliance platform (Drata, Vanta, etc.)

## Need Help?

- Neo4j query syntax: [Neo4j Cypher Manual](https://neo4j.com/docs/cypher-manual/current/)
- Sigstore verification: [Sigstore Documentation](https://docs.sigstore.dev/)
- Compliance frameworks: See [Non-Repudiation Overview](overview.md)

## Step 6: Cleaning Up

```bash
just down          # stop containers, keep volumes
just cleanup       # stop + remove containers, keep volumes
just destroy       # full tear-down (volumes removed)
```
