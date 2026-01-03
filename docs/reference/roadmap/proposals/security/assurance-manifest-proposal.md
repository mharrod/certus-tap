# Assurance Manifest & Policy-Driven Scanning

**Status:** Draft
**Author:** DevOps/RAG Agent
**Date:** 2025-12-09
## Executive Summary

The Assurance Manifest is a declarative paradigm for expressing trust requirements across Certus products. Instead of scattering policies across scripts and spreadsheets, organizations describe outcomes (“Protect PHI”, “Meet OSHA site safety”), map those outcomes to controls/tests, and connect tests to concrete evidence (scanner outputs, checklists, attestations). Written in Cue, the manifest becomes a single source of truth that:

- Captures high-level requirements understandable by non-technical stakeholders.
- Maps those requirements to tooling/execution profiles (security scanners today, broader inspection/report workflows tomorrow).
- Anchors provenance and signatures so evidence is auditable and immutable.

Once defined, the manifest can drive any assurance surface—Dagger modules, Certus Assurance jobs, third-party pipelines, or even physical inspection checklists. This proposal describes the paradigm as a whole and then dives into how the Dagger security module and broader Certus TAP stack consume it initially.

While the first implementation targets software security/privacy, the schema and registry must accommodate additional industries (healthcare, utilities, construction, public sector), allowing future manifests to specify non-IT controls without structural changes.

## Motivation

- **Fragmented policies** – today, scanner choices live in `justfile` comments or ad-hoc docs. Every new service re-discusses “which tools do we run?”
- **Partner variability** – external orgs have different languages (Python, Go, Node, Java) and compliance targets. A single hard-coded pipeline forces forks.
- **Pipeline integrity** – Certus Assurance generates evidence bundles, but without a declarative manifest we can’t prove the executed tools matched policy.
- **Extensibility pain** – adding a tool requires editing module code (Python), making it harder for security architects (and customers) to extend.

## Goals & Non-Goals

| Goals                                                                                                                     | Non-Goals                                                  |
| ------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| Declarative format to describe assurance needs (profiles, tools, thresholds, bundles)                                     | Replace SARIF/JSON artifact formats                        |
| Drive Dagger module behavior via manifest (no code changes for new tool mixes)                                            | Automate tool installation outside the Dagger module scope |
| Embed manifest digest in in-toto provenance for pipeline integrity                                                        | Build a new UI for editing manifests                       |
| Allow presets/macros so non-experts can author manifests                                                                  | Enforce vendor-specific scanners (remains opt-in)          |
| Enable cross-domain assurance (security + privacy today, but extendable to healthcare, construction, public sector, etc.) | Force every domain to adopt the same tooling set           |

## Proposed Solution

### Manifest Structure (Cue)

Use Cue to define a schema with **layered abstraction**:

1. **Outcomes** – human-readable goals (“Protect PHI”, “Maintain OSHA compliance”) authored by non-technical stakeholders.
2. **Controls/Tests** – control IDs and test requirements tied to those outcomes.
3. **Profiles/Tools** – concrete scanning or inspection tooling that satisfies the tests.

This structure lets compliance teams capture _what_ needs to be proven, while engineering teams describe _how_ it’s proven.

