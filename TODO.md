# TODO

This file tracks planned enhancements and desired upgrades across all Certus TAP services.

**Status Legend:**
- `[ ]` - Planned/Not Started
- `[~]` - In Progress
- `[x]` - Completed

---

## Certus Ask

### High Priority
- [ ] Add support for additional embedding models (Cohere, OpenAI, etc.)
- [ ] Implement query result caching for performance
- [ ] Add pagination for large result sets
- [ ] Improve error handling and user feedback

### Medium Priority
- [ ] Advanced query syntax (boolean operators, phrase matching)
- [ ] Query history and saved searches
- [ ] Export search results (CSV, JSON, PDF)
- [ ] Multi-workspace search capabilities

### Low Priority
- [ ] GraphQL API support
- [ ] Real-time index updates via webhooks
- [ ] Query suggestions/autocomplete
- [ ] Search analytics and metrics

---

## Certus Assurance

### High Priority
- [ ] Add comprehensive integration tests
- [ ] Support for additional security scanners (Snyk, Grype)
- [ ] Async scanning for large repositories
- [ ] Better error reporting for failed scans

### Medium Priority
- [ ] SBOM vulnerability enrichment from CVE databases
- [ ] Scan scheduling and automation
- [ ] Scan result comparison (diff between versions)
- [ ] Custom security profiles/policies

### Low Priority
- [ ] Container image scanning
- [ ] License compliance checks
- [ ] Dependency graph visualization
- [ ] Integration with CI/CD platforms

---

## Certus Trust

### High Priority
- [ ] Support for additional signing backends (AWS KMS, Azure Key Vault)
- [ ] Batch signature verification for performance
- [ ] Integration with public transparency logs (Rekor)
- [ ] Signature expiration and renewal workflows

### Medium Priority
- [ ] Key rotation automation
- [ ] Multi-signature support
- [ ] Signature revocation mechanism
- [ ] Trust policy enforcement

### Low Priority
- [ ] Hardware security module (HSM) support
- [ ] Notary v2 integration
- [ ] Cosign policy validation
- [ ] Audit trail visualization

---

## Certus Integrity

### High Priority
- [ ] Add comprehensive rate limit testing
- [ ] IP reputation service integration
- [ ] Custom rate limit strategies (per-user, per-endpoint)
- [ ] Real-time alerting for blocked requests

### Medium Priority
- [ ] DDoS mitigation patterns
- [ ] Adaptive rate limiting based on load
- [ ] Rate limit quota management UI
- [ ] Integration with SIEM systems

### Low Priority
- [ ] Geofencing/geographic restrictions
- [ ] Request fingerprinting
- [ ] Bot detection and mitigation
- [ ] Traffic pattern analysis

---

## Certus Transform

### High Priority
- [ ] Add support for DOCX/PPTX formats
- [ ] Streaming ingestion for large files
- [ ] Custom PII detection patterns/rules
- [ ] Better handling of OCR for scanned documents

### Medium Priority
- [ ] Image/diagram extraction from documents
- [ ] Multi-language document support
- [ ] Document classification/tagging
- [ ] Metadata extraction improvements

### Low Priority
- [ ] Audio transcription support
- [ ] Video content extraction
- [ ] Email (.eml, .msg) format support
- [ ] Archive format support (.zip, .tar.gz)

---

## Infrastructure & DevOps

### High Priority
- [ ] Production deployment guides (AWS, DigitalOcean, Azure)
- [ ] Performance benchmarking suite
- [ ] Database migration strategy
- [ ] Backup and disaster recovery procedures

### Medium Priority
- [ ] Horizontal scaling documentation
- [ ] Monitoring and observability setup (Prometheus, Grafana)
- [ ] Log aggregation configuration (ELK, Loki)
- [ ] Secret management best practices

### Low Priority
- [ ] Multi-region deployment guide
- [ ] Cost optimization strategies
- [ ] Auto-scaling configuration
- [ ] Load testing framework

---

## Testing & Quality

### High Priority
- [ ] Comprehensive unit test coverage
- [ ] Integration test suite
- [ ] End-to-end test scenarios

