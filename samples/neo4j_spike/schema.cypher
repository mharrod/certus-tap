// Neo4j Schema Definition for Spike
// This file contains all CREATE statements for nodes, relationships, constraints, and indexes

// ============================================================================
// CONSTRAINTS (Uniqueness + Existence)
// ============================================================================

CREATE CONSTRAINT finding_id_unique FOR (f:Finding) REQUIRE f.finding_id IS UNIQUE;
CREATE CONSTRAINT cwe_id_unique FOR (c:CWE) REQUIRE c.cwe_id IS UNIQUE;
CREATE CONSTRAINT control_id_unique FOR (ctrl:Control) REQUIRE ctrl.control_id IS UNIQUE;
CREATE CONSTRAINT threat_id_unique FOR (t:Threat) REQUIRE t.threat_id IS UNIQUE;
CREATE CONSTRAINT service_id_unique FOR (s:Service) REQUIRE s.service_id IS UNIQUE;
CREATE CONSTRAINT cve_id_unique FOR (v:CVE) REQUIRE v.cve_id IS UNIQUE;

// ============================================================================
// INDEXES (Performance)
// ============================================================================

CREATE INDEX cwe_id_index FOR (c:CWE) ON (c.cwe_id);
CREATE INDEX control_id_index FOR (ctrl:Control) ON (ctrl.control_id);
CREATE INDEX service_id_index FOR (s:Service) ON (s.service_id);
CREATE INDEX cve_id_index FOR (v:CVE) ON (v.cve_id);
CREATE INDEX finding_severity_index FOR (f:Finding) ON (f.severity);
CREATE INDEX finding_status_index FOR (f:Finding) ON (f.status);
CREATE INDEX control_framework_index FOR (ctrl:Control) ON (ctrl.framework);
CREATE INDEX threat_stride_index FOR (t:Threat) ON (t.stride_category);

// ============================================================================
// INITIAL DATA: CWE (Common Weakness Enumeration)
// ============================================================================

CREATE (cwe:CWE {
  cwe_id: 'CWE-79',
  title: 'Improper Neutralization of Input During Web Page Generation (Cross-site Scripting)',
  description: 'The software does not neutralize or incorrectly neutralizes user-controllable input before it is placed in output that is used as a web page that is served to other users.',
  severity: 'high'
});

CREATE (cwe:CWE {
  cwe_id: 'CWE-89',
  title: 'Improper Neutralization of Special Elements used in an SQL Command (SQL Injection)',
  description: 'The software constructs all or part of an SQL command using externally-influenced input from an upstream component, but it does not neutralize or incorrectly neutralizes special elements that could modify the intended SQL command.',
  severity: 'critical'
});

CREATE (cwe:CWE {
  cwe_id: 'CWE-94',
  title: 'Improper Control of Generation of Code (Code Injection)',
  description: 'The software constructs all or part of a code element using externally-influenced input from an upstream component, but it does not neutralize or incorrectly neutralizes special elements that could modify the intended code element.',
  severity: 'critical'
});

CREATE (cwe:CWE {
  cwe_id: 'CWE-22',
  title: 'Improper Limitation of a Pathname to a Restricted Directory (Path Traversal)',
  description: 'The software uses external input to construct a pathname that is intended to identify a file or directory that is located underneath a restricted parent directory, but the software does not properly neutralize special elements that can cause the pathname to resolve to a location that is outside of the restricted directory.',
  severity: 'high'
});

CREATE (cwe:CWE {
  cwe_id: 'CWE-352',
  title: 'Cross-Site Request Forgery (CSRF)',
  description: 'The web application does not, or can not, sufficiently verify whether a well-formed, valid, consistent request was intentionally provided by the user who submitted the request.',
  severity: 'medium'
});

// ============================================================================
// INITIAL DATA: CONTROLS (NIST 800-53)
// ============================================================================

CREATE (ctrl:Control {
  control_id: 'AC-3',
  framework: 'nist-800-53',
  title: 'Access Enforcement',
  description: 'The information system enforces approved authorizations for logical access to information and system resources in accordance with applicable access control policies.',
  status: 'partial'
});

CREATE (ctrl:Control {
  control_id: 'AC-7',
  framework: 'nist-800-53',
  title: 'Unsuccessful Logon Attempts',
  description: 'The information system enforces a limit of consecutive invalid logon attempts by a user during a system-defined time period and automatically [locks/delays logon] account/node for an organization-defined time period.',
  status: 'implemented'
});

CREATE (ctrl:Control {
  control_id: 'SC-7',
  framework: 'nist-800-53',
  title: 'Boundary Protection',
  description: 'The information system manages information flow to and from external networks (including wireless) by employing boundary protection mechanisms.',
  status: 'partial'
});

CREATE (ctrl:Control {
  control_id: 'SI-10',
  framework: 'nist-800-53',
  title: 'Information and Communication Technology (ICT) Security Testing',
  description: 'The organization includes security testing as part of system development life cycle activities.',
  status: 'missing'
});

