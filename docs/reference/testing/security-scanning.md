# Dagger Security Scanning

The TAP security checks now live in a dedicated Dagger module (`dagger_modules/security`).
The module provides **5 security profiles** optimized for different stages of development,
from quick smoke tests to comprehensive release scans. Each profile can produce security
evidence and artifacts in minutes, making security testing fast and accessible.

The module is distributed as a reference implementation: you can run it via `just`,
the Python CLI, or import it into Certus-Assurance.

## Security Profiles

The module provides profiles optimized for different languages and use cases:

| Profile              | Tools                             | Duration | Use Case                                      |
| -------------------- | --------------------------------- | -------- | --------------------------------------------- |
| **smoke**            | Ruff                              | ~20 sec  | CI health check, verify toolchain works       |
| **fast**             | Ruff, Bandit, detect-secrets      | ~2 min   | Pre-commit hooks, local development           |
| **medium**           | fast + Opengrep + attestation     | ~4 min   | Pre-push sanity checks                        |
| **standard**         | medium + Trivy                    | ~8 min   | PR gates, CI default                          |
| **full**             | standard + privacy + SBOM         | ~15 min  | Releases, main branch merges                  |
| **javascript**       | ESLint + retire.js + Trivy + SBOM | ~3 min   | Node.js/JavaScript projects (e.g. Juice Shop) |
| **attestation-test** | Ruff + SBOM + attestation         | ~30 sec  | Quick SBOM/attestation validation             |

**Legacy:** The `light` profile is aliased to `full` for backward compatibility.

**Language-Specific Profiles:** The `javascript` profile is optimized for Node.js/JavaScript projects and demonstrates the module's versatility across language ecosystems.

**Testing Tip:** Use `attestation-test` to quickly validate SBOM generation and in-toto attestation without running full security scans. Perfect for testing signing workflows.

## Tool Coverage by Profile

### All Profiles Include

- **Ruff** - Python linting and code quality checks
- **Summary generation** - Tool versions and finding counts

### Fast Profile Adds

- **Bandit** - Python security issue detection
- **detect-secrets** - Secret/credential detection across all files

### Medium Profile Adds

- **Opengrep** - Pattern-based security rules (Semgrep baseline from `config/semgrep-baseline.yml`)

### Standard Profile Adds

- **Trivy** - Filesystem scan for vulnerabilities, secrets, and misconfigurations

### Full Profile Adds

- **Privacy scan** - Regex heuristics across `samples/privacy-pack` (placeholder for Presidio)
- **SBOM generation** - Software Bill of Materials using Syft (SPDX + CycloneDX formats)
- **in-toto attestation** - Cryptographic attestation of scan execution and artifacts

### JavaScript Profile Includes

- **ESLint with security plugin** - JavaScript/TypeScript security linting with SARIF output
- **retire.js** - Detection of known vulnerable JavaScript libraries
- **detect-secrets** - Credential and secret detection across all files
- **Trivy** - Vulnerability scanning of npm dependencies and filesystem
- **SBOM generation** - Software Bill of Materials using Syft (works with package.json)
- **in-toto attestation** - Cryptographic attestation of scan execution

## Artifact Outputs

| Tool            | Output File                  | Format     | Profile          |
| --------------- | ---------------------------- | ---------- | ---------------- |
| Ruff            | `ruff.txt`                   | Text       | Python profiles  |
| Bandit          | `bandit.json`                | JSON       | Python profiles  |
| detect-secrets  | `detect-secrets.json`        | JSON       | All profiles     |
| Opengrep        | `opengrep.sarif.json`        | SARIF      | Python profiles  |
| Trivy           | `trivy.sarif.json`           | SARIF      | All profiles     |
| Privacy         | `privacy-findings.json`      | JSON       | full only        |
| ESLint Security | `eslint-security.sarif.json` | SARIF      | javascript       |
| retire.js       | `retire.json`                | JSON       | javascript       |
| Syft (SBOM)     | `sbom.spdx.json`             | SPDX JSON  | full, javascript |
| Syft (SBOM)     | `sbom.cyclonedx.json`        | CycloneDX  | full, javascript |
| Attestation     | `attestation.intoto.json`    | in-toto v1 | medium+          |
| Summary         | `summary.json`               | JSON       | All profiles     |

Each run writes artifacts into `build/security-results/<bundle_id>/`, where `<bundle_id>` defaults to `<timestamp>-<git-sha>`. The CLI automatically refreshes `build/security-results/latest` symlink for quick inspection.

## Prerequisites

- Docker Desktop (or compatible container runtime) running locally
- Python 3.11+ with `uv` installed
- Repo dependencies installed via `uv sync`
- Dagger automatically managed via the Python SDK (no separate CLI install needed)

## Running via `just` (Recommended)