### Medium Priority
- [ ] Performance regression testing
- [ ] Load testing and stress testing
- [ ] Chaos engineering experiments
- [ ] Accessibility testing

### Low Priority
- [ ] Property-based testing
- [ ] Mutation testing
- [ ] Fuzz testing
- [ ] Visual regression testing

---

## Security & Scanning

### High Priority
- [ ] Integrate SAST scanning into CI/CD pipeline
- [ ] Set up automated DAST scanning for running services
- [ ] Configure GitHub security features (Dependabot, Code Scanning, Secret Scanning)
- [ ] Establish security baseline with Certus Assurance self-scanning

### Medium Priority
- [ ] Container image scanning in CI/CD
- [ ] Software Composition Analysis (SCA) for dependencies
- [ ] Infrastructure as Code (IaC) security scanning (Checkov, tfsec)
- [ ] Regular penetration testing schedule
- [ ] Security scorecard tracking (OpenSSF Scorecard)

### Low Priority
- [ ] Runtime Application Self-Protection (RASP)
- [ ] API security testing (fuzzing, injection testing)
- [ ] Security champions program
- [ ] Bug bounty program
- [ ] Third-party security audits

### GitHub-Specific
- [ ] Enable GitHub Advanced Security (if available)
- [ ] Configure GitHub Actions security best practices
- [ ] Set up CodeQL analysis for all languages
- [ ] Enable dependency review in PRs
- [ ] Configure branch protection rules with security checks

### Certus Assurance Integration
- [ ] Self-scan Certus TAP repository weekly
- [ ] Publish scan results to transparency log
- [ ] Create security dashboard from Certus Assurance results
- [ ] Automate security posture reporting
- [ ] Integrate scan results into release process

### Security Monitoring
- [ ] Set up security event monitoring
- [ ] Configure vulnerability disclosure process
- [ ] Establish incident response procedures
- [ ] Create security metrics and KPIs
- [ ] Regular security review meetings

---

## Documentation

### High Priority
- [ ] API reference documentation (OpenAPI/Swagger)
- [ ] Architecture decision records (ADRs)
- [ ] Troubleshooting playbooks
- [ ] Migration guides for version upgrades

### Medium Priority
- [ ] Video tutorials for key workflows
- [ ] Interactive demos
- [ ] Best practices guide
- [ ] Security hardening guide

### Low Priority
- [ ] Case studies and success stories
- [ ] Comparison with alternatives
- [ ] Developer blog/newsletter
- [ ] Community contribution showcase

### Unfinished Tutorials

**High Priority (Complete for v1.0):**
- [ ] Certus Evaluate tutorials (model evaluation, metrics tracking)
- [ ] Certus Protect tutorials (data protection, access control)
- [ ] Security Analyst Capstone (complete end-to-end workflow)
- [ ] Getting Started guide (verify all steps work end-to-end)

**Medium Priority:**
- [ ] Agentic workflows tutorial (multi-agent development)
- [ ] Sovereign deployment tutorial (self-hosted setup)
- [ ] Advanced Ask tutorials (custom embeddings, hybrid retrieval)
- [ ] Advanced Trust tutorials (policy enforcement, key rotation)

**Low Priority:**
- [ ] Performance tuning guides
- [ ] Cost optimization tutorials
- [ ] Migration tutorials (from other RAG systems)
- [ ] Integration tutorials (Slack, Teams, etc.)

---

## Community & Governance

### High Priority
- [ ] Set up Zulip streams
- [ ] Define contribution workflow
- [ ] Code review guidelines
- [ ] Release process documentation

### Medium Priority
- [ ] Code of Conduct
- [ ] Maintainer guide
- [ ] Security disclosure policy
- [ ] Deprecation policy

### Low Priority
- [ ] Community meetings/office hours
- [ ] Swag and branding
- [ ] Conference presentations
- [ ] Academic paper publication

---

## Major Features & Proposals

Large features with detailed design documents in `docs/reference/roadmap/proposals/`:

