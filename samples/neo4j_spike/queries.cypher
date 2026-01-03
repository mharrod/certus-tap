// Neo4j Cypher Queries for Spike Validation
// Tests Query Patterns 1-4 from NEO4J_VALIDATION_SPIKE.md

// ============================================================================
// QUERY PATTERN 1: Simple Query
// Question: "What controls mitigate CWE-79 findings?"
// ============================================================================

// Query 1.1: Get all controls that mitigate CWE-79
MATCH (cwe:CWE {cwe_id: "CWE-79"})
MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
RETURN
  cwe.cwe_id as cwe_id,
  cwe.title as cwe_title,
  control.control_id as control_id,
  control.title as control_title,
  control.framework as framework,
  control.status as status
ORDER BY control.control_id;

// Query 1.2: Count findings per CWE
MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe:CWE)
RETURN
  cwe.cwe_id,
  cwe.title,
  count(f) as finding_count
ORDER BY finding_count DESC;

// Query 1.3: Get findings with severity >= high
MATCH (f:Finding)
WHERE f.severity IN ['critical', 'high']
RETURN
  f.finding_id,
  f.cwe_id,
  f.severity,
  f.cvss_score,
  f.epss_score,
  f.status
ORDER BY f.cvss_score DESC;

// ============================================================================
// QUERY PATTERN 2: Blast Radius (Multi-hop Dependencies)
// Question: "Which services are affected by CVE-2024-12345?"
// ============================================================================

// Query 2.1: Direct blast radius - services affected by CVE
MATCH (cve:CVE {cve_id: "CVE-2024-12345"})
MATCH (f:Finding)-[:FINDING_LINKS_CVE]->(cve)
MATCH (f)-[:FINDING_AFFECTS_SERVICE]->(affected_service:Service)
RETURN
  DISTINCT affected_service.service_id,
  affected_service.name,
  affected_service.criticality,
  f.finding_id,
  f.severity
ORDER BY affected_service.criticality DESC;

// Query 2.2: Transitive blast radius - downstream services
MATCH (cve:CVE {cve_id: "CVE-2024-12345"})
MATCH (f:Finding)-[:FINDING_LINKS_CVE]->(cve)
MATCH (f)-[:FINDING_AFFECTS_SERVICE]->(primary_affected:Service)
MATCH (primary_affected)<-[:SERVICE_DEPENDS_ON_SERVICE]-(downstream:Service)
RETURN
  DISTINCT downstream.service_id,
  downstream.name,
  downstream.criticality,
  primary_affected.service_id as directly_affected,
  'indirect' as exposure_type
ORDER BY downstream.criticality DESC;

// Query 2.3: Full blast radius (direct + transitive, limited depth)
MATCH (cve:CVE {cve_id: "CVE-2024-12345"})
MATCH (f:Finding)-[:FINDING_LINKS_CVE]->(cve)
MATCH (f)-[:FINDING_AFFECTS_SERVICE]->(s:Service)
MATCH (s)<-[:SERVICE_DEPENDS_ON_SERVICE*0..2]-(downstream:Service)
RETURN
  DISTINCT downstream.service_id,
  downstream.name,
  downstream.criticality,
  s.service_id as entry_point
ORDER BY downstream.criticality DESC;

// Query 2.4: Service dependency chain
MATCH (start:Service {service_id: "logging-service"})
MATCH path = (start)<-[:SERVICE_DEPENDS_ON_SERVICE*0..3]-(end:Service)
WHERE start <> end
RETURN
  [node in nodes(path) | node.service_id] as service_chain,
  length(path) as hop_count
ORDER BY hop_count DESC;

// ============================================================================
// QUERY PATTERN 3: Aggregation & Coverage
// Question: "How many findings support NIST AC-3 implementation?"
// ============================================================================

// Query 3.1: Count findings supporting control
MATCH (control:Control {control_id: "AC-3"})
MATCH (cwe:CWE)-[:CWE_VIOLATES_CONTROL]->(control)
MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe)
WHERE f.status IN ['open', 'patched']
RETURN
  control.control_id as control_id,
  control.title as control_title,
  count(DISTINCT f) as finding_count,
  collect(DISTINCT cwe.cwe_id) as related_cwes,
  count(CASE WHEN f.status = 'patched' THEN 1 END) as patched_count,
  round(100.0 * count(CASE WHEN f.status = 'patched' THEN 1 END) / count(f), 1) as patched_pct;

// Query 3.2: Control coverage assessment per framework
MATCH (control:Control)
WHERE control.framework = 'nist-800-53'
OPTIONAL MATCH (cwe:CWE)-[:CWE_VIOLATES_CONTROL]->(control)
OPTIONAL MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe)
WITH control, count(DISTINCT f) as finding_count
RETURN
  control.control_id,
  control.title,
  control.status,
  finding_count,
  CASE
    WHEN control.status = 'implemented' THEN 'Full'
    WHEN control.status = 'partial' THEN 'Partial'
    ELSE 'Missing'
  END as implementation_status
ORDER BY control.control_id;

// Query 3.3: Framework coverage summary
MATCH (control:Control)
WITH control.framework as framework,
     count(CASE WHEN control.status = 'implemented' THEN 1 END) as implemented,
     count(CASE WHEN control.status = 'partial' THEN 1 END) as partial,
     count(CASE WHEN control.status = 'missing' THEN 1 END) as missing,
     count(*) as total
RETURN
  framework,
  implemented,
  partial,
  missing,
  total,
  round(100.0 * implemented / total, 1) as implementation_pct
ORDER BY implementation_pct DESC;

// Query 3.4: Controls with no evidence
MATCH (control:Control)
WHERE NOT EXISTS {
  MATCH (cwe:CWE)-[:CWE_VIOLATES_CONTROL]->(control)
  MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe)
}
RETURN
  control.control_id,
  control.title,
  control.status,
  'no_evidence' as finding_status
