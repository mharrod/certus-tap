#!/bin/bash
# run-analysis.sh - Execute the complete capstone analysis workflow
# This script chains together semantic search, graph queries, and hybrid analysis

set -e

WORKSPACE_ID="${1:-product-acquisition-review}"

echo "🔍 Running Security Analyst Capstone Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Phase 1: Semantic Search Discovery
echo "📖 Phase 1: Exploratory Semantic Search"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "1️⃣  Finding HIGH/CRITICAL severity issues..."
CRITICALS=$(curl -s -X POST "localhost:9200/security-findings/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"terms": {"severity": ["critical", "high"]}},
    "aggs": {"by_severity": {"terms": {"field": "severity"}}},
    "size": 0
  }' | jq -r '.hits.total.value')

echo "   Found: $CRITICALS high/critical findings"

# Phase 2: Graph Analysis
echo ""
echo "📊 Phase 2: Knowledge Graph Structural Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "2️⃣  Analyzing findings by severity distribution..."
docker compose exec -T neo4j cypher-shell -u neo4j -p password \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)
   RETURN f.severity, count(f) AS count
   ORDER BY CASE f.severity WHEN "critical" THEN 0 WHEN "high" THEN 1 WHEN "medium" THEN 2 ELSE 3 END;' 2>/dev/null | grep -v "^$"

echo ""
echo "3️⃣  Identifying file hotspots (most vulnerable files)..."
docker compose exec -T neo4j cypher-shell -u neo4j -p password \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
   RETURN loc.uri, count(f) AS findings
   ORDER BY findings DESC
   LIMIT 5;' 2>/dev/null | grep -v "^$"

echo ""
echo "4️⃣  Analyzing package dependencies..."
docker compose exec -T neo4j cypher-shell -u neo4j -p password \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)
   MATCH (consumer:Package)-[:DEPENDS_ON]->(pkg)
   WITH pkg, count(consumer) AS dependents
   WHERE dependents > 0
   RETURN pkg.name, pkg.version, dependents
   ORDER BY dependents DESC
   LIMIT 5;' 2>/dev/null | grep -v "^$"

echo ""
echo "5️⃣  License compliance check..."
docker compose exec -T neo4j cypher-shell -u neo4j -p password \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)-[:USES_LICENSE]->(lic:License)
   RETURN lic.name AS license, count(distinct pkg) AS package_count
   ORDER BY package_count DESC;' 2>/dev/null | grep -v "^$"

# Phase 3: Hybrid Analysis
echo ""
echo "🔀 Phase 3: Hybrid Analysis (Semantic + Graph)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "6️⃣  Identifying high-risk patterns (SQL injection)..."
SQLI_COUNT=$(curl -s -X POST "localhost:9200/security-findings/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"match": {"message": "SQL injection"}},
    "size": 1000
  }' | jq -r '.hits.total.value')

echo "   SQL injection findings: $SQLI_COUNT"

echo ""
echo "7️⃣  Analyzing shell injection vulnerabilities..."
docker compose exec -T neo4j cypher-shell -u neo4j -p password \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding {rule_id: "B602"})
   OPTIONAL MATCH (f)-[:LOCATED_AT]->(loc:Location)
   RETURN f.rule_id, f.severity, loc.uri
   ORDER BY f.severity;' 2>/dev/null | grep -v "^$" || echo "   No B602 (shell injection) findings"

echo ""
echo "8️⃣  Cross-referencing: Files with findings + Package analysis..."
docker compose exec -T neo4j cypher-shell -u neo4j -p password \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
   WITH collect(distinct loc.uri) AS files, count(f) AS total
   RETURN total AS total_findings, files AS affected_files
   LIMIT 1;' 2>/dev/null | grep -v "^$"

# Phase 4: Generate Report Summary
echo ""
echo "📋 Summary Report"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "Key Metrics:"
echo "  • Total findings: $(docker compose exec -T neo4j cypher-shell -u neo4j -p password 'MATCH (:Scan)-[:CONTAINS]->(f:Finding) RETURN count(f);' 2>/dev/null | tail -1)"
echo "  • Critical findings: $(docker compose exec -T neo4j cypher-shell -u neo4j -p password 'MATCH (:Scan)-[:CONTAINS]->(f:Finding {severity: "critical"}) RETURN count(f);' 2>/dev/null | tail -1)"
echo "  • High findings: $(docker compose exec -T neo4j cypher-shell -u neo4j -p password 'MATCH (:Scan)-[:CONTAINS]->(f:Finding {severity: "high"}) RETURN count(f);' 2>/dev/null | tail -1)"
echo "  • Unique packages: $(docker compose exec -T neo4j cypher-shell -u neo4j -p password 'MATCH (:SBOM)-[:CONTAINS]->(p:Package) RETURN count(p);' 2>/dev/null | tail -1)"

echo ""
echo "✅ Analysis complete!"
echo ""
echo "📖 For detailed queries, see:"
echo "   • samples/capstone/queries-semantic.sh (OpenSearch queries)"
echo "   • samples/capstone/queries-graph.sh (Neo4j queries)"
echo "   • samples/capstone/queries-hybrid.sh (Combined analysis)"
