# Architecture Decision Records (ADRs)

This section documents significant architectural decisions made during the development of Certus-TAP. Each ADR provides context, rationale, and consequences of important design choices.

## Purpose

ADRs help us:

- **Document decisions** - Why we chose technology X over Y
- **Preserve context** - Understand reasoning years later
- **Enable discussions** - Reference in design reviews and code reviews
- **Track evolution** - See how architecture has changed
- **Onboard developers** - New team members understand the "why"

## Format

Each ADR follows this structure:

- **Status** - Proposed, Accepted, Superseded, Deprecated
- **Context** - Problem being solved, constraints, background
- **Decision** - What we decided and why
- **Consequences** - Positive, negative, and neutral impacts
- **Alternatives** - Options considered and why rejected
- **Related ADRs** - Links to related decisions
- **References** - Links to implementation and documentation

## Status Legend

- **Proposed** - Under consideration, not yet decided
- **Accepted** - Decision made and implemented
- **Superseded** - Replaced by a newer ADR
- **Deprecated** - No longer recommended but may still be used

## Current ADRs

| #                                               | Title                                             | Status   | Date       |
| ----------------------------------------------- | ------------------------------------------------- | -------- | ---------- |
| [0001](0001-structured-logging.md)              | Structured Logging with Structlog and OpenSearch  | Accepted | 2025-11-14 |
| [0002](0002-configuration-management.md)        | Configuration Management with Validation          | Accepted | 2025-11-14 |
| [0003](0003-error-handling.md)                  | Error Handling with Custom Exceptions             | Accepted | 2025-11-14 |
| [0004](0004-type-hints-strategy.md)             | Type Hints and Type Safety                        | Accepted | 2025-11-14 |
| [0005](0005-privacy-design.md)                  | Privacy-First Design with PII Detection           | Accepted | 2025-11-14 |
| [0006](0006-verification-first-storage.md)      | Verification-First Storage Workflow               | Accepted | 2025-11-14 |
| [0007](0007-deployment-topologies.md)           | Deployment Topologies (Hybrid, Self-Hosted, SaaS) | Accepted | 2025-11-15 |
| [0008](0008-separate-evaluate-and-integrity.md) | Separate certus-evaluate from certus-integrity    | Accepted | 2025-11-15 |
| [0009](0009-guardrail-framework.md)             | Guardrail Framework Standardization               | Accepted | 2025-11-15 |
| [0010](0010-observability-strategy.md)          | Unified Observability Strategy                    | Accepted | 2025-11-15 |

## Quick Navigation

### By Topic

**Logging & Observability**

- [ADR-0001: Structured Logging](0001-structured-logging.md)

**Configuration & Deployment**

- [ADR-0002: Configuration Management](0002-configuration-management.md)

**Error Handling & API Design**

- [ADR-0003: Error Handling](0003-error-handling.md)

**Code Quality**

- [ADR-0004: Type Hints Strategy](0004-type-hints-strategy.md)

**Security & Privacy**

- [ADR-0005: Privacy Design](0005-privacy-design.md)
- [ADR-0006: Verification-First Storage](0006-verification-first-storage.md)
- [ADR-0007: Deployment Topologies](0007-deployment-topologies.md)
- [ADR-0009: Guardrail Framework Standardization](0009-guardrail-framework.md)
- [ADR-0010: Unified Observability Strategy](0010-observability-strategy.md)

**Service Architecture**

- [ADR-0008: Separate certus-evaluate from certus-integrity](0008-separate-evaluate-and-integrity.md)

### By Status

**Accepted** - Currently active decisions

- ADR-0001, ADR-0002, ADR-0003, ADR-0004, ADR-0005, ADR-0006, ADR-0007, ADR-0008, ADR-0009, ADR-0010

## Decision Process

When making architectural decisions:

1. **Identify the decision** - What are we deciding?
2. **Gather context** - What's the problem? What are constraints?
3. **Explore alternatives** - What are other approaches?
4. **Decide** - What are we doing and why?
5. **Document** - Create or update ADR
6. **Communicate** - Reference in PR, design docs, meetings
7. **Review** - Discuss with team, get feedback
8. **Accept** - Mark status as Accepted when implemented

## Related Resources

- [Architecture Overview](../index.md)
- [Configuration Management](../Configuration/index.md)
- [Logging Architecture](../Logging/index.md)
- [Error Handling & Type Hints](../index.md#type-hints--error-handling)
- [Privacy Design](../index.md#privacy-first-design)

## Adding New ADRs

When creating a new ADR:

1. Use next sequential number (0006, 0007, etc.)
2. Follow the template format
3. Add entry to this index
4. Update `.pages` navigation
5. Link from related documentation
6. Reference in implementation code comments if relevant

---

**Last Updated**: 2025-11-14
**Maintained By**: Development Team
