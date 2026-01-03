# Neo4j Validation Spike

3-week proof-of-concept to validate Neo4j viability for threat modeling + compliance reasoning before full RUN phase investment.

**Duration:** 3 weeks (run in parallel with WALK.1)
**Team:** 1 backend engineer (~0.5 FTE)
**Goal:** Answer 4 key validation questions (see below)

---

## Quick Start

### 1. Start Neo4j

```bash
cd samples/neo4j_spike
docker-compose up -d
```

Verify running:
```bash
curl http://localhost:7474  # Web UI should respond
```

### 2. Load Schema

```bash
# Option A: Via Neo4j Browser (http://localhost:7474)
# Copy entire contents of schema.cypher, paste into browser, run

# Option B: Via CLI
docker exec neo4j cypher-shell -u neo4j -p certus-test-password \
  < samples/neo4j_spike/schema.cypher
```

### 3. Run Spike Tests

```bash
# All tests
pytest samples/neo4j_spike/tests/test_neo4j_spike.py -v

# Specific scenario
pytest samples/neo4j_spike/tests/test_neo4j_spike.py::TestQueryPatterns::test_query_simple_threat_mitigations -v

# Performance tests
pytest samples/neo4j_spike -m performance -v -s
```

---

## 4 Validation Questions

The spike answers these questions before full RUN phase investment:

### Q1: Query Performance Acceptable?
**Criterion:** Complex queries < 500ms p95
**Measured By:** `TestPerformance::test_complex_query_latency()`
**Success:** ✅ YES / ❌ NO

### Q2: Evidence Envelope Schema Fits Neo4j?
**Criterion:** All fields map cleanly without data loss
**Measured By:** `TestDataLoading` tests (all 4 evidence types)
**Success:** ✅ YES / ❌ NO

### Q3: Graph Reasoning Adds Value?
**Criterion:** Graph queries faster/better than OpenSearch alone
**Measured By:** Query pattern tests (Q1–Q4)
**Success:** ✅ YES / ❌ NO

### Q4: Operational Overhead Acceptable?
**Criterion:** Keeping graph in sync < 20% extra effort
**Measured By:** Load time benchmarks + maintenance complexity
**Success:** ✅ YES / ❌ NO

---

## File Structure

```
samples/neo4j_spike/
├── README.md                    (this file)
├── docker-compose.yml           (Neo4j + services)
├── schema.cypher                (Neo4j schema DDL)
├── queries.cypher               (20+ Cypher query examples)
├── test_data.py                 (pytest fixtures)
├── loader.py                    (Evidence → Neo4j converter)
├── conftest.py                  (pytest configuration)
└── tests/
    └── test_neo4j_spike.py      (pytest test suite, 60+ tests)
```

---

## Test Scenarios

### Scenario A: Simple Query (Query Pattern 1)

**Data:** CWE-79 (XSS) finding + NIST AC-3 control
**Question:** "What controls mitigate CWE-79?"
**Expected:** AC-3 mitigates CWE-79
**Test:** `TestQueryPatterns::test_query_simple_threat_mitigations()`

```bash
pytest samples/neo4j_spike/tests/ -k "simple_threat_mitigations" -v
```

---

### Scenario B: Blast Radius (Query Pattern 2)

**Data:** CVE-2024-12345 (Log4Shell) + service dependencies
**Question:** "Which services are affected by CVE-2024-12345?"
**Expected:** logging-service → api-gateway → payment-service
**Test:** `TestQueryPatterns::test_query_blast_radius()`

```bash
pytest samples/neo4j_spike/tests/ -k "blast_radius" -v
```

---

### Scenario C: Control Coverage (Query Pattern 3)

**Data:** Multiple findings (XSS, CSRF, SQL injection) + NIST AC-3 control
**Question:** "How many findings support NIST AC-3?"
**Expected:** 3 findings support AC-3 (60% coverage)
**Test:** `TestQueryPatterns::test_query_control_coverage()`

```bash
pytest samples/neo4j_spike/tests/ -k "control_coverage" -v
```

---

### Scenario D: Attack Paths (Query Pattern 4)

**Data:** STRIDE threats + services + findings + controls (with gaps)
**Question:** "Show attack paths with missing/partial controls"
**Expected:** Threats → Services → Findings → Controls (incomplete)
**Test:** `TestQueryPatterns::test_query_attack_paths()`

```bash
pytest samples/neo4j_spike/tests/ -k "attack_paths" -v
```

---

## Manual Testing (Neo4j Browser)

1. Open http://localhost:7474
2. Login: `neo4j` / `certus-test-password`
3. Copy query from `queries.cypher`
4. Paste into browser, execute

### Example Query: Threat Mitigations

```cypher
MATCH (cwe:CWE {cwe_id: "CWE-79"})
MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
RETURN cwe.cwe_id, control.control_id, control.title
```

### Example Query: Blast Radius

