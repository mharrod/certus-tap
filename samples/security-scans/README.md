# Security Scan Samples

This directory contains example security scan files for testing the Certus TAP ingestion pipeline.

## Folder Structure

```
security-scans/
├── sarif/           # SARIF vulnerability scan format
│   └── security-findings.sarif
├── bandit/          # Python security scanner results
│   └── bandit-scan.json
├── trivy/           # Container and dependency scanner results
│   └── trivy-scan.json
└── spdx/            # Software Bill of Materials (SBOM)
    └── sbom-example.spdx.json
```

## File Descriptions

### SARIF Files (`sarif/`)
**SARIF** (Static Analysis Results Format) is a standard format for reporting security findings.

- `security-findings.sarif` - Example findings from Bandit tool including shell injection, SQL injection, and code quality issues

**Ingest with:**
```bash
curl -X POST http://localhost:8000/v1/default/index/security \
  -F "uploaded_file=@/app/samples/security-scans/sarif/security-findings.sarif"
```

### Bandit Files (`bandit/`)
**Bandit** is a Python security linter that scans for common security issues.

- `bandit-scan.json` - Example Python security scan results (requires tool_hint)

**Ingest with:**
```bash
curl -X POST http://localhost:8000/v1/default/index/security \
  -F "uploaded_file=@/app/samples/security-scans/bandit/bandit-scan.json" \
  -F "tool_hint=bandit"
```

### Trivy Files (`trivy/`)
**Trivy** is a container and dependency vulnerability scanner.

- `trivy-scan.json` - Example container image scan with OS packages and npm vulnerabilities

**Ingest with:**
```bash
curl -X POST http://localhost:8000/v1/default/index/security \
  -F "uploaded_file=@/app/samples/security-scans/trivy/trivy-scan.json" \
  -F "tool_hint=trivy"
```

### SPDX Files (`spdx/`)
**SPDX** (Software Package Data Exchange) is a standard format for software bill of materials.

- `sbom-example.spdx.json` - Example SBOM with package dependencies and relationships

**Ingest with:**
```bash
curl -X POST http://localhost:8000/v1/default/index/security \
  -F "uploaded_file=@/app/samples/security-scans/spdx/sbom-example.spdx.json"
```

## Testing

To test all security scan ingestion:

```bash
# Test SARIF
curl -X POST http://localhost:8000/v1/default/index/security \
  -F "uploaded_file=@/app/samples/security-scans/sarif/security-findings.sarif"

# Test SPDX
curl -X POST http://localhost:8000/v1/default/index/security \
  -F "uploaded_file=@/app/samples/security-scans/spdx/sbom-example.spdx.json"

# Test Bandit (requires tool_hint)
curl -X POST http://localhost:8000/v1/default/index/security \
  -F "uploaded_file=@/app/samples/security-scans/bandit/bandit-scan.json" \
  -F "tool_hint=bandit"

# Test Trivy (requires tool_hint)
curl -X POST http://localhost:8000/v1/default/index/security \
  -F "uploaded_file=@/app/samples/security-scans/trivy/trivy-scan.json" \
  -F "tool_hint=trivy"
```

Then query the indexed findings:

```bash
curl -X POST http://localhost:8000/v1/default/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"What vulnerabilities were found?"}'
```

## Neo4j Exploration

After ingestion, explore the security graph in Neo4j at `http://localhost:7474`:

```cypher
# Find all findings
MATCH (f:Finding) RETURN f LIMIT 10

# Find high-severity findings
MATCH (f:Finding {severity: "HIGH"}) RETURN f

# Find locations affected by findings
MATCH (f:Finding)-[:LOCATED_IN]->(l:Location) RETURN f.title, l.file_path
```
