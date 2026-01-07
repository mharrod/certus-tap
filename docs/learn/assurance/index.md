# Certus Assurance Learning Path

>**STATUS:Tutorial is currently in beta. If you have issues see our [Communication & Support guide](../../about/communication.md)**

**Certus Assurance** is a verification-first security scanning service that generates cryptographically signed artifacts for use across the Certus platform.

## What is Certus Assurance?

Certus Assurance orchestrates security scanning tools (Trivy, Bandit, Semgrep, Syft, OWASP ZAP, Checkov, Presidio) and produces:

- **SARIF findings** - standardized security vulnerabilities
- **SBOMs** - software bill of materials (SPDX format)
- **Metadata** - scan configuration and summary
- **Cryptographic signatures** - tamper-proof provenance

These artifacts integrate with:

- **Certus Trust** - verifies signatures before accepting uploads
- **Certus Transform** - stores artifacts in content-addressed S3
- **Certus Ask** - ingests findings for multi-modal querying

## Learning Paths

### 🚀 New to Certus? Start Here

**Recommended path for beginners:**

1. [Quick Start: CLI Scan](quick-start-cli-scan.md) (10 min)
   - Scan a local project with the Dagger module
   - Understand SARIF, SBOM, and metadata
   - Inspect findings manually

2. [Custom Manifests: Tailored Scanning](custom-manifests.md) (15 min)
   - Write Cue manifests to customize scans
   - Compare scanning profiles (light vs standard)
   - Map findings to compliance frameworks

3. [End-to-End Workflow](end-to-end-workflow.md) (20 min)
   - Complete Certus integration: Assurance → Trust → Transform → Ask
   - Query findings with multiple strategies
   - Understand verification-first security

**After completing these tutorials, you'll be able to:**

- Scan projects locally or via API
- Customize scanning behavior with manifests
- Verify artifact provenance cryptographically
- Query findings using keyword, semantic, knowledge graph, and hybrid strategies

---

### 🔧 Ready for Production? Advanced Topics

**For users ready to deploy Certus in CI/CD:**

1. [Managed Service: API Scanning](managed-service-api-scanning.md) (15 min)
   - Scan remote GitHub repositories via API
   - Stream real-time scan logs via WebSocket
   - Compare CLI vs managed service workflows