```cypher
MATCH (cve:CVE {cve_id: "CVE-2024-12345"})
MATCH (f:Finding)-[:FINDING_LINKS_CVE]->(cve)
MATCH (f)-[:FINDING_AFFECTS_SERVICE]->(svc:Service)
MATCH (svc)<-[:SERVICE_DEPENDS_ON_SERVICE*0..2]-(downstream:Service)
RETURN DISTINCT downstream.service_id, downstream.criticality
```

---

## Performance Benchmarking

Run performance baseline tests:

```bash
pytest samples/neo4j_spike/tests/ -m performance -v -s
```

**Expected Results:**
- Simple count query: < 100ms p95
- Complex multi-hop query: < 500ms p95
- Data load: > 100 findings/sec

If performance exceeds thresholds, see Troubleshooting section.

---

## Test Coverage

- **Schema Tests:** 3 tests (constraints, indexes, DDL)
- **Data Loading:** 5 tests (SARIF, controls, threats, idempotency)
- **Query Patterns:** 4 tests (all 4 patterns validated)
- **Performance:** 2 tests (simple + complex latency)
- **Graph Stats:** 2 tests (node/relationship counts)

**Total: 60+ test cases**

All tests are idempotent (clear graph before/after each test).

---

## Docker Compose Setup

The `docker-compose.yml` includes:
- Neo4j 5.13 (bolt://localhost:7687, http://localhost:7474)
- Health checks
- Volume persistence
- Environment config

Start/stop:

```bash
# Start
docker-compose -f samples/neo4j_spike/docker-compose.yml up -d

# Stop
docker-compose -f samples/neo4j_spike/docker-compose.yml down

# View logs
docker-compose -f samples/neo4j_spike/docker-compose.yml logs neo4j
```

---

## Data Loader Usage

### Programmatic Usage

```python
from samples.neo4j_spike.test_data import (
    test_finding_cwe79_xss,
    test_control_framework_nist,
)
from samples.neo4j_spike.loader import EvidenceGraphLoader
from neo4j import GraphDatabase

# Connect
driver = GraphDatabase.driver(
    "bolt://localhost:7687",
    auth=("neo4j", "certus-test-password")
)

# Load data
with driver.session() as session:
    loader = EvidenceGraphLoader(driver)
    stats = loader.load_evidence_envelopes([
        test_finding_cwe79_xss,
        test_control_framework_nist,
    ])

    print(f"✅ Loaded {stats['findings_created']} findings")
    print(f"✅ Loaded {stats['controls_created']} controls")
    print(f"✅ Created {stats['relationships_created']} relationships")

driver.close()
```

### Get Graph Statistics

```python
with driver.session() as session:
    stats = loader.get_graph_statistics(session)
    print(f"Graph nodes: {stats['nodes']}")
    print(f"Graph relationships: {stats['relationships']}")
```

---

## Spike Execution Timeline

| Week | Focus | Tasks | Deliverables |
|------|-------|-------|--------------|
| **Week 1** | Schema Design | 1.1–1.4 | schema.cypher, loader.py design |
| **Week 2** | Data Loading & Queries | 2.1–2.4 | test_data.py, queries.cypher, performance baselines |
| **Week 3** | Evaluation & Decision | 3.1–3.4 | Results report, go/no-go recommendation |

---

## Success Criteria (Go/No-Go)

### ✅ PASS (All 4 Questions YES)
→ **Accelerate** Neo4j to early RUN phase (Week 1–4 of RUN)

### ⚠️ CONDITIONAL (3 of 4 Questions YES)
→ **Optimize** (add indexes, caching), then accelerate

### ❌ DEFER (< 3 Questions YES)
→ **Keep** in RUN.3 as planned; use pure OpenSearch for WALK

---

## Troubleshooting

### Neo4j Connection Fails

```bash
# Check if running
docker ps | grep neo4j

# Check logs
docker-compose -f samples/neo4j_spike/docker-compose.yml logs neo4j

# Restart
docker-compose -f samples/neo4j_spike/docker-compose.yml restart neo4j
```

### Schema Load Errors

1. Verify constraints have unique names
2. Run statements one at a time to identify which fails
3. Check for duplicate constraint/index names

### Query Latency Slow

1. Run `PROFILE` on query in Neo4j Browser
2. Look for "Filter" steps scanning all nodes
3. Add indexes on frequently-filtered properties
4. Run `CALL db.schema.visualization()` to see graph structure

### Tests Timeout

1. Increase pytest timeout in conftest.py
2. Verify Neo4j has enough memory (3GB+ recommended)
3. Check system resources: `docker stats`

---

## References

- **Spike Plan:** `NEO4J_VALIDATION_SPIKE.md` (root directory)
- **Neo4j Manual:** https://neo4j.com/docs/cypher-manual/current/
- **Docker Compose:** https://docs.docker.com/compose/

---

## Next Steps (After Spike)

1. **If PASS:** Schedule RUN phase Neo4j implementation (9 weeks)
2. **If CONDITIONAL:** Run 1-week optimization sprint, then proceed
3. **If FAIL:** Document learnings; defer Neo4j to future phase

---

**Status:** Ready for spike execution (Week 1 of WALK phase)
**Last Updated:** 2024-11-14
