# Component View (C4 Level 3)

This view breaks down the Certus-Assurance FastAPI service into the components that orchestrate scans, manage manifests, and publish verified bundles.

```mermaid
graph TB
    Operators["Operators / API Clients"]

    subgraph FastAPI["FastAPI Router (/v1/security-scans)"]
        Router["Security Scan Router\n(certus_assurance.api)"]
        StreamEndpoint["WebSocket Handler\n(stream_scan_logs)"]
        UploadEndpoint["Upload Request Endpoint\n(/upload-request)"]
    end

    subgraph Control["Execution Control"]
        Jobs["ScanJobManager\n(jobs.py)"]
        Logs["LogStreamManager\n(logs.py)"]
    end

    subgraph Pipeline["certus_assurance.pipeline"]
        Runner["CertusAssuranceRunner"]
        ManifestFetcher["ManifestFetcher\n(manifest.py)"]
        Runtime["ManagedRuntime / SampleSecurityScanner"]
        Cosign["CosignClient\n(signing.py)"]
    end

    subgraph Publishers["Artifact Publishers"]
        S3Publisher["TransformArtifactPublisher\n(storage.py)"]
        RegistryPublisher["RegistryMirrorPublisher /\nDockerRegistryPublisher"]
    end

    Git["Git Repositories"]
    SecModule["security_module runtime"]
    Trust["Certus-Trust /v1/verify-and-permit-upload"]
    S3["S3-Compatible Layer"]
    Registry["OCI Registry / Mirror"]
    Transform["Certus-Transform"]

    Operators --> Router
    Router --> Jobs
    Router --> StreamEndpoint
    Router --> UploadEndpoint
    Jobs --> Logs
    StreamEndpoint --> Logs
    Jobs --> Runner
    Runner --> ManifestFetcher
    Runner --> Runtime
    Runner --> Cosign
    Runner --> Logs
    ManifestFetcher --> S3
    Runtime --> SecModule
    Runner --> Git
    UploadEndpoint --> Trust
    UploadEndpoint --> S3Publisher
    UploadEndpoint --> RegistryPublisher
    S3Publisher --> S3
    S3Publisher --> Transform
    RegistryPublisher --> Registry
```

| Component                              | Responsibilities                                                                                                                                                           |
| -------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Security Scan Router                   | Implements `/v1/security-scans` POST/GET plus dependency wiring (settings, runner, publishers). Validates manifests, schedules jobs, and exposes stream URLs.              |
| WebSocket Handler                      | Bridges `LogStreamManager` histories and live events to clients so they can follow the pipeline without polling.                                                           |
| Upload Request Endpoint                | Builds Trust `UploadRequest` payloads from stored artifacts, calls `_submit_upload_request`, and invokes publishers when permission is granted.                            |
| ScanJobManager                         | ThreadPool-backed controller that tracks job lifecycle, persists metadata in-memory, and exposes status queries.                                                           |
| LogStreamManager                       | Allocates `LogStream` queues per scan, buffers history for late subscribers, and brokers runner emissions to WebSocket clients.                                            |
| CertusAssuranceRunner                  | Clones repositories, resolves manifests (inline, repo path, S3, or OCI), executes the security module runtime or sample scanner, and composes artifact bundles + metadata. |
| ManifestFetcher                        | Downloads manifests/signatures from the caller’s preferred location (local path, S3, OCI image) before handing them to the runner for verification.                        |
| ManagedRuntime / SampleSecurityScanner | Either executes the shared `security_module` runtime or the built-in sample scanner when ManagedRuntime is unavailable.                                                    |
| CosignClient                           | Wraps the cosign CLI for blob signing, attestation, and manifest verification. Used for both registry pushes and manifest validation.                                      |
| TransformArtifactPublisher             | Implements the raw→golden promotion workflow over the configured S3-compatible layer so downstream services ingest consistent bundles.                                     |
| Registry Publishers                    | Either mirror reports to a local filesystem (development) or build/push minimalist OCI images, optionally signing with cosign.                                             |
| Certus-Trust Integration               | `_submit_upload_request` contacts `/v1/verify-and-permit-upload` before anything leaves the host, ensuring only verified runs are published.                               |