CREATE (ctrl:Control {
  control_id: 'AU-12',
  framework: 'nist-800-53',
  title: 'Audit Generation',
  description: 'The information system provides audit record generation capability for the events defined in AU-2 at the information system and information system component level.',
  status: 'implemented'
});

// ============================================================================
// INITIAL DATA: THREATS (STRIDE)
// ============================================================================

CREATE (threat:Threat {
  threat_id: 'threat-tampering-001',
  stride_category: 'T',
  title: 'Attacker modifies user input in transit',
  description: 'An attacker intercepts and modifies HTTP requests/responses',
  likelihood: 'medium',
  impact: 'high'
});

CREATE (threat:Threat {
  threat_id: 'threat-spoofing-001',
  stride_category: 'S',
  title: 'Attacker forges authentication credentials',
  description: 'An attacker creates fake credentials to impersonate legitimate users',
  likelihood: 'high',
  impact: 'critical'
});

CREATE (threat:Threat {
  threat_id: 'threat-disclosure-001',
  stride_category: 'I',
  title: 'Information disclosure via error messages',
  description: 'Application exposes sensitive info (stack traces, SQL errors) to users',
  likelihood: 'medium',
  impact: 'medium'
});

CREATE (threat:Threat {
  threat_id: 'threat-dos-001',
  stride_category: 'D',
  title: 'Denial of Service via resource exhaustion',
  description: 'Attacker sends requests to exhaust memory/CPU resources',
  likelihood: 'medium',
  impact: 'high'
});

CREATE (threat:Threat {
  threat_id: 'threat-elevation-001',
  stride_category: 'E',
  title: 'Privilege escalation via unpatched code',
  description: 'Attacker exploits vulnerable code to gain admin access',
  likelihood: 'medium',
  impact: 'critical'
});

// ============================================================================
// INITIAL DATA: SERVICES
// ============================================================================

CREATE (svc:Service {
  service_id: 'auth-service',
  name: 'Authentication Service',
  description: 'Handles user login, MFA, password reset',
  criticality: 'critical',
  owner: 'security-team',
  status: 'active'
});

CREATE (svc:Service {
  service_id: 'api-gateway',
  name: 'API Gateway',
  description: 'Routes requests to backend services',
  criticality: 'critical',
  owner: 'platform-team',
  status: 'active'
});

CREATE (svc:Service {
  service_id: 'logging-service',
  name: 'Logging Service',
  description: 'Centralizes logs from all services',
  criticality: 'high',
  owner: 'platform-team',
  status: 'active'
});

CREATE (svc:Service {
  service_id: 'payment-service',
  name: 'Payment Service',
  description: 'Processes payments and transactions',
  criticality: 'critical',
  owner: 'finance-team',
  status: 'active'
});

CREATE (svc:Service {
  service_id: 'user-service',
  name: 'User Service',
  description: 'Manages user profiles and settings',
  criticality: 'high',
  owner: 'product-team',
  status: 'active'
});

// ============================================================================
// INITIAL DATA: CVEs (Common Vulnerabilities and Exposures)
// ============================================================================

CREATE (cve:CVE {
  cve_id: 'CVE-2024-12345',
  cwe_id: 'CWE-94',
  title: 'Log4j Remote Code Execution (Log4Shell variant)',
  cvss_v3: 10.0,
  epss: 0.97,
  published_date: datetime('2024-01-15'),
  is_exploited: true,
  exploit_count: 5000
});

CREATE (cve:CVE {
  cve_id: 'CVE-2023-50129',
  cwe_id: 'CWE-79',
  title: 'Stored XSS in Admin Panel',
  cvss_v3: 8.2,
  epss: 0.68,
  published_date: datetime('2023-11-20'),
  is_exploited: false,
  exploit_count: 0
});

CREATE (cve:CVE {
  cve_id: 'CVE-2023-45678',
  cwe_id: 'CWE-89',
  title: 'SQL Injection in User Search',
  cvss_v3: 9.1,
  epss: 0.85,
  published_date: datetime('2023-09-10'),
  is_exploited: true,
  exploit_count: 2500
});

// ============================================================================
// RELATIONSHIPS: CWE -> CONTROL (Violations)
// ============================================================================

MATCH (cwe:CWE {cwe_id: 'CWE-79'}), (ctrl:Control {control_id: 'AC-3'})
CREATE (cwe)-[r:CWE_VIOLATES_CONTROL {severity: 'high', description: 'XSS violates access control principles'}]->(ctrl);

MATCH (cwe:CWE {cwe_id: 'CWE-89'}), (ctrl:Control {control_id: 'AC-3'})
CREATE (cwe)-[r:CWE_VIOLATES_CONTROL {severity: 'critical', description: 'SQL injection violates access control'}]->(ctrl);

