# Certus Assurance Troubleshooting

This guide covers common issues with Certus Assurance scanning, both CLI and API modes.

## Quick Diagnosis

### Check Service Health

```bash
# Check if service is running
curl http://localhost:8056/health | jq .

# Expected response
{
  "status": "ok",
  "scanning_mode": "sample" | "production",
  "security_module_available": "True" | "False"
}
```

### Check Scanning Mode

Certus Assurance supports two modes:

| Mode       | security_module_available | Behavior                           | Speed       |
|------------|---------------------------|-------------------------------------|-------------|
| **Sample** | False                     | Returns pre-generated mock results  | <5 seconds  |
| **Production** | True                  | Runs real security tools            | 2-5 minutes |

**To switch modes:**

```bash
# Edit certus_assurance/deploy/docker-compose.yml
# Change: CERTUS_ASSURANCE_USE_SAMPLE_MODE=true
# To:     CERTUS_ASSURANCE_USE_SAMPLE_MODE=false

# Restart service
just assurance-down
just assurance-up
```

## CLI Issues

### "command not found: security-scan"

**Cause:** Security module not installed

**Solution:**

```bash
# Option 1: Using pipx (recommended for CLI tools)
pipx install --editable dagger_modules/security

# Option 2: Using pip in a virtual environment
python3 -m venv .venv
source .venv/bin/activate
pip install -e dagger_modules/security

# Verify installation
security-scan --help
```

### "Docker not running"

**Cause:** Docker daemon not started

**Solution:**

```bash
# macOS with Colima
colima start

# Verify Docker is running
docker ps

# Check Docker resources
docker system df
```

### "Dagger timeout"

**Cause:** Scan taking longer than default timeout (especially for large repositories)

**Solution:**

```bash
# Increase timeout for large repos
export DAGGER_TIMEOUT=900  # 15 minutes

# For very large repos (24K+ files)
export DAGGER_TIMEOUT=1800  # 30 minutes
```

### Scan taking too long

**For large repos (24K+ files):**

```bash
# Use faster profiles in CI
security-scan --profile fast --workspace .  # ~1 minute
security-scan --profile medium --workspace .  # ~2 minutes

# Run comprehensive scans less frequently
security-scan --profile light --workspace .  # Only on main branch or nightly
```

### "No findings"

**This is actually good!** It means no security issues were found.

The scan still generates:
- SBOM (list of dependencies)
- Summary metadata
- Attestation artifacts
- Clean bill of health

### Missing SBOM files

**Cause:** Not all profiles generate SBOM

**Solution:** Only these profiles generate SBOM:

```bash
--profile light
--profile full
--profile heavy
--profile javascript
--profile attestation-test
```

### Need JavaScript/Node.js scanning

**Solution:**

```bash
# Use the javascript profile
security-scan --profile javascript --workspace .

# This runs: eslint-security, retire-js, detect-secrets, trivy, sbom, attestation
```

## API/Service Issues

### Service not running

**Check Docker containers:**

```bash
# Check if container is running
docker ps | grep certus-assurance

# View logs
docker logs certus-assurance --tail=50

# Restart service
just assurance-down
just assurance-up
```

### Scan stuck in QUEUED

**Causes:**
- Worker capacity exhausted
- Service crashed
- Sample mode but missing artifacts
- Production mode without security tools

**Check status:**

```bash
# Check scan status
curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq '{status, error}'

# Check worker capacity
curl -s http://localhost:8056/stats | jq '.scans_by_status'

# Check scanning mode
curl http://localhost:8056/health | jq .scanning_mode
```

**Solutions:**

```bash
# View service logs for errors
docker logs certus-assurance -f

# Restart service
just assurance-down
just assurance-up

# If in production mode without tools, switch to sample mode
# Edit docker-compose.yml: CERTUS_ASSURANCE_USE_SAMPLE_MODE=true
```

**Common causes:**

- **Production mode** without security tools installed → Switch to sample mode
- **Sample mode** but sample artifacts missing → Check `samples/non-repudiation/scan-artifacts/` exists
- **Network issues** in production mode → Check git clone access to repository

### Scan fails with error

**Check the error details:**

```bash
# Get scan status and error
curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq '{status, error}'
```

**Common errors:**

#### "security_module not found"

**Cause:** Running in production mode without security module installed

**Solution:**

```bash
# Option 1: Switch to sample mode (for tutorials/demos)
# Edit docker-compose.yml: CERTUS_ASSURANCE_USE_SAMPLE_MODE=true
just assurance-down && just assurance-up

# Option 2: Install security module (for real scanning)
pip install -e dagger_modules/security
just assurance-down && just assurance-up
```

#### "Git clone failed"

**Cause:** Repository URL not accessible or invalid

**Check git URL:**

```bash
# Verify git URL is accessible
git ls-remote https://github.com/user/repo.git

# Check network connectivity
ping github.com
```

**Solutions:**

```bash
# Use specific commit instead of branch
"commit": "7bc2d0d"

# Verify repository is public or credentials are configured
# For private repos, configure git credentials in the service
```

#### "Directory not found"

**Cause:** Volume mount not configured for local directory scans

**Solution:**

```bash
# 1. Add volume mount to docker-compose.yml
volumes:
  - /path/to/your/project:/scans/my-project

# 2. Restart service
just assurance-down
just assurance-up

# 3. Use mounted path in API call
"local_path": "/scans/my-project"
```

#### "Archive upload failed" or "Unsupported file type"

**Cause:** Invalid archive format

