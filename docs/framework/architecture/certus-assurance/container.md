# Container View

```mermaid
graph LR
    subgraph Compose["docker-compose.certus.yml"]
        Assurance["certus-assurance (FastAPI 8056)"]
        LocalStack["LocalStack (raw/golden)"]
        Registry["Local OCI mirror (optional)"]
        Trust["certus-trust"]
    end

    security_module["security_module runtime"]:::ext
    Operators["CLI / UI / Agents"]:::ext

    Operators --> Assurance
    Assurance --> security_module
    Assurance --> LocalStack
    Assurance --> Registry
    Assurance --> Trust

    classDef ext fill:#2c2e3e,stroke:#c6a76b,color:#f5f5f2;
```

## Runtime Components

```mermaid
graph TB
    subgraph certus-assurance
        Router["FastAPI Router (/v1/security-scans, /stats, /health)"]
        JobManager["ScanJobManager (ThreadPool)"]
        Runner["CertusAssuranceRunner (pipeline)"]
        ManifestFetcher["ManifestFetcher (inline/file/URI)"]
        ArtifactPublisher["TransformArtifactPublisher (S3)"]
        RegistryPublisher["RegistryMirror/DockerPublisher"]
        Cosign["CosignClient (optional)"]
        LogStreams["LogStreamManager + WebSockets"]
    end

    Router --> JobManager
    JobManager --> Runner
    Runner --> ManifestFetcher
    Runner --> LogStreams
    Runner --> ArtifactPublisher
    Runner --> RegistryPublisher
    Runner --> Cosign
    ArtifactPublisher --> LocalStack
    RegistryPublisher --> Registry
    Router --> Trust
```

| Component                  | Responsibilities                                                                          |
| -------------------------- | ----------------------------------------------------------------------------------------- |
| FastAPI Router             | Exposes scan submission, status, WebSocket streams, upload requests, and stats endpoints. |
| ScanJobManager             | Queues scans in a thread pool and tracks status/metadata.                                 |
| CertusAssuranceRunner      | Clones repos, loads manifests, runs security_module scanners, bundles artifacts.          |
| ManifestFetcher            | Resolves manifests from inline JSON, repo paths, or URIs (S3/OCI).                        |
| TransformArtifactPublisher | Uploads bundles to raw → golden S3 buckets with metadata, ready for Transform ingestion.  |
| Registry Publishers        | Either mirror artifacts to disk or push tiny OCI images signed via cosign.                |
| LogStreamManager           | Keeps per-scan log history and streams events over WebSockets.                            |
| Cosign Client              | Optional signing of manifests/bundles prior to registry publication.                      |
| Certus-Trust               | Receives upload request payloads and returns permission + verification proof.             |
