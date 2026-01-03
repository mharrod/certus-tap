# Certus Assurance (Mock Security Service)

## Purpose

Describe the mock security scanning service packaged with Certus TAP (“Certus Assurance”), how it produces deterministic SARIF/SPDX artifacts with provenance, and how those artifacts integrate with Trust and TAP ingestion flows.

## Audience & Prerequisites

- Security analysts running the provenance tutorial.
- Developers extending the mock service or replacing it with real scanners.
- Familiarity with `tools/security/run_certus_assurance_security.py`, `scripts/load_security_into_neo4j.py`, and the provenance docs under `docs/learn/provenance/`.

## Overview

- Certus Assurance is a mock FastAPI service (port `8056`) that:
  - Accepts scan requests (`POST /v1/security-scans`).
  - Loads sample artifacts from `samples/non-repudiation/scan-artifacts/`.
  - Writes results to `.artifacts/certus-assurance/<scan_id>/`.
  - Generates provenance metadata and in-toto attestations.
- Outputs include SARIF (Trivy), SBOM (Syft), and supplemental docs used by the Neo4j ingestion tutorial.
- Integration with Certus Trust demonstrates upload/verification workflows (`/v1/security-scans/{id}/upload-request`).

## Key Concepts

### Artifact Layout

```
.artifacts/certus-assurance/<scan_id>/
├── scan.json                # Provenance metadata
├── logs/runner.log          # Execution log
├── reports/
│   ├── sast/trivy.sarif.json
│   ├── sbom/syft.spdx.json
│   └── dast/zap-dast.sarif.json (optional case study data)
└── reports/signing/
    └── cosign.attestation.jsonl
```

### API Endpoints (Mock Service)

| Endpoint                                           | Description                                                           |
| -------------------------------------------------- | --------------------------------------------------------------------- |
| `POST /v1/security-scans`                          | Submit a scan (payload includes `git_url`, `branch`, `requested_by`). |
| `GET /v1/security-scans/{scan_id}`                 | Poll status (`status`, `upload_status`, attestation info).            |
| `POST /v1/security-scans/{scan_id}/upload-request` | Trigger mock Certus Trust upload (sets `upload_status`).              |

### Helper Script

`tools/security/run_certus_assurance_security.py` runs a Dagger-based scan with OpenGrep, Bandit, Trivy and exports reports to `build/security-reports/` (lighter version of the SAST pipeline).

## Workflows / Operations

1. **Start the stack:** `just up` (includes Certus Assurance service).
2. **Submit a scan:**
   ```bash
   export SCAN_ID=$(curl -s -X POST http://localhost:8056/v1/security-scans \
     -H 'Content-Type: application/json' \
     -d '{"git_url":"https://github.com/mharrod/certus-TAP.git","branch":"main","requested_by":"tutorial@example.com"}' \
     | jq -r '.scan_id')
   ```
3. **Monitor status:**
   `curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq '{scan_id,status,upload_status}'`
4. **Inspect artifacts:**
   `ls ./.artifacts/certus-assurance/$SCAN_ID/reports/`
5. **Submit upload request (mock Trust):**
   ```bash
   curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request \
     -H 'Content-Type: application/json' \
     -d '{"tier":"verified"}'
   ```
6. **Ingest into TAP/Neo4j:** Use `scripts/load_security_into_neo4j.py` or `tools/security/run_certus_assurance_security.py` outputs to feed the SARIF/SPDX ingestion endpoints.

## Configuration / Interfaces

- Service code lives under `certus_assurance/`.
- Default storage path: `.artifacts/certus-assurance` (create the directory before running).
- Sample data pulled from `samples/non-repudiation/scan-artifacts/`.
- For Dagger helper (`tools/security/run_certus_assurance_security.py`):
  - CLI flags: `--export-dir`, `--opengrep-args`, `--bandit-args`, `--trivy-args`.
  - Reports exported to `build/security-reports/`.

## Troubleshooting / Gotchas

- **Service not running:** Ensure `just up` includes the `certus-assurance` container (`docker compose ps certus-assurance`).
- **Upload status stuck at `pending`:** Mock workflow only flips to `permitted` once the upload request endpoint is called; poll until it changes.
- **Artifacts missing:** Confirm `.artifacts/certus-assurance` exists and the process has write permissions (on macOS, run from project root).
- **Neo4j ingestion warnings:** After loading SARIF via `scripts/load_security_into_neo4j.py`, use the updated loader (no Cartesian products) and query with `SecurityScan` label.

## Related Documents

- [Security Scan with Provenance (Learn)](../../learn/provenance/security-scans.md)
- [Trust Verification Workflow](../../learn/provenance/verify-trust.md)
- [Neo4j Local Ingestion](../../learn/security-workflows/neo4j-local-ingestion-query.md)
- [SAST Pipeline (Component)](sast-pipeline.md)