2. [Custom Scanning Profiles](custom-manifests.md#creating-custom-profiles)
   - Define tool combinations for your stack
   - Set custom severity thresholds
   - Add compliance metadata

3. Reference: [Assurance Manifest Authoring](../../reference/core-reference/assurance-manifest-authoring.md)
   - Complete Cue manifest schema
   - Tool registry and parameters
   - Signing and verification options

**After completing these tutorials, you'll be able to:**

- Integrate Certus into GitHub Actions / GitLab CI
- Scan repositories on every commit
- Enforce custom compliance policies
- Automate artifact uploads to Certus Trust

---

## Tutorials Overview

| Tutorial                                               | Time   | Prerequisites  | What You'll Learn                           |
| ------------------------------------------------------ | ------ | -------------- | ------------------------------------------- |
| [Quick Start: CLI Scan](quick-start-cli-scan.md)       | 10 min | Docker         | Run your first security scan locally        |
| [Custom Manifests](custom-manifests.md)                | 15 min | Quick Start    | Customize scanning with Cue manifests       |
| [Managed Service API](managed-service-api-scanning.md) | 15 min | Docker Compose | Scan remote repos via Certus Assurance API  |
| [End-to-End Workflow](end-to-end-workflow.md)          | 20 min | Docker Compose | Complete integration: scan → verify → query |

---

## Choose Your Path

### I want to scan a local project

→ Start with [Quick Start: CLI Scan](quick-start-cli-scan.md)

### I want to scan a GitHub repository

→ Jump to [Managed Service API](managed-service-api-scanning.md)

### I want to customize scanning tools

→ Read [Custom Manifests](custom-manifests.md)

### I want the complete Certus experience

→ Follow [End-to-End Workflow](end-to-end-workflow.md)

### I want to integrate into CI/CD

→ Start with [Managed Service API](managed-service-api-scanning.md), then read [CI/CD Integration Guide](../../reference/integration/cicd-integration.md)

---

## Key Concepts

### Scanning Modes

**Sample Mode** (default for tutorials):

- Uses pre-generated artifacts from `samples/non-repudiation/scan-artifacts/`
- Works offline without scanner dependencies
- Fast and suitable for learning

**Production Mode** (real scanning):

- Runs actual security tools (Trivy, Semgrep, Bandit, etc.)
- Requires `security_module` installed
- Scans real repositories and generates fresh findings

Check your mode:

```bash
curl http://localhost:8056/health | jq .scanning_mode
```

### Scanning Profiles

Pre-configured tool combinations:

- **light** - 7 tools, ~2-3 min, good for CI/CD
  - Ruff, Bandit, detect-secrets, Opengrep, Trivy, Privacy, Syft
- **standard** - Same tools as light, stricter thresholds
- **polyglot** - Python + JavaScript tools, ~5-7 min
- **comprehensive** - All available tools, ~10-15 min

See [Custom Manifests](custom-manifests.md#comparing-profiles) for details.

### Artifact Types

Every scan produces:

- **manifest.json** - Configuration, metadata, identifiers
- **summary.json** - High-level findings summary
- **{tool}.sarif.json** - Tool-specific findings (SARIF format)
- **syft.spdx.json** - Software Bill of Materials
- **verification-proof.json** - Cryptographic signature

### Identifiers

Certus uses a 4-level hierarchy:

- **workspace_id** - Organization or team (e.g., `acme-corp`)
- **component_id** - Project or repository (e.g., `payment-service`)
- **assessment_id** - Unique scan instance (e.g., `assess_abc123`)
- **test_id** - Individual finding (e.g., `bandit_B608`)

See [Workspace Identifiers](../../reference/core-reference/workspace-identifiers.md) for details.

---

## Integration with Certus Platform

Certus Assurance is one component in the Certus security platform:

```
┌─────────────────┐
│ Certus Assurance│  Generate security artifacts
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Certus Trust   │  Verify cryptographic signatures
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Certus Transform│  Upload to S3 storage
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Certus Ask    │  Query findings with AI
└─────────────────┘
```

**Unique value:** Artifacts are cryptographically verified before being trusted. This ensures findings are traceable to authorized scans and haven't been tampered with.

See [End-to-End Workflow](end-to-end-workflow.md) for the complete integration.

---

## Common Use Cases

### Use Case 1: Developer Scanning (Local)

**Goal:** Scan my code before committing

**Path:**

1. [Quick Start: CLI Scan](quick-start-cli-scan.md)
2. [Custom Manifests](custom-manifests.md) (optional)

**Tools:** Dagger module (CLI)
**Time:** 2-5 minutes per scan

---

### Use Case 2: CI/CD Integration

**Goal:** Scan every commit in GitHub Actions

**Path:**

1. [Managed Service API](managed-service-api-scanning.md)
2. [CI/CD Integration Guide](../../reference/integration/cicd-integration.md)

**Tools:** Certus Assurance API
**Time:** 2-5 minutes per commit

---

### Use Case 3: Security Auditing

**Goal:** Generate compliance reports for auditors

**Path:**

1. [Quick Start: CLI Scan](quick-start-cli-scan.md)
2. [Custom Manifests](custom-manifests.md)
3. [End-to-End Workflow](end-to-end-workflow.md) (Step 11: Compliance Reports)

**Tools:** Assurance + Ask
**Output:** OWASP Top 10, CWE Top 25, PCI-DSS reports

---

### Use Case 4: Vulnerability Research

**Goal:** Query findings across multiple repositories

**Path:**

1. [Managed Service API](managed-service-api-scanning.md) - scan multiple repos
2. [End-to-End Workflow](end-to-end-workflow.md) - query with Ask

**Tools:** Assurance API + Ask API
**Strategies:** Semantic search, knowledge graphs

---

## Getting Help

### Troubleshooting

For detailed troubleshooting, see:

- **[Certus Assurance Troubleshooting Guide](../../reference/troubleshooting/certus_assurance.md)** - Comprehensive scanning issue resolution
- **[General Troubleshooting](../../reference/troubleshooting/README.md)** - Cross-component issues

**Quick fixes:**

- **Scan fails with "security_module not found"** - [Switch to sample mode or install module](../../reference/troubleshooting/certus_assurance.md#security_module-not-found)
- **No findings in Certus Ask** - [Check ingestion status](../../reference/troubleshooting/certus_ask.md)
- **Services won't start** - [Check Docker resources](../../reference/troubleshooting/README.md#service-wont-start)

### Reference Documentation

- [Assurance API Reference](../../reference/core-reference/README.md)
- [Manifest Authoring](../../reference/core-reference/assurance-manifest-authoring.md)
- [Workspace Identifiers](../../reference/core-reference/workspace-identifiers.md)
- [Provenance Verification](../../reference/core-reference/provenance-verification.md)

### Additional Learning

- [Trust Tutorials](../trust/README.md) - Learn about signature verification
- [Ask Tutorials](../ask/README.md) - Deep dive into querying strategies
- [Architecture Overview](../../architecture/README.md) - How Certus components interact

---

## What's Next?

After completing the tutorials:

1. **Integrate into your workflow**
   - Add Certus to your CI/CD pipeline
   - Scan repositories on every commit
   - Set up automated compliance reports

2. **Customize for your stack**
   - Create custom scanning profiles
   - Add proprietary compliance frameworks
   - Define organization-specific policies

3. **Explore advanced features**
   - Multi-repository analysis with Certus Ask
   - Vulnerability trend analysis
   - Attack path discovery with knowledge graphs

4. **Contribute**
   - Report issues on GitHub
   - Contribute tool integrations
   - Share custom manifests with the community

---

## Quick Links

- **GitHub:** [certus-tech/certus-TAP](https://github.com/certus-tech/certus-TAP)
- **API Docs:** [http://localhost:8056/docs](http://localhost:8056/docs) (when running)
- **Issues:** [GitHub Issues](https://github.com/certus-tech/certus-TAP/issues)
- **Discussions:** [GitHub Discussions](https://github.com/certus-tech/certus-TAP/discussions)

---

**Ready to get started?** → [Quick Start: CLI Scan](quick-start-cli-scan.md)
