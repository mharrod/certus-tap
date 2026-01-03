# Neo4j Knowledge Graph Guide

## Purpose
Document how Certus TAP uses Neo4j to store SARIF findings and SPDX dependency graphs so analysts can answer multi-hop security questions (e.g., “Which packages depend on package X and have GPL licenses?”).

## Audience & Prerequisites
- Security engineers and analysts who run the SARIF/SPDX ingestion workflows.
- Developers extending `SarifToNeo4j` / `SpdxToNeo4j`.
- Familiarity with Cypher and the ingestion loaders in `certus_ask/pipelines/neo4j_loaders/*`.

## Overview
- SARIF scans produce a **Security Graph**: `SecurityScan → Tool → Rule → Finding → (Severity, Location, CWE)`.
- SPDX SBOMs produce a **Supply Chain Graph**: `SBOM → Package → License / ExternalRef`, plus `DEPENDS_ON` and `HAS_VULNERABILITY` relationships.
- The graph enables deterministic answers for dependency, vulnerability, and compliance questions that are awkward in text search.

## Key Concepts

### Graph Architecture
| Source | Entry Point | Key Nodes | Relationships |
| ------ | ----------- | --------- | ------------- |
| SARIF  | `SarifToNeo4j.load()` | `SecurityScan`, `Tool`, `Rule`, `Finding`, `Severity`, `Location`, `CWE` | `SCANNED_WITH`, `CONTAINS`, `VIOLATES`, `HAS_SEVERITY`, `LOCATED_AT`, `DEFINES`, `RELATES_TO` |
| SPDX   | `SpdxToNeo4j.load()`  | `SBOM`, `Package`, `License`, `ExternalRef`, `Severity` (optional) | `CONTAINS`, `DEPENDS_ON`, `USES_LICENSE`, `HAS_REFERENCE`, `HAS_VULNERABILITY` |

Example SARIF subgraph:
```
(SecurityScan)-[:SCANNED_WITH]->(Tool)-[:DEFINES]->(Rule)
      \
       [:CONTAINS]->(Finding)-[:VIOLATES]->(Rule)
                                 |-[:HAS_SEVERITY]->(Severity)
                                 |-[:LOCATED_AT]->(Location)
                                 \-[:RELATES_TO]->(CWE)
```

Example SPDX subgraph:
```
(SBOM)-[:CONTAINS]->(Package)-[:DEPENDS_ON]->(Package)
                            |-[:USES_LICENSE]->(License)
                            |-[:HAS_REFERENCE]->(ExternalRef)
                            \-[:HAS_VULNERABILITY]->(Finding|CVSS)
```

### Common Nodes & Properties

| Label | Important Properties | Notes |
| ----- | -------------------- | ----- |
| `SecurityScan` | `id`, `timestamp`, `assessment_id` | One per ingestion run. |
| `Tool` | `name`, `version` | Bandit, Trivy, etc. |
| `Rule` | `id`, `name`, `description`, `help` | Referenced by findings. |
| `Finding` | `id`, `severity`, `message`, `rule_id` | Linked to scans and rules. |
| `Location` | `uri`, `line` | File path + line number. |
| `SBOM` | `id`, `name` | One per SPDX ingestion. |
| `Package` | `name`, `version`, `supplier` | May have multiple licenses or vulnerabilities. |
| `License` | `name` | Reused across packages. |

### Sample Cypher Queries

**Security Findings by Severity**
```cypher
MATCH (:SecurityScan {id: $scan_id})-[:CONTAINS]->(f:Finding)-[:HAS_SEVERITY]->(s:Severity)
RETURN s.level, count(f) AS count
ORDER BY count DESC;
```

**Transitive Package Dependencies**
```cypher
MATCH (:Package {name: $pkg})-[:DEPENDS_ON*]->(dep:Package)
RETURN DISTINCT dep.name, dep.version;
```

**Packages with GPL Licenses**
```cypher
MATCH (:SBOM {id: $sbom_id})-[:CONTAINS]->(p:Package)-[:USES_LICENSE]->(l:License {name: "GPL"})
RETURN p.name, p.version;
```

**Flask Impact Scope**
```cypher
MATCH (root:Package {name: "flask"})<-[:DEPENDS_ON*]-(dependent:Package)
RETURN DISTINCT dependent.name, dependent.version;
```

**Finding Details with Locations**
```cypher
MATCH (scan:SecurityScan {id: $scan_id})-[:CONTAINS]->(f:Finding)-[:LOCATED_AT]->(loc:Location)
RETURN f.rule_id, f.severity, loc.uri, loc.line
ORDER BY f.rule_id;
```

## Workflows / Operations

1. **Load SARIF:**
   ```bash
   docker compose exec ask-certus-backend bash -lc '
     source .venv/bin/activate &&
     python /app/scripts/load_security_into_neo4j.py \
       --workspace neo4j-security-scans \
       --neo4j-uri neo4j://neo4j:7687
   '
   ```
   → `SarifToNeo4j` creates/updates the security graph and logs `sarif.neo4j.load_complete`.

2. **Load SPDX:**
   Same script ingests the SBOM portion and logs `spdx.neo4j.load_complete`.

3. **Query Neo4j:**
   - Browser: `http://localhost:7474` (`neo4j/password`).
   - CLI: `docker compose exec -T neo4j cypher-shell -u neo4j -p password 'MATCH ...'`.

4. **Integrate with RAG:**
   Retrieval flows can combine OpenSearch hits with Neo4j queries. For example, find policy docs in OpenSearch and then enrich them with graph results (packages, dependencies, vulnerabilities) before sending to the LLM.

## Configuration / Interfaces
- Connection defaults live in `.env` (`NEO4J_URI=neo4j://neo4j:7687`, `NEO4J_USER=neo4j`, `NEO4J_PASSWORD=password`).
- Schema constraints/indices are defined in `samples/neo4j_spike/schema.cypher`. Apply them via:
  ```bash
  docker compose exec -T neo4j cypher-shell -u neo4j -p password < samples/neo4j_spike/schema.cypher
  ```
- Loader code: `certus_ask/pipelines/neo4j_loaders/sarif_loader.py` and `spdx_loader.py`.
- Container logs: `docker compose logs -f neo4j` or check backend logs for `neo4j.notifications`.

## Troubleshooting / Gotchas
- **Cartesian product warnings:** Ensure MATCH clauses bind nodes separately before MERGE (fixed in `sarif_loader`).
- **Missing nodes:** Confirm ingestion ran successfully; rerun loader if you reset Neo4j volumes.
- **Performance:** Add indexes on frequently queried properties (`Package.name`, `Finding.rule_id`, `License.name`).
- **Authentication errors:** Validate creds in `.env` match the values for the `neo4j` service.
- **Graph drift:** Rerun schema file if you drop the database or encounter constraint errors.

## Related Documents
- [Neo4j Local Ingestion Guide (Learn)](../../learn/security-workflows/neo4j-local-ingestion-query.md)
- [Security Analyst Capstone](../../learn/security-workflows/security-analyst-capstone.md)
- [Metadata Envelope Reference](metadata-envelopes.md)
- [API – Metadata Envelopes](../api/metadata-envelopes.md)
