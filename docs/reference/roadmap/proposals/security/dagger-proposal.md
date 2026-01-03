# Unified Dagger Security Module

**Status:** Draft
**Author:** DevOps/RAG Agent
**Date:** 2025-12-07
## Executive Summary

We will evolve the existing `tools/sast/run_local_scan.py` workflow into a first-class Dagger module that orchestrates the entire TAP security surface: light-weight SAST/secrets scans for every PR and heavy SAST/DAST/API/privacy workflows for gated environments. The module will publish artifacts (SARIF, SBOM, provenance), enforce policy gates, and expose simple developer ergonomics via `just test-security-light` / `just test-security-heavy` plus `dagger call` entry points. Because the module is self-contained, we can distribute it to partner organizations, giving them a turnkey path to run open-source scanners and push signed security evidence into Certus TAP without bespoke pipelines.

**Key Goals**

1. **Single Entry Point:** One Dagger module coordinates SAST, DAST, API, privacy, and supply-chain checks.
2. **Profile Modes:** Light profile (fast subset) for PRs, heavy profile (full suite with stack bootstrap) for releases.
3. **Artifact + Provenance:** Automatically publish SARIF/SBOM reports, cosine-signed attestation, and in-toto metadata.
4. **Policy & Notifications:** Enforce severity thresholds, emit Slack/webhook notifications, and document pass/fail outcomes.
5. **Developer Experience:** Document workflows in `docs/reference/testing/security-scanning.md` and expand the `justfile` so tests stay reproducible and frictionless.

## Motivation

### Current State

- `run_local_scan.py` already leverages Dagger but is a bespoke script with no modular interface.
- `run_e2e_pipeline.py` shells out to local scans and manually uploads artifacts.
- Security testing guidance spans multiple docs, and developers must choose between ad-hoc scripts or manual pytest markers.
- Heavy scans require humans to remember to start the stack, supply secrets, and route reports back to storage.

### Problems Addressed

1. **Fragmented Pipelines:** SAST, DAST, and API scans live in separate scripts with inconsistent outputs.
2. **Slow Feedback for Devs:** Running every tool locally is costly; teams need a light profile that completes in minutes.
3. **Missing Guardrails:** Severity thresholds and pass/fail criteria are not codified; results are advisory only.
4. **Artifacts Not Centralized:** SARIF/SBOM/provenance artifacts do not automatically land in S3/LocalStack or GitHub Security.
5. **Docs Drift:** Testing docs describe `uv` and `pytest` commands but do not explain how to invoke Dagger scans through `just`.

## Why Dagger?

- **Deterministic environments:** Dagger snapshots the repo and executes scans inside reproducible containers, so toolchains stay identical across laptops and CI.
- **Composable pipelines:** Each security domain (SAST, IaC, DAST, SBOM, etc.) becomes a reusable function that we can stitch into `light` or `heavy` profiles without duplicating scripts.
- **Performance via caching:** Built-in cache volumes let us reuse Trivy/Dependency-Check databases and OCI layers, keeping heavy runs under control.
- **Secret hygiene:** Dagger secrets keep cosign keys, API tokens, and webhook creds out of logs and artifacts, simplifying compliance.
- **Uniform UX:** The same module powers `dagger call ...`, `just test-security-*`, and GitHub Actions workflows, eliminating drift between local and CI executions.
- **External adoption:** Packaging the pipeline as a Dagger module means other organizations can reuse it verbatim to run OSS security tooling, generate provenance, and feed artifacts into Certus TAP, accelerating ecosystem growth.

## Goals & Non-Goals

| Goals                                                                              | Non-Goals                                                                |
| ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| Standardize security testing via a Dagger module with `light` and `heavy` profiles | Replace existing pytest suites (service/unit tests remain unchanged)     |
| Integrate artifact publishing, cosign signing, and provenance capture              | Build a new UI for report consumption                                    |
| Automate stack bootstrap for DAST/API suites                                       | Replace Certus-Assurance scanners (re-use existing tools)                |
| Provide CLI + `just` entry points with documented workflows                        | Immediate integration with every external CI (start with GitHub Actions) |

## Proposed Solution

### Module Overview