```cue
package assurance

#Tool: {
  id: string // e.g., "ruff", "bandit", "opengrep", "trivy", "gosec"
  config?: {...} // tool-specific knobs (rules file, severity, skip dirs)
}

#Profile: {
  name: string
  description?: string
  tools: [...#Tool]
  bundle: {
    includePrivacy: bool | *false
    runtimeCeilingMinutes: int | *10
  }
  thresholds?: {
    critical: int | *0
    high: int | *5
    medium: int | *50
  }
}

#TestRequirement: {
  name: string
  description?: string
  evidence?: [...string] // e.g., SARIF, SBOM, attestation types
  linkedProfile?: string
}

#Outcome: {
  name: string
  description?: string
  controls: [...#RegulatoryControl]
}

#RegulatoryControl: {
  framework: string // e.g., "SOC2", "ISO27001", "NIST 800-53"
  controlId: string
  tests: [...#TestRequirement]
}

#Manifest: {
  product: string
  version: string
  owners: [...string]
  presets?: [...string]
  profiles: [...#Profile]
  compliance?: [...#Outcome]
}

manifest: #Manifest & {
  product: "certus-tap"
  version: "2025-12-09"
  owners: ["security@certus.dev"]
  profiles: [
    presets.pythonBaseline, // expands tools = [ruff, bandit, opengrep, detect-secrets]
    presets.smokeBaseline,  // Ruff + Bandit
  ]
  compliance: [
    {
      name: "Protect PHI"
      description: "Meet HIPAA safeguards for software handling patient data."
      controls: [
        {
          framework: "HIPAA"
          controlId: "164.306(a)"
          tests: [
            {name: "Application SAST", evidence: ["bandit.json","opengrep.sarif.json"], linkedProfile: "light"},
            {name: "Secrets Detection", evidence: ["detect-secrets.json"], linkedProfile: "light"},
          ]
        },
        {
          framework: "HIPAA"
          controlId: "164.308(a)(1)(ii)(A)"
          tests: [
            {name: "Vulnerability Scan", evidence: ["trivy.sarif.json"], linkedProfile: "light"},
          ]
        },
      ]
    },
    {
      name: "Site Safety"
      description: "Ensure construction site safety inspections satisfy OSHA controls."
      controls: [
        {
          framework: "OSHA"
          controlId: "1926.20(b)"
          tests: [
            {name: "Safety Checklist Review", evidence: ["site-safety-report.pdf"], linkedProfile: "constructionBaseline"},
          ]
        },
      ]
    },
  ]
}
```

- **Presets/macros** live in reusable Cue files (`presets.cue`) so authors can reference `presets.pythonBaseline` instead of enumerating every tool.
- **Overrides**: Cue’s `&` operator lets teams refine presets (`pythonBaseline & { tools: append(tools, {id: "gitleaks"}) }`).
- **Outcome hierarchy** empowers non-technical stakeholders to express high-level requirements while engineers map those outcomes to profiles via `linkedProfile`.

### Manifest Lifecycle

1. **Authoring** – Architects (or compliance teams) edit `assurance/manifest.cue` (or `manifest.<workspace>.cue`) to capture tech stacks, tool profiles, and regulatory requirements. Cue tooling (`cue fmt`, `cue vet`) ensures schema compliance and validates references (e.g., frameworks/control IDs).
2. **Compilation** – Prior to running Dagger or scheduling a Certus Assurance job, the CLI/API executes `cue export` to produce a JSON manifest (material for provenance). Compliance metadata travels with the manifest so downstream services know which frameworks/tests are being satisfied.
3. **Execution** – Dagger module and Certus Assurance workers read the manifest JSON, select the requested profile (e.g., `--profile light`), resolve tool commands, and run scanners accordingly. When multiple profiles are defined (e.g., `light`, `node`, `iac`), the scheduler can chain them based on manifest declarations.
4. **Provenance** – Summary JSON, SARIF, SBOMs, and in-toto attestations embed the manifest digest + profile name + relevant compliance references (framework/control/test). Certus Transform stores the manifest alongside artifacts so auditors can trace evidence to requirements.
5. **Policy Gates & Reporting** – When uploading SARIF or verifying bundles, Certus services check manifest thresholds and compliance mappings (e.g., “Did CC7.2 tests produce non-zero findings?”). Dashboards can group scans by framework, control, or manifest version.

### Integration Points

| Component/Service      | Role                                                                                                                                           |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| Dagger module          | Loads manifest, maps `id` → `ToolCommand`, runs requested profile, exports bundles + summary linked to the manifest digest.                    |
| Certus Assurance (API) | Accepts manifest references (digest or uploaded file) when scheduling scans, stores the manifest with each bundle, enforces policy thresholds. |
| Certus TAP Services    | Downstream services (Transform, Trust, Assurance UI) read manifest metadata to drive ingestion, reporting, and analyst workflows.              |
| Ingestion pipelines    | When ingesting bundles into OpenSearch/Neo4j, index manifest metadata for filtering/reporting and compliance tracking.                         |
| In-toto attestations   | Include manifest digest + profile in materials and metadata for verifiability, proving scans complied with declared policy.                    |

### Tool Registry & Extensibility (Security Today, Other Domains Tomorrow)

Maintain a `tool_registry.cue` (or JSON) that maps tool ids to metadata. The initial registry is security/privacy focused, but the structure must support non-IT contexts (e.g., safety inspections, physical asset audits) as Certus expands into healthcare, construction, public sector, etc.:

```cue
tool_registry: {
  ruff: {
    command: ["ruff", "check", ...]
    image: "python:3.11-slim"
    domains: ["software"]
    languages: ["python"]
  }
  bandit: {...}
  trivy: {...}
  // future additions: kubernetes bench, medical device checklist, OSHA audit scripts, etc.
}
```