```bash
# Quick smoke test (20 seconds)
just test-security-smoke

# Fast pre-commit scan (2 minutes)
just test-security-fast

# Medium pre-push scan (4 minutes)
just test-security-medium

# Standard CI scan (8 minutes)
just test-security-standard

# Full comprehensive scan (12 minutes)
just test-security-full
```

Each recipe:

1. Spins up a disposable `python:3.11-slim` container via Dagger
2. Installs required security tools
3. Runs the selected profile stages
4. Writes artifacts to `build/security-results/<bundle_id>/`
5. Updates `build/security-results/latest` symlink

## Running via Python CLI

For IDE integration or custom workflows:

```bash
# From dagger_modules/security directory
cd dagger_modules/security
PYTHONPATH=. uv run python -m security_module.cli \
  --workspace ../.. \
  --export-dir ../../build/security-results \
  --profile fast

# Available profiles: smoke, fast, medium, standard, full
```

## Running via Dagger Call

For CI pipelines or when you need the native Dagger interface:

```bash
# Smoke profile
dagger call --mod dagger_modules/security smoke \
  --source . \
  --export-path build/security-results

# Standard profile (recommended for CI)
dagger call --mod dagger_modules/security standard \
  --source . \
  --privacy-assets dagger_modules/security/assets/privacy-pack \
  --export-path build/security-results

# Full profile
dagger call --mod dagger_modules/security full \
  --source . \
  --privacy-assets dagger_modules/security/assets/privacy-pack \
  --export-path build/security-results
```

**Note:** When using `dagger call`, the module applies default exclusions but cannot customize them per-call. For custom exclusions, use the Python CLI which reads from `constants.py`.

## Artifact Layout

```
build/security-results/
├── 20251209-204606-cfe67f6/  # First run
│   ├── bandit.json
│   ├── detect-secrets.json
│   ├── opengrep.sarif.json
│   ├── privacy-findings.json
│   ├── ruff.txt
│   ├── sbom.spdx.json           # SPDX SBOM (full profile only)
│   ├── sbom.cyclonedx.json      # CycloneDX SBOM (full profile only)
│   ├── attestation.intoto.json  # in-toto attestation (full profile only)
│   ├── summary.json
│   └── trivy.sarif.json
├── 20251209-205130-cfe67f6/  # Second run
│   └── ...
└── latest -> 20251209-205130-cfe67f6/  # Always points to newest
```

`summary.json` records:

- Tool versions
- Which tools were executed vs skipped
- Bundle ID and generation timestamp
- Finding counts per SARIF/JSON report (future enhancement)

CI jobs can parse this file to enforce policy gates (e.g., fail when severity thresholds are exceeded).

## Supply Chain Security: Attestations & Signing

The **full** profile generates an in-toto attestation (`attestation.intoto.json`) that provides cryptographic proof of:

- Which security tools were executed
- What artifacts were generated with SHA256 digests
- When the scan occurred
- Build metadata (bundle ID, profile name)

### in-toto Attestation Structure

The attestation follows the [in-toto v1 specification](https://github.com/in-toto/attestation/tree/main/spec/v1):

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {"name": "summary.json", "digest": {"sha256": "abc123..."}},
    {"name": "sbom.spdx.json", "digest": {"sha256": "def456..."}}
  ],
  "predicateType": "https://in-toto.io/attestation/v1",
  "predicate": {
    "buildType": "https://certus.dev/security-scan/v1",
    "builder": {"id": "https://certus.dev/dagger-security-module/v1"},
    "invocation": {
      "configSource": {"entryPoint": "security.full"},
      "parameters": {
        "bundleId": "20251209-210431-cfe67f6",
        "executedTools": ["ruff", "bandit", "trivy", "sbom-spdx", ...]
      }
    },
    "metadata": {
      "buildStartedOn": "2025-12-09T21:04:31Z",
      "completeness": {"parameters": true, "materials": false}
    }
  }
}
```

### Signing Artifacts with cosign

While the Dagger module includes cosign in the toolchain, **signing is currently a manual post-processing step**. This design allows organizations to control their signing keys and policies outside the scan container.

**Quick Start - Using the Helper Script:**

1. Generate a cosign key pair (one-time setup):

```bash
cosign generate-key-pair
# Creates cosign.key (private) and cosign.pub (public)
# Store cosign.key securely (e.g., secrets manager, vault)
```

2. Run the attestation test profile (fast):

```bash
just test-security-attestation
```

3. Sign all artifacts using the helper script:

```bash
./scripts/sign-security-artifacts.sh build/security-results/latest cosign.key
```

Expected output:

```
🔐 Signing security artifacts in build/security-results/latest

📜 Signing attestation...
   ✓ attestation.intoto.json.sig
📦 Signing sbom.cyclonedx.json...
   ✓ sbom.cyclonedx.json.sig
📦 Signing sbom.spdx.json...
   ✓ sbom.spdx.json.sig