```
dagger_modules/
└── security/
    ├── main.py            # module entry points
    ├── sast.py            # light/heavy SAST orchestration
    ├── dast.py            # OWASP ZAP + API fuzzing hooks
    ├── api.py             # Postman/Newman, contract tests
    ├── artifacts.py       # publishing + signing helpers
    └── stack.py           # TAP stack bootstrap (Docker compose / services)
```

- **Light Profile (`security.light`)**
- Ruff + Bandit + Opengrep (Semgrep fork) + Trivy filesystem + secrets detection + Presidio sample scan.
  - Optional targeted SBOM (Syft) without dependency-check or cosign signing.
  - Runs entirely in a Dagger container, no TAP stack needed, finishes <10 minutes.
- Outputs SARIF (Opengrep/Bandit/Trivy), `ruff.txt`, short SBOM snippet.

- **Heavy Profile (`security.heavy`)**
  - Everything from light profile plus:
    - Trivy image scans (backend, worker).
    - OWASP ZAP DAST against running TAP stack (launched via `stack.py` helpers using `just up` semantics).
    - API regression (Postman/Newman) + fuzzing.
    - Privacy/Presidio full scans across `samples/privacy-pack`.
    - SBOM generation (SPDX + CycloneDX), OWASP Dependency-Check, license audit.
    - Cosign signing + in-toto provenance emission.
    - Artifact publishing to the Certus Transform S3-compatible store (`build/sast-reports` plus S3 upload) and optional GitHub upload (code scanning, release assets).
    - **Stack bootstrap + placeholder DAST:** The runtime automatically spins up a lightweight HTTP service via Dagger service bindings (or logs a no-op locally) and executes a placeholder DAST/API script against `STACK_BASE_URL`. This exercises the runtime abstraction today and is the integration point for full OWASP ZAP/API suites in later phases.

### Shared Capabilities

- **Policy Gates:** Fail builds when severity thresholds exceed `light` or `heavy` budgets (configurable JSON). Example: `CRITICAL > 0` or `HIGH > 5` triggers failure.
- **Runtime-Aware Enforcement:** The CLI (`security-scan --runtime dagger|local`), Dagger module, and Certus-Assurance all parse the emitted SARIF/Bandit/DAST artifacts and exit non-zero when manifest thresholds are violated, ensuring policy parity across environments.
- **Notifications:** Optional Slack/webhook payload summarizing findings and artifact locations.
- **Caching:** Reuse Trivy/Dependency-Check DBs via Dagger cache volumes to cut heavy runtime.
- **Documentation & Commands:** Update testing docs to reference `dagger call security.light`/`security.heavy` and `just test-security-light` / `just test-security-heavy`.
- **CI Integration:** Provide GitHub Actions workflow templates for PR (light) and nightly (heavy) pipelines.
- **API & CLI Parity:** Implement the core scan logic as a reusable Python package so both the FastAPI service (for MCP/ACP/managed use) and the CLI/Dagger entry points call the same functions. This ensures local `just` targets, CI jobs, and the hosted API all stay in sync while giving us an HTTP surface when needed.

### Profile Flags & CLI Usage

The CLI (`tools/security/security-scan.py`) now accepts explicit profile flags so operators can drive the same light/heavy behavior documented above without memorizing module names:

```bash
# Run the light bundle locally, pointing at the exported manifest
security-scan --manifest ./manifest.json --profile light --runtime local

# Exercise the heavy profile (stack bootstrap + DAST placeholder) under Dagger
security-scan --manifest ./manifest.json --profile heavy --runtime dagger --stack-base-url http://localhost:8005
```

- `--profile` supports every manifest profile (smoke/light/heavy/etc.) with `light` as the default. Heavy automatically flips `requiresStack=True` so the runtime binds a placeholder stack service and executes the new DAST/API helper.
- `--manifest` accepts the exported Cue JSON, which feeds tool selection + policy gates. The flag is required whenever a profile needs manifest context (all managed/service flows now enforce this).
- `--runtime` (`local` or `dagger`) keeps feature parity; heavy + local prints a note when stack bootstrap falls back to the host.
- Additional toggles (`--stack-base-url`, `--skip-privacy`, future `--requires-stack`) are forwarded directly to the runtime so Certus-Assurance, CI, and CLI stay in sync.

