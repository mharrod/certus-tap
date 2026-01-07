# Changelog

All notable changes to Certus TAP will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

### Changed

### Fixed

### Security

## [0.0.1] - YYYY-MM-DD

### Added
- Initial project structure
- Certus Ask: RAG-based document querying
- Certus Assurance: Security scanning with SARIF/SBOM
- Certus Trust: Signature verification and provenance
- Certus Integrity: Rate limiting and request filtering
- Certus Transform: Document ingestion with PII detection
- Docker Compose development environment
- LocalStack integration for S3/AWS services
- OpenSearch for semantic and keyword search
- Neo4j for knowledge graph queries
- Haystack pipeline for NLP processing
- Basic tutorial documentation
- Getting started guide

---

## Guidelines for Maintaining This Changelog

### When to Update
- Update this file with every meaningful change
- Group changes under [Unreleased] until ready for release
- When releasing, rename [Unreleased] to version number with date

### Categories

Use these sections in order (omit empty sections):

#### Added
- New features, components, or capabilities
- New documentation or tutorials

#### Changed
- Changes to existing functionality
- Updates to dependencies
- Performance improvements
- Documentation updates

#### Deprecated
- Features that will be removed in future versions
- Include migration guidance

#### Removed
- Removed features or functionality
- Breaking changes (also note in migration guide)

#### Fixed
- Bug fixes
- Documentation corrections
- Security patches (non-sensitive)

#### Security
- Security-related changes
- Vulnerability fixes
- DO NOT disclose details of unfixed vulnerabilities

### Version Numbering

Following [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking changes, incompatible API changes
- **MINOR** (0.X.0): New features, backwards-compatible
- **PATCH** (0.0.X): Bug fixes, backwards-compatible

Pre-release versions:
- **Alpha**: 0.0.X-alpha.Y (early development, unstable)
- **Beta**: 0.0.X-beta.Y (feature complete, testing)
- **RC**: 0.0.X-rc.Y (release candidate)

### Example Entry

```markdown
## [1.2.0] - 2026-03-15

### Added
- Support for PostgreSQL as alternative to OpenSearch (#123)
- API rate limiting per workspace (#145)
- New tutorial: Hybrid search workflows

### Changed
- Upgraded Haystack to v2.0 (#156)
- Improved error messages in ingestion pipeline
- Updated getting-started guide for clarity

### Fixed
- Memory leak in document processing (#167)
- Broken links in trust tutorials (#172)

### Security
- Updated dependencies to patch CVE-2026-1234
```

### Tips

- **Be specific**: "Fixed bug in search" → "Fixed search returning duplicate results for queries with wildcards"
- **Link to issues**: Reference Zulip threads or commit hashes where relevant
- **User perspective**: Write for end users, not developers
- **Breaking changes**: Clearly mark and explain migration path
- **Date format**: Use ISO 8601 (YYYY-MM-DD)

---

## Version History

<!-- Links to version diffs will go here when using Git tags -->
<!-- [Unreleased]: https://github.com/mharrod/certus-tap/compare/v0.1.0...HEAD -->
<!-- [0.1.0]: https://github.com/mharrod/certus-tap/releases/tag/v0.1.0 -->
