# Neo4j Validation Spike Plan

**Objective:** Prove Neo4j viability for threat modeling + compliance reasoning before full RUN phase investment

**Duration:** 3 weeks / ~0.5 FTE (1 backend engineer)
**Timing:** Run in parallel with WALK.1 (Evidence Envelope) — Weeks 1–3 of WALK phase
**Success Criteria:** Answer 4 key validation questions (see "Go/No-Go Decision" section)
**Outcome:** Recommendation to accelerate Neo4j to early RUN or defer to RUN.3

---

## Phase Overview

| **Week** | **Focus** | **Deliverables** |
|----------|----------|-----------------|
| **Week 1** | Schema design + Neo4j setup | DDL (CREATE statements), local instance running |
| **Week 2** | Data loader + sample queries | Loader script, 5+ test queries, performance baselines |
| **Week 3** | Evaluation + documentation | Spike summary, go/no-go recommendation, next steps |

---

---

## Week 1: Schema Design & Neo4j Setup

### Task 1.1: Design Neo4j Schema (Knowledge Graph Model)

**Goal:** Define minimal viable graph structure for threat reasoning

**Deliverables:**
- Node type definitions (6 types)
- Relationship type definitions (8 types)
- Property schemas (required + optional fields)
- Constraints (uniqueness, existence)

**Details:**

#### Node Types

```
NODE: Finding
├─ Properties:
│  ├─ finding_id: String (UNIQUE)
│  ├─ cwe_id: String (indexed)
│  ├─ severity: Enum (critical, high, medium, low)
│  ├─ cvss_score: Float (0–10)
│  ├─ epss_score: Float (0–1)
│  ├─ title: String
│  ├─ description: String
│  ├─ first_seen: DateTime
│  └─ status: Enum (open, patched, waived)

NODE: CWE
├─ Properties:
│  ├─ cwe_id: String (UNIQUE, indexed)
│  ├─ title: String
│  ├─ description: String
│  └─ related_cwe_ids: List[String]

NODE: Control
├─ Properties:
│  ├─ control_id: String (UNIQUE, indexed)
│  ├─ framework: Enum (nist-800-53, iso-27001, cis)
│  ├─ title: String
│  ├─ description: String
│  ├─ status: Enum (implemented, partial, missing, waived)
│  └─ evidence_count: Integer

NODE: Threat
├─ Properties:
│  ├─ threat_id: String (UNIQUE)
│  ├─ stride_category: Enum (S, T, R, I, D, E)
│  ├─ title: String
│  ├─ description: String
│  ├─ likelihood: Enum (high, medium, low)
│  └─ impact: Enum (high, medium, low)

NODE: Service
├─ Properties:
│  ├─ service_id: String (UNIQUE, indexed)
│  ├─ name: String
│  ├─ description: String
│  ├─ criticality: Enum (critical, high, medium, low)
│  ├─ owner: String
│  └─ status: Enum (active, deprecated, archived)

NODE: CVE
├─ Properties:
│  ├─ cve_id: String (UNIQUE, indexed)
│  ├─ cwe_id: String
│  ├─ cvss_v3: Float
│  ├─ epss: Float
│  ├─ published_date: DateTime
│  ├─ is_exploited: Boolean
│  └─ exploit_count: Integer
```

#### Relationship Types

```
Relationship: FINDING_HAS_CWE
├─ From: Finding → CWE
├─ Properties: confidence: Float (0–1)
└─ Semantics: "This finding is an instance of CWE X"

Relationship: CWE_VIOLATES_CONTROL
├─ From: CWE → Control
├─ Properties: severity: Enum (critical, high, medium)
└─ Semantics: "CWE X violates compliance requirement Control Y"

Relationship: CONTROL_MITIGATES_THREAT
├─ From: Control → Threat
├─ Properties: coverage: Enum (full, partial, none)
└─ Semantics: "Control X mitigates Threat Y"

Relationship: THREAT_AFFECTS_SERVICE
├─ From: Threat → Service
├─ Properties: likelihood: Enum (high, medium, low)
└─ Semantics: "Threat X is relevant to Service Y"

Relationship: SERVICE_DEPENDS_ON_SERVICE
├─ From: Service → Service
├─ Properties: criticality: Enum (critical, high, medium)
└─ Semantics: "Service X depends on Service Y"

Relationship: FINDING_AFFECTS_SERVICE
├─ From: Finding → Service
├─ Properties: impact: Enum (critical, high, medium, low)
└─ Semantics: "Finding X impacts Service Y"

Relationship: CVE_HAS_CWE
├─ From: CVE → CWE
├─ Properties: none
└─ Semantics: "CVE X contains CWE weakness Y"

Relationship: FINDING_LINKS_CVE
├─ From: Finding → CVE
├─ Properties: detected_by: String (tool name)
└─ Semantics: "Finding X corresponds to CVE Y"
```

**Constraints:**
```cypher
CREATE CONSTRAINT finding_id_unique FOR (f:Finding) REQUIRE f.finding_id IS UNIQUE;
CREATE CONSTRAINT cwe_id_unique FOR (c:CWE) REQUIRE c.cwe_id IS UNIQUE;
CREATE CONSTRAINT control_id_unique FOR (ctrl:Control) REQUIRE ctrl.control_id IS UNIQUE;
CREATE CONSTRAINT threat_id_unique FOR (t:Threat) REQUIRE t.threat_id IS UNIQUE;
CREATE CONSTRAINT service_id_unique FOR (s:Service) REQUIRE s.service_id IS UNIQUE;
CREATE CONSTRAINT cve_id_unique FOR (v:CVE) REQUIRE v.cve_id IS UNIQUE;
```

**Indexes (Performance):**
```cypher
CREATE INDEX cwe_id_index FOR (c:CWE) ON (c.cwe_id);
CREATE INDEX control_id_index FOR (ctrl:Control) ON (ctrl.control_id);
CREATE INDEX service_id_index FOR (s:Service) ON (s.service_id);
CREATE INDEX cve_id_index FOR (v:CVE) ON (v.cve_id);
CREATE INDEX finding_severity_index FOR (f:Finding) ON (f.severity);
CREATE INDEX finding_status_index FOR (f:Finding) ON (f.status);
CREATE INDEX control_framework_index FOR (ctrl:Control) ON (ctrl.framework);
CREATE INDEX threat_stride_index FOR (t:Threat) ON (t.stride_category);
```

**Acceptance Criteria:**
- ✅ Schema DDL created (Cypher CREATE statements)
- ✅ All node types + relationships documented
- ✅ Constraints + indexes defined
- ✅ Property schemas match WALK.1 Evidence Envelope format
- ✅ No circular relationships (DAG-like structure)

---

### Task 1.2: Set Up Local Neo4j Instance

