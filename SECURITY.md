# Security Policy

## Supported Versions

Certus TAP is currently in **Pre-Alpha / Experimental** status. Security updates are provided on a best-effort basis for the latest development version only.

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |
| < main  | :x:                |

**Note:** This project is not production-ready. Use in production environments is strongly discouraged until a stable release is announced.

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue in Certus TAP, please report it responsibly.

### How to Report

**DO NOT** open a public GitHub issue for security vulnerabilities.

Instead, please report security issues via one of the following methods:

1. **GitHub Security Advisories** (Preferred)
   - Navigate to the [Security tab](../../security/advisories)
   - Click "Report a vulnerability"
   - Fill out the advisory form with details

2. **Email**
   - Send details to: [security contact - update this email]
   - Include "SECURITY" in the subject line
   - Provide detailed information about the vulnerability

### What to Include

When reporting a vulnerability, please include:

- **Description** of the vulnerability
- **Steps to reproduce** the issue
- **Potential impact** (what could an attacker do?)
- **Affected versions** (if known)
- **Suggested fix** (if you have one)
- **Your contact information** for follow-up

### What to Expect

1. **Acknowledgment**: We will acknowledge receipt within 48 hours
2. **Assessment**: We will investigate and assess the severity within 5 business days
3. **Updates**: We will keep you informed of our progress
4. **Resolution**: We will work on a fix and coordinate disclosure timing with you
5. **Credit**: We will credit you in the security advisory (unless you prefer to remain anonymous)

### Disclosure Policy

- **Coordinated Disclosure**: We follow a coordinated disclosure process
- **Embargo Period**: We typically request a 90-day embargo to develop and test fixes
- **Public Disclosure**: After fixes are released, we will publish a security advisory
- **CVE Assignment**: For serious vulnerabilities, we will request a CVE identifier

## Security Best Practices for Users

### Pre-Alpha Warning

⚠️ **This project is experimental and not security-hardened for production use.**

If you choose to deploy Certus TAP in any environment:

### General Recommendations

1. **Isolate deployments** - Use network segmentation and firewalls
2. **Keep dependencies updated** - Regularly update Python packages and system libraries
3. **Use strong authentication** - Implement proper access controls
4. **Encrypt data** - Use TLS/SSL for all network communication
5. **Monitor logs** - Set up logging and monitoring for suspicious activity
6. **Limit exposure** - Don't expose services directly to the internet
7. **Review configuration** - Check `.env` files and ensure secrets aren't committed

### Known Security Considerations

- **Development Mode**: Many services run in development mode with reduced security
- **Default Credentials**: Change all default passwords and API keys
- **LocalStack**: Uses test AWS credentials - never use real AWS credentials
- **Docker Compose**: Default configs prioritize ease of use over security
- **Trust Services**: Sigstore/Rekor are configured for testing, not production PKI

## Security Features

Certus TAP includes several security-focused components:

### Certus Trust
- Artifact signing and verification using Sigstore
- Transparency logs via Rekor
- SLSA provenance generation

### Certus Assurance
- SAST (Static Application Security Testing) scanning
- SBOM (Software Bill of Materials) generation
- Vulnerability scanning with Trivy
- Secret detection
- Privacy scanning for PII

### Certus Integrity
- Rate limiting and abuse prevention
- Request validation and sanitization
- Audit logging
- Guardrails for LLM interactions

See [docs/framework/workflows/assurance.md](docs/framework/workflows/assurance.md) for more details.

## Security Scanning

This repository uses automated security scanning:

- **Bandit** - Python security linter
- **Semgrep** - Static analysis for security patterns
- **Trivy** - Container and dependency scanning
- **detect-secrets** - Secret detection
- **GitHub Dependabot** - Dependency vulnerability alerts (coming soon)

## Third-Party Dependencies

We regularly update dependencies to address security vulnerabilities. See `pyproject.toml` and `uv.lock` for current versions.

### Known Vulnerable Dependencies

We track known vulnerable dependencies and work to update or mitigate them. Check GitHub Security Advisories for current status.

## Security-Related Configuration

### Environment Variables

Never commit sensitive environment variables to version control:

- `.env` is gitignored
- `.env.example` contains safe template values
- Use secrets management in production deployments

### Docker Security

- Container images should be scanned before deployment
- Use non-root users where possible
- Limit container capabilities
- Keep base images updated

## Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmarks](https://www.cisecurity.org/benchmark/docker)
- [SLSA Framework](https://slsa.dev/)
- [Sigstore Documentation](https://docs.sigstore.dev/)

## Questions?

For general security questions (not vulnerability reports), please open a GitHub Discussion.

---

**Last Updated:** January 2026
