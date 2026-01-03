# Provenance & Attestation Verification

Every Certus Assurance test produces a signed provenance bundle:

- `attestation.intoto.json` – provenance statement emitted by the Dagger module.
- `manifest.json` / `manifest.sig` – the policy executed, plus its verified signature.
- `scan.json` – identifiers, git metadata, and artifact map.

This tutorial shows how to verify those artifacts after a run, regardless of
whether you ran via the CLI or the managed API.

## 1. Locate the Bundle

If you ran locally or via the CLI, the bundle lives under your `--export-dir`
(e.g., `security-results/<test_id>/`). For managed tests, download the bundle
from S3 or use the registry mirror path returned by:

```bash
curl http://localhost:8000/v1/security-scans/<test_id> | jq '.remote_artifacts'
```

## 2. Verify the Manifest Signature

```bash
cosign verify-blob \
  --key cosign.pub \
  --signature manifest.sig \
  manifest.json
```

This proves the manifest in the bundle is identical to the one you authored.
Because Certus Assurance already performed this step before running, failures
here indicate tampering after the fact.

## 3. Inspect `manifest-info.json`

This file contains the resolved profile, tools executed, and manifest digest.
Use it to confirm the requested profile was honored:

```bash
jq . manifest-info.json
```

## 4. Verify the In-Toto Attestation

If you configured Cosign for registry pushes, the scratch image the service
builds is already signed + attested. To verify locally:

```bash
cosign verify-attestation \
  --key cosign.pub \
  --type https://slsa.dev/provenance/v1 \
  registry.example.com/certus-assurance/<test_id>:latest
```

This checks the attestation stored in the registry. To verify the file in the
bundle, use the same `verify-blob` command:

```bash
cosign verify-blob \
  --key cosign.pub \
  --signature attest.sig \
  reports/signing/attestation.intoto.json
```

(If you don’t store a detached signature for the attestation, run `cosign
verify-attestation` against the registry reference instead.)

## 5. Cross-Link With `scan.json`

`scan.json` acts as the control plane record. Confirm the identifiers match the
assessment you intended:

```bash
jq '{workspace_id, component_id, assessment_id, test_id, manifest_digest}' scan.json
```

Use this data to index the artifacts in OpenSearch or another evidence store so
auditors can query “all tests for assessment X.”

## 6. Verify Remote Copies

When artifacts are uploaded to S3 in both raw and golden tiers, object metadata
includes `test_id`, `workspace_id`, `component_id`, `assessment_id`, and
`manifest_digest`. Spot-check by running:

```bash
aws s3api head-object \
  --bucket golden-bucket \
  --key security-scans/<test_id>/golden/scan.json
```

You should see the identifiers in the `Metadata` section.

## 7. Automate Evidence Collection

For audits, automate the previous steps in a pipeline:

1. Download bundle (or read from S3).
2. Verify manifest and attestation signatures.
3. Extract identifiers + manifest digest.
4. Store the results in an evidence database (OpenSearch, Trust, etc.).

This guarantees every test has an independent verification trail and makes it
easy to answer “which manifest executed this attestation?” months later.***