ORDER BY control.control_id;

// ============================================================================
// QUERY PATTERN 4: Conditional (Attack Paths)
// Question: "Show attack paths with missing/partial controls"
// ============================================================================

// Query 4.1: Attack paths - incomplete controls
MATCH (threat:Threat {stride_category: "T"})
MATCH (threat)<-[:THREAT_AFFECTS_SERVICE]-(svc:Service)
MATCH (svc)<-[:FINDING_AFFECTS_SERVICE]-(f:Finding)
MATCH (f)-[:FINDING_HAS_CWE]->(cwe:CWE)
MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
WHERE control.status IN ['missing', 'partial']
RETURN
  threat.threat_id,
  threat.title,
  svc.service_id,
  f.finding_id,
  cwe.cwe_id,
  control.control_id,
  control.status,
  control.title as control_title
ORDER BY svc.service_id, control.control_id;

// Query 4.2: Attack surface analysis
MATCH (threat:Threat)
MATCH (threat)<-[:THREAT_AFFECTS_SERVICE]-(svc:Service)
WITH threat, collect(DISTINCT svc.service_id) as affected_services, count(DISTINCT svc) as service_count
RETURN
  threat.threat_id,
  threat.title,
  threat.stride_category,
  threat.likelihood,
  threat.impact,
  service_count as affected_service_count,
  affected_services
ORDER BY service_count DESC;

// Query 4.3: Threat-to-control path (with gaps)
MATCH (threat:Threat)
OPTIONAL MATCH (threat_control)-[:CONTROL_MITIGATES_THREAT]->(threat)
OPTIONAL MATCH (threat)<-[:THREAT_AFFECTS_SERVICE]-(svc:Service)
OPTIONAL MATCH (svc)<-[:FINDING_AFFECTS_SERVICE]-(f:Finding)
OPTIONAL MATCH (f)-[:FINDING_HAS_CWE]->(cwe:CWE)
OPTIONAL MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(vuln_control:Control)
WITH threat, threat_control, svc, f, vuln_control,
     count(DISTINCT threat_control) as mitigating_controls,
     count(DISTINCT f) as related_findings,
     count(DISTINCT vuln_control) as affected_controls
RETURN
  threat.threat_id,
  threat.title,
  threat.stride_category,
  mitigating_controls,
  related_findings,
  affected_controls,
  CASE
    WHEN mitigating_controls > 0 AND affected_controls = 0 THEN 'Well-Mitigated'
    WHEN mitigating_controls > 0 AND affected_controls > 0 THEN 'Partially-Mitigated'
    ELSE 'Unmitigated'
  END as mitigation_status
ORDER BY mitigation_status;

// ============================================================================
// PERFORMANCE TEST QUERIES (for benchmarking)
// ============================================================================

// Perf 1: Simple count (should be < 100ms)
MATCH (c:Control)
RETURN count(c);

// Perf 2: Single-hop traversal (should be < 100ms)
MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe:CWE)
RETURN count(f);

// Perf 3: Two-hop traversal (should be < 200ms)
MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe:CWE)
MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
RETURN count(f);

// Perf 4: Three-hop traversal (should be < 500ms)
MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe:CWE)
MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
MATCH (control)-[:CONTROL_MITIGATES_THREAT]->(threat:Threat)
RETURN count(f);

// Perf 5: Complex multi-hop with aggregation (target < 500ms)
MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe:CWE)
MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
OPTIONAL MATCH (control)-[:CONTROL_MITIGATES_THREAT]->(threat:Threat)
OPTIONAL MATCH (threat)<-[:THREAT_AFFECTS_SERVICE]-(svc:Service)
WITH control, count(DISTINCT f) as finding_count, count(DISTINCT threat) as threat_count
RETURN control.control_id, finding_count, threat_count;

// ============================================================================
// DATA VERIFICATION QUERIES
// ============================================================================

// Verify nodes exist
MATCH (f:Finding) RETURN "Finding" as type, count(f) as count
UNION ALL
MATCH (c:CWE) RETURN "CWE" as type, count(c) as count
UNION ALL
MATCH (ctrl:Control) RETURN "Control" as type, count(ctrl) as count
UNION ALL
MATCH (t:Threat) RETURN "Threat" as type, count(t) as count
UNION ALL
MATCH (s:Service) RETURN "Service" as type, count(s) as count
UNION ALL
MATCH (v:CVE) RETURN "CVE" as type, count(v) as count;

// Verify relationships exist
MATCH ()-[r:FINDING_HAS_CWE]->() RETURN "FINDING_HAS_CWE" as type, count(r) as count
UNION ALL
MATCH ()-[r:CWE_VIOLATES_CONTROL]->() RETURN "CWE_VIOLATES_CONTROL" as type, count(r) as count
UNION ALL
MATCH ()-[r:CONTROL_MITIGATES_THREAT]->() RETURN "CONTROL_MITIGATES_THREAT" as type, count(r) as count
UNION ALL
MATCH ()-[r:THREAT_AFFECTS_SERVICE]->() RETURN "THREAT_AFFECTS_SERVICE" as type, count(r) as count
UNION ALL
MATCH ()-[r:SERVICE_DEPENDS_ON_SERVICE]->() RETURN "SERVICE_DEPENDS_ON_SERVICE" as type, count(r) as count
UNION ALL
MATCH ()-[r:CVE_HAS_CWE]->() RETURN "CVE_HAS_CWE" as type, count(r) as count
UNION ALL
MATCH ()-[r:FINDING_LINKS_CVE]->() RETURN "FINDING_LINKS_CVE" as type, count(r) as count;