The registry schema should capture tags such as `domains` or `controlFamilies` so manifest authors can pick tools even outside software (e.g., `domains: ["healthcare"]`). Certus Assurance can load multiple registries or allow organizations to extend the base list with their own tooling.

### Preset & Pattern Distribution

To keep manifests approachable, Certus will curate a Git-based repository of Cue presets and outcome templates:

1. **Repo layout:** `assurance-presets/` contains directories such as `profiles/`, `outcomes/`, `controls/`, each defining reusable Cue packages. For example, `profiles/python.cue` exports `pythonBaseline`, `profiles/construction.cue` exports `constructionSafetyBaseline`, and `outcomes/hipaa.cue` exports `hipaaPrivacyOutcome`.
2. **Cue modules:** The presets repo exposes a Cue module (`cue.mod`, `module: github.com/certus/assurance-presets`). Manifest authors add it as a dependency (`cue mod get github.com/certus/assurance-presets@vX.Y.Z`) and import presets via `import "github.com/certus/assurance-presets/profiles"` to reference `profiles.pythonBaseline`.
3. **Composition & overrides:** Presets are defined as functions/structs that can be merged or extended (using Cue’s `&` and `append`). This lets teams start with a baseline and add local tweaks without forked code.

### Authoring & Export Workflow

1. Install Cue plus the presets registry (`cue mod init` + `cue mod get github.com/certus/assurance-presets@<tag>`).
2. Author or update `assurance/manifest.cue`, importing presets and the shared `tool_registry`.
3. Validate locally with `cue fmt` and `cue vet` (add to CI to block invalid manifests).
4. Export JSON for the engine/service: `cue export assurance/manifest.cue --out json > build/manifest.json`.
5. Provide the exported file (or its digest) to `security_module` / Certus-Assurance (`security_module run --manifest build/manifest.json --profile light`).
6. Embed the manifest digest in provenance artifacts so downstream systems can verify which policy ran.

### Acceptance Criteria & Metrics

- Schema completeness: CI enforces `cue fmt`/`cue vet` and validates at least two reference manifests (e.g., HIPAA light, polyglot heavy).
- Registry availability: tool registry and presets published with semantic versions and documentation.
- Provenance linkage: SARIF/SBOM/attestations include manifest digest + profile name.
- Compliance coverage: at least one framework template (HIPAA/SOC2) proven end-to-end (manifest → scan → indexed metadata).

### Dependencies & Interfaces

- Upstream: shares schedule with the unified roadmap (`security-platform-architecture.md`) and depends on security/tooling input for registry entries.
- Downstream: exported manifests feed directly into `security_module` (engine) and Certus-Assurance (service). Any schema change must be communicated to those teams before they lock phase milestones.

4. **Governance:** Security/compliance architects manage the preset repo via Git, review contributions, and tag releases so downstream manifests can pin versions. Partner organizations can clone/fork the repo or add their own preset modules alongside Certus-provided ones.

By publishing patterns in Git, we give every organization a consistent source of reusable blocks while keeping manifests declarative and light.

### Profiles & Bundles

- **Light** remains the default baseline (Ruff/Bandit/Opengrep/detect-secrets/Trivy/privacy), defined in `presets`.
- **Smoke** (Ruff + Bandit) is also a preset.
- Additional presets: `goBaseline`, `nodeBaseline`, `iacBaseline`, `containerBaseline`, etc.
- Future presets can target non-software contexts: e.g., `medicalBaseline` (HIPAA privacy checks, PHI redaction validation), `constructionSafetyBaseline` (OSHA inspection checklists), `publicSectorBaseline` (FISMA/FedRAMP controls). The manifest format should allow these to coexist with software-centric profiles.
- Manifests can mix and match (e.g., `profiles: [presets.lightBaseline, presets.medicalBaseline]`) so multi-disciplinary products meet regulated industry requirements without separate tooling pipelines.

### Cue + In-toto Flow Across Certus

