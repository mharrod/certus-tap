# Reference Documentation

Welcome to the Certus TAP reference documentation. This section provides technical specifications, API documentation, component guides, and operational references.

---

## Documentation Structure

### [Core Reference](core-reference/)

Foundational reference materials for working with Certus TAP:

- **[Assurance Manifest Reference](core-reference/assurance-manifest-reference.md)** - Declarative policy and configuration syntax
- **[Local SAST Scanning](core-reference/local-sast-scanning.md)** - Security scanning workflows
- **[Multi-Workspace Isolation](core-reference/multi-workspace-isolation.md)** - Workspace configuration and isolation
- **[Non-Repudiation Flow](core-reference/non-repudation-flow.md)** - Provenance and verification workflows
- **[Troubleshooting](core-reference/troubleshooting.md)** - General troubleshooting guide
- **[Reference Doc Template](core-reference/reference-doc-template.md)** - Template for creating new reference docs

---

### [Architecture](architecture/)

Service layer architecture and design patterns:

- **[Dependency Injection](architecture/dependency-injection.md)** - FastAPI dependency injection patterns
- **[Adding Ingestion Service](architecture/adding-ingestion-service.md)** - How to add new ingestion services

---

### [Components](components/)

Individual Certus component documentation:

- **Certus Assurance** - Evidence storage and validation
- **Certus Integrity** - Service health and observability
- **Certus Transform** - Data transformation pipelines
- **Certus Trust** - Provenance and signing
- **Datalake Orchestration** - S3/LocalStack data management
- **SAST Pipeline** - Security scanning integration
- **Neo4j Guide** - Graph database usage
- **OpenSearch Explorer** - Search and analytics
- **Ollama Configuration** - Local LLM setup
- **Streamlit Console** - UI components
- **Logging Stack** - Structured logging infrastructure

---

### [API Reference](api/)

HTTP API specifications and standards:

- **[API Documentation Standard](api/api-doc-standard.md)** - How to document APIs
- **[API Response Format](api/api-response.md)** - Standard response structure
- **[API Error Codes](api/api-error-codes.md)** - Error handling and codes
- **[API Versioning](api/api-versioning.md)** - Versioning strategy
- **[Metadata Envelopes](api/metadata-envelopes.md)** - Standard metadata wrapper format

---

### [Testing](testing/)

Testing infrastructure, patterns, and guides:

- **[Testing Overview](testing/index.md)** - Testing philosophy and approach
- **[Best Practices](testing/best-practices.md)** - Testing guidelines
- **[Service Layer Testing](testing/service-layer-testing.md)** - How to test FastAPI services
- **[Test Suite Reference](testing/test-suite-reference.md)** - Available test suites
- **[Testing Checklist](testing/testing-checklist.md)** - Pre-commit checklist
- **[Fixtures](testing/fixtures.md)** - Test data and fixtures
- **[Service Playbook](testing/service-playbook.md)** - Service testing playbook
- **[Preflight Deep Dive](testing/preflight-deep-dive.md)** - Preflight check internals

---

### [Logging](logging/)

Structured logging system documentation:

- **[Logging Overview](logging/index.md)** - Purpose and architecture
- **[Getting Started](logging/getting-started.md)** - Quick start guide
- **[Configuration](logging/configuration.md)** - Logger configuration
- **[Usage](logging/usage.md)** - How to use structured logging
- **[OpenSearch](logging/opensearch.md)** - OpenSearch integration
- **[Privacy Operations](logging/privacy-operations.md)** - PII handling in logs
- **[Privacy Queries](logging/privacy-queries.md)** - Querying privacy-sensitive logs
- **[API Reference](logging/api-reference.md)** - Logging API
- **[Troubleshooting](logging/troubleshooting.md)** - Common logging issues

---

### [Troubleshooting](troubleshooting/)

Consolidated troubleshooting guides:

- **[Troubleshooting Index](troubleshooting/index.md)** - Overview and quick links
- **[General Issues](troubleshooting/general.md)** - Common problems across components
- **[Logging Issues](troubleshooting/logging.md)** - OpenSearch and log ingestion
- **[Component Issues](troubleshooting/components.md)** - Component-specific troubleshooting

---

### [Roadmap](roadmap/)

Project roadmap, proposals, and enhancements:

- **[Roadmap Overview](roadmap/README.md)** - Project roadmap introduction
- **[Implementation Priority](roadmap/implemenation-priority.md)** - Prioritized implementation plan
- **[Proposal Submission](roadmap/proposal-submission.md)** - How to submit proposals
- **[Proposal Template](roadmap/PROPOSAL-TEMPLATE.md)** - Template for new proposals
- **[Proposals](roadmap/proposals/)** - Approved and pending proposals
  - [AI Proposals](roadmap/proposals/ai/) - Agent frameworks, MCP, chat interfaces
  - [Core Proposals](roadmap/proposals/core/) - Core services and architecture
  - [Security Proposals](roadmap/proposals/security/) - Security enhancements
  - [Misc Proposals](roadmap/proposals/misc/) - Other proposals

---

## How to Use This Documentation

### By Task

- **Setting up Certus TAP**: Start with [Core Reference](core-reference/)
- **Understanding architecture**: Read [Architecture](architecture/)
- **Integrating with APIs**: Check [API Reference](api/)
- **Writing tests**: See [Testing](testing/)
- **Debugging issues**: Go to [Troubleshooting](troubleshooting/)
- **Understanding future direction**: Review [Roadmap](roadmap/)

### By Role

**Developers**

1. [Architecture](architecture/) - Understand service patterns
2. [API Reference](api/) - Learn API conventions
3. [Testing](testing/) - Write tests
4. [Components](components/) - Component details

**Operators**

1. [Core Reference](core-reference/) - Configuration and setup
2. [Logging](logging/) - Monitor systems
3. [Troubleshooting](troubleshooting/) - Resolve issues
4. [Components](components/) - Component operations

**Contributors**

1. [Roadmap](roadmap/) - Understand priorities
2. [Proposal Submission](roadmap/proposal-submission.md) - Submit ideas
3. [Reference Doc Template](core-reference/reference-doc-template.md) - Document features
4. [Participation](../about/participation.md) - Contribution model

**Researchers**

1. [Roadmap Proposals](roadmap/proposals/) - Research directions
2. [Core Reference](core-reference/) - System capabilities
3. [Components](components/) - Technical details
4. [API Reference](api/) - Integration points

---

## Documentation Standards

All reference documentation should:

- Be technically accurate and up-to-date
- Include practical examples
- Follow the [Reference Doc Template](core-reference/reference-doc-template.md)
- Link to related documentation
- Include version information where applicable

For contributing documentation, see [Participation & Contributions](../about/participation.md).

---

## Quick Links

- [Framework Documentation](../framework/index.md) - Conceptual architecture and workflows
- [Learn](../learn/index.md) - Tutorials and how-to guides
- [About](../about/index.md) - Project vision and principles
- [Participation](../about/participation.md) - How to contribute
- [Governance](../../GOVERNANCE.md) - Project governance
