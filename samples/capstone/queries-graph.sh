#!/bin/bash
# queries-graph.sh - Neo4j graph queries for capstone analysis
# Shows how to analyze relationships, dependencies, and impact

NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

run_query() {
    local title="$1"
    local query="$2"
    echo "$title"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" "$query" 2>/dev/null | tail -n +2
    echo ""
}

echo "📊 Knowledge Graph Queries (Neo4j)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Query 1: Finding severity distribution
run_query "1️⃣  Severity Distribution" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)
   RETURN f.severity, count(f) AS count
   ORDER BY CASE f.severity WHEN "critical" THEN 0 WHEN "high" THEN 1 WHEN "medium" THEN 2 ELSE 3 END;'

# Query 2: Most common security rules
run_query "2️⃣  Most Common Security Issues (by rule)" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)
   RETURN f.rule_id, f.severity, count(f) AS occurrences
   ORDER BY occurrences DESC
   LIMIT 10;'

# Query 3: File hotspots
run_query "3️⃣  File Hotspots (Files with Most Findings)" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
   RETURN loc.uri, count(f) AS findings
   ORDER BY findings DESC
   LIMIT 10;'

# Query 4: Critical findings details
run_query "4️⃣  All Critical Findings with Details" \
  'MATCH (scan:Scan)-[:CONTAINS]->(f:Finding {severity: "critical"})
   OPTIONAL MATCH (f)-[:LOCATED_AT]->(loc:Location)
   RETURN f.rule_id, f.message, loc.uri, loc.line
   ORDER BY f.rule_id;'

# Query 5: Package and license inventory
run_query "5️⃣  Complete Package Inventory" \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)
   OPTIONAL MATCH (pkg)-[:USES_LICENSE]->(lic:License)
   RETURN pkg.name, pkg.version, lic.name AS license, pkg.supplier
   ORDER BY pkg.name, pkg.version;'

# Query 6: License distribution
run_query "6️⃣  License Distribution" \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)-[:USES_LICENSE]->(lic:License)
   RETURN lic.name AS license, count(distinct pkg) AS package_count
   ORDER BY package_count DESC;'

# Query 7: High-risk packages (depended on by many)
run_query "7️⃣  High-Risk Packages (Many Dependents)" \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)
   MATCH (consumer:Package)-[:DEPENDS_ON]->(pkg)
   WITH pkg, count(consumer) AS dependents
   WHERE dependents > 0
   RETURN pkg.name, pkg.version, dependents
   ORDER BY dependents DESC
   LIMIT 10;'

# Query 8: Transitive dependencies
run_query "8️⃣  Transitive Dependencies (Flask)" \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package {name: "flask"})
   MATCH (pkg)-[:DEPENDS_ON*0..2]->(dep:Package)
   RETURN distinct dep.name, dep.version
   ORDER BY dep.name;'

# Query 9: Packages depending on vulnerable lib
run_query "9️⃣  Packages Depending on Requests" \
  'MATCH (:SBOM)-[:CONTAINS]->(vuln:Package {name: "requests"})
   MATCH (consumer:Package)-[:DEPENDS_ON]->(vuln)
   RETURN consumer.name, consumer.version
   ORDER BY consumer.name;'

# Query 10: GPL/restrictive license check
run_query "🔟 Copyleft License Packages" \
  'MATCH (:SBOM)-[:CONTAINS]->(pkg:Package)-[:USES_LICENSE]->(lic:License)
   WHERE lic.name CONTAINS "GPL" OR lic.name CONTAINS "AGPL"
   RETURN pkg.name, pkg.version, lic.name
   ORDER BY pkg.name;'

# Query 11: Findings in specific files
run_query "1️⃣1️⃣  All Findings in app/database.py" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location {uri: "app/database.py"})
   RETURN f.rule_id, f.severity, f.message, loc.line
   ORDER BY loc.line;'

# Query 12: Cross-reference findings to packages
run_query "1️⃣2️⃣  Findings Affecting Key Modules" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
   WHERE loc.uri CONTAINS "app/" OR loc.uri CONTAINS "database" OR loc.uri CONTAINS "auth"
   RETURN loc.uri, f.rule_id, f.severity, count(f) AS count
   ORDER BY count DESC;'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Graph analysis complete!"
echo ""
echo "💡 Tips:"
echo "   - Modify package names in queries (flask → requests, celery, etc.)"
echo "   - Change file paths to analyze different modules"
echo "   - Add LIMIT clauses to reduce large result sets"
echo "   - Use OPTIONAL MATCH for relationships that might not exist"
