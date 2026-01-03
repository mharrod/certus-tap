// Sample Neo4j Cypher queries and their expected results for forensic analysis

// Query 1: Find all verified scans
MATCH (s:SecurityScan)
WHERE s.chain_verified = true AND s.outer_signature_valid = true
RETURN
  s.assessment_id as assessment_id,
  s.signer_outer as verified_by,
  s.verification_timestamp as verified_at,
  count(distinct r:Finding)-[:HAS_FINDING]->(r) as findings_count
ORDER BY s.verification_timestamp DESC
LIMIT 10

// Expected results:
[
  {
    "assessment_id": "assessment-20240115-001",
    "verified_by": "certus-trust@certus.cloud",
    "verified_at": "2024-01-15T14:35:25Z",
    "findings_count": 6
  },
  {
    "assessment_id": "assessment-20240114-002",
    "verified_by": "certus-trust@certus.cloud",
    "verified_at": "2024-01-14T11:20:15Z",
    "findings_count": 12
  },
  {
    "assessment_id": "assessment-20240113-001",
    "verified_by": "certus-trust@certus.cloud",
    "verified_at": "2024-01-13T09:45:30Z",
    "findings_count": 8
  }
]

// Query 2: Verify unbroken chain for specific assessment
MATCH (s:SecurityScan {assessment_id: "assessment-20240115-001"})
RETURN s.chain_unbroken,
       s.inner_signature_valid,
       s.outer_signature_valid,
       s.signer_inner,
       s.signer_outer,
       s.sigstore_timestamp

// Expected results:
[
  {
    "s.chain_unbroken": true,
    "s.inner_signature_valid": true,
    "s.outer_signature_valid": true,
    "s.signer_inner": "certus-assurance@certus.cloud",
    "s.signer_outer": "certus-trust@certus.cloud",
    "s.sigstore_timestamp": "2024-01-15T14:35:23Z"
  }
]

// Query 3: Timeline of findings by severity across verified scans
MATCH (s:SecurityScan)-[:HAS_FINDING]->(f:Finding)
WHERE s.chain_verified = true
RETURN
  s.verification_timestamp as scan_date,
  f.severity,
  count(f) as count
ORDER BY scan_date DESC, f.severity

// Expected results:
[
  { "scan_date": "2024-01-15T14:35:25Z", "severity": "CRITICAL", "count": 1 },
  { "scan_date": "2024-01-15T14:35:25Z", "severity": "HIGH", "count": 2 },
  { "scan_date": "2024-01-15T14:35:25Z", "severity": "MEDIUM", "count": 2 },
  { "scan_date": "2024-01-15T14:35:25Z", "severity": "LOW", "count": 1 },
  { "scan_date": "2024-01-14T11:20:15Z", "severity": "CRITICAL", "count": 2 },
  { "scan_date": "2024-01-14T11:20:15Z", "severity": "HIGH", "count": 4 },
  { "scan_date": "2024-01-14T11:20:15Z", "severity": "MEDIUM", "count": 6 }
]

// Query 4: Chain of custody - complete audit trail for investigation
MATCH (s:SecurityScan {assessment_id: "assessment-20240115-001"})-[:HAS_FINDING]->(f:Finding)
RETURN
  s.scan_id as scan_id,
  s.requested_by as requested_by,
  s.created_at as scan_created,
  s.verification_timestamp as verified_at,
  s.signer_inner as assurance_signer,
  s.signer_outer as trust_signer,
  s.sigstore_timestamp as immutable_record_timestamp,
  count(f) as finding_count
ORDER BY s.created_at

// Expected results:
[
  {
    "scan_id": "scan_550e8400e29b41d4a716446655440000",
    "requested_by": "security-team@certus.cloud",
    "scan_created": "2024-01-15T14:30:00Z",
    "verified_at": "2024-01-15T14:35:25Z",
    "assurance_signer": "certus-assurance@certus.cloud",
    "trust_signer": "certus-trust@certus.cloud",
    "immutable_record_timestamp": "2024-01-15T14:35:23Z",
    "finding_count": 6
  }
]

// Query 5: Incident investigation - who modified what and when
MATCH (s:SecurityScan {assessment_id: "assessment-20240115-001"})
RETURN
  s.assessment_id as assessment_id,
  s.scan_id as scan_id,
  s.created_at as created,
  s.verification_timestamp as verified,
  datetime(s.verification_timestamp) - datetime(s.created_at) as verification_delay,
  s.requested_by as requester,
  s.signer_inner as inner_signer,
  s.signer_outer as outer_signer,
  s.rekor_entry_uuid as sigstore_entry

// Expected results:
[
  {
    "assessment_id": "assessment-20240115-001",
    "scan_id": "scan_550e8400e29b41d4a716446655440000",
    "created": "2024-01-15T14:30:00Z",
    "verified": "2024-01-15T14:35:25Z",
    "verification_delay": "PT5M25S",
    "requester": "security-team@certus.cloud",
    "inner_signer": "certus-assurance@certus.cloud",
    "outer_signer": "certus-trust@certus.cloud",
    "sigstore_entry": "550e8400-e29b-41d4-a716-446655440001"
  }
]

