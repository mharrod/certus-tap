# Preflight Checks

This directory contains preflight check scripts for verifying that the required services are running before starting tutorials.

## Available Preflight Scripts

### Tutorial-Specific Preflight Checks

| Script | Command | Services Checked | Tutorials |
|--------|---------|------------------|-----------|
| `transform.sh` | `just preflight-transform` | opensearch, localstack, neo4j, ask-backend | Transform tutorials |
| `ask.sh` | `just preflight-ask` | opensearch, neo4j, localstack, ask-backend | Ask tutorials |
| `trust.sh` | `just preflight-trust` | All infrastructure + trust + assurance + transform + ask | Trust tutorials |
| `integrity.sh` | `just preflight-integrity` | victoriametrics, otel-collector, opensearch, ask-backend | Integrity tutorials |
| `assurance.sh` | `just preflight-assurance` | assurance, localstack, victoriametrics, otel-collector | Assurance tutorials (basic) |
| `assurance-verified.sh` | `just preflight-assurance-verified` | assurance, trust, localstack, registry | Assurance tutorials (verified) |

### General Preflight Checks

| Script | Command | Description |
|--------|---------|-------------|
| `all.sh` | `just preflight` | Checks all services (comprehensive) |
| `security-capstone.sh` | `just preflight-security` | Security-specific smoke tests |

## Usage

### Before Starting Tutorials

1. Start the services for your tutorial:
   ```bash
   just transform-up    # For Transform tutorials
   just ask-up          # For Ask tutorials
   just trust-up        # For Trust tutorials
   just integrity-up    # For Integrity tutorials
   just assurance-up    # For Assurance tutorials
   ```

2. Run the corresponding preflight check:
   ```bash
   just preflight-transform
   just preflight-ask
   just preflight-trust
   just preflight-integrity
   just preflight-assurance
   ```

3. If all checks pass ✅, proceed with the tutorial.

### Running Preflight Checks Directly

You can also run preflight scripts directly:

```bash
./scripts/preflight/transform.sh
./scripts/preflight/ask.sh
./scripts/preflight/integrity.sh
```

## What Preflight Checks Do

Each preflight script:

1. **Verifies service availability** - Checks that required HTTP endpoints are responding
2. **Tests connectivity** - Confirms services can be reached (OpenSearch, Neo4j, S3, etc.)
3. **Validates configuration** - Checks environment variables are set (where applicable)
4. **Reports status** - Clear output showing what passed/failed

## Troubleshooting

If a preflight check fails:

1. **Check service status**: `docker compose ps`
2. **View service logs**: `docker compose logs <service-name>`
3. **Restart services**:
   ```bash
   just <tutorial>-down
   just <tutorial>-up
   ```
4. **Check environment**: Ensure `.env` file has required variables

## Adding New Preflight Checks

To add a new tutorial-specific preflight:

1. Create `scripts/preflight/<tutorial>.sh`
2. Use existing scripts as templates
3. Make it executable: `chmod +x scripts/preflight/<tutorial>.sh`
4. Add justfile entry:
   ```justfile
   preflight-<tutorial>:
       @./scripts/preflight/<tutorial>.sh
   ```
5. Document it in this README

## Service Dependencies by Tutorial

### Transform
- **Required**: opensearch, localstack, neo4j, ask-certus-backend
- **Optional**: victoriametrics, otel-collector, dashboards

### Ask
- **Required**: opensearch, neo4j, localstack, ask-certus-backend
- **Optional**: victoriametrics, otel-collector, dashboards

### Trust
- **Required**: All infrastructure + certus-trust + certus-assurance + certus-transform + ask-certus-backend
- **Optional**: rekor, fulcio, registry

### Integrity
- **Required**: victoriametrics, otel-collector, ask-certus-backend
- **Optional**: opensearch, grafana

### Assurance (Basic)
- **Required**: certus-assurance, localstack
- **Optional**: victoriametrics, otel-collector

### Assurance (Verified)
- **Required**: certus-assurance, certus-trust, localstack
- **Optional**: registry, victoriametrics, otel-collector