**Goal:** Get Neo4j running in development environment

**Options:**

**Option A: Docker (Recommended for dev/testing)**
```yaml
# docker-compose.yml addition
services:
  neo4j:
    image: neo4j:5.13
    environment:
      NEO4J_AUTH: neo4j/certus-test-password
      NEO4J_PLUGINS: '["apoc", "graph-data-science"]'
    ports:
      - "7687:7687"  # Bolt protocol
      - "7474:7474"  # Web UI
    volumes:
      - neo4j_data:/data
      - neo4j_logs:/logs
    healthcheck:
      test: ["CMD", "neo4j", "status"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  neo4j_data:
  neo4j_logs:
```

**Option B: LocalStack / Testcontainers (For CI/testing)**
```python
from testcontainers.neo4j import Neo4jContainer

# Use in tests
with Neo4jContainer() as container:
    driver = GraphDatabase.driver(container.get_connection_url())
    # Run tests...
```

**Deliverables:**
- ✅ docker-compose updated
- ✅ Neo4j instance starts cleanly
- ✅ Web UI accessible at http://localhost:7474
- ✅ Connection verified (test query returns success)
- ✅ Documentation: "How to start Neo4j for spike"

**Acceptance Criteria:**
- ✅ `docker-compose up` brings up Neo4j + app services
- ✅ Neo4j health check passes
- ✅ Schema can be loaded (Task 1.1 DDL executes)
- ✅ Simple query runs in < 100ms

---

### Task 1.3: Load Schema into Neo4j

**Goal:** Execute schema DDL to create nodes, relationships, constraints, indexes

**Implementation:**
```python
# certus_ask/services/neo4j_setup.py
from neo4j import GraphDatabase
from pathlib import Path

class Neo4jSchema:
    def __init__(self, uri: str, auth: tuple):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def load_schema(self):
        """Load schema from DDL file"""
        schema_file = Path(__file__).parent / "schema.cypher"
        with open(schema_file) as f:
            statements = f.read().split(";")

        with self.driver.session() as session:
            for statement in statements:
                if statement.strip():
                    try:
                        session.run(statement)
                        logger.info(f"Schema statement executed: {statement[:50]}...")
                    except Exception as e:
                        logger.error(f"Failed to execute: {statement[:50]}...", exc_info=e)
                        raise

    def verify_schema(self):
        """Verify schema created successfully"""
        with self.driver.session() as session:
            result = session.run("CALL db.schema.nodeTypeProperties()")
            nodes = [record for record in result]

            expected_nodes = {"Finding", "CWE", "Control", "Threat", "Service", "CVE"}
            actual_nodes = {record[0] for record in nodes}

            assert expected_nodes.issubset(actual_nodes), \
                f"Missing node types. Expected {expected_nodes}, got {actual_nodes}"
            logger.info(f"✅ Schema verified: {len(actual_nodes)} node types")
```

**Deliverables:**
- ✅ `schema.cypher` file with all DDL statements
- ✅ `Neo4jSchema` loader class
- ✅ Verification script (checks all nodes + relationships exist)
- ✅ Test: `test_neo4j_schema_loads()`

**Acceptance Criteria:**
- ✅ All 6 node types created
- ✅ All 8 relationship types created
- ✅ All constraints + indexes applied
- ✅ Verification script passes
- ✅ Graph is empty but ready for data

---

### Task 1.4: Design Data Loader (Evidence → Graph)

**Goal:** Plan how to convert WALK.1 Evidence Envelopes → Neo4j nodes/edges

**Approach:**

```python
# certus_ask/services/evidence_to_neo4j.py
from certus_ask.models import EvidenceEnvelope, SarifNormalized, ControlFramework
from neo4j import GraphDatabase

class EvidenceGraphLoader:
    """Convert Evidence Envelopes to Neo4j nodes + relationships"""

    def __init__(self, driver):
        self.driver = driver

    def load_evidence_envelopes(self, envelopes: List[EvidenceEnvelope]):
        """
        Ingest evidence envelopes:
        1. SARIF findings → Finding nodes + CWE links
        2. Control framework → Control nodes
        3. Threat models → Threat nodes + relationships
        4. Services → Service nodes
        """
        with self.driver.session() as session:
            for envelope in envelopes:
                if envelope.source_type == "sarif":
                    self._load_sarif_evidence(session, envelope)
                elif envelope.source_type == "control":
                    self._load_control_framework(session, envelope)
                elif envelope.source_type == "threat_model":
                    self._load_threat_model(session, envelope)
                # ... other source types

    def _load_sarif_evidence(self, session, envelope: EvidenceEnvelope):
        """
        Convert SARIF finding to Finding node:
        - Create Finding node (CWE, severity, title)
        - Create CWE node (if not exists)
        - Create FINDING_HAS_CWE relationship
        - Create CVE node (if EPSS enrichment present)
        - Create FINDING_LINKS_CVE relationship (if matched)
        """
        sarif_data = envelope.structured_data

        finding_query = """
        MERGE (f:Finding {finding_id: $finding_id})
        SET f.cwe_id = $cwe_id,
            f.severity = $severity,
            f.cvss_score = $cvss_score,
            f.epss_score = $epss_score,
            f.title = $title,
            f.first_seen = $first_seen,
            f.status = 'open'

        WITH f
        MATCH (c:CWE {cwe_id: $cwe_id})
        CREATE (f)-[r:FINDING_HAS_CWE {confidence: 1.0}]->(c)
        """

        session.run(finding_query, {
            "finding_id": sarif_data["ruleId"],
            "cwe_id": sarif_data["cwe_id"],
            "severity": sarif_data["severity"],
            "cvss_score": sarif_data.get("cvss_score", 0),
            "epss_score": sarif_data.get("epss_score", 0),
            "title": sarif_data["title"],
            "first_seen": envelope.timestamp,
        })

    def _load_control_framework(self, session, envelope: EvidenceEnvelope):
        """
        Convert control framework to Control nodes:
        - Create Control nodes (framework, ID, title)
        - Create CWE_VIOLATES_CONTROL relationships
        - Set implementation status
        """
        controls = envelope.structured_data.get("controls", [])

        for control in controls:
            control_query = """
            MERGE (c:Control {control_id: $control_id})
            SET c.framework = $framework,
                c.title = $title,
                c.description = $description,
                c.status = $status
            """

            session.run(control_query, {
                "control_id": control["id"],
                "framework": control["framework"],
                "title": control["title"],
                "description": control["description"],
                "status": control.get("status", "missing"),
            })

    def _load_threat_model(self, session, envelope: EvidenceEnvelope):
        """
        Convert threat model to Threat nodes + relationships:
        - Create Threat nodes (STRIDE category, title)
        - Create CONTROL_MITIGATES_THREAT relationships
        - Create THREAT_AFFECTS_SERVICE relationships
        """
        threats = envelope.structured_data.get("threats", [])

        for threat in threats:
            threat_query = """
            MERGE (t:Threat {threat_id: $threat_id})
            SET t.stride_category = $stride,
                t.title = $title,
                t.likelihood = $likelihood,
                t.impact = $impact

            WITH t
            UNWIND $mitigating_controls AS control_id
            MATCH (c:Control {control_id: control_id})
            MERGE (c)-[r:CONTROL_MITIGATES_THREAT {coverage: 'partial'}]->(t)
            """

            session.run(threat_query, {
                "threat_id": threat["id"],
                "stride": threat["stride_category"],
                "title": threat["title"],
                "likelihood": threat.get("likelihood", "medium"),
                "impact": threat.get("impact", "medium"),
                "mitigating_controls": threat.get("mitigating_controls", []),
            })
```

