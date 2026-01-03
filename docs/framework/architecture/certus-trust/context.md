# Context

Certus-Trust is the signing, verification, and transparency service that backs the Certus platform’s non‑repudiation guarantees. It exposes HTTP APIs (FastAPI) that wrap Sigstore (Fulcio, Rekor, TUF) and orchestrates policy workflows with other Certus services.

## System Context (C4 Level 1)

```mermaid
graph TB
    subgraph Users
        Assurance["Certus-Assurance Service"]
        Transform["Certus-Transform Service"]
        Operators["Platform Operators / API Clients"]
    end

    subgraph Trust["Certus-Trust"]
        API["FastAPI HTTP API"]
    end

    subgraph Sigstore["Sigstore Stack"]
        Fulcio["Fulcio CA / OIDC"]
        Rekor["Rekor Transparency Log"]
        TUF["TUF Metadata Svc"]
        Keycloak["Keycloak (OIDC Provider)"]
    end

    subgraph Storage["S3-Compatible Layer (LocalStack)"]
        Buckets["raw/ · processed/ prefixes"]
    end

    Assurance -->|Sign, Verify, Non-Repudiation| API
    Transform -->|verify-and-permit-upload| API
    Operators -->|Health, Keys, Stats| API

    API --> Fulcio
    API --> Rekor
    API --> TUF
    API --> Keycloak
    API --> Buckets
    API --> Transform

```

| Actor / System                   | Description                                                                                                  |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------ |
| Certus-Assurance                 | Produces scan artifacts and inner signatures; invokes Certus-Trust to sign/verify evidence.                  |
| Certus-Transform                 | Receives upload permissions from Trust before writing to the S3-compatible layer or registries.              |
| Platform Operators / API Clients | Call health, stats, transparency, and key distribution endpoints.                                            |
| Fulcio / Keycloak                | Provide certificates and identity for keyless signing.                                                       |
| Rekor                            | Stores transparency log entries for signatures and non-repudiation proofs.                                   |
| TUF                              | Publishes signing keys/metadata for downstream consumers.                                                    |
| S3-Compatible Layer (LocalStack) | Local buckets used when Trust issues upload permissions or references artifact locations.                    |
| Certus-Trust FastAPI API         | Single container exposing `/v1/sign`, `/v1/verify`, `/v1/transparency`, `/v1/verify-and-permit-upload`, etc. |