MATCH (cwe:CWE {cwe_id: 'CWE-352'}), (ctrl:Control {control_id: 'AC-7'})
CREATE (cwe)-[r:CWE_VIOLATES_CONTROL {severity: 'medium', description: 'CSRF violates access enforcement'}]->(ctrl);

MATCH (cwe:CWE {cwe_id: 'CWE-22'}), (ctrl:Control {control_id: 'SC-7'})
CREATE (cwe)-[r:CWE_VIOLATES_CONTROL {severity: 'high', description: 'Path traversal violates boundary protection'}]->(ctrl);

// ============================================================================
// RELATIONSHIPS: CONTROL -> THREAT (Mitigations)
// ============================================================================

MATCH (ctrl:Control {control_id: 'AC-3'}), (threat:Threat {threat_id: 'threat-tampering-001'})
CREATE (ctrl)-[r:CONTROL_MITIGATES_THREAT {coverage: 'partial', confidence: 0.8}]->(threat);

MATCH (ctrl:Control {control_id: 'AC-3'}), (threat:Threat {threat_id: 'threat-spoofing-001'})
CREATE (ctrl)-[r:CONTROL_MITIGATES_THREAT {coverage: 'full', confidence: 0.9}]->(threat);

MATCH (ctrl:Control {control_id: 'SC-7'}), (threat:Threat {threat_id: 'threat-dos-001'})
CREATE (ctrl)-[r:CONTROL_MITIGATES_THREAT {coverage: 'partial', confidence: 0.75}]->(threat);

MATCH (ctrl:Control {control_id: 'AU-12'}), (threat:Threat {threat_id: 'threat-disclosure-001'})
CREATE (ctrl)-[r:CONTROL_MITIGATES_THREAT {coverage: 'full', confidence: 0.85}]->(threat);

// ============================================================================
// RELATIONSHIPS: THREAT -> SERVICE (Affects)
// ============================================================================

MATCH (threat:Threat {threat_id: 'threat-tampering-001'}), (svc:Service {service_id: 'api-gateway'})
CREATE (threat)-[r:THREAT_AFFECTS_SERVICE {likelihood: 'high'}]->(svc);

MATCH (threat:Threat {threat_id: 'threat-spoofing-001'}), (svc:Service {service_id: 'auth-service'})
CREATE (threat)-[r:THREAT_AFFECTS_SERVICE {likelihood: 'critical'}]->(svc);

MATCH (threat:Threat {threat_id: 'threat-disclosure-001'}), (svc:Service {service_id: 'user-service'})
CREATE (threat)-[r:THREAT_AFFECTS_SERVICE {likelihood: 'medium'}]->(svc);

MATCH (threat:Threat {threat_id: 'threat-dos-001'}), (svc:Service {service_id: 'logging-service'})
CREATE (threat)-[r:THREAT_AFFECTS_SERVICE {likelihood: 'high'}]->(svc);

// ============================================================================
// RELATIONSHIPS: SERVICE -> SERVICE (Dependencies)
// ============================================================================

MATCH (s1:Service {service_id: 'api-gateway'}), (s2:Service {service_id: 'auth-service'})
CREATE (s1)-[r:SERVICE_DEPENDS_ON_SERVICE {criticality: 'critical', description: 'Auth required for all requests'}]->(s2);

MATCH (s1:Service {service_id: 'api-gateway'}), (s2:Service {service_id: 'logging-service'})
CREATE (s1)-[r:SERVICE_DEPENDS_ON_SERVICE {criticality: 'high', description: 'Logs all API requests'}]->(s2);

MATCH (s1:Service {service_id: 'payment-service'}), (s2:Service {service_id: 'user-service'})
CREATE (s1)-[r:SERVICE_DEPENDS_ON_SERVICE {criticality: 'high', description: 'Validates user account'}]->(s2);

MATCH (s1:Service {service_id: 'payment-service'}), (s2:Service {service_id: 'api-gateway'})
CREATE (s1)-[r:SERVICE_DEPENDS_ON_SERVICE {criticality: 'critical', description: 'Routes payment requests'}]->(s2);

// ============================================================================
// RELATIONSHIPS: CVE -> CWE (Contains)
// ============================================================================

MATCH (cve:CVE {cve_id: 'CVE-2024-12345'}), (cwe:CWE {cwe_id: 'CWE-94'})
CREATE (cve)-[r:CVE_HAS_CWE]->(cwe);

MATCH (cve:CVE {cve_id: 'CVE-2023-50129'}), (cwe:CWE {cwe_id: 'CWE-79'})
CREATE (cve)-[r:CVE_HAS_CWE]->(cwe);

MATCH (cve:CVE {cve_id: 'CVE-2023-45678'}), (cwe:CWE {cwe_id: 'CWE-89'})
CREATE (cve)-[r:CVE_HAS_CWE]->(cwe);

// ============================================================================
// Schema initialization complete
// Ready for evidence envelope ingestion
// ============================================================================
