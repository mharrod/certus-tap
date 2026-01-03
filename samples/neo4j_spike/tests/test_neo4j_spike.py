"""
Neo4j Spike Test Suite

Tests all spike scenarios:
- Schema loading
- Data ingestion (SARIF, controls, threats, services)
- Query patterns (simple, blast radius, coverage, attack paths)
- Performance baselines
"""

import time

import pytest


class TestNeo4jSchema:
    """Tests for Neo4j schema loading and validation"""

    @pytest.mark.neo4j
    def test_schema_constraints(self, neo4j_session):
        """Test: Constraints created correctly"""
        result = neo4j_session.run("SHOW CONSTRAINTS")

        constraints = list(result)
        constraint_names = [c["name"] for c in constraints]

        expected = [
            "finding_id_unique",
            "cwe_id_unique",
            "control_id_unique",
            "threat_id_unique",
            "service_id_unique",
            "cve_id_unique",
        ]

        for expected_constraint in expected:
            assert expected_constraint in constraint_names, f"Missing constraint: {expected_constraint}"

    @pytest.mark.neo4j
    def test_schema_indexes(self, neo4j_session):
        """Test: Indexes created correctly"""
        result = neo4j_session.run("SHOW INDEXES")

        indexes = list(result)
        index_names = [idx["name"] for idx in indexes]

        expected = [
            "cwe_id_index",
            "control_id_index",
            "service_id_index",
            "cve_id_index",
            "finding_severity_index",
            "finding_status_index",
            "control_framework_index",
            "threat_stride_index",
        ]

        for expected_index in expected:
            assert expected_index in index_names, f"Missing index: {expected_index}"


class TestDataLoading:
    """Tests for loading evidence envelopes into Neo4j"""

    @pytest.mark.neo4j
    def test_load_sarif_finding(self, neo4j_session, neo4j_loader, test_finding_cwe79_xss):
        """Test: SARIF finding → Finding node"""
        # Load finding
        stats = neo4j_loader.load_evidence_envelopes([test_finding_cwe79_xss])

        assert stats["findings_created"] >= 1

        # Verify node created
        result = neo4j_session.run("MATCH (f:Finding {finding_id: $id}) RETURN f", id="finding-cwe79-001")
        finding = result.single()
        assert finding is not None
        assert finding["f"]["severity"] == "high"
        assert finding["f"]["cvss_score"] == 7.5

    @pytest.mark.neo4j
    def test_load_creates_relationships(self, neo4j_session, neo4j_loader, test_finding_cwe79_xss):
        """Test: Finding -[FINDING_HAS_CWE]-> CWE relationship created"""
        # Pre-load CWE node
        neo4j_session.run("CREATE (c:CWE {cwe_id: $id, title: $title})", id="CWE-79", title="Cross-Site Scripting")

        # Load finding
        neo4j_loader.load_evidence_envelopes([test_finding_cwe79_xss])

        # Verify relationship created
        result = neo4j_session.run(
            """MATCH (f:Finding)-[r:FINDING_HAS_CWE]->(c:CWE {cwe_id: 'CWE-79'})
               RETURN r"""
        )
        rel = result.single()
        assert rel is not None
        assert rel["r"]["confidence"] == 1.0

    @pytest.mark.neo4j
    def test_load_is_idempotent(self, neo4j_session, neo4j_loader, test_finding_cwe79_xss):
        """Test: Loading same finding twice doesn't create duplicates"""
        # Pre-load CWE
        neo4j_session.run("CREATE (c:CWE {cwe_id: $id, title: $title})", id="CWE-79", title="Cross-Site Scripting")

        # Load twice
        neo4j_loader.load_evidence_envelopes([test_finding_cwe79_xss])
        neo4j_loader.load_evidence_envelopes([test_finding_cwe79_xss])

        # Verify only 1 Finding node exists
        result = neo4j_session.run("MATCH (f:Finding {finding_id: 'finding-cwe79-001'}) RETURN count(f) as count")
        count = result.single()["count"]
        assert count == 1

    @pytest.mark.neo4j
    def test_load_control_framework(self, neo4j_session, neo4j_loader, test_control_framework_nist):
        """Test: Control framework → Control nodes"""
        stats = neo4j_loader.load_evidence_envelopes([test_control_framework_nist])

        assert stats["controls_created"] >= 1

        # Verify node created
        result = neo4j_session.run("MATCH (c:Control {control_id: $id}) RETURN c", id="AC-3")
        control = result.single()
        assert control is not None
        assert control["c"]["framework"] == "nist-800-53"
        assert control["c"]["status"] == "partial"

    @pytest.mark.neo4j
    def test_load_threat_model(self, neo4j_session, neo4j_loader, test_threat_stride_tampering):
        """Test: Threat model → Threat nodes"""
        stats = neo4j_loader.load_evidence_envelopes([test_threat_stride_tampering])

        assert stats["threats_created"] >= 1

        # Verify node created
        result = neo4j_session.run("MATCH (t:Threat {threat_id: $id}) RETURN t", id="threat-tampering-001")
        threat = result.single()
        assert threat is not None
        assert threat["t"]["stride_category"] == "T"