**Deliverables:**
- ✅ `EvidenceGraphLoader` class design
- ✅ Methods for each source type (SARIF, control, threat, service)
- ✅ Cypher query templates
- ✅ Error handling + logging
- ✅ Documentation: data mapping (Evidence → Graph)

**Acceptance Criteria:**
- ✅ Loader handles all 4 evidence types
- ✅ Queries are idempotent (MERGE not CREATE)
- ✅ Relationships created correctly
- ✅ Performance plan: < 500ms per evidence envelope

---

## Week 2: Data Loading & Query Validation

### Task 2.1: Create Test Data Set

**Goal:** Generate sample evidence envelopes for Neo4j testing

**Sample Data Scenarios:**

**Scenario A: Simple Finding → Control Mitigation**
```
Finding: CWE-79 (XSS in login form)
├─ FINDING_HAS_CWE → CWE-79
├─ CWE_VIOLATES_CONTROL → NIST AC-3 (Access Controls)
├─ CONTROL_MITIGATES_THREAT → Threat: "Tampering" (STRIDE)
└─ THREAT_AFFECTS_SERVICE → Service: "auth-service"
```

**Scenario B: Blast Radius (Multi-hop)**
```
Finding: CVE-2024-12345 (Log4Shell in logging library)
├─ FINDING_LINKS_CVE → CVE-2024-12345
├─ CVE_HAS_CWE → CWE-94 (Code Injection)
├─ [Target] Service A
│  ├─ SERVICE_DEPENDS_ON_SERVICE → Service B
│  ├─ SERVICE_DEPENDS_ON_SERVICE → Service C
│  └─ [All affected by finding via dependency]
```

**Scenario C: Control Coverage (Multi-finding)**
```
Control: NIST AC-3
├─ [Evidence Count: 5 findings support this control]
├─ FINDING_1 → CWE-1: "Missing authentication"
├─ FINDING_2 → CWE-2: "Weak password policy"
├─ FINDING_3 → CWE-3: "Unencrypted credentials"
├─ FINDING_4 → CWE-4: "Exposed API keys"
└─ Status: "Partial" (4/5 findings addressed)
```

**Implementation:**
```python
# tests/fixtures/neo4j_test_data.py
import pytest
from certus_ask.models import EvidenceEnvelope

@pytest.fixture
def test_finding_cwe79():
    """CWE-79 (XSS) finding"""
    return EvidenceEnvelope(
        evidence_id="finding-001",
        source_type="sarif",
        timestamp=datetime.now(),
        structured_data={
            "ruleId": "cwe-79-xss",
            "cwe_id": "CWE-79",
            "severity": "high",
            "cvss_score": 7.5,
            "epss_score": 0.42,
            "title": "Cross-Site Scripting (XSS) in login form",
            "description": "User input not sanitized in login endpoint",
        }
    )

@pytest.fixture
def test_finding_log4shell():
    """CVE-2024-12345 (Log4Shell variant) finding"""
    return EvidenceEnvelope(
        evidence_id="finding-002",
        source_type="sarif",
        structured_data={
            "ruleId": "log4j-rce",
            "cwe_id": "CWE-94",
            "severity": "critical",
            "cvss_score": 10.0,
            "epss_score": 0.97,
            "cve_id": "CVE-2024-12345",
            "title": "Log4j Remote Code Execution",
        }
    )

@pytest.fixture
def test_control_nist_ac3():
    """NIST AC-3 (Access Controls) control"""
    return EvidenceEnvelope(
        evidence_id="control-001",
        source_type="control",
        structured_data={
            "controls": [{
                "id": "AC-3",
                "framework": "nist-800-53",
                "title": "Access Enforcement",
                "description": "System enforces approved access control...",
                "status": "partial",
            }]
        }
    )

@pytest.fixture
def test_threat_stride_tampering():
    """STRIDE Threat: Tampering"""
    return EvidenceEnvelope(
        evidence_id="threat-001",
        source_type="threat_model",
        structured_data={
            "threats": [{
                "id": "threat-tampering-001",
                "stride_category": "T",
                "title": "Attacker modifies user input in transit",
                "likelihood": "medium",
                "impact": "high",
                "mitigating_controls": ["AC-3", "SC-7"],  # AC-3, SC-7
            }]
        }
    )

@pytest.fixture
def test_service_auth():
    """Service: auth-service"""
    return {
        "service_id": "auth-service",
        "name": "Authentication Service",
        "criticality": "critical",
        "status": "active",
    }
```

**Deliverables:**
- ✅ 3+ test scenarios (simple, blast radius, coverage)
- ✅ pytest fixtures for test data
- ✅ JSON test data files (for reusability)
- ✅ Documentation: what each scenario tests

**Acceptance Criteria:**
- ✅ Test data covers 4 node types + all relationship types
- ✅ Scenarios are realistic (based on actual SARIF/control data)
- ✅ Data can be loaded without errors

---

### Task 2.2: Implement & Test Data Loader

**Goal:** Load test data into Neo4j and verify relationships