**Solution:** Only these formats are supported:
- `.tar`
- `.tar.gz`
- `.tgz`
- `.tar.bz2`
- `.zip`

```bash
# Create valid archive
tar -czf my-project.tar.gz /path/to/project

# Or use zip
zip -r my-project.zip /path/to/project
```

## Profile & Manifest Issues

### Custom manifest fails validation

**Check manifest structure:**

```bash
# Validate JSON syntax
cat manifest.json | jq .

# Check required fields
{
  "product": "my-app",
  "version": "1.0.0",
  "profiles": [
    {
      "name": "my-profile",
      "description": "Description",
      "tools": [{"id": "ruff"}]
    }
  ]
}
```

### Profile name not recognized

**Without manifest:** Must use built-in profile names:
- `smoke`, `fast`, `medium`, `standard`, `light`, `full`, `heavy`, `javascript`, `attestation-test`

**With manifest:** Can use custom profile names that match your manifest

```bash
# With custom manifest
security-scan --manifest ~/my-manifest.json --profile my-custom-profile
```

### Threshold violations

**Expected behavior:** Scans complete but exit with code 2 if findings exceed thresholds

**Check policy results:**

```bash
# View policy results
cat security-results/latest/policy-result.json | jq .

# Example output
{
  "passed": false,
  "violations": [
    "high findings exceeded threshold (15 > 10)"
  ]
}
```

**This is by design for CI/CD:** Artifacts are always exported for review, but pipelines can check the policy result and block deployment.

## Performance Issues

### Scan takes too long

**For large repositories:**

```bash
# Use faster profiles
--profile smoke     # ~30 seconds (linting only)
--profile fast      # ~1 minute (secrets + basic SAST)
--profile medium    # ~2 minutes (balanced)

# Reserve comprehensive scans for nightly/main branch
--profile light     # ~5 minutes (full security + SBOM)
--profile heavy     # ~10+ minutes (includes DAST)
```

### High memory usage

**Solution:**

```bash
# Allocate more resources to Docker
# Docker Desktop: Settings → Resources → Memory (8GB+ recommended)

# Check current usage
docker stats

# Clean up unused resources
docker system prune -a
```

### Disk space issues

**Solution:**

```bash
# Check disk usage
docker system df

# Clean up old images and volumes
docker system prune -a --volumes

# Remove old scan results
rm -rf security-results/*/
rm -rf certus-assurance-artifacts/*/
```

## Artifact Issues

### Missing artifacts after scan

**Check export directory:**

```bash
# Verify artifacts exist
ls -la security-results/latest/

# For API scans
ls -la certus-assurance-artifacts/$SCAN_ID/
```

### Artifacts not uploaded to S3

**This requires the full workflow:** Assurance → Trust → Transform

**Check upload status:**

```bash
# Check upload status
curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq '.upload_status'

# Possible statuses:
# - null or missing: No upload requested
# - "pending": Upload request submitted
# - "permitted": Trust approved, uploading
# - "uploaded": Complete
# - "denied": Trust rejected
```

**See [End-to-End Workflow Troubleshooting](../../learn/assurance/end-to-end-workflow.md#troubleshooting) for upload issues**

## Integration Issues

### Pre-commit hook fails

**Solution:**

```bash
# Use fastest profile for pre-commit
security-scan --profile smoke --workspace .

# Or install via pre-commit framework
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: security-scan
      name: Security Scan
      entry: security-scan --profile smoke --workspace .
      language: system
```

### CI/CD timeout

**Solution:**

```bash
# Increase CI timeout
# GitHub Actions example
timeout-minutes: 15

# Use appropriate profile for CI stage
--profile fast      # PR checks
--profile medium    # Branch protection
--profile standard  # Main branch
--profile light     # Nightly/release
```

## Advanced Troubleshooting

### Enable debug logging

```bash
# For CLI
export DAGGER_DEBUG=1
security-scan --profile light --workspace .

# For service (edit docker-compose.yml)
environment:
  - LOG_LEVEL=DEBUG

# Restart service
just assurance-down && just assurance-up
```

### Examine scan execution

```bash
# View scan summary
cat security-results/latest/summary.json | jq .

# Check which tools ran
cat security-results/latest/summary.json | jq '.executed'

# Check for skipped tools
cat security-results/latest/summary.json | jq '.skipped'
```

### Verify tool output

```bash
# Check individual tool outputs
cat security-results/latest/bandit.json | jq '.results | length'
cat security-results/latest/trivy.sarif.json | jq '.runs[0].results | length'

# View SBOM
cat security-results/latest/sbom.spdx.json | jq '.packages | length'
```

## Getting More Help

If none of these solutions work:

1. **Collect diagnostics:**
   ```bash
   # Service logs
   docker logs certus-assurance --tail=100 > assurance-logs.txt
   
   # Scan status
   curl -s http://localhost:8056/v1/security-scans/$SCAN_ID > scan-status.json
   
   # Health check
   curl http://localhost:8056/health > health.json
   ```

2. **Check GitHub Issues:** https://github.com/certus-tech/certus/issues

3. **File a bug report** with:
   - Error message
   - Service logs
   - Scan configuration
   - Reproduction steps

## See Also

- [Quick Start CLI Tutorial](../../learn/assurance/quick-start-cli-scan.md)
- [Managed Service API Tutorial](../../learn/assurance/managed-service-api-scanning.md)
- [Custom Profiles Tutorial](../../learn/assurance/custom-manifests.md)
- [End-to-End Workflow Troubleshooting](../../learn/assurance/end-to-end-workflow.md#troubleshooting)
- [General Troubleshooting](README.md)