class TestQueryPatterns:
    """Tests for Cypher query patterns"""

    @pytest.mark.neo4j
    def test_query_simple_threat_mitigations(self, neo4j_session):
        """Test Query Pattern 1: Get controls that mitigate CWE-79"""
        # Setup: Create minimal graph
        neo4j_session.run("""
            CREATE (cwe:CWE {cwe_id: 'CWE-79', title: 'XSS'})
            CREATE (ctrl:Control {control_id: 'AC-3', title: 'Access'})
            CREATE (cwe)-[:CWE_VIOLATES_CONTROL]->(ctrl)
        """)

        # Run query
        result = neo4j_session.run("""
            MATCH (cwe:CWE {cwe_id: "CWE-79"})
            MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
            RETURN control.control_id, control.title
            ORDER BY control.control_id
        """)

        controls = list(result)
        assert len(controls) >= 1
        assert controls[0]["control.control_id"] == "AC-3"

    @pytest.mark.neo4j
    def test_query_blast_radius(self, neo4j_session):
        """Test Query Pattern 2: Which services affected by CVE"""
        # Setup: Create minimal graph for blast radius
        neo4j_session.run("""
            CREATE (cve:CVE {cve_id: 'CVE-2024-12345', cwe_id: 'CWE-94'})
            CREATE (finding:Finding {finding_id: 'finding-001', cwe_id: 'CWE-94'})
            CREATE (svc1:Service {service_id: 'logging-service', name: 'Logging', criticality: 'high'})
            CREATE (svc2:Service {service_id: 'api-gateway', name: 'Gateway', criticality: 'critical'})
            CREATE (finding)-[:FINDING_LINKS_CVE]->(cve)
            CREATE (finding)-[:FINDING_AFFECTS_SERVICE]->(svc1)
            CREATE (svc2)-[:SERVICE_DEPENDS_ON_SERVICE]->(svc1)
        """)

        # Query: Direct blast radius
        result = neo4j_session.run("""
            MATCH (cve:CVE {cve_id: "CVE-2024-12345"})
            MATCH (f:Finding)-[:FINDING_LINKS_CVE]->(cve)
            MATCH (f)-[:FINDING_AFFECTS_SERVICE]->(svc:Service)
            RETURN DISTINCT svc.service_id, svc.criticality
        """)

        affected = list(result)
        assert len(affected) >= 1
        assert affected[0]["svc.service_id"] == "logging-service"

    @pytest.mark.neo4j
    def test_query_control_coverage(self, neo4j_session):
        """Test Query Pattern 3: Count findings supporting control"""
        # Setup
        neo4j_session.run("""
            CREATE (control:Control {control_id: 'AC-3', title: 'Access'})
            CREATE (cwe:CWE {cwe_id: 'CWE-79', title: 'XSS'})
            CREATE (finding:Finding {finding_id: 'f1', status: 'open'})
            CREATE (finding2:Finding {finding_id: 'f2', status: 'patched'})
            CREATE (cwe)-[:CWE_VIOLATES_CONTROL]->(control)
            CREATE (finding)-[:FINDING_HAS_CWE]->(cwe)
            CREATE (finding2)-[:FINDING_HAS_CWE]->(cwe)
        """)

        # Query
        result = neo4j_session.run("""
            MATCH (control:Control {control_id: "AC-3"})
            MATCH (cwe:CWE)-[:CWE_VIOLATES_CONTROL]->(control)
            MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe)
            WHERE f.status IN ['open', 'patched']
            RETURN
              count(DISTINCT f) as finding_count,
              count(CASE WHEN f.status = 'patched' THEN 1 END) as patched_count
        """)

        row = result.single()
        assert row["finding_count"] == 2
        assert row["patched_count"] == 1

    @pytest.mark.neo4j
    def test_query_attack_paths(self, neo4j_session):
        """Test Query Pattern 4: Attack paths with incomplete controls"""
        # Setup
        neo4j_session.run("""
            CREATE (threat:Threat {threat_id: 't1', stride_category: 'T', title: 'Tampering'})
            CREATE (svc:Service {service_id: 'svc1', name: 'Service 1'})
            CREATE (finding:Finding {finding_id: 'f1'})
            CREATE (cwe:CWE {cwe_id: 'CWE-79', title: 'XSS'})
            CREATE (control:Control {control_id: 'AC-3', status: 'missing'})
            CREATE (threat)<-[:THREAT_AFFECTS_SERVICE]-(svc)
            CREATE (svc)<-[:FINDING_AFFECTS_SERVICE]-(finding)
            CREATE (finding)-[:FINDING_HAS_CWE]->(cwe)
            CREATE (cwe)-[:CWE_VIOLATES_CONTROL]->(control)
        """)

        # Query: Incomplete controls
        result = neo4j_session.run("""
            MATCH (threat:Threat {stride_category: "T"})
            MATCH (threat)<-[:THREAT_AFFECTS_SERVICE]-(svc:Service)
            MATCH (svc)<-[:FINDING_AFFECTS_SERVICE]-(f:Finding)
            MATCH (f)-[:FINDING_HAS_CWE]->(cwe:CWE)
            MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
            WHERE control.status IN ['missing', 'partial']
            RETURN
              threat.threat_id, svc.service_id, f.finding_id, control.status
        """)

        paths = list(result)
        assert len(paths) >= 1
        assert paths[0]["control.status"] == "missing"


