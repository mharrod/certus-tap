# Certus-Trust

## Purpose

Certus-Trust is the cloud service that provides the final, authoritative attestation layer for assessments. It consumes bundles verified by Certus-Transform, revalidates inner signatures, applies an outer cosign signature plus Sigstore attestation, and exposes verification metadata back to Certus TAP.

## Audience & Prerequisites

- Compliance and platform engineers responsible for non-repudiation.
- Developers integrating the mock provenance chain with production signing infrastructure.
- Familiarity with the non-repudiation flow, OCI registries, and Cosign/Sigstore.

## Overview

- Receives immutable assessment artifacts from Certus-Transform (typically via OCI registry).
- Validates inner signatures (produced by Certus-Assurance) to ensure the bundle hasn’t been tampered with.
- Applies its own outer signature and emits a Sigstore attestation, writing both back to the registry/transparency log.
- Publishes verification metadata so downstream systems (Certus Ask, Streamlit, auditors) can confirm chain-of-custody.

## Key Concepts

### Responsibilities

1. **Inner Verification:** Double-check Cosign signatures created by Certus-Assurance (defense in depth).
2. **Outer Signature:** Sign the registry artifact to prove Certus-Trust validated the contents (`cosign sign-blob` or `cosign sign --key <trust-key>`).
3. **Sigstore Attestation:** Record the verification event (who signed, when, digest) and push to the transparency log.
4. **Metadata Publication:** Provide verification proofs back to Certus TAP (via APIs or events) so ingestion pipelines can annotate scans with `chain_verified`, `signer_inner`, `signer_outer`, timestamps, etc.

### Artifact Format

- OCI reference: `registry.example.com/certus/<client>:<version>` with:
  - Assessment layers (security reports, SBOMs, provenance).
  - Inner `.sig` files.
  - Manifest digest.
- Certus-Trust adds:
  - `*.outer.sig` (signed digest).
  - Sigstore attestation referencing the manifest digest.

### Integration Points

- Certus-Transform notifies Certus-Trust when an artifact is ready.
- Trust service emits verification proofs consumed by Certus TAP (e.g., stored alongside Neo4j scan nodes via `_link_verification_to_scan`).
- Streamlit / API endpoints surface verification status to analysts.

## Workflows / Operations

1. **Receive Notification** that a verified bundle exists (webhook, queue, manual trigger).
2. **Pull Artifact** from OCI registry (`oras pull ...@sha256:<digest>`).
3. **Verify Inner Signatures** using the Certus-Assurance public key:
   ```bash
   cosign verify-blob --certificate cosign.pub --signature report.sig report.json
   ```
4. **Sign Artifact** with Certus-Trust key:
   ```bash
   cosign sign --key trust-key.pem registry.example.com/certus/client:v1.0.0
   ```
5. **Record Attestation** (Sigstore transparency log or custom ledger).
6. **Publish Metadata** (REST API/queue) summarizing:
   - `chain_verified = true`
   - `signer_inner = certus-assurance`
   - `signer_outer = certus-trust`
   - `sigstore_timestamp`
   - `verification_timestamp`
7. **Certus Ask Ingestion** reads this metadata to enrich SARIF scans (e.g., `certus_ask/pipelines/neo4j_loaders/sarif_loader.py` links verification info to `SecurityScan` nodes).

## Configuration / Interfaces

- Keys & certificates:
  - Trust signing key (hardware-backed or key management service).
  - Assurance public key (for inner verification).
- Registry credentials for pulling/pushing signatures.
- API endpoints for publishing verification proofs (consumed by Certus TAP ingestion).
- Monitoring/alerting to detect failed verifications.

## Troubleshooting / Gotchas

- **Inner signature failure:** Immediately reject artifact and notify Certus-Transform; treat as potential tampering.
- **Transparency log errors:** Ensure Sigstore connectivity; store attestation locally if log is unreachable and replay later.
- **Key rotation:** Coordinate with Certus-Transform and TAP ingestion when rotating Trust keys; update trusted certificates in TAP config.
- **Clock skew:** Correct timestamps are critical for audit. Ensure Trust nodes use synchronized time (NTP).

## Related Documents

- [Non-Repudiation Flow](../../architecture/NON_REPUDIATION_FLOW.md)
- [Trust Verification Tutorial](../../learn/provenance/verify-trust.md)
- [Security Scan with Provenance](../../learn/provenance/security-scans.md)
- [Certus-Transform (Component)](certus-transform.md)
- [Metadata Envelopes (API)](../api/metadata-envelopes.md) – verification fields surface there.
