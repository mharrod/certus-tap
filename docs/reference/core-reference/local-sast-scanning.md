# Local SAST Scanning Pipeline

Run static application security testing (SAST) tools locally via a containerized Dagger pipeline. This pipeline helps catch security issues before committing code.

## Overview

The local SAST scanner orchestrates four security tools in a disposable container:

| Tool        | Purpose                                                  |
| ----------- | -------------------------------------------------------- |
| **Trivy**   | Vulnerability scanner for dependencies and configuration |
| **Semgrep** | Pattern-based SAST (custom rules)                        |
| **Bandit**  | Python security issue detection                          |
| **Ruff**    | Python linter (performance, style, security rules)       |
| **Syft**    | SBOM (Software Bill of Materials) generator              |

## Prerequisites

- Docker daemon running (required by Dagger)
- Python 3.9+ with `uv` package manager
- `dagger-io` dependency (already in dev group of `pyproject.toml`)

Install dependencies:

```bash
just install
```

## Quick Start

Run all SAST tools on the current repository:

```bash
just sast-scan
```

Or invoke the script directly with `uv`:

```bash
uv run python tools/sast/run_local_scan.py
```

Reports are exported to `build/sast-reports/` by default (use `--export-dir` to add a build ID so multiple runs don’t overwrite each other), including provenance metadata and signatures:

```
build/sast-reports/
├── trivy.sarif.json          # Vulnerabilities and misconfigurations (SARIF)
├── bandit.sarif.json         # Python security issues (SARIF)
├── semgrep.sarif.json        # Pattern matching results (SARIF)
├── ruff.txt                  # Linting findings
├── sbom.spdx.json            # Software Bill of Materials (SPDX format)
├── sbom.cyclonedx.json       # Software Bill of Materials (CycloneDX format)
└── provenance/               # In-toto provenance & cosign signatures
    ├── layout.intoto.jsonl   # Overall workflow definition
    ├── trivy.intoto.jsonl    # Trivy step provenance
    ├── semgrep.intoto.jsonl  # Semgrep step provenance
    ├── bandit.intoto.jsonl   # Bandit step provenance
    ├── ruff.intoto.jsonl     # Ruff step provenance
    └── syft.intoto.jsonl     # Syft step provenance
```

## Usage

### Run All Tools

```bash
uv run python tools/sast/run_local_scan.py
```

### Run Specific Tools

```bash
uv run python tools/sast/run_local_scan.py --tools trivy,bandit,ruff
uv run python tools/sast/run_local_scan.py --tools syft  # Just SBOM generation
```

If you want to skip Semgrep (e.g., due to long runtimes) but keep the rest of the security stack:

```bash
uv run python tools/sast/run_local_scan.py \
  --tools trivy,bandit,ruff,syft,dependency-check,license-check,pii-detection,secrets-detection
```

The end-to-end helper supports the same flag:

```bash
uv run python tools/sast/run_e2e_pipeline.py \
  --tools trivy,bandit,ruff,syft,dependency-check,license-check,pii-detection,secrets-detection \
  --workspace ${WORKSPACE:-sast-workspace} \
  --base-url http://localhost:8000
```

To explicitly run every scanner (including Semgrep) while keeping the ability to toggle tools, supply the full list:

```bash
uv run python tools/sast/run_local_scan.py \
  --tools trivy,semgrep,bandit,ruff,syft,dependency-check,license-check,pii-detection,secrets-detection
```

```bash
uv run python tools/sast/run_e2e_pipeline.py \
  --tools trivy,semgrep,bandit,ruff,syft,dependency-check,license-check,pii-detection,secrets-detection \
  --workspace ${WORKSPACE:-sast-workspace} \
  --base-url http://localhost:8000
```

> ℹ️ When you omit a tool (for example, Semgrep in the shorter list above), the export step logs warnings such as `lstat .../bandit.sarif.json: no such file or directory`. That simply means the tool didn't run, so no artifact exists. Re-run with the full tool list if you need every SARIF file.

### With Provenance & Signatures

Generate in-toto provenance metadata and sign all artifacts with cosign:

```bash
# Create in-toto provenance + sign with cosign (keyless OIDC)
uv run python tools/sast/run_local_scan.py --sign-artifacts

# With explicit keyless signing
uv run python tools/sast/run_local_scan.py --sign-artifacts --keyless
```

This creates:

- `provenance/layout.intoto.jsonl` - Overall workflow definition
- `provenance/*.intoto.jsonl` - Individual step provenance for each tool
- `provenance/*.sig` - Cosign signatures for all artifacts (requires cosign installed)

### Pass Tool-Specific Arguments

```bash
# Filter Trivy to only HIGH and CRITICAL severity
uv run python tools/sast/run_local_scan.py --trivy-args "--severity HIGH,CRITICAL"

# Pass custom Bandit args
uv run python tools/sast/run_local_scan.py --bandit-args "--tests B201,B301"

# Custom export directory (with build ID to preserve runs)
BUILD_ID=$(date +%Y%m%d-%H%M%S)
uv run python tools/sast/run_local_scan.py --export-dir ./security-reports/$BUILD_ID
```