class TestPerformance:
    """Performance baseline tests"""

    @pytest.mark.neo4j
    @pytest.mark.performance
    def test_simple_query_latency(self, neo4j_session):
        """Benchmark: Simple count query (target < 100ms p95)"""
        neo4j_session.run("CREATE (c:Control {control_id: 'test'})")

        latencies = []
        for _ in range(10):
            start = time.perf_counter()
            result = neo4j_session.run("MATCH (c:Control) RETURN count(c)")
            result.consume()
            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        # Performance assertion
        assert p95 < 100, f"Simple query p95 latency {p95:.2f}ms exceeds 100ms threshold"

    @pytest.mark.neo4j
    @pytest.mark.performance
    def test_complex_query_latency(self, neo4j_session):
        """Benchmark: Complex multi-hop query (target < 500ms p95)"""
        # Setup test data
        neo4j_session.run("""
            CREATE (f:Finding {finding_id: 'f1', severity: 'high'})
            CREATE (cwe:CWE {cwe_id: 'CWE-79'})
            CREATE (ctrl:Control {control_id: 'AC-3'})
            CREATE (t:Threat {threat_id: 't1'})
            CREATE (f)-[:FINDING_HAS_CWE]->(cwe)
            CREATE (cwe)-[:CWE_VIOLATES_CONTROL]->(ctrl)
            CREATE (ctrl)-[:CONTROL_MITIGATES_THREAT]->(t)
        """)

        # Run 10 iterations to measure
        latencies = []
        for _ in range(10):
            start = time.perf_counter()

            result = neo4j_session.run("""
                MATCH (f:Finding)-[:FINDING_HAS_CWE]->(cwe:CWE)
                MATCH (cwe)-[:CWE_VIOLATES_CONTROL]->(control:Control)
                MATCH (control)-[:CONTROL_MITIGATES_THREAT]->(threat:Threat)
                RETURN count(f)
            """)
            result.consume()

            end = time.perf_counter()
            latencies.append((end - start) * 1000)  # ms

        p95 = sorted(latencies)[int(len(latencies) * 0.95)]

        # Performance assertion
        assert p95 < 500, f"Complex query p95 latency {p95:.2f}ms exceeds 500ms threshold"


class TestGraphStatistics:
    """Tests for graph statistics and validation"""

    @pytest.mark.neo4j
    def test_graph_statistics(self, neo4j_session):
        """Test: Get graph statistics (node + relationship counts)"""
        # Load some test data first
        neo4j_session.run("""
            CREATE (f:Finding {finding_id: 'test-f1'})
            CREATE (c:Control {control_id: 'test-c1'})
            CREATE (t:Threat {threat_id: 'test-t1'})
        """)

        # Get statistics
        result = neo4j_session.run("MATCH (n) RETURN labels(n) as label, count(*) as count")
        node_stats = {record["label"][0]: record["count"] for record in result}

        assert "Finding" in node_stats
        assert node_stats["Finding"] >= 1

    @pytest.mark.neo4j
    def test_relationship_statistics(self, neo4j_session):
        """Test: Count relationships by type"""
        # Setup
        neo4j_session.run("""
            CREATE (f:Finding {finding_id: 'f1'})
            CREATE (c:CWE {cwe_id: 'CWE-1'})
            CREATE (f)-[:FINDING_HAS_CWE]->(c)
        """)

        # Get stats
        result = neo4j_session.run("MATCH ()-[r]->() RETURN type(r) as rel_type, count(*) as count")

        rel_stats = {record["rel_type"]: record["count"] for record in result}

        assert "FINDING_HAS_CWE" in rel_stats
        assert rel_stats["FINDING_HAS_CWE"] >= 1
