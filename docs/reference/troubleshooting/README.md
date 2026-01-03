# Troubleshooting Guide

This section contains troubleshooting guides for Certus components and common issues.

## Quick Diagnosis

### Identify Which Component is Failing

```bash
# Check all services
just preflight

# Check specific service health
curl http://localhost:8056/health | jq .  # Certus Assurance
curl http://localhost:8057/v1/health | jq .  # Certus Trust
curl http://localhost:8100/health | jq .  # Certus Transform
curl http://localhost:8000/health | jq .  # Certus Ask
```

### Common Cross-Component Issues

#### Docker Issues

```bash
# Check Docker is running
docker ps

# Check Docker resources
docker system df

# Restart Docker (macOS with Colima)
colima restart

# Clean up unused resources
docker system prune -a
```

#### Port Conflicts

```bash
# Check what's using ports
lsof -i :8056  # Certus Assurance
lsof -i :8057  # Certus Trust
lsof -i :8100  # Certus Transform
lsof -i :8000  # Certus Ask
lsof -i :9200  # OpenSearch
lsof -i :7687  # Neo4j
lsof -i :5432  # PostgreSQL
lsof -i :4566  # LocalStack (S3)
```

#### Network Issues

```bash
# Test internal networking
docker network ls
docker network inspect certus-network

# Restart networking
docker compose down
docker compose up -d
```

#### Service Won't Start

```bash
# Check logs for errors
docker compose logs <service-name> --tail=50

# Restart specific service
docker compose restart <service-name>

# Restart all services with fresh state
just down
just up
```

## Component-Specific Troubleshooting

- **[Certus Assurance](certus_assurance.md)** - Scanning, profiles, manifests, CLI issues
- **[Certus Trust](certus_trust.md)** - Signature verification, upload permissions, policy issues
- **[Certus Transform](certus_transform.md)** - S3 uploads, artifact storage, bucket issues
- **[Certus Ask](certus_ask.md)** - Query issues, ingestion failures, Neo4j/OpenSearch problems

## Getting Help

If you can't resolve your issue:

1. **Check logs** - Most issues show up in service logs
2. **Check GitHub Issues** - Search existing issues at https://github.com/certus-tech/certus/issues
3. **File a bug** - Create a new issue with logs and reproduction steps
4. **Join community** - Ask in Discord or community channels

## Common Error Patterns

### "Connection refused"

**Symptom:** Service can't connect to another service

**Causes:**

- Service not started
- Wrong port
- Network isolation

**Solution:**

```bash
# Check service is running
docker ps | grep <service-name>

# Check service logs
docker compose logs <service-name>

# Restart services
just down && just up
```

### "Timeout"

**Symptom:** Operation takes too long and times out

**Causes:**

- Large repository/scan
- Insufficient resources
- Slow network

**Solution:**

```bash
# Increase timeout (for Dagger scans)
export DAGGER_TIMEOUT=900  # 15 minutes

# Check system resources
docker stats

# Allocate more resources to Docker
# (Docker Desktop: Settings → Resources)
```

### "Permission denied"

**Symptom:** Can't access files or directories

**Causes:**

- Volume mount permissions
- User/group mismatch

**Solution:**

```bash
# Check volume mounts in docker-compose.yml
# Ensure paths exist and are accessible

# Fix permissions
chmod -R 755 /path/to/directory
```

### "Module not found"

**Symptom:** Python import errors

**Causes:**

- Missing dependencies
- Wrong virtual environment
- Module not installed

**Solution:**

```bash
# Reinstall dependencies
pip install -e .

# Or rebuild Docker container
docker compose build <service-name>
docker compose up -d <service-name>
```

## Reset Everything

If all else fails, completely reset:

```bash
# Stop all services and remove volumes
just down -v

# Clean Docker system
docker system prune -a --volumes

# Remove all Certus data
rm -rf certus-assurance-artifacts/
rm -rf security-results/

# Start fresh
just up
```

**Warning:** This deletes all scan data, artifacts, and database content.
