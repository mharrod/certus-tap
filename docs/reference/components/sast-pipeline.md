# SAST Pipeline (Dagger Runner)

## Purpose
Provide a reference for the local SAST pipeline implemented via Dagger (`tools/sast/run_local_scan.py`), including the tools it runs, provenance artifacts, and how to execute or extend it.

## Audience & Prerequisites
- Developers running pre-commit security scans.
- DevSecOps engineers integrating the pipeline into CI.
- Familiarity with Dagger, Python 3.11, and optional Cosign/in-toto tooling.

## Overview
- Spins up a disposable `python:3.11-slim` container via Dagger.
- Installs security/privacy/supply chain tools (Trivy, Semgrep, Bandit, Ruff, Syft, Presidio, TruffleHog, OWASP Dependency-Check, license scanners).
- Runs each tool against the repository, exporting reports under `build/sast-reports`.
- Generates in-toto provenance metadata and optional Cosign signatures for auditability.

## Key Concepts

### Tools & Domains
| Domain | Tools |
| ------ | ----- |
| **Security** | Trivy (filesystem), Semgrep, Bandit, Ruff |
| **Supply Chain** | Syft (SPDX/CycloneDX), OWASP Dependency-Check, pip-licenses |
| **Privacy** | Presidio analyzers, TruffleHog |

### Output Structure
```
build/sast-reports/
├── SECURITY/
│   ├── trivy.json
│   ├── semgrep.txt
│   ├── bandit.json
│   └── ruff.txt
├── SUPPLY_CHAIN/
│   ├── sbom.spdx.json
│   ├── sbom.cyclonedx.json
│   ├── dependency-check.json
│   └── licenses.json
├── PRIVACY/
│   ├── pii-detection.json
│   └── secrets-detection.json
└── provenance/
    ├── layout.intoto.jsonl
    ├── *.intoto.jsonl
    └── *.sig (if signing enabled)
```

### Provenance & Signing
- `enrich_documents_with_metadata()` is unrelated; this pipeline uses in-toto link metadata.
- Cosign can sign each artifact (`--sign-artifacts`, `--keyless`).
- Metadata includes commands, timestamps, environment variables, and output hashes.

## Workflows / Operations

### Prerequisites
- Docker daemon available (Dagger requirement).
- Python 3.9+ with `uv` (or system Python) to run the script.
- Optional: Cosign installed (`go install github.com/sigstore/cosign/cmd/cosign@latest`).

### Quick Start
```bash
# Install dependencies
just install

# Run full pipeline (default export dir)
uv run python tools/sast/run_local_scan.py
```

### Run Specific Tools
```bash
uv run python tools/sast/run_local_scan.py --tools trivy,bandit,syft
```
Tools field accepts comma-separated names; omit `--tools` to run all.

### Pass Tool Arguments
```bash
uv run python tools/sast/run_local_scan.py \
  --trivy-args "--severity HIGH,CRITICAL" \
  --bandit-args "--tests B201,B301"
```

### Change Export Directory
```bash
uv run python tools/sast/run_local_scan.py --export-dir ./security-reports
```

### Enable Signing
```bash
uv run python tools/sast/run_local_scan.py --sign-artifacts --keyless
```

## Configuration / Interfaces
- Script: `tools/sast/run_local_scan.py`.
- Report formatter utilities: `tools/sast/report_formatter.py` (parse JSON/text into unified findings lists).
- CLI flags:
  - `--tools`
  - `--export-dir`
  - `--trivy-args`, `--semgrep-args`, etc.
  - `--sign-artifacts`
  - `--keyless`
- Dagger mounts the repo (excludes `.git`, `.venv`, `node_modules`, etc.) and runs scans inside the container.

## Troubleshooting / Gotchas
- **Dagger connection errors:** Ensure Docker is running; Dagger needs the engine.
- **Cosign not found:** Install `cosign` if enabling signing; otherwise use `--sign-artifacts=false`.
- **Large repos:** Adjust `EXCLUDES` list in the script to skip heavy directories (build artifacts, vendor folders).
- **Tool failures:** Each tool runs via `container.with_exec(... || true)` so the pipeline continues; inspect logs under `build/sast-reports/SECURITY/*.txt/json`.
- **Slow runs:** Use `--tools` to limit to essential scanners when iterating locally.

## Related Documents
- [Local SAST Scanning (Learn)](../../learn/testing/local-sast-scanning.md)
- [Metadata Envelope Reference](metadata-envelopes.md) – Provenance parallels.
- [Logging Stack](logging-stack.md) – Ingest SAST logs/results if needed.
- [Certus Assurance Security Checks](streamlit-console.md#privacy-scan) – Companion workflows.
