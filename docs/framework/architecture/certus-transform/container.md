# Container View (C4 Level 2)

The data prep service ships as a single FastAPI container with LocalStack S3, an optional OCI registry, and outbound HTTP calls to Certus-Trust and the Certus-Ask SaaS backend.

## Local Compose Stack

```mermaid
graph LR
    subgraph Compose["docker-compose.yml"]
        Transform["certus-transform\n(FastAPI 8100)"]
        LocalStack["S3-Compatible Layer"]
        Registry["Local OCI Registry (optional)"]
    end

    Trust["certus-trust"]:::ext
    Ask["certus-ask (SaaS)"]:::ext

    Transform --> LocalStack
    Transform --> Registry
    Transform --> Trust
    Transform --> Ask

    classDef ext fill:#2c2e3e,stroke:#c6a76b,color:#f5f5f2;
```

| Container        | Responsibilities                                                                 |
| ---------------- | ------------------------------------------------------------------------------- |
| certus-transform | Hosts FastAPI routers for uploads, privacy scans, promotions, verification, etc.|
| S3-Compatible    | Raw/quarantine/golden buckets (LocalStack in dev, AWS S3 in prod).              |
| Local Registry   | Optional OCI registry mirror for verified bundles.                              |
| certus-trust     | Verifies scans and calls Transform to execute uploads (gatekeeper).            |
| certus-ask       | Receives golden keys via `/v1/ingest/security`.                                 |

## Runtime Components

```mermaid
graph TB
    subgraph FastAPI
        Router["APIRouters (uploads/privacy/promotion/ingest/verification/health)"]
        Uploads["Uploads Router"]
        Privacy["Privacy Router (Presidio scans)"]
        Promotion["Promotion Router"]
        Verification["Verification Router (/v1/execute-upload)"]
        Ingest["Ingest Router (SaaS bridge)"]
        Health["Health & stats"]
    end

    S3Client["Boto3 LocalStack Client"]
    PrivacySvc["Presidio Analyzer"]
    TrustClient["Trust Client"]
    SaaSClient["Certus-Ask HTTP Client"]
    LocalStack["S3-Compatible Layer"]
    Registry["OCI Registry"]

    Router --> Uploads
    Router --> Privacy
    Router --> Promotion
    Router --> Verification
    Router --> Ingest
    Router --> Health

    Uploads --> S3Client
    Privacy --> PrivacySvc
    Privacy --> S3Client
    Promotion --> S3Client
    Verification --> TrustClient
    Verification --> S3Client
    Verification --> Registry
    Ingest --> SaaSClient
```

| Component        | Notes                                                                                           |
| ---------------- | ----------------------------------------------------------------------------------------------- |
| Uploads Router   | Streams user uploads into `raw` bucket prefixes.                                                |
| Privacy Router   | Runs Presidio scans, quarantines findings, writes optional reports.                             |
| Promotion Router | Legacy promotion path (raw → golden) for basic tier environments.                               |
| Verification Router | Handles `/v1/execute-upload` and `/v1/execute-upload/batch`, writes to S3/OCI with proof.    |
| Ingest Router    | Calls Certus-Ask SaaS ingestion endpoints for golden keys.                                      |
| Health Router    | Exposes `/health` + `/health/stats`.                                                            |
| Trust Client     | Optional helper when Transform needs to re-verify a chain.                                      |
| SaaS Client      | HTTPX client hitting Certus-Ask `/v1/{workspace}/index/security/s3`.                            |
