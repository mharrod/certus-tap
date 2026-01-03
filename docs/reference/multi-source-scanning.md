# Multi-Source Scanning Guide

Certus Assurance supports scanning code from multiple source types, not just git repositories. This guide covers all supported source types and how to use them.

## Supported Source Types

| Source Type | Description | Use Case |
|------------|-------------|----------|
| **git** | Clone from git repository (default) | Standard CI/CD workflows, version-controlled projects |
| **directory** | Scan local filesystem directory | Development, local testing, non-git projects |
| **archive** | Upload and scan compressed archive | Supply chain analysis, artifact scanning, CI artifacts |

## 1. Git Source (Default)

Scan code from a git repository. This is the original and default behavior.

### API Request

```bash
curl -X POST http://localhost:8056/v1/security-scans \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "my-workspace",
    "component_id": "my-app",
    "assessment_id": "assess_001",
    "source_type": "git",
    "git_url": "https://github.com/example/my-app.git",
    "branch": "main",
    "manifest": {
      "product": "my-app",
      "version": "1.0",
      "profiles": [{"name": "light", "description": "Security scan", "tools": []}]
    }
  }'
```

### Source-Type Field (Optional)

Since `git` is the default, you can omit `source_type`:

```json
{
  "workspace_id": "my-workspace",
  "component_id": "my-app",
  "assessment_id": "assess_001",
  "git_url": "https://github.com/example/my-app.git",
  "manifest": {...}
}
```

### Provenance Tracking

For git sources:
- **Provenance ID**: Git commit SHA
- **Metadata**: Includes commit SHA, branch name, git URL

## 2. Directory Source (Phase 1)

Scan a local directory without requiring git. Perfect for development and testing.

### Use Cases

- Scanning work-in-progress code during development
- Testing security scanners on local codebases
- Scanning projects not in version control
- Scanning SVN, Mercurial, or other VCS projects

### API Request

```bash
curl -X POST http://localhost:8056/v1/security-scans \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "my-workspace",
    "component_id": "my-app",
    "assessment_id": "assess_002",
    "source_type": "directory",
    "directory_path": "/path/to/my/project",
    "manifest": {
      "product": "my-app",
      "version": "1.0-dev",
      "profiles": [{"name": "light", "description": "Security scan", "tools": []}]
    }
  }'
```

### Important Notes

1. **Path Requirements**:
   - Must be an absolute path
   - Must exist and be readable by the Certus Assurance service
   - For Docker deployments, the path must be mounted into the container

2. **Docker Volume Mounting**:
   ```yaml
   # docker-compose.yml
   services:
     certus-assurance:
       volumes:
         - /local/projects:/scans  # Mount your local directory
   ```

   Then reference the mounted path:
   ```json
   {
     "source_type": "directory",
     "directory_path": "/scans/my-project"
   }
   ```

3. **No Cleanup**: Directory sources are NOT deleted after scanning (unlike git clones)

### Provenance Tracking

For directory sources:
- **Provenance ID**: SHA256 hash of directory contents
- **Metadata**: Includes directory path, content hash
- **Hash Calculation**: Reproducible hash based on file paths and contents

## 3. Archive Source (Phase 2)

Upload and scan compressed archive files (.tar.gz, .zip, etc.).

### Use Cases

- Supply chain security: Scanning third-party libraries
- Artifact scanning: Scanning build artifacts
- CI/CD integration: Scanning packaged code
- Offline scanning: No git server required

### Supported Formats

- `.tar`
- `.tar.gz` / `.tgz`
- `.tar.bz2`
- `.zip`

### Two-Step Process

#### Step 1: Upload Archive

```bash
curl -X POST http://localhost:8056/v1/security-scans/upload-archive \
  -F "file=@/path/to/my-app-1.0.tar.gz"
```

Response:
```json
{
  "archive_path": "/artifacts/uploads/1735488000000_my-app-1.0.tar.gz",
  "archive_hash": "a1b2c3d4e5f6...",
  "filename": "my-app-1.0.tar.gz",
  "size": 1048576
}
```

#### Step 2: Scan Uploaded Archive

```bash
curl -X POST http://localhost:8056/v1/security-scans \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "my-workspace",
    "component_id": "third-party-lib",
    "assessment_id": "assess_003",
    "source_type": "archive",
    "archive_path": "/artifacts/uploads/1735488000000_my-app-1.0.tar.gz",
    "manifest": {
      "product": "third-party-lib",
      "version": "1.0",
      "profiles": [{"name": "light", "description": "Security scan", "tools": []}]
    }
  }'
```

### Provenance Tracking

For archive sources:
- **Provenance ID**: SHA256 hash of the archive file
- **Metadata**: Includes archive path, archive hash, original filename
- **Cleanup**: Extracted contents are deleted after scanning

## Comparison Matrix

| Feature | Git | Directory | Archive |
|---------|-----|-----------|---------|
| **Setup** | Clone repository | Mount directory | Upload file |
| **Provenance** | Git commit SHA | Content hash | Archive hash |
| **Cleanup** | ✓ (temp clone deleted) | ✗ (preserved) | ✓ (extracted files deleted) |
| **Requires VCS** | ✓ Git only | ✗ Any or none | ✗ None |
| **Network Access** | May require | No | No |
| **CI/CD Integration** | ✓ Excellent | ✓ Good | ✓ Excellent |
| **Reproducibility** | ✓ Perfect (SHA) | ~ Good (hash) | ✓ Perfect (hash) |