These flags are mirrored in the Dagger module (`dagger call security heavy --manifest=...`) and the FastAPI surface (`POST /v1/security-scans` now accepts `profile` + `manifest`), ensuring every consumption model runs the same pipeline.

### Execution Scenarios

- **Reusable Dagger Module:** The module will be stored in the Certus Git repository (and optionally mirrored to a public module registry) so any organization can `dagger call security.light`/`security.heavy` directly from their pipelines without requiring the rest of TAP. Documentation must cover cloning/tagging conventions so partners can pin module versions.
- **Certus-Assurance Engine:** `docs/reference/roadmap/proposals/certus-assurance-proposal.md` consumes this module as its core scan runner; the FastAPI + CLI surfaces simply orchestrate the same light/heavy profiles.
- **Certus TAP Testing Suite:** Within this repository we will invoke the module from the TAP testing suite via `just test-security-light` / `just test-security-heavy` (and related CI workflows). It will **not** be wired into `./scripts/preflight.sh`; instead, teams call the security tests explicitly when running the broader testing suite or gated CI jobs.
- **Future OCI Distribution (Reference Implementation):** As the module matures we intend to publish signed OCI module snapshots (e.g., `ghcr.io/certus/dagger-security:<tag>`) so external adopters can `dagger mod install` without cloning the repo. This is long-term/optional; we’ll treat it as a reference implementation with cosign+in-toto signatures and digest pinning guidance so organizations can mirror or validate the module in their own registries when ready for production use.

### Toolchain Coverage

The module will orchestrate a broad OSS toolchain. Profiles determine which stages run by default, but every tool below must be supported and exposed via configuration toggles:

- **Static Application Security Testing (SAST):** Opengrep (Semgrep rules), CodeQL (community edition), Bandit, Flawfinder, Brakeman, Gosec, Psalm, Cppcheck, Horusec.
- **Software Composition Analysis & SBOM:** Trivy, Syft, Grype, Dependency-Track, CycloneDX CLI, OWASP Dependency-Check, OSS Review Toolkit (ORT).
- **Secrets Detection:** Gitleaks, TruffleHog (OSS), detect-secrets.
- **Infrastructure as Code & Policy:** Checkov, Terrascan, Kics, tfsec, Conftest, Open Policy Agent (OPA), Gatekeeper, Kyverno.
- **API Security & DAST:** OWASP ZAP, Schemathesis, w3af, Akto (community), RESTler, GraphQL Raider.
- **Container & Kubernetes Security:** Trivy, Kubescape, kube-bench, kube-hunter, Falco, Inspektor Gadget.
- **Cloud & Platform Security:** Cloud Custodian, Steampipe, ScoutSuite, Prowler (community).
- **Supply Chain Integrity & Provenance:** Cosign, in-toto, SLSA Generator, Sigstore, Rekor (transparency log).
- **Runtime & Observability Security:** Falco, Tetragon, Tracee.
- **Project/Dependency Trust:** OpenSSF Scorecard, DepScan.
- **Fuzzing & Robustness:** AFL++, libFuzzer, OSS-Fuzz (where applicable), zzuf.

Each category will map to a pluggable Dagger stage, with shared artifact schemas (SARIF, SBOM, logs) and policy gates so teams can enable/disable tools per profile without drifting from the standard workflow.

## Dependencies & Considerations

- **Secrets Management:** Dagger module will request GitHub/Slack tokens, cosign keys, and API credentials from the environment or `.env`.
- **Stack Bootstrap:** Heavy profile must ensure OpenSearch, LocalStack, MLflow, etc., are reachable; module should either run `docker compose up` inside Dagger or orchestrate service containers via Dagger itself.
- **Resource Usage:** Heavy runs may exceed workstation resources; plan to run them in CI or powerful runners when necessary.
- **Failure Modes:** Provide clear exit codes and logs so teams understand when policy gates fail vs. infrastructure issues (e.g., stack startup failure).
- **Distribution:** If the module is shared with partner organizations, document how to configure credentials, push artifacts into Certus Transform, and opt in/out of specific tools while keeping provenance intact.

## Risks

