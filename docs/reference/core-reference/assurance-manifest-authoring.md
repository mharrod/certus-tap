# Authoring & Signing Assurance Manifests

This tutorial walks through building a Cue-based assurance manifest, exporting
JSON, and signing it with Cosign so Certus Assurance can verify the policy
before executing. You will:

1. Choose a preset as a starting point.
2. Customize profiles, controls, and compliance mappings.
3. Export JSON and share it with your team.
4. Sign the manifest and store it in Git, S3, or a registry.

## 1. Start from a Preset

The repository ships Cue presets under `dagger_modules/security/manifests/`.
Pick one that matches your use case (e.g., `python-light`, `polyglot-heavy`,
`supply-chain`). Format and validate the entire tree:

```bash
cd dagger_modules/security/manifests
cue fmt ./...
cue vet ./...
```

Copy the closest preset into `presets/company/` (or another folder) so you can
track your changes separately:

```bash
cp examples/python-heavy.cue presets/company/payment-api-heavy.cue
```

## 2. Customize Profiles & Controls

Inside the Cue file you can:

- Modify the `profiles` array to add/remove tools (`"tools": ["ruff", "trivy", ...]`).
- Attach `controls` metadata (`control_ids`, `severity`, `references`) used by
  compliance teams.
- Embed `component` and `assessment` metadata so every scan inherits the right
  identifiers.

Example snippet:

```cue
profiles: [{
    name: "heavy"
    description: "Full SAST+DAST+SBOM sweep"
    tools: ["ruff", "bandit", "detect-secrets", "trivy", "zap", "syft"]
    controls: [{
        control_ids: ["ACME-APPSEC-001", "PCI-DSS-6.3"]
        description: "Static code analysis"
    }]
}]

component: {
    id: "payment-api"
    owner: "PaySec Guild"
}
```

Re-run `cue vet` after edits to ensure constraints still pass.

## 3. Export JSON & Commit

Export the manifest to JSON for use by the CLI, API, or pipelines:

```bash
cue export presets/company/payment-api-heavy.cue \
  > security-results/payment-api-heavy.json
```

Commit both the Cue source and exported JSON (if you want deterministic builds)
or regenerate JSON during CI before invoking scans.

## 4. Sign the Manifest

To make verification mandatory, sign the exported JSON with Cosign. This
produces a detached signature that Certus Assurance will verify if you set
`CERTUS_ASSURANCE_MANIFEST_VERIFICATION_KEY_REF`.

```bash
cosign sign-blob \
  --yes \
  --key cosign.key \
  --output-signature security-results/payment-api-heavy.json.sig \
  security-results/payment-api-heavy.json
```

Publish the public key (`cosign.pub`) somewhere your automation can reach it
and store the JSON + `.sig` pair in one of three locations:

1. **Git / file server** – reference via `file:///absolute/path`.
2. **S3** – upload both objects, then use `s3://bucket/path.json` and
   `...path.json.sig`.
3. **OCI registry** – build a scratch image containing `manifest.json` and
   `manifest.sig` and push it (see the “Remote Manifest Execution” tutorial).

## 5. Record Metadata

Regardless of where you store the manifest, add a README (or inline comment) that
captures:

- `workspace_id`, `component_id`, and `assessment_id` values expected at runtime.
- Supported profiles and how to select them.
- Compliance mappings or evidence references this manifest satisfies.
- Contact info for the team that owns the manifest.

This documentation ensures downstream teams know how to invoke the profile,
what controls it covers, and how to update it safely.

## Next Steps

- Automate `cue fmt`, `cue vet`, `cue export`, and `cosign sign-blob` via CI so
  every manifest change produces signed JSON automatically.
- Store manifests in a dedicated Git repository and consume them via Git
  submodules or `manifest_uri` references inside Certus Assurance.
- Pair this tutorial with the “Remote Manifest Execution” guide to see how the
  signed JSON is fetched and verified at runtime.***