## Metadata Differences

Each source type produces slightly different metadata in scan results:

### Git Source Metadata

```json
{
  "source_type": "git",
  "provenance_id": "abc123def456...",
  "git_url": "https://github.com/example/repo.git",
  "git_commit": "abc123def456...",
  "branch": "main"
}
```

### Directory Source Metadata

```json
{
  "source_type": "directory",
  "provenance_id": "789xyz...",
  "directory_path": "/scans/my-project",
  "content_hash": "789xyz..."
}
```

### Archive Source Metadata

```json
{
  "source_type": "archive",
  "provenance_id": "456def...",
  "archive_path": "/artifacts/uploads/1735488000000_app.tar.gz",
  "archive_hash": "456def...",
  "archive_name": "app.tar.gz"
}
```

## Validation Rules

The API validates that the correct fields are provided for each source type:

| Source Type | Required Fields | Optional Fields |
|------------|----------------|-----------------|
| **git** | `git_url` | `branch`, `commit` |
| **directory** | `directory_path` | None |
| **archive** | `archive_path` | None |

### Error Examples

Missing git_url for git source:
```bash
❌ Error: "git_url is required when source_type='git'"
```

Missing directory_path for directory source:
```bash
❌ Error: "directory_path is required when source_type='directory'"
```

Missing archive_path for archive source:
```bash
❌ Error: "archive_path is required when source_type='archive'"
```

## Best Practices

### 1. Git Source

- ✓ Use specific commit SHAs for reproducibility
- ✓ Use local git paths for offline development: `file:///path/to/repo.git`
- ✓ Preferred for production CI/CD workflows

### 2. Directory Source

- ✓ Mount volumes carefully in Docker environments
- ✓ Use absolute paths
- ✓ Ideal for local development and testing
- ⚠ Content hash changes with any file modification

### 3. Archive Source

- ✓ Use for scanning third-party dependencies
- ✓ Perfect for air-gapped environments
- ✓ Archive hash provides perfect reproducibility
- ⚠ Remember to upload the archive first

## Example Workflows

### Development Workflow (Directory)

```bash
# 1. Develop code locally
cd ~/projects/my-app

# 2. Mount directory in docker-compose.yml
# volumes:
#   - ~/projects:/scans

# 3. Scan local directory
curl -X POST http://localhost:8056/v1/security-scans \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "dev",
    "component_id": "my-app",
    "assessment_id": "dev_'$(date +%s)'",
    "source_type": "directory",
    "directory_path": "/scans/my-app",
    "manifest": {...}
  }'
```

### CI/CD Workflow (Git)

```bash
# 1. Triggered by git push

# 2. Scan specific commit
curl -X POST http://localhost:8056/v1/security-scans \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "production",
    "component_id": "my-app",
    "assessment_id": "ci_'$CI_PIPELINE_ID'",
    "source_type": "git",
    "git_url": "'$CI_REPOSITORY_URL'",
    "commit": "'$CI_COMMIT_SHA'",
    "manifest": {...}
  }'
```

### Supply Chain Workflow (Archive)

```bash
# 1. Download third-party library
wget https://example.com/lib-1.0.tar.gz

# 2. Upload to Certus
ARCHIVE_RESPONSE=$(curl -X POST http://localhost:8056/v1/security-scans/upload-archive \
  -F "file=@lib-1.0.tar.gz")

ARCHIVE_PATH=$(echo $ARCHIVE_RESPONSE | jq -r '.archive_path')

# 3. Scan uploaded archive
curl -X POST http://localhost:8056/v1/security-scans \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "supply-chain",
    "component_id": "third-party-lib",
    "assessment_id": "vendor_review_001",
    "source_type": "archive",
    "archive_path": "'$ARCHIVE_PATH'",
    "manifest": {...}
  }'
```

## Troubleshooting

### Directory Not Found

**Error**: `Directory not found: /scans/my-project`

**Solution**: Ensure the directory is mounted in Docker:
```yaml
volumes:
  - /local/path:/scans
```

### Archive Upload Failed

**Error**: `Unsupported file type`

**Solution**: Only these formats are supported: `.tar`, `.tar.gz`, `.tgz`, `.tar.bz2`, `.zip`

### Permission Denied

**Error**: `Failed to read directory`

**Solution**: Ensure the Certus Assurance process has read permissions:
```bash
chmod -R 755 /path/to/project
```

## Migration Guide

### Migrating from Git-Only to Multi-Source

Existing git-based scans continue to work without changes:

**Before (still works)**:
```json
{
  "git_url": "https://github.com/example/repo.git",
  "manifest": {...}
}
```

**After (equivalent)**:
```json
{
  "source_type": "git",
  "git_url": "https://github.com/example/repo.git",
  "manifest": {...}
}
```

**New capability (directory)**:
```json
{
  "source_type": "directory",
  "directory_path": "/scans/my-project",
  "manifest": {...}
}
```

## See Also

- [End-to-End Workflow](./end-to-end-workflow.md) - Complete scanning workflow
- [Architecture: Source Type Support](../../architecture/source-type-support.md) - Implementation details
- [API Reference](../../api/security-scans.md) - Complete API documentation
