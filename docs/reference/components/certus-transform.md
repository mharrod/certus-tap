# Certus-Transform

## Purpose

Serve as the on-premises verification and sanitization hub that ingests signed assessment artifacts from Certus-Assurance, validates all signatures, performs privacy redaction, and prepares immutable bundles for upstream publication.

## Audience & Prerequisites

- Platform operators running the verification-first workflow.
- Engineers integrating the mock provenance chain with real scanners.
- Familiarity with the non-repudiation flow (`docs/architecture/NON_REPUDIATION_FLOW.md`) and the verification-first ADR (`docs/architecture/ADRs/0006-verification-first-storage.md`).

## Overview

- Certus-Transform consumes the signed reports produced by Certus-Assurance (or the local SAST pipeline) from customer-controlled storage (typically S3).
- It verifies **every** cosign signature plus in-toto link file to ensure data integrity.
- If validation succeeds, Transform sanitizes and normalizes the dataset (PII removal, redaction) and stages it for publication (OCI registry upload).
- If any verification step fails, Transform rejects the entire assessment, logs an incident, and alerts operators.

## Key Concepts

### Input Expectations

- Directory per assessment (UUID) containing:
  - `SECURITY/`, `SUPPLY_CHAIN/`, `PRIVACY/` subfolders with reports + `.sig` files.
  - `provenance/` folder with `layout.intoto.jsonl` and per-tool `.intoto.jsonl` plus signatures.
  - `scan.json` metadata tying the run back to Certus-Assurance.

### Verification Workflow

1. Enumerate every artifact and corresponding `.sig`.
2. Run `cosign verify-blob` (or `cosign verify --signature`) against each pair using the Certus-Assurance public key.
3. Validate in-toto layout and link files to ensure the workflow definition matches observed products.
4. Abort immediately on any signature failure; do not accept partial results.

### Sanitization & Audit

- Once verified, Transform:
  - Runs additional privacy scans (if required by customer policy).
  - Redacts sensitive paths or filenames.
  - Generates an audit log entry (what was ingested, when, by whom).
  - Packages files for downstream use (OCI layer tarballs, zipped evidence bundles, etc.).

### Publication

- After vetting, Transform pushes the bundle to the OCI registry (Step 4 in the non-repudiation flow) so Certus-Trust can apply the outer signature.

## Workflows / Operations

1. **Monitor inbound bucket/prefix** for new assessment folders (e.g., S3 `s3://assessments/<uuid>/`).
2. **Run verification pipeline** (CLI or automation) that:
   - Downloads artifacts.
   - Executes signature verification for every file.
   - Logs success/failure to the security team.
3. **Perform sanitization** (custom scripts or Streamlit privacy review) if required.
4. **Upload to registry** with provenance intact (e.g., `oras push registry.example.com/certus/<client>:<version>`).
5. **Notify Certus-Trust** (or trigger webhook) that a verified bundle is ready for outer signing.

## Configuration / Interfaces

- Certificates/keys: store Certus-Assurance public key (for signature verification) securely; rotate when the scanner keys rotate.
- Storage config: S3 bucket / prefix or filesystem path where Certus-Assurance drops artifacts (`docs/reference/datalake/storage.md` covers layout).
- CLI helper: Combine `cosign` + `in-toto verify` commands into scripts or workflows.
- OCI registry credentials: required to push sanitized bundles (Step 4).

## Troubleshooting / Gotchas

- **Signature mismatch:** Ensure you’re using the correct Certus-Assurance public key; mismatches usually mean the wrong key or tampered artifact.
- **Partial uploads:** Don’t begin verification until all files (including `.sig`) are present; enforce atomic uploads or use staging prefixes.
- **PII leakage:** Sanitization should run after verification; if redaction modifies files, document the transformation and consider re-signing internally for audit.
- **Registry push failures:** Validate registry credentials and network access; failed pushes leave assessments stuck between Transform and Trust.

## Related Documents

- [Non-Repudiation Flow](../../architecture/NON_REPUDIATION_FLOW.md)
- [Verification-First Storage ADR](../../architecture/ADRs/0006-verification-first-storage.md)
- [Security Scan with Provenance](../../learn/provenance/security-scans.md)
- [Certus Assurance (Component)](certus-assurance.md)
- [Certus Trust (Component)](certus-trust.md)