**Implementation:**
```python
# tests/test_evidence_to_neo4j.py
import pytest
from certus_ask.services.evidence_to_neo4j import EvidenceGraphLoader

@pytest.fixture
def neo4j_session(neo4j_driver):
    """Create fresh Neo4j session for each test"""
    yield neo4j_driver.session()

class TestEvidenceGraphLoader:

    def test_load_sarif_finding_creates_nodes(self, neo4j_session, test_finding_cwe79):
        """Test: SARIF finding → Finding + CWE nodes"""
        loader = EvidenceGraphLoader(neo4j_session)

        # Load finding
        loader.load_evidence_envelopes([test_finding_cwe79])

        # Verify Finding node created
        result = neo4j_session.run(
            "MATCH (f:Finding {finding_id: $id}) RETURN f",
            id="cwe-79-xss"
        )
        finding = result.single()
        assert finding is not None
        assert finding["f"]["severity"] == "high"
        assert finding["f"]["cvss_score"] == 7.5

    def test_load_creates_relationships(self, neo4j_session, test_finding_cwe79):
        """Test: Finding -[FINDING_HAS_CWE]-> CWE"""
        loader = EvidenceGraphLoader(neo4j_session)

        # Pre-load CWE node
        neo4j_session.run(
            "CREATE (c:CWE {cwe_id: 'CWE-79', title: 'Cross-Site Scripting'})"
        )

        # Load finding
        loader.load_evidence_envelopes([test_finding_cwe79])

        # Verify relationship created
        result = neo4j_session.run(
            """MATCH (f:Finding)-[r:FINDING_HAS_CWE]->(c:CWE {cwe_id: 'CWE-79'})
               RETURN r, c"""
        )
        rel = result.single()
        assert rel is not None
        assert rel["r"]["confidence"] == 1.0

    def test_load_is_idempotent(self, neo4j_session, test_finding_cwe79):
        """Test: Loading same finding twice doesn't create duplicates"""
        loader = EvidenceGraphLoader(neo4j_session)

        # Setup CWE
        neo4j_session.run(
            "CREATE (c:CWE {cwe_id: 'CWE-79', title: 'XSS'})"
        )

        # Load twice
        loader.load_evidence_envelopes([test_finding_cwe79])
        loader.load_evidence_envelopes([test_finding_cwe79])

        # Verify only 1 Finding node exists
        result = neo4j_session.run(
            "MATCH (f:Finding {finding_id: 'cwe-79-xss'}) RETURN count(f) as count"
        )
        count = result.single()["count"]
        assert count == 1

    def test_load_all_scenarios(self, neo4j_session,
                               test_finding_cwe79,
                               test_control_nist_ac3,
                               test_threat_stride_tampering):
        """Test: Load all scenarios together"""
        loader = EvidenceGraphLoader(neo4j_session)

        # Pre-load CWE, Control, Threat
        neo4j_session.run("CREATE (c:CWE {cwe_id: 'CWE-79', title: 'XSS'})")
        neo4j_session.run(
            "CREATE (c:Control {control_id: 'AC-3', framework: 'nist-800-53'})"
        )
        neo4j_session.run(
            "CREATE (t:Threat {threat_id: 'threat-tampering-001', stride_category: 'T'})"
        )

        # Load all envelopes
        loader.load_evidence_envelopes([
            test_finding_cwe79,
            test_control_nist_ac3,
            test_threat_stride_tampering
        ])

        # Verify all nodes exist
        result = neo4j_session.run(
            "MATCH (n) RETURN labels(n) as label, count(n) as count"
        )
        nodes_by_type = {record["label"][0]: record["count"] for record in result}
        assert nodes_by_type["Finding"] >= 1
        assert nodes_by_type["Control"] >= 1
        assert nodes_by_type["Threat"] >= 1
```

**Deliverables:**
- ✅ Data loader fully implemented
- ✅ Unit tests for all load operations (4+ tests)
- ✅ Integration test (all scenarios together)
- ✅ Performance baseline: time to load 100 findings
- ✅ Error handling: duplicate detection, missing nodes

**Acceptance Criteria:**
- ✅ All unit tests pass
- ✅ Data loads without errors
- ✅ Relationships created correctly
- ✅ Idempotency verified (no duplicates on re-load)
- ✅ Load time < 1 second per 100 findings

---

### Task 2.3: Define & Test Query Patterns

**Goal:** Validate Cypher queries answer key reasoning questions

**Query Pattern 1: Threat Mitigations (Simple)**

```cypher
# Question: "What controls mitigate CWE-79 findings?"

MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe:CWE {cwe_id: "CWE-79"})
MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
RETURN
  f.finding_id,
  cwe.cwe_id,
  control.control_id,
  control.title
ORDER BY control.control_id
```

**Expected Result:**
```
| finding_id    | cwe_id  | control_id | title              |
|---------------|---------|------------|--------------------|
| cwe-79-xss    | CWE-79  | AC-3       | Access Enforcement |
| cwe-79-xss    | CWE-79  | AC-7       | Unsuccessful Login |
```

**Query Pattern 2: Blast Radius (Multi-hop)**

```cypher
# Question: "Which services are affected by CVE-2024-12345?"

MATCH (cve:CVE {cve_id: "CVE-2024-12345"})
MATCH (f:Finding)-[:FINDING_LINKS_CVE]->(cve)
MATCH (f)-[:FINDING_AFFECTS_SERVICE]->(s:Service)
MATCH (s)-[:SERVICE_DEPENDS_ON_SERVICE*0..2]->(downstream:Service)
RETURN
  DISTINCT downstream.service_id,
  downstream.name,
  downstream.criticality,
  s.service_id as direct_affected
ORDER BY downstream.criticality DESC
```

**Expected Result:**
```
| service_id       | name                | criticality | direct_affected |
|------------------|---------------------|-------------|-----------------|
| logging-service  | Logging Service     | critical   | auth-service    |
| api-gateway      | API Gateway         | critical   | logging-service |
| payment-service  | Payment Service     | high       | api-gateway     |
```

**Query Pattern 3: Control Evidence Count (Aggregation)**

```cypher
# Question: "How many findings support NIST AC-3 implementation?"

MATCH (control:Control {control_id: "AC-3"})
MATCH (cwe:CWE)-[:CWE_VIOLATES_CONTROL]->(control)
MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe)
WHERE f.status IN ['open', 'patched']
RETURN
  control.control_id,
  control.title,
  count(DISTINCT f) as finding_count,
  collect(DISTINCT cwe.cwe_id) as related_cwes,
  (count(CASE WHEN f.status = 'patched' THEN 1 END) * 100 / count(f)) as patched_pct
```

**Expected Result:**
```
| control_id | title              | finding_count | related_cwes                | patched_pct |
|------------|--------------------|-----------|---------------------------------|-------------|
| AC-3       | Access Enforcement | 5         | ["CWE-79", "CWE-94", ...]  | 60          |
```

**Query Pattern 4: Attack Path (Conditional)**

```cypher
# Question: "Show me the attack path: external input → vulnerable function → database"

MATCH (threat:Threat {stride_category: "I"})
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
  control.status
```

**Expected Result:**
```
Shows all information disclosure threats with missing/partial controls
```

**Implementation & Tests:**