1. **Long-Running Pipelines:** Heavy profile could exceed CI timeouts if not optimized (mitigate via caching and parallel stages).
2. **Secret Sprawl:** Improper handling of tokens in logs or provenance could leak credentials (mitigate via masking and Dagger secret mounts).
3. **Stack Drift:** Automated stack bootstrap may conflict with developer-hosted stacks (provide opt-out flag to reuse an existing stack).
4. **Documentation Lag:** Without clear docs, developers may bypass the module (mitigate by updating `docs/reference/testing` and `tests/README.md` concurrently).

### Runtime Abstraction & Package Interface

The `security_module` package must expose a runtime-neutral API so the Dagger module, CLI, and Certus-Assurance all reuse the same orchestration code:

```python
from security_module import run_scan

run_scan(
    manifest_path="build/manifest.json",
    workspace=".",
    profile="standard",
    runtime="dagger",  # dagger|local|managed
    export_dir="build/security-results",
    options={...},
)
```

- `runtime="dagger"` drives the existing Dagger client flow.
- `runtime="local"` runs scanners directly on the host (for lightweight lint-only workflows or future air-gapped modes).
- `runtime="managed"` is the interface Certus-Assurance will call (delegates to remote runners/queues).

The Dagger entry points (`security.light`, CLI) become thin wrappers that parse arguments, read manifest JSON, and call `run_scan(...)`. This ensures new features land once in the package and surface everywhere.

### Acceptance Criteria & Metrics

- Profile SLAs: smoke ≤30s, fast ≤2m, medium ≤4m, standard ≤8m, full ≤15m (on reference hardware) with documented variance.
- Artifact parity: every profile produces the promised SARIF/SBOM/attestation bundle; CI compares output schema/hashes to golden examples.
- Feature parity: DAST/API/IaC stacks implemented per roadmap (stack bootstrap, Slack/webhook notifications, policy gates).
- Distribution: published PyPI package and Dagger module tagged with release notes + cosign/in-toto signatures.

### Dependencies & Interfaces

- Upstream: consumes manifest exports (`assurance-manifest-proposal.md`) and the architecture roadmap for scheduling.
- Downstream: Certus-Assurance service adopts this package as its scan engine; any breaking change must be coordinated via `security-platform-architecture.md`.

## Phased Roadmap

### Phase 0 – Foundation (Complete / Current State)

- `run_local_scan.py` executes SAST tools with Dagger manually; `run_e2e_pipeline.py` consumes outputs.
- Actions: inventory existing tool outputs, confirm `just test-security` wiring, and document current behavior.

### Phase 1 – Module Skeleton & Light Profile (Weeks 1-2)

- Create Dagger module structure with `security.light` entry point.
- Port existing SAST stages (Ruff, Bandit, Opengrep, Trivy filesystem, secrets, Presidio sample) into module functions.
- Define artifact schema (directory layout, SARIF naming) and generate summary JSON for downstream consumers.
- Add `just test-security-light` that calls `dagger call security.light`.
- Update `docs/reference/testing/security-scanning.md` with light profile instructions and policy gates.

### Phase 2 – Heavy Profile & Stack Bootstrap (Weeks 3-5)

- Implement `stack.py` helper to start TAP stack (Docker compose or service containers) with health checks.
- Add OWASP ZAP, API regression (Newman/Postman), Trivy image scans, SBOM (Syft/CycloneDX), Dependency-Check, license audit.
- Integrate cosign signing + in-toto provenance (reuse from `run_local_scan.py`).
- Publish artifacts to the Certus Transform S3-compatible bucket and optionally upload SARIF to GitHub code scanning.
- Introduce `just test-security-heavy` and document prerequisites (stack, secrets).

### Phase 3 – Policy Gates, Notifications, and CI Templates (Weeks 6-7)

- Encode severity thresholds in config (JSON/YAML) and fail builds when exceeded.
- Add Slack/webhook notification hooks summarizing findings and linking to artifacts.
- Provide GitHub Actions workflows:
  - `security-light.yml` for PR gating (runs on main + PR, executes `dagger call security.light`).
  - `security-heavy.yml` for nightly/release builds.
- Extend `docs/reference/testing/testing-checklist.md` and `tests/README.md` to cover gating expectations.

### Phase 4 – Adoption & Hardening (Weeks 8+)