// Query 6: Compliance - all findings in verified scans with remediation status
MATCH (s:SecurityScan)-[:HAS_FINDING]->(f:Finding)
WHERE s.chain_verified = true AND s.assessment_id = "assessment-20240115-001"
OPTIONAL MATCH (f)-[:REMEDIATED_BY]->(r:Remediation)
RETURN
  f.rule_id as finding_id,
  f.title as title,
  f.severity as severity,
  f.cwe_id as cwe,
  r.status as remediation_status,
  r.estimated_fix_date as fix_date
ORDER BY f.severity DESC

// Expected results:
[
  {
    "finding_id": "CVE-2024-1086",
    "title": "HTTP response smuggling in requests library",
    "severity": "CRITICAL",
    "cwe": null,
    "remediation_status": "IN_PROGRESS",
    "fix_date": "2024-01-20"
  },
  {
    "finding_id": "CWE-89",
    "title": "SQL Injection vulnerability",
    "severity": "HIGH",
    "cwe": "CWE-89",
    "remediation_status": "PLANNED",
    "fix_date": "2024-02-15"
  },
  {
    "finding_id": "CWE-78",
    "title": "Command Injection vulnerability",
    "severity": "HIGH",
    "cwe": "CWE-78",
    "remediation_status": "PLANNED",
    "fix_date": "2024-02-15"
  },
  {
    "finding_id": "CWE-295",
    "title": "Improper Certificate Validation",
    "severity": "MEDIUM",
    "cwe": "CWE-295",
    "remediation_status": "BACKLOG",
    "fix_date": "2024-03-30"
  },
  {
    "finding_id": "CWE-798",
    "title": "Hardcoded credentials",
    "severity": "MEDIUM",
    "cwe": "CWE-798",
    "remediation_status": "RESOLVED",
    "fix_date": "2024-01-18"
  },
  {
    "finding_id": "CWE-327",
    "title": "Use of Broken Cryptographic Algorithm",
    "severity": "LOW",
    "cwe": "CWE-327",
    "remediation_status": "BACKLOG",
    "fix_date": "2024-04-30"
  }
]

// Query 7: Dependency analysis from SBOM
MATCH (s:SecurityScan {assessment_id: "assessment-20240115-001"})-[:HAS_SBOM]->(sbom:SBOM)-[:HAS_COMPONENT]->(c:Component)
RETURN
  c.name as package,
  c.version as version,
  c.license as license,
  c.purl as package_url,
  count(distinct f:Finding) as vulnerability_count
ORDER BY vulnerability_count DESC

// Expected results:
[
  {
    "package": "requests",
    "version": "2.31.0",
    "license": "Apache-2.0",
    "package_url": "pkg:pypi/requests@2.31.0",
    "vulnerability_count": 1
  },
  {
    "package": "fastapi",
    "version": "0.104.1",
    "license": "MIT",
    "package_url": "pkg:pypi/fastapi@0.104.1",
    "vulnerability_count": 0
  },
  {
    "package": "pydantic",
    "version": "2.5.0",
    "license": "MIT",
    "package_url": "pkg:pypi/pydantic@2.5.0",
    "vulnerability_count": 0
  },
  {
    "package": "cryptography",
    "version": "41.0.7",
    "license": "Apache-2.0 OR BSD-3-Clause",
    "package_url": "pkg:pypi/cryptography@41.0.7",
    "vulnerability_count": 0
  }
]

// Query 8: Verify complete chain from creation to verification to storage
MATCH (s:SecurityScan {assessment_id: "assessment-20240115-001"})
RETURN
  "✓ Scan created by Assurance" as step_1,
  "✓ Signed with inner_signature at " + s.created_at as step_2,
  "✓ Promoted to Transform at " + s.promotion_timestamp as step_3,
  "✓ Verified by Trust at " + s.verification_timestamp as step_4,
  "✓ Recorded in Sigstore at " + s.sigstore_timestamp as step_5,
  "✓ Stored in Ask Neo4j" as step_6,
  CASE
    WHEN s.chain_verified AND s.inner_signature_valid AND s.outer_signature_valid
    THEN "✓ CHAIN VERIFIED - NON-REPUDIATION GUARANTEED"
    ELSE "✗ CHAIN VERIFICATION FAILED"
  END as result

// Expected results:
[
  {
    "step_1": "✓ Scan created by Assurance",
    "step_2": "✓ Signed with inner_signature at 2024-01-15T14:30:00Z",
    "step_3": "✓ Promoted to Transform at 2024-01-15T14:32:50Z",
    "step_4": "✓ Verified by Trust at 2024-01-15T14:35:25Z",
    "step_5": "✓ Recorded in Sigstore at 2024-01-15T14:35:23Z",
    "step_6": "✓ Stored in Ask Neo4j",
    "result": "✓ CHAIN VERIFIED - NON-REPUDIATION GUARANTEED"
  }
]
