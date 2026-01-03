# Assurance Manifest Starter Kit

This directory contains the Cue assets referenced throughout the security
platform roadmap:

- `schema.cue`: Canonical manifest schema validated in CI via `cue vet`
- `tool_registry.cue`: Source of truth for supported tool identifiers
- `presets.cue`: Reusable profiles that map to CLI/Dagger bundles
- `examples/`: Ready-to-export manifests tested with the light profile

## Exporting A Manifest

```bash
cd dagger_modules/security/manifests
cue fmt ./...
cue vet ./...
cue export examples/python-light.cue > ../../security-results/python-light.json
```

The exported JSON can be passed directly to `security-scan --manifest` or
mounted into the Dagger module via `--manifest`.

## File Overview

| File                        | Purpose                                                                            |
| --------------------------- | ---------------------------------------------------------------------------------- |
| `schema.cue`                | Authoritative schema for manifests, profiles, compliance blocks, and notifications |
| `tool_registry.cue`         | Registry of supported tooling (SAST, secrets, SBOM) and default configuration      |
| `presets.cue`               | Definitions for `light`, `standard`, and `polyglot` bundles used during Phase 0/1  |
| `examples/python-light.cue` | A manifest that targets Python microservices using the light preset                |
| `examples/polyglot.cue`     | Example showing how to merge multiple presets for mixed stacks                     |

When you add new tools or presets, update these files and reference them in
`docs/reference/roadmap/enhancements/security-platform-architecture.md` so the
phase table remains the single source of truth.

## Authoring Workflow

1. **Start from presets**: import entries from `presets.cue` and override the
   `profiles` array inside your manifest. Thresholds, notifications, or
   additional tools can be customized per profile.
2. **Add compliance mappings**: populate `manifest.compliance[].controls[].tests`
   so evidence such as `bandit.json` or `trivy.sarif.json` links back to HIPAA,
   SOC2, or other frameworks.
3. **Export JSON**: run `cue export` and feed the output into
   `security-scan --manifest`. During scans the metadata is copied into every
   artifact (SARIF, CycloneDX, SPDX, attestations) which keeps provenance
   bindings intact.

Example snippet:

```cue
manifest: #Manifest & {
    product: "payments-api"
    version: "1.4.2"
    owners: ["security@acme.com"]
    profiles: [
        presets.light & {
            name: "light"
            notify: { slack: "#sec-alerts" }
        },
    ]
    compliance: [{
        name: "SOC2 Security"
        controls: [{
            framework: "SOC2"
            controlId: "CC7.1"
            tests: [{
                name: "SAST baseline"
                evidence: ["bandit.json", "detect-secrets.json"]
                linkedProfile: "light"
                threshold: { critical: 0, high: 5 }
            }]
        }]
    }]
}
```

## CI Enforcement

Use `just manifest-check` (also invoked by `just check`) to run:

1. `cue fmt ./...` – canonical formatting
2. `cue vet ./...` – schema validation
3. `git diff --exit-code dagger_modules/security/manifests` – ensures formatted
   results are committed

CI fails if formatting changes are required, so run the command locally after
editing Cue files.

## Related Tutorials

See `docs/learn/assurance/manifest-driven-security-scans.md` for a walkthrough
that exports a manifest and runs both local and Dagger scans end-to-end.
