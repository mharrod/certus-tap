# Assurance Manifest Quick Reference

This guide summarizes how to author, validate, sign, and consume assurance manifests across Certus TAP. If you need the architectural deep-dive, see `docs/framework/architecture/assurance-manifests/`.

## Purpose
Manifests codify **what** to assess (targets, profiles), **how** to evaluate it (thresholds, guardrails), and **where** to store outputs (raw/golden buckets, OCI repos). They are the contract between manifest authors, Certus-Assurance, Certus-Transform, certus-evaluate, and certus-integrity.

## Authoring Checklist
1. **Start from templates** under `manifests/examples/` (CUE files).
2. **Define targets** (`targets { type: "_repo", git_url: "...", branch: ... }` or other asset types).
3. **Assign profiles** (`profiles.security`, `profiles.ai_eval`, etc.).
4. **Set evaluation thresholds** (`thresholds { faithfulness: 0.7, relevancy: 0.6, deepeval: 0.75 }`).
5. **Bind policies** (`policies { gate: "security-critical", bundle_digest: "<SHA256>" }`).
6. **Declare storage destinations** (`storage.raw_prefix`, `storage.golden_prefix`, `storage.oci_repo`).
7. **Document metadata** (`owners`, `workspace_id`, `component_id`, `risk_tier`).

## Validation Commands
Use the CUE CLI or the helper script:
```bash
cue vet manifests/example.cue schema/manifest_schema.cue
cue export manifests/example.cue > manifest.json
```
or
```bash
uv run scripts/manifest/validate.py --manifest manifests/example.cue
```

## Signing Workflow
1. **Render JSON** with `cue export` or the Python helper.
2. **Bundle** artifacts (manifest JSON + metadata) into an OCI/S3 package:
   ```bash
   uv run scripts/manifest/package.py \
     --manifest manifest.json \
     --out bundle/manifest.tar
   ```
3. **Sign** with cosign (or Certus-Trust):
   ```bash
   cosign sign-blob \
     --key cosign.key \
     --output-signature manifest.sig \
     manifest.json
   ```
4. **Push** bundle to Git/OCI/S3; record the digest for manifests referencing it.

## Runtime Consumption
- **certus-assurance**: Provide `manifest`, `manifest_path`, or `manifest_uri` (file://, s3://, oci://). The service verifies the signature before executing scans and uploads to manifest-defined prefixes.
- **certus-transform**: Reads manifest metadata to route normalized outputs and enforce anonymization rules.
- **certus-evaluate**: Uses manifest thresholds/policy bindings to evaluate RAG responses and guardrails.
- **certus-integrity**: Embeds manifest IDs/digests into `IntegrityDecision` objects so evidence retains provenance.

## Manifest Fields Reference
| Field | Description |
|-------|-------------|
| `version` | Schema version (e.g., `1.0`). |
| `workspace_id` | Workspace slug for isolation. |
| `component_id` | Asset/component under test. |
| `profiles` | Named configs for scanners/evaluators (security, ai, privacy). |
| `thresholds` | Evaluation thresholds with defaults (deepeval, faithfulness, relevancy, guardrail overrides). |
| `policies` | Policy bundle references (OPA/CUE) for certus-assurance/integrity. |
| `targets` | One or more assets (repos, images, datasets, models). |
| `storage` | Raw/golden prefixes, bucket names, OCI repos for artifact placement. |
| `owners` | Emails or IDs for responsible parties. |

## Fetching Manifests in Runtime
Example (Python):
```python
from certus_assurance.manifest import ManifestFetcher

fetcher = ManifestFetcher(settings)
path, sig_path, cleanup = fetcher.fetch("oci://registry/manifest:2025-01")
manifest_text = path.read_text()
# pass `manifest_text` to the pipeline
cleanup()
```

## Best Practices
- **Immutable history**: Use Git tags and OCI digests; avoid mutable latest tags for production.
- **Review & approval**: Enforce CODEOWNERS/PR review before merging manifest changes.
- **Traceability**: Include `manifest_digest` in ingest/eval metadata; certus-evaluate logs already reference it.
- **Environment overrides**: Use manifest composition/imports for dev vs prod differences rather than editing base manifests.

## Troubleshooting
- **Signature failure**: Ensure cosign key references match; verify Rekor connectivity when `mock_sigstore=false`.
- **Threshold missing**: certus-evaluate falls back to defaults; check manifest `thresholds` section was exported.
- **Storage mismatch**: Verify bucket/prefix allowlists on certus-trust; manifests cannot point to arbitrary destinations.
- **Invalid schema**: Update to the latest `schema/manifest_schema.cue`; bump manifest `version` when new fields are added.

## Related Docs
- [Assurance Manifests Architecture](../../framework/architecture/assurance-manifests/)
- [Certus-Assurance Architecture](../../framework/architecture/certus-assurance/)
- [Certus-Evaluate Architecture](../../framework/architecture/certus-evaluate/)
- [System Landscape](../../framework/architecture/system-landscape.md)
