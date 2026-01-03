# Component View (C4 Level 3)

```mermaid
graph TB
    subgraph FastAPI_App["certus_transform.main:app"]
        Uploads["Uploads Router (/v1/uploads)"]
        Privacy["Privacy Router (/v1/privacy/scan)"]
        Promotion["Promotion Router (/v1/promotions)"]
        Ingest["Ingest Router (/v1/ingest/security)"]
        Verification["Verification Router (/v1/execute-upload)"]
        Health["Health Router (/health, /health/stats)"]
    end

    S3Client["services.s3_client.get_s3_client"]
    Presidio["certus_integrity Presidio Analyzer"]
    SaaS["services.saas.ingest_security_keys"]
    Trust["services.trust.TrustClient"]
    LocalStack["S3-Compatible Buckets"]
    Registry["OCI Registry"]
    Ask["Certus-Ask SaaS"]
    TrustSvc["Certus-Trust"]

    Uploads --> S3Client --> LocalStack
    Privacy --> Presidio
    Privacy --> S3Client
    Promotion --> S3Client
    Ingest --> SaaS --> Ask
    Verification --> S3Client
    Verification --> Trust
    Verification --> LocalStack
    Verification --> Registry
    Trust --> TrustSvc
    Health --> FastAPI_App
```

| Component        | Responsibilities                                                                                                       |
| ---------------- | --------------------------------------------------------------------------------------------------------------------- |
| Uploads Router   | Single-file uploads into raw/active prefixes with configurable destination folders.                                   |
| Privacy Router   | Scans raw prefixes with Presidio, quarantines detections under `<prefix>/quarantine/`, writes optional scan reports.  |
| Promotion Router | Legacy raw→golden copy logic for environments that do not use verification-first workflow.                            |
| Ingest Router    | Calls Certus-Ask SaaS ingestion endpoints with golden keys for SARIF/SPDX pipelines.                                  |
| Verification Router | Receives `/v1/execute-upload` from Certus-Trust, writes markers/artifacts to S3 and optional OCI registry, records metadata. |
| Health Router    | Liveness/stats endpoints tracking upload counts, quarantines, promotions, etc.                                        |
| S3 Client        | Memoized boto3 client pinned to customer LocalStack/S3.                                                               |
| Trust Client     | Optional helper for verifying chains (mirrors Certus-Trust API).                                                      |
| SaaS Client      | HTTPX helper that forwards golden keys to Certus-Ask ingestion endpoints.                                             |
