# Component View (C4 Level 3)

```mermaid
graph TB
    subgraph Authoring["Authoring Layer"]
        CueSchemas["CUE Schemas\n(cue.mod, schema/*.cue)"]
        Profiles["Profile Library\n(profiles/*.cue)"]
        CLI["Manifest CLI"]
        LSP["Editor Plugin / Validation Server"]
    end

    subgraph Packaging["Packaging & Verification"]
        BundleBuilder["Bundle Builder\n(manifest.json, manifest.sig, metadata)"]
        PolicySigning["Policy Signing\n(cosign, Sigstore)"]
        Metadata["Manifest Metadata\n(version, owners, thresholds)"]
    end

    subgraph Runtime["Runtime Components"]
        Resolver["ManifestResolver\n(certus_assurance.manifest.ManifestFetcher)"]
        Validator["ManifestValidator\n(certus_evaluate thresholds + certus_integrity policies)"]
        PolicyBindings["PolicyBindings\n(policy bundle references, gate IDs)"]
        Thresholds["Threshold Bank\n(evaluation + guardrail defaults)"]
        StorageTargets["Storage Targets\n(raw/golden prefixes, OCI repos)"]
    end

    CueSchemas --> CLI
    Profiles --> CLI
    CLI --> BundleBuilder
    LSP --> CLI
    BundleBuilder --> PolicySigning
    PolicySigning --> Metadata
    Metadata --> Resolver
    Metadata --> Validator
    Metadata --> StorageTargets
    PolicyBindings --> Validator
    Thresholds --> Validator
```

| Component            | Responsibilities                                                                                                           |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| CUE Schemas          | Define manifest structure (targets, scanners, policies, evaluation thresholds, storage locations).                         |
| Profile Library      | Curated profiles (light, standard, full, AI-eval) that authors reuse across manifests.                                     |
| Manifest CLI / LSP   | Validate manifests, render JSON for runtime consumption, and offer IDE feedback (hover docs, schema validation).           |
| Bundle Builder       | Produces OCI/S3 bundles containing manifest JSON, metadata, and optional signatures.                                       |
| Policy Signing       | Uses cosign/Sigstore to sign manifest digests; optionally attaches transparency log entries.                               |
| Manifest Metadata    | Captures owners, workspace/component IDs, SLA tier, policy bundle digests, evaluation thresholds, evidence storage targets.|
| ManifestResolver     | Fetches manifests from inline payloads, Git, S3, or OCI references; verifies signatures before returning text.             |
| ManifestValidator    | Applies schema versioning, ensures required fields exist, and distributes threshold data to certus-evaluate/integrity.    |
| PolicyBindings       | Links manifest items to policy bundles (OPA/CUE) for certus-assurance and certus-integrity gates.                          |
| Threshold Bank       | Stores default evaluation/guardrail thresholds; manifests can override per asset or environment.                           |
| Storage Targets      | Defines raw/golden prefixes, bucket names, OCI repositories used by certus-assurance and certus-transform.                 |