- Gather feedback from teams, adjust thresholds, expand coverage (e.g., Terraform/OPA scans).
- Optimize runtime via caching (Dagger cache volumes) and concurrency.
- Add metrics dashboard (e.g., push summary to OpenSearch) for tracking pass/fail trends.
- Formalize support docs and troubleshooting guides.
- Prototype MCP/Zed ACP adapters so developers (and LLM copilots) can trigger `security.light`/`security.heavy` scans directly from IDEs or agents, reusing the same Dagger module APIs.

### Phase 5 – Managed Service Integration (Future)

- Embed the Dagger module inside Certus-Assurance so customers can submit repositories via API and let Certus run scans on their behalf.
- Extend Certus-Assurance queueing/scheduling to invoke `security.light`/`security.heavy` with tenant-specific tool selections and severity gates.
- Manage credentials (Git tokens, OCI registry creds, cosign keys) centrally and stream signed artifacts directly into Certus Transform and TAP indexes.
- Document the managed workflow so customers know how to trigger scans, monitor progress, and retrieve results without running Dagger locally.

### Scanner Enablement Cadence

We will stage the remaining toolchain coverage in bi-weekly waves so every scanner lands with docs, policy gates, and artifact plumbing. Ownership rotates between DevSecOps and TAP depending on target domain.

| Sprint Window          | Focus Area            | Tools                                                             | Notes                                                 |
| ---------------------- | --------------------- | ----------------------------------------------------------------- | ----------------------------------------------------- |
| Weeks 1-2 (Phase 1)    | Baseline SAST/Secrets | Ruff, Bandit, Opengrep, Trivy FS, detect-secrets, Presidio sample | Ship with light profile + docs.                       |
| Weeks 3-4 (Phase 2)    | Container & SBOM Core | Trivy image, Syft, CycloneDX, Dependency-Check, license audit     | Align with stack bootstrap; wire artifact uploads.    |
| Weeks 5-6              | IaC & Policy          | Checkov, Terrascan, tfsec, Conftest/OPA                           | Add policy gate thresholds + sample configs.          |
| Weeks 7-8              | API & DAST            | OWASP ZAP, Schemathesis, Newman/Postman suites                    | Requires stable stack health checks.                  |
| Weeks 9-10             | Runtime & Kubernetes  | Kubescape, kube-bench, kube-hunter, Falco                         | Gate behind heavy profile and optional runner sizing. |
| Weeks 11-12            | Cloud & Trust         | Cloud Custodian, Prowler, Scorecard, DepScan                      | Finalize provenance schema + cosign integration.      |
| Ongoing (post Phase 4) | Fuzzing / Advanced    | AFL++, libFuzzer harnesses, OSS-Fuzz hooks                        | Scheduled per service; opt-in until harnesses mature. |

Each sprint closes with:

1. Tool enablement merged behind configuration toggles.
2. Documentation updates (`docs/reference/testing/` + `tests/README.md`) for invocation and policy gates.
3. `just test-security-*` smoke run plus `./scripts/preflight.sh` update if the tool is part of the default guardrail set.

## Deliverables

- `dagger_modules/security` module with `light` and `heavy` profiles plus subcomponents.
- Updated `justfile` targets and documentation referencing the module.
- Artifact storage in LocalStack S3 and optional GitHub code scanning uploads.
- Policy gate configuration files and notification templates.
- GitHub Actions workflows for PR and nightly use cases.

## Success Metrics

1. **Adoption:** 100% of PRs run the light profile; nightly builds run heavy profile.
2. **Runtime:** Light profile completes in <10 minutes; heavy profile completes in <45 minutes with caching.
3. **Artifact Availability:** SARIF/SBOM/provenance automatically published for every heavy run.
4. **Policy Enforcement:** Builds fail automatically when severity budgets are exceeded (tracked via CI).
5. **Documentation:** Testing reference docs and `tests/README.md` explicitly cover Dagger workflows and just targets.

## Next Steps

1. Approve this proposal and assign an owner for Phase 1.
2. Create a tracking issue/epic with phase checklist and dependencies (Docker stack improvements, Slack webhook credentials, cosign keys).
3. Begin Phase 1 implementation focusing on module skeleton, light profile, and documentation updates.
