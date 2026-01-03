# Certus Dagger Security Module

This directory is designed to be **copied or exported** as a standalone Dagger
module. Everything required to run security profiles (code, configs,
tests, sample privacy data) lives here so partner organizations can import the
module without depending on the rest of Certus TAP.

## Layout

```
dagger_modules/security/
├── assets/privacy-pack/        # bundled PII sample corpus (copied from TAP)
├── config/                     # Opengrep baselines & other configs
├── tests/                      # module-local tests
├── security_module/            # Python package (main/cli/sast/etc.)
│   ├── scripts/                # standalone Python scripts for scans
│   ├── main.py                 # Dagger module entry points
│   ├── cli.py                  # CLI interface
│   └── sast.py                 # pipeline implementation
├── dagger.json                 # module manifest
└── pyproject.toml              # packaging metadata
```

## Security Profiles

The module provides 5 profiles optimized for different use cases:

| Profile      | Tools                        | Duration | Use Case                                |
| ------------ | ---------------------------- | -------- | --------------------------------------- |
| **smoke**    | Ruff                         | ~20 sec  | CI health check, verify toolchain works |
| **fast**     | Ruff, Bandit, detect-secrets | ~2 min   | Pre-commit hooks, local development     |
| **medium**   | fast + Opengrep              | ~4 min   | Pre-push sanity checks                  |
| **standard** | fast + Trivy + SBOM          | ~10 min  | PR gates, CI default, supply chain      |
| **full**     | standard + Opengrep + privacy | ~15 min  | Releases, comprehensive analysis        |

**Legacy:** `light` profile is aliased to `full` for backward compatibility.

## Running via Dagger

```bash
# Quick smoke test
dagger call --mod dagger_modules/security smoke \
  --source . \
  --export-path /tmp/security-results

# Fast profile (recommended for pre-commit)
dagger call --mod dagger_modules/security fast \
  --source . \
  --export-path /tmp/security-results

# Standard profile (recommended for CI)
dagger call --mod dagger_modules/security standard \
  --source . \
  --privacy-assets dagger_modules/security/assets/privacy-pack \
  --export-path /tmp/security-results

# Full profile (comprehensive)
dagger call --mod dagger_modules/security full \
  --source . \
  --privacy-assets dagger_modules/security/assets/privacy-pack \
  --export-path /tmp/security-results
```

Each run writes to `/tmp/security-results/<bundle_id>/` (default `<timestamp>-<git-sha>`).
The Python CLI automatically refreshes `/tmp/security-results/latest`; when invoking
the module via `dagger call`, run `python scripts/promote_latest.py /tmp/security-results`
afterward to update the symlink (or copy on platforms without symlink support).

## Running via CLI

```bash
# Fast profile for local development
PYTHONPATH=dagger_modules/security uv run python -m security_module.cli \
  --workspace . \
  --export-dir /tmp/security-results \
  --profile fast

# Standard profile for CI
PYTHONPATH=dagger_modules/security uv run python -m security_module.cli \
  --workspace . \
  --export-dir /tmp/security-results \
  --profile standard \
  --bundle-id optional-name
```

### Maintaining `latest`

Host-side symlinks/copies cannot be created from inside the Dagger module runtime.
If you rely on `dagger call`, execute:

```bash
python dagger_modules/security/scripts/promote_latest.py build/security-light
```

after each run to point `build/security-light/latest` at the newest bundle (the script
falls back to copying if symlinks are unavailable).

When copied to its own repository, keep the same structure so `dagger call`
finds `dagger.json` at the module root.

## Excluding Files from Scans

The module automatically excludes common directories (`.git`, `.venv`, `node_modules`, `build`, etc.)
using Dagger's `exclude` parameter.

### Default Exclusions

The module excludes these by default:

- `.git`, `.venv`, `venv`, `env`, `test_venv`
- `node_modules`, `dist`, `build`, `site`
- `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`
- `*.egg-info`, `.tox`, `.nox`
- Binary files: `*.so`, `*.dylib`
- `.DS_Store`

### Customizing Exclusions

**Option 1: Modify the module (for permanent project-specific exclusions)**

Edit `dagger_modules/security/security_module/constants.py` and add patterns to `EXCLUDES`:

```python
EXCLUDES = [
    # ... existing excludes ...
    "my_custom_venv",   # Your custom virtual environment
    "data",             # Large datasets
    "models",           # ML model files
    "*.pth",            # PyTorch weights
]
```

**Option 2: Scan a subdirectory (for one-off scans)**

Target a specific directory instead of the entire project:

```bash
dagger call --mod dagger_modules/security smoke --source ./src
```

### Troubleshooting: "No space left on device"

If scans fail with disk space errors:

1. **Add project-specific excludes** to `constants.py` (large datasets, ML models, custom venvs)
2. **Scan a subdirectory** instead of the entire project (see Option 2 above)
3. **Clean up Dagger cache**:
   ```bash
   docker system prune -a
   ```

## Testing

The module ships with colocated tests:

```bash
uv run pytest dagger_modules/security/tests
```

If you split this directory into its own repo, keep the same command (or add a
dedicated `just` target) so CI can validate that assets/configs remain in sync.
