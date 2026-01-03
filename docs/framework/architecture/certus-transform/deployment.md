# Deployment

## Local Developer Stack

```mermaid
graph TB
    subgraph DevLaptop
        subgraph Compose["docker-compose.yml"]
            Transform["certus-transform 8100"]
            LocalStack["LocalStack (raw/golden)"]
            Registry["OCI Registry (optional)"]
        end
    end

    Trust["certus-trust"]:::ext
    Assurance["certus-assurance"]:::ext

    Assurance --> Transform
    Trust --> Transform
    Transform --> LocalStack
    Transform --> Registry

    classDef ext fill:#2c2e3e,stroke:#c6a76b,color:#f5f5f2;
```

| Service             | Notes                                                                                             |
| ------------------- | ------------------------------------------------------------------------------------------------- |
| certus-transform    | FastAPI container exposing `/v1/*` routes for uploads, privacy scans, verification, ingestion.    |
| LocalStack          | Raw/quarantine/golden buckets; use `AWS_ACCESS_KEY_ID/SECRET` from `.env`.                        |
| OCI Registry        | Optional registry container; `_push_to_oci_registry` simply creates tags/markers for testing.     |
| certus-trust        | Sends `/v1/execute-upload` requests once signatures are verified.                                 |
| certus-assurance    | Legacy workflows can still call upload/promotion APIs.                                            |

## Production Blueprint

```mermaid
graph LR
    subgraph CustomerVPC
        subgraph AppTier
            ALB["API Gateway / WAF"]
            Transform["certus-transform\n(ECS/K8s)"]
        end

        subgraph Storage
            Raw["S3 raw bucket"]
            Golden["S3 golden bucket"]
            Registry["OCI registry (ECR/Harbor)"]
        end
    end

    Trust["Certus-Trust"]:::ext --> ALB --> Transform
    Assurance["Certus-Assurance"]:::ext --> ALB
    Transform --> Raw
    Transform --> Golden
    Transform --> Registry
    Transform --> SaaS["Certus-Ask SaaS"]:::ext
```

Deployment considerations:

- **Network:** Keep S3/OCI endpoints private; only expose ALB/WAF for API clients (Assurance/Trust/operators).
- **Secrets:** Store AWS credentials, SaaS API keys, and Trust tokens in a secret manager (not `.env`).
- **Observability:** Ship `/health/stats` metrics into whatever telemetry stack backs the rest of TAP.
- **Scaling:** The verification-first workflow is CPU-light; autoscale on request rate or queue depth if future async workers are added.
