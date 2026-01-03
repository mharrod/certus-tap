# Sequence Diagrams

## `/v1/sign` – Keyless Signing Flow

```mermaid
sequenceDiagram
    participant Assurance as Certus-Assurance
    participant Trust as Certus-Trust API
    participant Fulcio as Fulcio/Keycloak
    participant Rekor as Rekor Log

    Assurance->>Trust: POST /v1/sign (artifact hash + metadata)
    alt mock_sigstore=true
        Trust->>Trust: Generate mock signature + log entry
        Trust-->>Assurance: 202 + mock signature/certificate
    else mock_sigstore=false
        Trust->>Fulcio: Request short-lived cert (OIDC token)
        Fulcio-->>Trust: Certificate + subject
        Trust->>Rekor: Submit entry (hash + signature + cert)
        Rekor-->>Trust: UUID + log index + timestamp
        Trust-->>Assurance: 202 + signature + transparency entry
    end
```

## `/v1/verify` – Signature Verification

```mermaid
sequenceDiagram
    participant Client as Caller
    participant Trust as Certus-Trust
    participant Rekor as Rekor

    Client->>Trust: POST /v1/verify (artifact hash + signature)
    Trust->>Trust: Cryptographically verify signature
    Trust->>Rekor: Search entries by artifact hash
    alt Entry found & matches signer
        Rekor-->>Trust: Matching entry metadata
        Trust-->>Client: valid=true, signer, transparency_index
    else No entry / mismatch
        Trust-->>Client: valid=false, details
    end
```

## `/v1/sign-artifact` and `/v1/verify-chain`

```mermaid
sequenceDiagram
    participant Assurance
    participant Trust
    participant Rekor

    Assurance->>Trust: POST /v1/sign-artifact (assessment bundle)
    Trust->>Trust: Verify inner signatures + artifact locations
    Trust->>Rekor: (future) Record outer signature
    Trust-->>Assurance: Outer signature + verification proof

    Assurance->>Trust: POST /v1/verify-chain
    Trust->>Trust: Check inner + outer signatures + Sigstore timestamps
    Trust-->>Assurance: chain_verified true/false
```

## `/v1/verify-and-permit-upload` – Gatekeeper Workflow

```mermaid
sequenceDiagram
    participant Assurance
    participant Trust
    participant Signing as Signing Service
    participant Transform as Certus-Transform

    Assurance->>Trust: POST /v1/verify-and-permit-upload (scan metadata + artifacts)
    Trust->>Trust: Validate inner signature + artifact list
    alt Verification succeeds
        Trust->>Signing: Sign upload bundle (mock or Sigstore)
        Signing-->>Trust: Rekor entry uuid + signature
        Trust->>Transform: POST /v1/execute-upload (async)
        Trust-->>Assurance: UploadPermission permitted=true (+proof, storage config)
    else Verification fails
        Trust-->>Assurance: UploadPermission permitted=false (+reason)
    end
```

## `/v1/transparency` – Transparency Queries

```mermaid
sequenceDiagram
    participant Client
    participant Trust
    participant Rekor

    Client->>Trust: GET /v1/transparency/{entry_id}?include_proof=true
    alt mock mode
        Trust->>Trust: Fetch entry from in-memory log + build mock proof
        Trust-->>Client: TransparencyLogEntry + proof hashes
    else production
        Trust->>Rekor: Fetch entry + inclusion proof
        Rekor-->>Trust: Entry payload
        Trust-->>Client: TransparencyLogEntry + proof
    end
```