✅ Successfully signed all artifacts
```

4. Verify signatures:

```bash
cosign verify-blob \
  --key cosign.pub \
  --signature build/security-results/latest/attestation.intoto.json.sig \
  --insecure-ignore-tlog \
  build/security-results/latest/attestation.intoto.json
```

**Manual Signing (Advanced):**

For manual control or custom workflows:

```bash
# Sign the attestation
cosign sign-blob \
  --key cosign.key \
  --tlog-upload=false \
  --output-signature attestation.intoto.json.sig \
  attestation.intoto.json

# Sign SBOM files individually
cosign sign-blob --key cosign.key --tlog-upload=false \
  --output-signature sbom.spdx.json.sig \
  sbom.spdx.json

cosign sign-blob --key cosign.key --tlog-upload=false \
  --output-signature sbom.cyclonedx.json.sig \
  sbom.cyclonedx.json
```

### Keyless Signing with Sigstore

For CI/CD environments, use Sigstore's keyless signing (requires OIDC authentication):

```yaml
# GitHub Actions example
- name: Sign attestation
  env:
    COSIGN_EXPERIMENTAL: 1
  run: |
    cosign sign-blob \
      --output-signature attestation.intoto.json.sig \
      --output-certificate attestation.intoto.json.cert \
      build/security-results/latest/attestation.intoto.json
```

### Publishing to OCI Registry

Signed artifacts can be pushed to an OCI registry for distribution:

```bash
# Push attestation bundle to registry
oras push localhost:5000/certus/security-scans:latest \
  attestation.intoto.json:application/vnd.in-toto+json \
  sbom.spdx.json:application/spdx+json \
  sbom.cyclonedx.json:application/vnd.cyclonedx+json

# Attach signatures
cosign attach signature localhost:5000/certus/security-scans:latest \
  --signature attestation.intoto.json.sig
```

See [`docs/learn/provenance/sign-attestations.md`](../../learn/provenance/sign-attestations.md) for complete workflows including verification, ingestion into Certus TAP, and compliance reporting.

## Choosing the Right Profile

| When to Use        | Recommended Profile |
| ------------------ | ------------------- |
| Pre-commit hook    | `fast`              |
| Pre-push check     | `medium`            |
| PR gate in CI      | `standard`          |
| Main branch merge  | `full`              |
| Release candidate  | `full`              |
| Quick sanity check | `smoke`             |

## Customizing Exclusions

The module automatically excludes common directories:

- `.git`, `.venv`, `venv`, `env`, `test_venv`
- `node_modules`, `dist`, `build`, `site`
- `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
- `*.egg-info`, `.tox`, `.nox`, `*.so`, `*.dylib`, `.DS_Store`

To add project-specific exclusions, edit `dagger_modules/security/security_module/constants.py`:

```python
EXCLUDES = [
    # ... existing excludes ...
    "my_custom_venv",   # Your custom virtual environment
    "data",             # Large datasets
    "models",           # ML model files
]
```

Alternatively, scan a subdirectory instead of the entire project:

```bash
dagger call --mod dagger_modules/security smoke --source ./src
```

## Troubleshooting

| Symptom                                          | Fix                                                                                                                                     |
| ------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------- |
| `permission denied` / cannot start Dagger engine | Ensure Docker is running and your user can talk to its socket.                                                                          |
| `no space left on device`                        | Add project-specific excludes (large venvs, datasets, ML models) to `constants.py` or clean up Dagger cache with `docker system prune`. |
| `opengrep` exits with non-zero status            | Verify `dagger_modules/security/config/semgrep-baseline.yml` is valid YAML.                                                             |
| Trivy cannot update DB                           | Allow network access or check Trivy cache at `/tmp/trivy-cache`.                                                                        |
| Privacy stage returns empty list                 | Confirm `samples/privacy-pack/` exists; the stage gracefully skips missing files but produces an empty report.                          |
| Git sync failures                                | Commit or stash changes before running scans - Dagger needs a stable workspace.                                                         |

## CI Integration

### GitHub Actions Example

```yaml
name: Security Scan
on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  security-fast:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - name: Run fast security scan
        run: just test-security-fast
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: security-results
          path: build/security-results/latest/
```

For main branch or releases, use `test-security-standard` or `test-security-full`.

## Future Roadmap

The heavy profile (DAST, API testing, SBOM generation, provenance) and Certus-Assurance
integration will arrive in later roadmap phases per `docs/reference/roadmap/proposals/dagger-proposal.md`.

**Planned additions:**

- Policy gates with severity thresholds
- Notifications (Slack/webhook)
- GitHub Security tab integration
- Additional tools (CodeQL, Dependency-Check, OWASP ZAP)
- OCI module distribution

For now, the 5 profiles provide comprehensive SAST + secrets + composition coverage suitable for most development workflows.
