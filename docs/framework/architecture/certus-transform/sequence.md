# Sequence Diagrams

## Verification-First Upload (`/v1/execute-upload`)

```mermaid
sequenceDiagram
    participant Trust as Certus-Trust
    participant Transform as Certus-Transform
    participant S3 as S3-Compatible Layer
    participant OCI as OCI Registry

    Trust->>Transform: POST /v1/execute-upload (artifacts + proof)
    Transform->>Transform: Validate request, increment counters
    Transform->>S3: Write marker/artifact with verification metadata
    opt Storage config includes OCI
        Transform->>OCI: Push image/tag
    end
    Transform-->>Trust: 200 + uploaded_artifacts + S3/OCI references
```

## Privacy Scan and Quarantine (`/v1/privacy/scan`)

```mermaid
sequenceDiagram
    participant Operator
    participant Transform
    participant Analyzer as Presidio Analyzer
    participant S3 as S3-Compatible Layer

    Operator->>Transform: POST /v1/privacy/scan (bucket/prefix)
    Transform->>S3: List objects under prefix
    loop for each object
        Transform->>S3: GET object
        Transform->>Analyzer: analyze(text)
        alt Findings detected
            Transform->>S3: COPY object to quarantine prefix
            Transform->>S3: DELETE original
        end
    end
    alt report requested
        Transform->>S3: PUT plaintext report
    end
    Transform-->>Operator: summary (scanned/quarantined/report key)
```

## Legacy Promotion (`/v1/promotions/golden`)

```mermaid
sequenceDiagram
    participant Operator
    participant Transform
    participant S3 as S3-Compatible Layer

    Operator->>Transform: POST /v1/promotions/golden (raw keys)
    Transform->>S3: COPY each key to golden bucket/prefix
    alt copy succeeds
        Transform->>Transform: increment promotion_success
        Transform-->>Operator: promoted key list
    else copy fails
        Transform->>Transform: increment promotion_failed
        Transform-->>Operator: HTTP 500 with error
    end
```

## Golden Ingestion (`/v1/ingest/security`)

```mermaid
sequenceDiagram
    participant Operator
    participant Transform
    participant SaaS as Certus-Ask Backend

    Operator->>Transform: POST /v1/ingest/security {workspace, keys}
    Transform->>SaaS: POST /v1/{workspace}/index/security/s3 (one per key)
    SaaS-->>Transform: Ingestion response
    Transform-->>Operator: workspace_id + responses
```
