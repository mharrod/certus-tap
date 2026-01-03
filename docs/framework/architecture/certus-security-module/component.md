# Component View (C4 Level 3)

The module is intentionally self-contained so partners can copy the directory and run scans anywhere. Each major Python module maps to a component below.

```mermaid
graph TB
    CLI["security_module.cli\n(Click CLI + config parsing)"]
    Scripts["scripts/*.py\n(summary, attestation, embed_manifest_metadata, privacy, DAST placeholder)"]
    DaggerEntry["security_module.main.Security\n(Dagger @object_type)"]
    Scanner["security_module.scanner.SecurityScanner"]
    Manifest["manifest.py / policy.py\n(manifest parsing + enforcement)"]
    ToolResolver["tooling.py\n(profile definitions, tool selection, stack detection)"]
    Runtime["runtime.py\n(LocalRuntime, DaggerModuleRuntime, ScanRequest)"]
    Pipeline["sast.py: LightProfilePipeline\n(command graphs + artifact layout)"]
    Artifacts["artifacts.py\n(export helpers, discover bundle layout)"]
    Constants["constants.py\n(paths, excludes, privacy defaults)"]

    CLI --> Scanner
    DaggerEntry --> Scanner
    Scanner --> Manifest
    Scanner --> ToolResolver
    Scanner --> Runtime
    Scanner --> Constants
    Manifest --> ToolResolver
    ToolResolver --> Runtime
    Runtime --> Pipeline
    Pipeline --> Scripts
    Scripts --> Artifacts
    Runtime --> Artifacts
```

| Component                 | Responsibilities                                                                                                 |
| ------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| CLI (`security_module.cli`)              | User-facing interface with shared options (profile, workspace, export dir, privacy assets, manifest references). |
| Scripts (`scripts/*.py`)  | Standalone helpers invoked by runtimes: summaries, manifest embedding, privacy scan orchestration, attestation.  |
| Dagger Entry (`main.py`)  | Declares public Dagger functions that wrap `SecurityScanner` calls with Dagger directories/services.             |
| SecurityScanner           | Normalizes paths, loads manifests/JSON, builds `ScanRequest`, and dispatches into whichever runtime is available.|
| Manifest & Policy Modules | Parse Cue-exported JSON, load thresholds, and enforce policy before returning metadata for manifest-info files.  |
| Tool Resolver (`tooling.py`) | Maps scan profiles to concrete tools, handles manifest overrides, and determines if stack services are required. |
| Runtime Adapters          | Implement host execution (`LocalRuntime`) and `dagger` execution (`DaggerModuleRuntime`), streaming logs upstream.|
| LightProfilePipeline      | Wires concrete Dagger steps or subprocesses for each tool, identity of artifact directories, and stack services. |
| Artifacts Helpers         | Ensure exports land in deterministic folders and expose `.discover()` for Certus-Assurance artifact bundling.    |
| Constants                 | Centralizes module root paths, exclude patterns, privacy directories, and default export directories.            |
