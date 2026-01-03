#!/bin/bash
# setup-capstone.sh - Automated setup for security analyst capstone
# This script abstracts the complexity of Neo4j schema loading and data ingestion

set -e

WORKSPACE_ID="${1:-product-acquisition-review}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
NEO4J_URI="${NEO4J_URI:-neo4j://localhost:7687}"

echo "🔧 Setting up Security Analyst Capstone"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Workspace ID: $WORKSPACE_ID"
echo ""

# Step 1: Verify services are running
echo "✓ Checking services..."
if ! docker compose ps opensearch | grep -q "Up"; then
    echo "❌ OpenSearch not running. Start with: docker compose up -d opensearch"
    exit 1
fi

if ! docker compose ps neo4j | grep -q "Up"; then
    echo "❌ Neo4j not running. Start with: docker compose up -d neo4j"
    exit 1
fi

echo "  ✓ OpenSearch running"
echo "  ✓ Neo4j running"
echo ""

# Step 2: Load Neo4j schema
echo "📊 Loading Neo4j schema..."
docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  < samples/neo4j_spike/schema.cypher > /dev/null 2>&1
echo "  ✓ Schema loaded"
echo ""

# Step 3: Ingest sample data into Neo4j
echo "📥 Ingesting sample data..."
source .venv/bin/activate
python scripts/load_security_into_neo4j.py \
  --workspace "$WORKSPACE_ID" \
  --neo4j-uri "$NEO4J_URI" \
  --neo4j-user "$NEO4J_USER" \
  --neo4j-password "$NEO4J_PASSWORD" > /dev/null 2>&1
echo "  ✓ SARIF findings loaded"
echo "  ✓ SBOM packages loaded"
echo ""

# Step 4: Create OpenSearch indexes (if not exists)
echo "🔍 Setting up OpenSearch indexes..."
curl -s -X PUT "localhost:9200/security-findings" \
  -H 'Content-Type: application/json' \
  -d '{
    "settings": {"number_of_shards": 1, "number_of_replicas": 0},
    "mappings": {
      "properties": {
        "rule_id": {"type": "keyword"},
        "severity": {"type": "keyword"},
        "message": {"type": "text"},
        "file_path": {"type": "keyword"},
        "timestamp": {"type": "date"}
      }
    }
  }' 2>/dev/null || echo "  ℹ️  Index already exists"

echo "  ✓ OpenSearch indexes ready"
echo ""

# Step 5: Verify data loaded
echo "🔍 Verifying data ingestion..."
FINDINGS=$(docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:Scan)-[:CONTAINS]->(f:Finding) RETURN count(f) as count;' 2>/dev/null | tail -1)

PACKAGES=$(docker compose exec -T neo4j cypher-shell -u "$NEO4J_USER" -p "$NEO4J_PASSWORD" \
  'MATCH (:SBOM)-[:CONTAINS]->(p:Package) RETURN count(p) as count;' 2>/dev/null | tail -1)

echo "  ✓ Findings: $FINDINGS"
echo "  ✓ Packages: $PACKAGES"
echo ""

echo "✅ Capstone setup complete!"
echo ""
echo "📖 Next steps:"
echo "   1. Read: docs/learn/semantic-search.md (OpenSearch queries)"
echo "   2. Read: docs/learn/neo4j-local-ingestion.md (Neo4j queries)"
echo "   3. Read: docs/learn/hybrid-search.md (Combined analysis)"
echo "   4. Run: samples/capstone/run-analysis.sh"
