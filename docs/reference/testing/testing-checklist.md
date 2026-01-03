# Testing Cadence Checklist

Quick reference for when to run each class of tests/security scans across the development pipeline.

## Daily Development Flow

- ✅ **On every local change**
  - `just test-fast` (alias for `uv run python -m pytest -m "not smoke"`) or target the affected modules.
  - Aim for <1 min feedback; keep fixtures/mocks lean.

- ✅ **Before committing changes**
  - Run `pre-commit run --all-files` (or `just lint`) to execute formatting hooks.
  - **Security:** `just test-security-fast` (~2 min) - Quick SAST + secrets check for pre-commit validation.

- ✅ **Before pushing / opening a PR**
  - `just test` (coverage run)
  - `just preflight` (Docker stack + ingestion/query acceptance)
  - **Security:** `just test-security-medium` (~4 min) - Pre-push sanity check with pattern-based rules.

- ✅ **Before merging PR**
  - All CI checks must pass (lint, tests, security)
  - Coverage must stay above targets (85% service/router, 80% overall)
  - **Security:** PR gates run `just test-security-standard` (~8 min) in CI automatically.

## Security Scanning Strategy

The Dagger security module provides 5 profiles optimized for different stages:

| Profile    | When to Run                 | Duration | Tools                          |
| ---------- | --------------------------- | -------- | ------------------------------ |
| `smoke`    | CI health check             | ~20 sec  | Ruff only                      |
| `fast`     | Pre-commit hook             | ~2 min   | Ruff + Bandit + detect-secrets |
| `medium`   | Pre-push check              | ~4 min   | fast + Opengrep rules          |
| `standard` | **PR gate (required)**      | ~8 min   | medium + Trivy vulnerabilities |
| `full`     | Release / main branch merge | ~12 min  | standard + privacy detection   |

**Commands:**

```bash
just test-security-smoke     # Quick toolchain verification
just test-security-fast      # Pre-commit recommended
just test-security-medium    # Pre-push recommended
just test-security-standard  # CI default for PRs
just test-security-full      # Release gate
```

**Legacy:** `just test-security-light` is aliased to `full` for backward compatibility.

See [Security Scanning Reference](security-scanning.md) for detailed tool coverage and artifact outputs.

## CI Expectations

- 🛠 **PR workflows**
  - Lint + `just test-fast` (fast/unit/integration suites)
  - **Security:** `just test-security-standard` (8 min) - Automated PR gate
  - Coverage must stay above targets (85% service/router, 80% overall)
- 🌙 **Nightly jobs**
  - `just test-smoke` (Docker-backed smoke suites)
  - `just test-tutorial` (long-form published walkthroughs)
  - **Security:** `just test-security-full` (12 min) - Comprehensive scan for drift detection

## Release / Milestone Gates

- 🧪 **Pre-release**
  - Full coverage run (`just test`) + `just preflight` on a clean checkout
  - **Security:** `just test-security-full` - Comprehensive scan including privacy detection
  - Archive outputs (coverage XML, preflight logs, security reports) with the release artifacts
  - Results stored in `build/security-results/<bundle_id>/`

## Security Artifacts

Each security scan produces:

- SARIF files for code scanning integration
- JSON reports for automated policy gates
- `summary.json` with tool versions and execution metadata
- Results available in `build/security-results/latest/`

Artifacts can be:

- Uploaded to GitHub Security tab (future)
- Pushed to S3 for audit trails (future)
- Parsed for policy enforcement (future)

## Tips

- Keep unit/integration tests fast to encourage running them continually
- Use markers (`smoke`, `tutorial`, `slow`) so long-running suites stay opt-in outside nightly/release flows
- If a change impacts infrastructure or cross-service contracts, treat the security scan and preflight as mandatory before merging
- **Security:** Run `fast` or `medium` profiles locally during development; let CI handle `standard` and `full` profiles to save time
- Commit changes before running security scans - Dagger needs a stable workspace
- Add project-specific excludes to `dagger_modules/security/security_module/constants.py` if scans fail with "no space left on device"