```python
# tests/test_neo4j_queries.py
import pytest
from certus_ask.services.neo4j_queries import Neo4jQueries

class TestNeo4jQueries:

    def test_query_threat_mitigations(self, neo4j_session, test_data_loaded):
        """Test: Get controls that mitigate CWE-79"""
        queries = Neo4jQueries(neo4j_session)

        results = queries.get_mitigating_controls("CWE-79")

        assert len(results) >= 1
        assert results[0]["control_id"] == "AC-3"
        assert results[0]["finding_count"] >= 1

    def test_query_blast_radius(self, neo4j_session, test_data_loaded):
        """Test: Get services affected by CVE"""
        queries = Neo4jQueries(neo4j_session)

        affected = queries.get_affected_services("CVE-2024-12345")

        assert len(affected) >= 1
        assert affected[0]["criticality"] == "critical"

    def test_query_control_evidence(self, neo4j_session, test_data_loaded):
        """Test: Count findings supporting control"""
        queries = Neo4jQueries(neo4j_session)

        evidence = queries.get_control_evidence("AC-3")

        assert evidence["finding_count"] >= 1
        assert evidence["patched_pct"] >= 0

    def test_query_attack_path(self, neo4j_session, test_data_loaded):
        """Test: Get attack paths (conditional reasoning)"""
        queries = Neo4jQueries(neo4j_session)

        paths = queries.get_attack_paths(stride_category="I")

        assert len(paths) >= 0  # May have 0 if data doesn't match
        if len(paths) > 0:
            assert "threat_id" in paths[0]
            assert "control_status" in paths[0]
```

**Deliverables:**
- ✅ 4+ Cypher query patterns documented
- ✅ Query implementation in `Neo4jQueries` class
- ✅ Unit tests for each query (4+ tests)
- ✅ Expected results documented
- ✅ Query performance baselines

**Acceptance Criteria:**
- ✅ All 4 query patterns implemented
- ✅ All tests pass
- ✅ Queries return correct results
- ✅ Query latency < 500ms per query (measured)

---

### Task 2.4: Measure Performance Baselines

**Goal:** Establish latency + throughput benchmarks

**Metrics to Measure:**

```python
# benchmarks/neo4j_performance.py
import time
from statistics import mean, stdev

class Neo4jPerformanceTest:
    """Measure Neo4j query performance"""

    def benchmark_simple_queries(self, session, iterations=100):
        """Benchmark simple queries (threat mitigations)"""
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = session.run("""
                MATCH (c:Control) RETURN count(c)
            """).single()
            end = time.perf_counter()

            latencies.append((end - start) * 1000)  # ms

        return {
            "p50": sorted(latencies)[len(latencies) // 2],
            "p95": sorted(latencies)[int(len(latencies) * 0.95)],
            "p99": sorted(latencies)[int(len(latencies) * 0.99)],
            "mean": mean(latencies),
            "stdev": stdev(latencies),
        }

    def benchmark_complex_queries(self, session, iterations=50):
        """Benchmark complex queries (blast radius, attack paths)"""
        latencies = []

        for _ in range(iterations):
            start = time.perf_counter()
            result = session.run("""
                MATCH (cve:CVE)-[]->(f:Finding)
                MATCH (f)-[]->(s:Service)
                MATCH (s)-[:SERVICE_DEPENDS_ON_SERVICE*0..2]->(downstream:Service)
                RETURN count(DISTINCT downstream)
            """).single()
            end = time.perf_counter()

            latencies.append((end - start) * 1000)  # ms

        return {
            "p50": sorted(latencies)[len(latencies) // 2],
            "p95": sorted(latencies)[int(len(latencies) * 0.95)],
            "p99": sorted(latencies)[int(len(latencies) * 0.99)],
            "mean": mean(latencies),
            "stdev": stdev(latencies),
        }

    def benchmark_data_load(self, session, num_envelopes=1000):
        """Benchmark data loading (findings/sec)"""
        loader = EvidenceGraphLoader(session)
        envelopes = [generate_random_finding() for _ in range(num_envelopes)]

        start = time.perf_counter()
        loader.load_evidence_envelopes(envelopes)
        end = time.perf_counter()

        elapsed_sec = end - start
        findings_per_sec = num_envelopes / elapsed_sec

        return {
            "total_time_sec": elapsed_sec,
            "findings_per_sec": findings_per_sec,
            "avg_per_finding_ms": (elapsed_sec / num_envelopes) * 1000,
        }

# Run benchmarks
@pytest.mark.performance
def test_performance_baselines(neo4j_session):
    bench = Neo4jPerformanceTest()

    simple = bench.benchmark_simple_queries(neo4j_session)
    complex_q = bench.benchmark_complex_queries(neo4j_session)
    load = bench.benchmark_data_load(neo4j_session)

    print(f"\n{'=' * 60}")
    print(f"Simple Queries (control count)")
    print(f"{'=' * 60}")
    print(f"p50: {simple['p50']:.2f}ms")
    print(f"p95: {simple['p95']:.2f}ms")
    print(f"p99: {simple['p99']:.2f}ms")

    print(f"\n{'=' * 60}")
    print(f"Complex Queries (blast radius)")
    print(f"{'=' * 60}")
    print(f"p50: {complex_q['p50']:.2f}ms")
    print(f"p95: {complex_q['p95']:.2f}ms")
    print(f"p99: {complex_q['p99']:.2f}ms")

    print(f"\n{'=' * 60}")
    print(f"Data Loading")
    print(f"{'=' * 60}")
    print(f"Total time: {load['total_time_sec']:.2f}s")
    print(f"Findings/sec: {load['findings_per_sec']:.0f}")

    # Assertions (success criteria)
    assert simple['p95'] < 100, "Simple queries must be < 100ms (p95)"
    assert complex_q['p95'] < 500, "Complex queries must be < 500ms (p95)"
    assert load['findings_per_sec'] > 100, "Must load > 100 findings/sec"
```

**Deliverables:**
- ✅ Performance test suite (3 benchmarks)
- ✅ Latency measurements (p50, p95, p99)
- ✅ Throughput measurement (findings/sec)
- ✅ Baseline report document
- ✅ Success thresholds defined

**Acceptance Criteria:**
- ✅ Simple query p95 < 100ms
- ✅ Complex query p95 < 500ms
- ✅ Data load > 100 findings/sec
- ✅ Measurements documented + committed

---

## Week 3: Evaluation & Decision

### Task 3.1: Evaluate Against Validation Questions

**Goal:** Answer 4 key questions from spike objectives

**Question 1: Query Performance Acceptable?**

Success Criteria: Complex queries (blast radius, attack paths) execute in < 500ms p95

**Evaluation:**
- ✅ If p95 < 500ms → PASS (proceed to next question)
- ❌ If p95 > 500ms → FAIL (investigate: need optimization, indexing, or redesign)

**Possible Remediation:**
- Add composite indexes (e.g., on `(finding_id, cwe_id)`)
- Reduce graph depth (limit multi-hop traversals)
- Cache popular query results
- Consider query optimization (profile with EXPLAIN)