1. `cue` manifest exported → `manifest.json` (checked into repo or supplied with scan requests).
2. Dagger runs (locally or in Certus Assurance workers) use `manifest.json` to execute the requested profile(s).
3. `summary.json`, SARIF files, and in-toto statements reference the manifest hash + profile name.
4. Certus Assurance stores the manifest alongside artifacts in WORM-compliant storage (e.g., versioned S3/LocalStack buckets) and optionally packages bundles into signed OCI artifacts that include the manifest, provenance, and scanner outputs.
5. Certus TAP ingestion services write manifest metadata into OpenSearch/Neo4j for querying (“show all bundles run under manifest X”).
6. Downstream verifiers—including customers, auditors, and third parties—can fetch the manifest, verify its digest, and review artifacts via signed OCI references or API endpoints. WORM storage + in-toto attestations ensure evidence is immutable and traceable.

## Dependencies & Considerations

- **Tool coverage** – need to maintain a growing registry of scanners (Py, JS, Go, Java, IaC, containers, etc.).
- **Cue tooling** – ensure developer environments have `cue` installed or vendor through Docker (use `cue` container in Dagger).
- **Backward compatibility** – default manifest should mirror today’s light profile; teams can opt into richer manifests gradually.
- **Validation** – integrate `cue vet` in CI/just to ensure manifests compile before running Dagger.
- **Versioning** – tag manifest versions and store along with Dagger module tags to keep reproducibility.

## Risks

1. **Manifest Drift** – If teams bypass the manifest and call Dagger directly, policies diverge. Mitigation: require manifest digest in pipeline invocation.
2. **Complexity** – Cue can intimidate some users. Provide presets, docs, and a CLI helper (`certus assurance plan render`) to show resolved tool lists.
3. **Registry Sprawl** – Too many tool definitions might be hard to maintain. Encourage contributions via PR + automated smoke tests.
4. **Performance** – Large manifests with many tools could reintroduce the “slow scan” problem. Use bundling options (smoke vs light vs heavy) and run profiles selectively.

## Phased Roadmap

1. **Phase 1 – Schema & Presets (Weeks 1–2)**
   - Define Cue schema + presets (`pythonBaseline`, `smokeBaseline`, etc.).
   - Update Dagger module to accept `manifest.json` input (optional at first).
   - Document authoring workflow (`docs/reference/testing/assurance-manifest.md`).

2. **Phase 2 – Enforcement & Provenance (Weeks 3–4)**
   - Require manifest digest when running Certus Assurance scans (API/CLI).
   - Embed manifest hash into `summary.json` and in-toto statements.
   - Add CI job to vet manifests (`just assurance-validate`).

3. **Phase 3 – Registry Expansion (Weeks 5–7)**
   - Add presets for Go, Node, Java, IaC, container, and supply-chain tooling.
   - Provide examples for partner orgs (e.g., `examples/manifests/acme.cue`).
   - Publish docs on customizing thresholds, bundling rules, and gating.

4. **Phase 4 – Domain Extensions & Automation (Weeks 8+)**
   - Introduce domain-specific preset packs (healthcare privacy, construction safety, public sector compliance) leveraging the same manifest schema.
   - (Optional) Build a lightweight form/YAML generator that outputs Cue for teams uncomfortable editing by hand.
   - Integrate manifest selection into the Certus Assurance web UI/API schedules.
   - Add metrics dashboards linking manifest versions → scan results/headline compliance frameworks across industries.

5. **Future – OCI / Managed Distribution**
   - Bundle manifest + module + tool registry into signed OCI artifacts (aligns with future module distribution vision).
   - Let organizations pin both module version and manifest digest when consuming Certus Assurance as a managed service.

## Appendix: Example Manifest & Derived Profiles

```cue
import "tool_registry.cue"

presets: {
  lightBaseline: #Profile & {
    name: "light"
    tools: [
      tool_registry.ruff,
      tool_registry.bandit,
      tool_registry.opengrep & {config.rules: "./config/semgrep-baseline.yml"},
      tool_registry.detect_secrets,
      tool_registry.trivy & {config.skipDirs: [".venv","build","dist"]},
      tool_registry.privacySample,
    ]
  }
  smokeBaseline: #Profile & {
    name: "smoke"
    tools: [tool_registry.ruff, tool_registry.bandit]
  }
}

manifest: #Manifest & {
  product: "certus-tap"
  version: "2025-12-09"
  owners: ["security@certus.dev"]
  profiles: [
    presets.lightBaseline,
    presets.smokeBaseline,
    presets.nodeBaseline & {bundle.runtimeCeilingMinutes: 20},
  ]
}
```

Cue command to export:

```bash
cue export assurance/manifest.cue -o build/security-light/manifest.json
```

Pass the JSON to the Dagger module (`--manifest build/security-light/manifest.json`) so the engine knows which profile + tools to run.
