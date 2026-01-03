# Testing Architecture

Comprehensive guide to testing in Certus-TAP including fixtures, test patterns, and coverage strategy.

## Overview

The Certus-TAP testing framework provides:

- **Fixture Foundation** - 26+ reusable pytest fixtures for common test scenarios
- **Service Layer Tests** - Comprehensive tests for OpenSearch, S3, and Presidio services
- **Router Tests** - Integration tests for all API endpoints
- **Pipeline Tests** - Edge case handling and error scenarios
- **Docker Integration** - Full-stack testing with real containers
- **85%+ Coverage** - Target coverage across all critical components

## Quick Start

### Run All Tests

```bash
# Install dependencies
uv sync --group dev

# Run all tests
just test

# Fast selection (unit + integration, skips smoke)
just test-fast

# Smoke suites (requires Docker stack)
just test-smoke

# Tutorials and security scans
just test-tutorial
just test-security

# Run specific suites directly
just test-services
just test-routers
```

### Run by Category

```bash
# Only fast tests (skip slow)
uv run python -m pytest -m "not slow"

# Only privacy-related tests
just test-privacy

# Only integration tests (require Docker/moto)
just test-integration

# Only service layer tests
just test-services

# Skip end-to-end smoke suites (default for PRs)
just test-fast

# Run the full smoke stack (requires Docker + LocalStack + Neo4j)
just test-smoke

# Execute long-running tutorial walkthroughs
just test-tutorial
```

!!! tip "Environment defaults & sample data"
Test fixtures now auto-detect whether Docker service names (`ask-certus-backend`, `opensearch`, `localstack`) are resolvable; when they are not, the suite falls back to host-mapped ports (`localhost:8000`, `localhost:9200`, `localhost:4566`). You can override the targets via `API_BASE`, `OS_ENDPOINT`, `LOCALSTACK_ENDPOINT`, `NEO4J_BOLT_URI`, etc. Smoke fixtures also seed LocalStack with the `samples/` corpus automatically, so `just test-fast` no longer requires a manual `just datalake-upload-samples` step.

!!! info "Smoke suites"
`just preflight` and the default CI workflow run `uv run python -m pytest -m "not smoke"` so developers get rapid feedback. Trigger `uv run python -m pytest -m smoke` (or the nightly `smoke-tests.yml` workflow) when you need to exercise the Dockerized stack end-to-end, and `uv run python -m pytest -m tutorial` for the published walkthrough scenarios.

## Documentation Structure

- **[Overview](overview.md)** – Strategy, goals, workflow, and suite entry points.
- **[Fixtures](fixtures.md)** – Complete catalog of shared pytest fixtures.
- **[Service & Router Playbook](service-playbook.md)** – Patterns and tooling for service modules plus FastAPI routers.
- **[Best Practices](best-practices.md)** – Naming, assertions, isolation, and general testing guidance.
- **[Preflight Deep Dive](preflight-deep-dive.md)** – How `./scripts/preflight.sh` exercises the Docker stack.
- **[Security Scanning](security-scanning.md)** – Dagger-powered OpenGrep/Bandit/Trivy pipeline for shift-left security tests.

## Test Coverage

| Component   | Coverage | Tests    |
| ----------- | -------- | -------- |
| Services    | 85%+     | 100+     |
| Routers     | 85%+     | 80+      |
| Pipelines   | 80%+     | 60+      |
| Edge Cases  | 80%+     | 50+      |
| **Overall** | **80%+** | **~300** |

## Key Features

✅ **Fixture Reusability** - No duplicate setup code
✅ **Mocking** - Mock AWS/OpenSearch without containers
✅ **Factory Patterns** - Generate test data dynamically
✅ **Fast Tests** - Unit tests complete in seconds
✅ **Real Tests** - Integration tests with Docker
✅ **Well-Documented** - Every fixture and pattern explained
✅ **Scalable** - Framework grows with codebase

## Getting Started

1. **Read the Overview** - Understand the test structure
2. **Review Available Fixtures** - Know what's available
3. **Look at Examples** - See working test patterns
4. **Write Your Tests** - Follow the patterns for new code
5. **Run and Verify** - Check coverage and pass/fail

## Test Layers

### Unit Tests (Fast - seconds)

Service layer tests using mocks

- OpenSearch operations
- S3 file operations
- Presidio analysis
- Privacy logging

### Integration Tests (Medium - minutes)

Router tests with FastAPI TestClient

- Endpoint request/response
- Request validation
- Error handling
- Response formats

### End-to-End Tests (Slow - minutes)

Full-stack tests with Docker containers

- Complete workflows
- Service interaction
- Resilience scenarios
- Performance benchmarks

## CI/CD Integration

Tests run automatically on:

- Pull requests
- Commits to main branch
- Pre-commit hooks (local)

Coverage must meet:

- 85%+ for service layer
- 85%+ for routers
- 80%+ overall

## Next Steps

- Read [Overview](overview.md) for architecture details
- Check [Fixtures Guide](fixtures.md) for available fixtures
- Review the [Service & Router Playbook](service-playbook.md) for hands-on examples
- Run the test suite locally