### Fail the run when findings exist

By default the scanner exits successfully even if SARIF files contain findings (so automated post-processing can continue). Add `--fail-on-findings` to return exit code `1` whenever Trivy/Semgrep/Bandit report results:

```bash
uv run python tools/sast/run_local_scan.py --fail-on-findings
```

The flag also works with the e2e helper:

```bash
uv run python tools/sast/run_e2e_pipeline.py --fail-on-findings ...
```

### Combined Example

```bash
export BUILD_ID=$(date +%Y%m%d-%H%M%S)
uv run python tools/sast/run_local_scan.py \
  --tools trivy,bandit,syft \
  --trivy-args "--severity HIGH,CRITICAL" \
  --sign-artifacts \
  --export-dir ./build/sec-reports/$BUILD_ID
```

## Ingesting into Certus

Once the scan finishes, you can send the SARIF/SBOM outputs into Certus TAP for analysis:

1. **Manual ingestion** – call the security endpoint for each SARIF and the SPDX SBOM:

   ```bash
   WORKSPACE=sast-workspace
   curl -X POST "http://localhost:8000/v1/${WORKSPACE}/index/security" \
     -F "uploaded_file=@build/sast-reports/$BUILD_ID/SECURITY/trivy.sarif.json"

   curl -X POST "http://localhost:8000/v1/${WORKSPACE}/index/security" \
     -F "uploaded_file=@build/sast-reports/$BUILD_ID/SECURITY/semgrep.sarif.json"

   curl -X POST "http://localhost:8000/v1/${WORKSPACE}/index/security" \
     -F "uploaded_file=@build/sast-reports/$BUILD_ID/SECURITY/bandit.sarif.json"

   curl -X POST "http://localhost:8000/v1/${WORKSPACE}/index/security" \
     -F "uploaded_file=@build/sast-reports/$BUILD_ID/SUPPLY_CHAIN/sbom.spdx.json" \
     -F "format=spdx"
   ```

2. **Automated pipeline** – run the helper script to scan (or reuse existing artifacts), ingest them, execute keyword/semantic/graph queries, and generate a Markdown report:

   ```bash
   uv run python tools/sast/run_e2e_pipeline.py \
     --workspace ${WORKSPACE:-sast-workspace} \
     --build-id $BUILD_ID \
     --base-url http://localhost:8000 \
     --opensearch-url http://localhost:9200 \
     --neo4j-uri neo4j://localhost:7687 \
     --neo4j-user neo4j --neo4j-password password
   ```

- Use `--skip-scan --export-dir build/sast-reports/$BUILD_ID` if you want to ingest/report on an existing run without rerunning the tools.
- Use `--skip-ingest` if you only want to run the report/analysis portions (for example, artifacts were already ingested in a previous step).

## Understanding Reports

### Trivy Report (`trivy.sarif.json`)

Contains vulnerabilities, misconfigurations, and secrets detected across dependencies and configuration files.

Example findings:

- **Vulnerability**: Known CVE in a dependency
- **Misconfiguration**: Insecure Dockerfile, Kubernetes YAML, etc.
- **Secret**: Exposed API key, password, or credential

### Bandit Report (`bandit.sarif.json`)

Python-specific security issues. Examples:

- Use of insecure hash functions
- Hardcoded passwords
- SQL injection risks
- Insecure deserialization

### Ruff Report (`ruff.txt`)

Python linting with security rules (subset of Bandit). Examples:

- Complexity issues
- Unused imports
- Deprecated API usage

## Provenance & Attestation

### Understanding Provenance Metadata

When you run with `--sign-artifacts`, the scanner generates in-toto provenance metadata that records:

- **What tools ran** - Exact tool names and versions
- **When they ran** - Timestamp of each step
- **What they scanned** - Complete file list and their hashes (SHA256)
- **What they produced** - Output files and their hashes
- **How they ran** - Exact command-line arguments
- **Chain of custody** - Cryptographic proof the workflow wasn't modified

This is valuable for:

- **Audit trails** - Prove to auditors/regulators exactly what was scanned
- **Reproducibility** - Re-run the exact same scan with identical parameters
- **Verification** - Detect if reports were modified after scanning
- **Compliance** - Support PCI-DSS, HIPAA, SOC2, ISO 27001 audits
- **Expert witness** - Cryptographic proof of work performed

### Provenance Files

The `provenance/` directory contains:

**layout.intoto.jsonl**

- Overall workflow definition
- Lists all steps that should execute
- Expected outputs and their required hashes
- Use for verifying the complete assessment chain

**Individual link files** (e.g., `trivy.intoto.jsonl`)

- Records for each tool execution
- Contains: command run, files scanned, results generated, timestamp
- One file per tool (trivy, semgrep, bandit, ruff, syft)
- Example: `trivy.intoto.jsonl` shows exactly what Trivy scanned and found

**Signature files** (e.g., `trivy.json.sig`)

- Cosign signatures for each artifact
- Cryptographically prove artifacts weren't modified
- Can be verified independently by clients

### Verifying Provenance

**View what a tool actually scanned:**

```bash
cat build/sast-reports/provenance/trivy.intoto.jsonl | jq .signed.command
```

