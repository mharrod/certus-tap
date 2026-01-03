# Security Analyst Capstone - Helper Scripts & Assets

This directory contains automated helper scripts for the Security Analyst Capstone tutorial. These scripts abstract the complexity of Neo4j schema loading, data ingestion, and analysis queries.

## Quick Start

```bash
# 1. Setup (load schema, ingest sample data)
./setup-capstone.sh

# 2. Run automated analysis
./run-analysis.sh

# 3. Explore individual query types
./queries-semantic.sh      # OpenSearch semantic search
./queries-graph.sh         # Neo4j graph queries
./queries-hybrid.sh        # Hybrid analysis workflows
```

## Scripts Overview

### setup-capstone.sh
**Purpose:** Initialize the capstone environment
**Does:**
- Verifies OpenSearch and Neo4j are running
- Loads Neo4j schema from `samples/neo4j_spike/schema.cypher`
- Ingests SARIF findings into Neo4j
- Ingests SBOM packages into Neo4j
- Creates OpenSearch indexes

**Usage:**
```bash
./setup-capstone.sh [workspace-id]
```

**Example:**
```bash
./setup-capstone.sh product-acquisition-review
```

### run-analysis.sh
**Purpose:** Execute complete capstone analysis workflow
**Does:**
- Phase 1: Semantic discovery (OpenSearch)
- Phase 2: Structural analysis (Neo4j)
- Phase 3: Hybrid analysis (both tools)
- Generates summary metrics

**Usage:**
```bash
./run-analysis.sh [workspace-id]
```

### queries-semantic.sh
**Purpose:** Show OpenSearch semantic search examples
**Includes:**
1. Critical severity findings
2. SQL injection vulnerabilities
3. Authentication/credential issues
4. Severity distribution
5. Packages with security concerns
6. License compliance checks

**Usage:**
```bash
./queries-semantic.sh [opensearch-url]
```

### queries-graph.sh
**Purpose:** Show Neo4j graph analysis examples
**Includes:**
1. Severity distribution
2. Most common security issues
3. File hotspots
4. Critical findings details
5. Package inventory
6. License distribution
7. High-risk packages (many dependents)
8. Transitive dependencies
9. Packages depending on vulnerable libs
10. GPL/restrictive license packages
11. Findings in specific files
12. Cross-reference findings to packages

**Usage:**
```bash
./queries-graph.sh
```

### queries-hybrid.sh
**Purpose:** Show hybrid analysis workflows combining both tools
**Includes:**
- Workflow 1: SQL injection discovery & impact analysis
- Workflow 2: License compliance review
- Workflow 3: Risk hotspot analysis
- Workflow 4: Dependency risk assessment
- Workflow 5: Security posture summary

**Usage:**
```bash
./queries-hybrid.sh
```

## Customization

### Override Neo4j Credentials
```bash
export NEO4J_USER=myuser
export NEO4J_PASSWORD=mypass
export NEO4J_URI=neo4j://myhost:7687
./setup-capstone.sh
```

### Override OpenSearch URL
```bash
export OPENSEARCH_URL=http://localhost:9200
./queries-semantic.sh
```

### Modify Sample Data
Edit before running setup:
- SARIF findings: `samples/security-scans/sarif/security-findings.sarif`
- SBOM packages: `samples/security-scans/spdx/sbom-example.spdx.json`

Then re-run `setup-capstone.sh` to re-ingest.

## File Structure

```
samples/capstone/
├── README.md                    # This file
├── setup-capstone.sh           # Initialize environment
├── run-analysis.sh             # Execute analysis
├── queries-semantic.sh         # OpenSearch examples
├── queries-graph.sh            # Neo4j examples
└── queries-hybrid.sh           # Hybrid workflows
```

## Related Documentation

- **Semantic Search**: `docs/learn/semantic-search.md`
- **Knowledge Graphs**: `docs/learn/neo4j-local-ingestion-query.md`
- **Hybrid Analysis**: `docs/learn/hybrid-search.md`
- **Full Capstone**: `docs/learn/security-analyst-capstone.md`

## Troubleshooting

**Q: "Service not running" error**
```bash
# Start services
docker compose up -d opensearch neo4j ask-certus-backend
```

**Q: "Index already exists" warning**
This is normal and safe - existing indexes are reused.

**Q: "No documents found" in queries**
Ensure `setup-capstone.sh` completed successfully.

**Q: Scripts not executable**
```bash
chmod +x /samples/capstone/*.sh
```

## Advanced Usage

### Run specific phase only
```bash
# Just semantic search
source .venv/bin/activate
curl -X POST "localhost:9200/security-findings/_search" \
  -H 'Content-Type: application/json' \
  -d '{"query": {"term": {"severity": "critical"}}, "size": 100}'
```

### Combine multiple analyses
```bash
./queries-semantic.sh > /tmp/semantic-results.txt
./queries-graph.sh > /tmp/graph-results.txt
./queries-hybrid.sh > /tmp/hybrid-results.txt

# Compare results
diff /tmp/semantic-results.txt /tmp/graph-results.txt
```

### Export results for reporting
```bash
./run-analysis.sh | tee capstone-report-$(date +%Y%m%d).txt
```

## Performance Notes

- Initial setup: ~30-60 seconds
- Analysis runs: ~15-30 seconds
- Indexes are persistent (survives container restart)
- Re-running setup on same workspace re-ingests data

## Next Steps

1. Read `docs/learn/security-analyst-capstone.md` for complete tutorial
2. Run `./run-analysis.sh` to see end-to-end workflow
3. Explore individual `queries-*.sh` scripts for detailed examples
4. Modify queries to test against your own data
5. Create custom analysis workflows combining these scripts