---

**Question 2: Evidence Envelope Schema Fits Neo4j?**

Success Criteria: Evidence envelopes map cleanly to nodes/edges without data loss

**Evaluation:**
- ✅ If all envelope fields map to node properties → PASS
- ❌ If fields are lost or require workarounds → FAIL

**Acceptance:**
- SARIF findings → Finding nodes (100% lossless)
- Control frameworks → Control nodes (100% lossless)
- Threat models → Threat nodes + relationships (100% lossless)
- Service metadata → Service nodes (100% lossless)

---

**Question 3: Graph Reasoning Adds Value?**

Success Criteria: Graph queries produce better/faster answers than OpenSearch alone

**Evaluation:**

| **Capability** | **OpenSearch Only** | **Neo4j Enhanced** | **Winner** |
|---|---|---|---|
| Find mitigating controls for finding | Keyword search + inference | Direct graph traversal | Neo4j (faster, deterministic) |
| Blast radius analysis | Manual service dependency lookup | Multi-hop traversal | Neo4j (faster, accurate) |
| Attack path discovery | Keyword search + manual reasoning | Conditional traversal | Neo4j (possible, not in OS) |
| Control coverage assessment | Aggregate queries + counting | Graph aggregations | Tie (both work) |

**Recommendation:** Proceed if ≥3 of 4 queries are faster in Neo4j

---

**Question 4: Operational Overhead Acceptable?**

Success Criteria: Keeping graph in sync requires < 20% additional effort

**Evaluation:**

| **Task** | **Effort** | **Complexity** | **Notes** |
|---|---|---|---|
| Load evidence → Neo4j | 1–2 seconds | Low | Idempotent, parallelizable |
| Sync on data updates | + 200ms per update | Medium | Need CDC or event-driven |
| Index maintenance | ~1 hour/month | Low | Automated (Neo4j handles) |
| Schema versioning | 1–2 hours per version | High | Need migration scripts |

**Acceptance:**
- If < 20% overhead → PASS (integrate Neo4j into WALK pipeline)
- If > 20% overhead → DEFER (consider async loading or RUN phase integration)

---

### Task 3.2: Compile Spike Results Report

**Goal:** Document findings + recommendation for stakeholders

**Report Template:**

```markdown
# Neo4j Validation Spike — Results Report

## Executive Summary
- **Duration:** 3 weeks (Week 1–3 of WALK phase)
- **Team:** 1 backend engineer
- **Status:** [PASS / CONDITIONAL / FAIL]
- **Recommendation:** [Accelerate to early RUN / Keep in RUN.3 / Defer further]

---

## Findings by Question

### 1. Query Performance ✅ / ⚠️ / ❌
**Verdict:** [PASS / CONDITIONAL / FAIL]

**Data:**
- Simple queries (control count): p95 = 45ms ✅
- Complex queries (blast radius): p95 = 380ms ✅
- Attack path queries: p95 = 620ms ⚠️ (over 500ms)

**Analysis:**
- Most queries well under 500ms threshold
- Attack path queries occasionally exceed; likely due to graph depth
- Optimization: add index on (finding_id, service_id) for faster path traversal

**Recommendation:** PASS with optimization note

---

### 2. Schema Fit ✅ / ❌
**Verdict:** PASS

**Data:**
- 100% of SARIF findings mapped to nodes
- 100% of control frameworks mapped
- 100% of threat models mapped
- 0% data loss observed

**Detailed Mapping:**
```
EvidenceEnvelope {
  evidence_id → Finding.finding_id
  structured_data.cwe_id → Finding.cwe_id + FINDING_HAS_CWE rel
  structured_data.severity → Finding.severity
  ...
}
```

**Recommendation:** PASS — No schema gaps identified

---

### 3. Graph Value Add ✅ / ⚠️ / ❌
**Verdict:** PASS (with caveats)

**Capability Comparison:**

| Capability | OpenSearch | Neo4j | Verdict |
|---|---|---|---|
| Find mitigations | 250ms (keyword search) | 45ms (direct traversal) | Neo4j ✅ |
| Blast radius | ~2000ms (manual + inference) | 380ms (multi-hop) | Neo4j ✅ |
| Attack paths | Not possible (no traversal) | 620ms (conditional) | Neo4j ✅ |
| Coverage count | 500ms (aggregation) | 450ms (aggregation) | Tie ≈ |

**Analysis:**
- 3 of 4 queries faster in Neo4j
- Attack paths are unique value (not possible in OpenSearch)
- Recommendation: Valuable enough to accelerate

---

### 4. Operational Overhead ✅ / ⚠️ / ❌
**Verdict:** PASS (with planning)

**Effort Breakdown:**
- Evidence → Neo4j load: 1–2 seconds per 100 findings (~1% overhead)
- Index maintenance: automated (Neo4j built-in)
- Schema versioning: need 1–2 hours per major version
- Sync on updates: requires CDC or event-driven design (~4 hours to implement)

**Overhead Estimate:**
- Initial setup: 40 hours (already done in spike)
- Ongoing maintenance: 2–4 hours/month
- Per-release: 1–2 hours (schema updates)
- **Total: ~15–20% of backend effort** ⚠️

**Mitigation:**
- Defer CDC/event-driven to RUN phase; batch load initially
- Overhead drops to ~5% once automated

---

## Spike Deliverables Summary

| Category | Status | Details |
|---|---|---|
| **Schema** | ✅ Done | 6 node types, 8 relationships, indexed |
| **Data Loader** | ✅ Done | 4 source types (SARIF, control, threat, service) |
| **Query Patterns** | ✅ Done | 4 validated queries (simple, complex, aggregation, conditional) |
| **Performance** | ✅ Done | Baselines: p50/p95/p99 measured |
| **Tests** | ✅ Done | 15+ unit + integration tests |
| **Documentation** | ✅ Done | Schema diagrams, query examples, setup guide |

---

## Key Insights

### What Went Well ✅
1. **Rapid validation** — Proved concept in 3 weeks, low risk
2. **Schema fit** — Evidence envelopes map cleanly to graph model
3. **Query performance** — Mostly under 500ms; good for interactive queries
4. **Idempotent loading** — MERGE-based approach prevents duplicates

### What Needs Attention ⚠️
1. **Attack path latency** — 620ms occasionally exceeds threshold; needs indexing
2. **Sync complexity** — Event-driven updates require design work
3. **Schema evolution** — Need migration scripts for future changes
4. **Memory usage** — Neo4j with 10k+ nodes/edges might need tuning

---

## Recommendation: [ACCELERATE / CONDITIONAL / DEFER]

### Option 1: Accelerate Neo4j to Early RUN (Recommended) ✅
**If:** All 4 validation questions PASS
**Then:** Move Neo4j work to start of RUN phase (Week 1–4)
**Benefit:** Graph-based reasoning available 4 weeks earlier
**Risk:** Low (schema proven, queries validated)

**Next Steps:**
1. Implement in parallel with WALK.2–3 (threat modeling + compliance)
2. Keep Learning from WALK data; refine schema as needed
3. Plan Event-Driven sync for RUN phase (defer CDC implementation)

---

### Option 2: Keep in RUN.3 (If Conditional) ⚠️
**If:** 3 of 4 validation questions pass, but performance needs optimization
**Then:** Keep in RUN phase, plan optimization sprint first
**Benefit:** More time to optimize; less schedule pressure
**Risk:** Delayed value; fewer iterations before GA

**Next Steps:**
1. Add composite indexes to address latency
2. Profile queries with EXPLAIN plans
3. Consider caching for frequently-asked queries

---

### Option 3: Defer Further (If FAIL) ❌
**If:** 2 or fewer validation questions pass
**Then:** Defer Neo4j; consider alternative (e.g., pure OpenSearch)
**Benefit:** Focus on core WALK deliverables
**Risk:** Miss opportunity for graph-based reasoning

---

## Estimated Effort if Accelerated

| Task | Weeks | FTE | Notes |
|---|---|---|---|
| RUN.3a Neo4j Production | 3 | 1.0 | Deploy, multi-region replication |
| RUN.3b Cypher Query Optimization | 2 | 0.5 | Performance tuning, caching |
| RUN.3c Event-Driven Sync | 2 | 0.75 | CDC or polling-based loader |
| RUN.3d Testing + Documentation | 2 | 0.5 | Chaos tests, architecture guide |
| **Total** | **9 weeks** | **~2.75 FTE** | Overlaps with RUN.1–2 |

---

## Success Criteria for Production Deployment

Before moving Neo4j to production, ensure:
- [ ] All Cypher queries tested with 100k+ nodes
- [ ] Performance baselines confirmed at scale
- [ ] Replication tested (multi-region failover)
- [ ] Schema migration strategy documented
- [ ] Event-driven sync implemented + tested
- [ ] Disaster recovery plan + backup strategy

---

## Appendix: Detailed Test Results

[Attach detailed benchmark results, query outputs, test coverage report]

---

**Report Date:** [Date]
**Prepared By:** [Engineer name]
**Reviewed By:** [Lead/PM]
**Status:** Ready for Stakeholder Review
```

