#!/bin/bash
# queries-hybrid.sh - Hybrid search combining OpenSearch and Neo4j
# Shows real-world security analysis workflows

NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
OPENSEARCH_URL="${OPENSEARCH_URL:-localhost:9200}"

echo "🔀 Hybrid Analysis Workflows"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Workflow 1: Discover SQL injection, analyze impact
echo "Workflow 1️⃣: SQL Injection Discovery & Impact Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Step 1: Discover SQL injection findings (OpenSearch semantic search)"
SQLI_FINDINGS=$(curl -s -X POST "$OPENSEARCH_URL/security-findings/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"match": {"message": "SQL injection"}},
    "size": 100
  }' | jq '.hits.total.value')

echo "  Found: $SQLI_FINDINGS SQL injection findings"

echo ""
echo "Step 2: Analyze impacted files with graph (Neo4j)"
docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (scan:Scan)-[:CONTAINS]->(f:Finding {rule_id: "B105"})
   OPTIONAL MATCH (f)-[:LOCATED_AT]->(loc:Location)
   RETURN f.rule_id, f.severity, loc.uri, count(f) AS occurrences
   ORDER BY f.severity, loc.uri;' 2>/dev/null | tail -n +2

echo ""
echo "Step 3: Determine if affected modules have high dependencies"
docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)
   MATCH (consumer:Package)-[:DEPENDS_ON]->(pkg)
   WITH pkg, count(consumer) AS dependents
   WHERE dependents > 1
   RETURN pkg.name, dependents
   ORDER BY dependents DESC
   LIMIT 5;' 2>/dev/null | tail -n +2

echo ""
echo "📋 Recommendation: High-priority if B105 findings are in core modules"
echo ""

# Workflow 2: License compliance
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Workflow 2️⃣: License Compliance Review"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Step 1: Find restrictive licenses (OpenSearch)"
GPL_PACKAGES=$(curl -s -X POST "$OPENSEARCH_URL/sbom-packages/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "bool": {
        "should": [
          {"match": {"licenses": "GPL"}},
          {"match": {"licenses": "AGPL"}}
        ]
      }
    }
  }' | jq -r '.hits.hits[] | ._source.name')

if [ -n "$GPL_PACKAGES" ]; then
  echo "  GPL packages found:"
  echo "$GPL_PACKAGES" | sed 's/^/    - /'
else
  echo "  No GPL packages found"
fi

echo ""
echo "Step 2: Check dependencies in graph (Neo4j)"
docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)-[:USES_LICENSE]->(lic:License)
   WHERE lic.name CONTAINS "GPL" OR lic.name CONTAINS "AGPL"
   MATCH (consumer:Package)-[:DEPENDS_ON*1..2]->(pkg)
   RETURN consumer.name, count(distinct pkg) AS gpl_deps
   ORDER BY gpl_deps DESC;' 2>/dev/null | tail -n +2 || echo "  No GPL packages in dependency graph"

echo ""
echo "📋 Recommendation: Review license compliance policy for identified packages"
echo ""

# Workflow 3: Risk hotspot analysis
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Workflow 3️⃣: Risk Hotspot Analysis"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Step 1: Find hotspot files (Neo4j graph)"
echo "  Files with most findings:"
docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
   RETURN loc.uri, count(f) AS findings,
          count(CASE WHEN f.severity = "critical" THEN 1 END) AS critical
   ORDER BY findings DESC
   LIMIT 5;' 2>/dev/null | tail -n +2

echo ""
echo "Step 2: Analyze specific hotspot (example: app/database.py)"
docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (scan:Scan)-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location {uri: "app/database.py"})
   RETURN f.rule_id, f.severity, f.message
   ORDER BY CASE f.severity WHEN "critical" THEN 0 WHEN "high" THEN 1 ELSE 2 END;' 2>/dev/null | tail -n +2

echo ""
echo "📋 Recommendation: Prioritize remediating files with multiple critical findings"
echo ""

# Workflow 4: Dependency risk
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Workflow 4️⃣: Dependency Risk Assessment"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "Step 1: Identify high-value packages (many dependents)"
docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)
   MATCH (consumer:Package)-[:DEPENDS_ON]->(pkg)
   WITH pkg, count(consumer) AS dependents
   WHERE dependents > 0
   RETURN pkg.name, dependents, pkg.version
   ORDER BY dependents DESC
   LIMIT 5;' 2>/dev/null | tail -n +2

echo ""
echo "Step 2: Check for known issues in high-value packages (OpenSearch)"
echo "  Searching for cryptography-related packages..."
curl -s -X POST "$OPENSEARCH_URL/sbom-packages/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"match": {"name": "cryptography"}},
    "_source": ["name", "version", "licenses"]
  }' | jq '.hits.hits[] | {name: ._source.name, version: ._source.version}'

echo ""
echo "📋 Recommendation: Monitor high-value packages closely for security updates"
echo ""

# Workflow 5: Complete security posture summary
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Workflow 5️⃣: Complete Security Posture Summary"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "📊 Metrics:"
TOTAL_FINDINGS=$(docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding) RETURN count(f);' 2>/dev/null | tail -1)

CRITICAL_FINDINGS=$(docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding {severity: "critical"}) RETURN count(f);' 2>/dev/null | tail -1)

HIGH_FINDINGS=$(docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding {severity: "high"}) RETURN count(f);' 2>/dev/null | tail -1)

TOTAL_PACKAGES=$(docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:SBOM)-[:CONTAINS]->(p:Package) RETURN count(p);' 2>/dev/null | tail -1)

echo "  Total Findings: $TOTAL_FINDINGS"
echo "  Critical: $CRITICAL_FINDINGS | High: $HIGH_FINDINGS"
echo "  Packages: $TOTAL_PACKAGES"

echo ""
echo "✅ Hybrid analysis complete!"
echo ""
echo "💡 Next steps:"
echo "   1. Review detailed findings in docs/learn/hybrid-search.md"
echo "   2. Create remediation roadmap based on risk priority"
echo "   3. Implement fixes starting with CRITICAL findings"
echo "   4. Re-run analysis after fixes to validate"
