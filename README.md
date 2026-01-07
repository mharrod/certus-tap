<p align="center">
  <img src="docs/assets/images/logo.png" alt="Agentic RAG TAP Logo" width="150"/>
</p>

# Certus TAP

**Certus TAP** (Transparency, Assurance, and Privacy) is a reference implementation demonstrating trustworthy security assurance workflows. It combines document ingestion, RAG-based querying, security scanning with provenance, rate limiting, and PII detection into a unified platform.

## Status

**Current Phase:** Pre-Alpha / Experimental
V
This project is highly volatile and should be used as a reference implementation rather than production software. Proper testing and security hardening are required before production use.

**Need help?** See our [Communication & Support guide](docs/about/communication.md) or join us on [Zulip](https://certus.zulipchat.com)

## Key Features

- **Certus Ask**: RAG-based document querying with semantic search, keyword search, and knowledge graphs
- **Certus Assurance**: Security scanning (SARIF/SBOM) with cryptographic signing and provenance tracking
- **Certus Trust**: Signature verification, transparency logs, and non-repudiation workflows
- **Certus Integrity**: Rate limiting, request filtering, and compliance evidence generation
- **Certus Transform**: Document ingestion with PII detection, format conversion, and privacy screening

Built with FastAPI, Haystack, OpenSearch, Neo4j, LocalStack, and Sigstore.

## Quick Start

1. Clone the repo and install dependencies: `uv sync --group backend --dev`
2. Copy `.env.example` to `.env` and configure settings
3. Start the documentation server: `just docs-serve`
4. Bring up the stack: `just up`
5. Run preflight checks: `just preflight`

See the [Getting Started guide](docs/learn/getting-started.md) for detailed instructions.

## Documentation

Start the Zensical documentation server with `just docs-serve`, or browse the documentation directly:

- **[Getting Started](docs/learn/getting-started.md)** — local development setup from clean checkout to first RAG query
- **[Learn Tutorials](docs/learn/index.md)** — hands-on guides for Ask, Assurance, Trust, Integrity, and Transform
- **[Framework Reference](docs/framework/index.md)** — technology-agnostic principles and architecture patterns
- **[Installation Guide](docs/installation/index.md)** — environment setup and stack configuration
- **[Reference Docs](docs/reference/index.md)** — component architecture, troubleshooting, and API references

## Contributing & Governance

Certus TAP is in early development. The repository is public to share ideas and research direction.

- **Contributions**: Gated by default. See [participation guidelines](docs/about/participation.md)
- **Governance**: See [GOVERNANCE.md](GOVERNANCE.md) for decision-making and stewardship
- **License**: AGPL v3 — see [LICENSE](LICENSE) for details