**Deliverables:**
- ✅ Comprehensive results report (4–6 pages)
- ✅ Clear PASS/FAIL/CONDITIONAL verdict for each question
- ✅ Recommendation with rationale
- ✅ Effort estimate if accelerated
- ✅ Next steps (decision path)

**Acceptance Criteria:**
- ✅ Report is clear + actionable
- ✅ Recommendation is defensible (data-driven)
- ✅ Stakeholders can make informed decision

---

### Task 3.3: Create Go/No-Go Decision Framework

**Goal:** Clear decision path for leadership

```
SPIKE RESULTS DECISION TREE

┌─ Question 1: Query Performance < 500ms p95? ─┐
│                                               │
├─ YES ─┐                          NO ──┐
│       │                               │
│   Continue ──┐                    [CONDITIONAL]
│             │                    ├─ Optimize queries
│             │                    ├─ Add indexes
│    ┌────────┴─────────────┐      └─ Retest
│    │                      │
│    Q2: Schema fit OK?     │      FAIL
│    │                      │       │
│    ├─ YES ──┐             │       │
│    │        │      NO ─┐  │       │
│    │    Continue  [NO]─┼──┴──────┬┴─────────┐
│    │       │            │        │          │
│    │    ┌──┴────────┐   │        │          │
│    │    │           │   │        │          │
│    │   Q3: Value Add?   │        │          │
│    │    │           │   │        │          │
│    │    ├─ YES ──┐  │   │        │          │
│    │    │        │  NO ─┼───────┤          │
│    │    │    Continue [CONDITIONAL]        │
│    │    │       │  │    │   |              │
│    │    │    ┌──┘  │    │   |              │
│    │    │    │     │    │   |              │
│    │   Q4: Overhead < 20%?  |              │
│    │    │    │     │    │   |              │
│    │    ├─ YES ──┐ │    │   |              │
│    │    │        │ NO ──┤   |              │
│    │    │    [ACCELERATE]   |              │
│    │    │       │ [DEFER]   |              │
│    │    │       │    │      |              │
│    └────┴──┬────┴──┬─┴──────┴──────────────┘
│           │        │
│        PASS    DEFER/CONDITIONAL/FAIL
│           │        │
└───────────┴────────┴─ DECISION & NEXT STEPS
```

**Decision Outcomes:**

| **Scenario** | **Questions Passed** | **Verdict** | **Action** |
|---|---|---|---|
| All 4 PASS | 4/4 | **ACCELERATE** | Move Neo4j to Week 1 of RUN |
| 3 PASS (Q1–3) | 3/4 | **CONDITIONAL** | Optimize, then accelerate |
| 2–3 PASS (Q2–4) | 2/4 | **DEFER** | Keep in RUN.3, plan optimization |
| < 2 PASS | <2/4 | **FAIL** | Defer/reconsider approach |

---

### Task 3.4: Document Learnings & Optimization Plan

**Goal:** Capture insights for RUN phase implementation