### Core Services (Partially Implemented)
- [~] [Certus Assurance](docs/reference/roadmap/proposals/core/certus-assurance-proposal.md) - Security scanning (implemented, enhancements ongoing)
- [~] [Certus Trust](docs/reference/roadmap/proposals/core/certus-trust-proposal.md) - Signature verification (implemented, enhancements ongoing)
- [~] [Certus Integrity](docs/reference/roadmap/proposals/core/certus-integrity.md) - Rate limiting (implemented, enhancements ongoing)
- [ ] [Certus Insight](docs/reference/roadmap/proposals/core/certus-insight-proposal.md) - Automated security insights and recommendations
- [ ] [Certus Protect](docs/reference/roadmap/proposals/core/certus-protect-guardrails-proposal.md) - Data protection and guardrails
- [ ] [Certus Evaluate](docs/reference/roadmap/proposals/core/evaluation/) - Model evaluation framework (4 design docs)

### Core Infrastructure
- [x] [Service Layer Migration](docs/reference/roadmap/proposals/core/service-layer-migration-proposal.md) - Refactor to service layer pattern
- [ ] [DigitalOcean Deployment](docs/reference/roadmap/proposals/core/digitalocean-deployment-proposal.md) - Production deployment guide

### AI & Agentic
- [ ] [AAIF Agent Framework](docs/reference/roadmap/proposals/ai/aaif/aaif-agent-framework-proposal.md) - Multi-agent orchestration
- [ ] [AI Agent Trust Framework](docs/reference/roadmap/proposals/ai/aaif/ai-agent-trust-framework-proposal.md) - Trust for AI agents
- [ ] [AgentSecOps](docs/reference/roadmap/proposals/ai/agentsecops/agentsecops-proposal.md) - Security operations for agents
- [ ] [Chat Interface](docs/reference/roadmap/proposals/ai/chat-proposal.md) - Conversational interface
- [ ] [MCP Integration](docs/reference/roadmap/proposals/ai/MCP/mcp-proposal.md) - Model Context Protocol
- [ ] [MCP Trust Pilot](docs/reference/roadmap/proposals/ai/MCP/mcp-trust-pilot-proposal.md) - Trusted MCP servers

### Security
- [x] [Assurance Manifests](docs/reference/roadmap/proposals/security/assurance-manifest-proposal.md) - Security scanning manifests
- [ ] [Authentication & Authorization](docs/reference/roadmap/proposals/security/authentication-authorization-proposal.md) - Auth framework
- [ ] [Dagger Integration](docs/reference/roadmap/proposals/security/dagger-proposal.md) - CI/CD pipelines
- [ ] [Infrastructure Secrets](docs/reference/roadmap/proposals/security/infrastructure-secrets-management.md) - Secrets management
- [ ] [Policy Engine](docs/reference/roadmap/proposals/security/policy-engine-proposal.md) - Policy enforcement
- [ ] [Runtime Security](docs/reference/roadmap/proposals/security/runtime-security-proposal.md) - Runtime protection
- [ ] [Security SLM](docs/reference/roadmap/proposals/security/security-slm-proposal.md) - Security-focused language model

### Miscellaneous
- [ ] [n8n Workflow Integration](docs/reference/roadmap/proposals/misc/n8n-workflow-integration-proposal.md) - Workflow automation
- [ ] [Sovereign AI Platform](docs/reference/roadmap/proposals/misc/sovereign-ai-learning-platform-proposal.md) - Self-hosted learning

**Status Legend:**
- `[ ]` = Proposal exists, not yet implemented
- `[~]` = Partially implemented, ongoing work
- `[x]` = Fully implemented (move to CHANGELOG)

---

## Research & Exploration

Ideas that need investigation before committing (no formal proposals yet):

- [ ] Federated learning for privacy-preserving model training
- [ ] Zero-knowledge proofs for compliance verification
- [ ] Homomorphic encryption for secure computation
- [ ] Differential privacy for data anonymization
- [ ] Blockchain integration for immutable audit logs
- [ ] Quantum-resistant cryptography

---

## Notes

- This is a living document - priorities may shift
- Items marked completed should be moved to CHANGELOG.md
- Breaking changes require documentation in migration guides
- Security-related items should be prioritized appropriately