Output shows the exact Trivy command that ran:

```json
["trivy", "fs", "--scanners", "vuln,secret,config", "--format", "json", ...]
```

**Check when each step executed:**

```bash
cat build/sast-reports/provenance/trivy.intoto.jsonl | jq .signed.environment.timestamp
```

**See all output files from a scan step:**

```bash
cat build/sast-reports/provenance/trivy.intoto.jsonl | jq .signed.products
```

Shows all files generated with their SHA256 hashes - proves nothing was changed after scanning.

**Verify a scan report wasn't modified** (requires cosign installed):

```bash
cosign verify-blob \
  --signature build/sast-reports/provenance/trivy.json.sig \
  build/sast-reports/trivy.json
```

If the file was modified, verification fails. If it passes, you have cryptographic proof the report is authentic.

**Full provenance verification** (requires in-toto CLI):

```bash
# Install in-toto verification tools
pip install in-toto

# Verify the complete assessment chain
in-toto-verify -l build/sast-reports/provenance/ \
               -k <public-key> \
               --layout layout.intoto
```

This ensures:

- All expected steps executed
- No steps were skipped
- No steps were reordered
- All outputs match their expected hashes

### Using Provenance for Compliance

For regulatory audits, provide clients with:

1. **Scan reports** - All JSON/text files in `build/sast-reports/`
2. **Provenance metadata** - Everything in `build/sast-reports/provenance/`
3. **Verification instructions** - Steps to verify signatures and chain of custody

Auditors can then independently verify that:

- Assessment used industry-standard tools (Trivy, Semgrep, Bandit)
- Tools scanned the complete codebase
- Results were generated on a specific date/time
- Results were not modified after generation

## Performance

- **First run**: ~30-60 seconds (pulls container, downloads tool databases)
- **Subsequent runs**: ~10-20 seconds (uses cached layers)

Dagger caches container layers, so repeated scans are much faster.

## Exit Codes

The scanner returns:

- **0**: No high-severity findings detected
- **1**: Trivy or Bandit detected issues

Low-severity findings from Ruff don't affect the exit code (informational only).

## Troubleshooting

### Docker daemon not running

```
Error: failed to connect to Dagger daemon
```

Start Docker:

```bash
open /Applications/Docker.app  # macOS
# or
sudo systemctl start docker     # Linux
```

### Permission denied: `/var/run/docker.sock`

Add your user to the `docker` group:

```bash
sudo usermod -aG docker $USER
newgrp docker
```

### Tool installation failures

If a tool fails to install, check that:

- Python 3.11-slim has system dependencies available
- Network connectivity is available for package downloads
- Disk space is sufficient

### Dagger version mismatch

If you see version errors, ensure the Dagger daemon is up-to-date:

```bash
dagger version
```

### Missing SARIF files during export

```
⚠ Could not export SECURITY/bandit.sarif.json: lstat /tmp/sast-reports/SECURITY/bandit.sarif.json: no such file or directory
```

This is informational. Either the tool wasn't included in `--tools` or it exited before writing a report. The pipeline continues so other artifacts still export. Rerun with the full tool list (or without `--tools`) if you need that SARIF file regenerated.

## Integrating with Pre-Commit (Optional)

To run SAST scans as a Git pre-commit hook, add to `.pre-commit-config.yaml`:

```yaml
- repo: local
  hooks:
    - id: sast-scan
      name: SAST scan (Dagger)
      entry: uv run python tools/sast/run_local_scan.py
      language: system
      pass_filenames: false
      stages: [commit]
      verbose: true
```

Then reinstall hooks:

```bash
pre-commit install
```

**Note**: This will run on every commit and may be slow. Consider making it non-blocking or stage-specific.

To run with provenance + signatures in pre-commit:

```yaml
- repo: local
  hooks:
    - id: sast-scan-with-provenance
      name: SAST scan with provenance
      entry: uv run python tools/sast/run_local_scan.py --sign-artifacts
      language: system
      pass_filenames: false
      stages: [commit]
      verbose: true
```

## Customization

### Excluding Files/Directories

The pipeline excludes these by default:

```
.git, .venv, dist, site, node_modules, draft, htmlcov, __pycache__
```

To exclude additional paths, edit `tools/sast/run_local_scan.py` and add to `EXCLUDES`.

### Custom Tool Arguments

Each tool accepts additional CLI arguments via the script:

```bash
uv run python tools/sast/run_local_scan.py \
  --trivy-args "--format sarif" \
  --bandit-args "--exclude tests"
```

See tool documentation:

- [Trivy CLI docs](https://aquasecurity.github.io/trivy/)
- [Bandit docs](https://bandit.readthedocs.io/)
- [OpenGrep docs](https://semgrep.dev/docs/)
- [Ruff docs](https://docs.astral.sh/ruff/)

## What's Next?

- Review findings in `build/sast-reports/`
- Fix security issues before pushing code
- Consider running in CI/CD pipelines (future integration with Certus Assurance)

## See Also

- [Security scanning with Dagger](./security-scanning.md) - Certus Assurance service scanner
- [Testing overview](./testing-overview.md) - Complete testing guide