```markdown
# Neo4j Spike Learnings & Optimization Plan

## Schema Optimizations for RUN Phase

### 1. Add Relationship Cardinality Hints
Current: Relationships without metadata
Future: Add cardinality, weight, confidence scores

```cypher
CREATE (f)-[r:FINDING_HAS_CWE {
  confidence: 0.95,
  source: "deepeval",
  verified: true
}]->(cwe)
```

### 2. Implement Graph Partitioning
Large graphs (100k+ nodes) benefit from partitioning:
- By date (recent findings vs. historical)
- By service (shard by service_id)
- By framework (NIST vs. ISO separate subgraphs)

### 3. Add Materialized Views
Pre-compute expensive queries:
- Control coverage per framework (daily)
- Blast radius per CVE (hourly)
- Attack surface per threat (daily)

---

## Performance Optimizations for RUN Phase

### 1. Cypher Query Profiling
Use `EXPLAIN` + `PROFILE` to identify bottlenecks:

```cypher
PROFILE
MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe)
WHERE f.severity = 'critical'
RETURN count(f)
```

### 2. Index Strategies
- Composite indexes: `(finding_id, cwe_id)` for common joins
- Text indexes: full-text search on descriptions
- Bitmap indexes: for enum fields (severity, status)

### 3. Query Caching
Cache results for 1–24 hours:
- Control coverage (changes daily)
- Threat mitigations (changes weekly)
- Service dependencies (changes rarely)

---

## Sync Strategy for RUN Phase

### Phase 1 (Week 1–2): Batch Loading
- Load evidence envelopes via scheduled job
- Simple: idempotent MERGE queries
- Cost: low (1–2 seconds per batch)

### Phase 2 (Week 3–4): Event-Driven (Optional)
- Subscribe to WALK.1 updates
- Stream new findings → Neo4j in real-time
- Add complexity but improves freshness

### Phase 3 (Post-RUN): Change Data Capture
- Use CDC tool (Debezium) for large-scale sync
- Automatic replication to secondary regions
- Complex but scalable

---

## Testing Strategy for RUN Phase

### 1. Scale Testing
- Test with 100k+ nodes
- Verify latency remains < 500ms
- Measure memory + CPU usage

### 2. Chaos Testing
- Kill Neo4j pod → verify failover
- Corrupt index → verify recovery
- High concurrency (100+ clients) → measure p99 latency

### 3. Schema Migration Testing
- Test upgrade path (v1 → v2 schema)
- Verify data consistency
- Measure downtime (target: 0 for breaking schema changes)

---

## Known Limitations & Future Work

### Limitation 1: Transitive Control Mapping
Current: Direct CWE → Control links only
Future: Infer controls via threat → control mapping

**Example:**
```
Finding(CWE-79) → Threat(Tampering) → Control(AC-3)
```

**Effort:** 2 weeks in RUN.3b

---

### Limitation 2: Evidence Lineage in Graph
Current: Graph shows reasoning, not evidence chain
Future: Add parent evidence_id → child evidence_id relationships

**Example:**
```
SarifFinding(orig) → [enriched by] → EnrichedFinding(EPSS added)
```

**Effort:** 1 week in RUN.3c

---

### Limitation 3: Multi-Tenant Isolation
Current: Single graph for all tenants (proof of concept)
Future: Separate graphs or row-level security

**Effort:** 3–4 weeks in FLY phase

---

## Recommendations for Team

1. **Start with Option A (Accelerate)** if all 4 questions pass
   - Low risk, high reward
   - Feedback loop from WALK helps refine schema
   - Team ramps up on Neo4j early

2. **Plan Option B (Optimize then Accelerate)** if 3 questions pass
   - Add indexing spike (1 week)
   - Retest performance
   - Proceed with acceleration

3. **Defer gracefully** if < 3 questions pass
   - Don't force Neo4j; focus on WALK
   - Revisit after WALK.1 is done
   - May discover graph value later

---

**Key Takeaway:** Neo4j is viable for threat reasoning. Whether to accelerate depends on performance thresholds + team capacity. Either way, learning from spike reduces risk in production deployment.
```

**Deliverables:**
- ✅ Optimization plan for RUN phase (schema, performance, sync)
- ✅ Known limitations documented
- ✅ Scale testing strategy
- ✅ Chaos testing plan
- ✅ Team recommendations

**Acceptance Criteria:**
- ✅ Learnings documented + actionable
- ✅ RUN phase has clear optimization roadmap
- ✅ No surprises for production deployment

---

## Go/No-Go Decision Framework

### Success Scenarios (Proceed)

**PASS (All 4 Questions Yes):**
- ✅ Performance < 500ms p95
- ✅ Schema maps cleanly
- ✅ Graph adds value
- ✅ Overhead < 20%

**Action:** **Accelerate to early RUN**
- Start RUN.3 in Week 1 of RUN phase
- 9 weeks effort (overlaps with RUN.1–2)
- Deploy to production by early Q4 2025
- Deliver graph-based reasoning 4 weeks early

---

### Conditional Scenarios (Optimize & Retry)

**CONDITIONAL (3 of 4 Yes, likely Q1 failed):**
- ⚠️ Performance slightly over (620ms vs. 500ms threshold)
- ✅ Schema fits
- ✅ Value clear
- ✅ Overhead acceptable

**Action:** **Optimize, then accelerate**
- Add indexes + cache layer (1 week)
- Retest performance
- If improved → proceed with acceleration
- If not → defer to RUN.3

---

### Failure Scenarios (Defer)

**DEFER (< 3 Questions Pass):**
- ❌ Performance unacceptable even with optimization
- ❌ Schema doesn't fit
- ❌ Operational overhead too high

**Action:** **Keep in RUN.3**
- Implement as planned (Weeks 9–12 of RUN)
- More time for design + optimization
- Less schedule pressure
- Consider alternative (pure OpenSearch) if needed

---

## Spike Timeline Summary

```
Week 1: Schema Design + Neo4j Setup (40 hours)
├─ Task 1.1: Schema DDL (12 hours)
├─ Task 1.2: Local Neo4j instance (8 hours)
├─ Task 1.3: Load schema (8 hours)
└─ Task 1.4: Data loader design (12 hours)

Week 2: Data Loading & Queries (40 hours)
├─ Task 2.1: Test data set (8 hours)
├─ Task 2.2: Implement + test loader (12 hours)
├─ Task 2.3: Query patterns (12 hours)
└─ Task 2.4: Performance baselines (8 hours)

Week 3: Evaluation & Decision (40 hours)
├─ Task 3.1: Validate 4 questions (12 hours)
├─ Task 3.2: Results report (16 hours)
├─ Task 3.3: Decision framework (8 hours)
└─ Task 3.4: Optimization plan (4 hours)

TOTAL: 120 hours (~0.5 FTE for 3 weeks)
```

---

## Risks & Mitigations

| **Risk** | **Likelihood** | **Impact** | **Mitigation** |
|---|---|---|---|
| Query performance doesn't meet threshold | Medium | High | Add indexing, cache popular queries, consider redesign |
| Schema gaps discovered late | Low | High | Validate with WALK.1 data early (Week 2) |
| Overhead higher than estimated | Medium | Medium | Start with batch loading (simpler); defer event-driven |
| Team unfamiliar with Cypher | Medium | Low | Pair with Neo4j expert; create query examples |
| Neo4j licensing/cost concerns | Low | High | Use Community Edition for POC; evaluate Aura for prod |

---

## Success Definition

**Spike Succeeds If:**
- ✅ 4 validation questions answered clearly
- ✅ Go/No-Go decision made with 80%+ confidence
- ✅ No surprises in RUN phase (schema holds up, perf acceptable)
- ✅ Team confidence in Neo4j approach increases

**Spike Fails If:**
- ❌ Cannot answer validation questions
- ❌ Major schema gaps discovered
- ❌ Performance unacceptable + no clear optimization path
- ❌ Team loses confidence in approach

---

**Report Status:** Ready for Stakeholder Sign-Off
**Next Step:** Present findings + recommendation to leadership; decide: Accelerate, Conditional, or Defer
