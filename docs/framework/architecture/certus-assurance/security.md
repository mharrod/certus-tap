# Security

Certus-Assurance is the entry point for untrusted repositories and manifests, so the service enforces verification before executing scanners or uploading anything to shared storage. The diagrams below call out the trust boundaries and the controls that harden each hop.

## Data Flow & Trust Boundaries

```mermaid
graph TB
    Operators["Operators / Automation"]
    API["Certus-Assurance API"]
    Runner["CertusAssuranceRunner"]
    Runtime["security_module runtime / Sample scanner"]
    ManifestFetcher["ManifestFetcher"]
    Cosign["CosignClient / cosign CLI"]
    Trust["Certus-Trust"]
    S3["S3-Compatible Layer (raw→golden)"]
    Registry["OCI Registry / Mirror"]
    Transform["Certus-Transform"]

    Operators --> API
    API --> Runner
    Runner --> ManifestFetcher
    ManifestFetcher --> S3
    Runner --> Runtime
    Runner --> Cosign
    API --> Trust
    API --> S3
    API --> Registry
    Trust --> S3
    S3 --> Transform
```

Trust boundaries:

- **Caller → API:** Authenticated HTTP (for automation) plus WebSocket streaming. Payload validation ensures one manifest source is provided.
- **Runner → External Inputs:** Repository clones, manifest downloads, and optional runtime execution are sandboxed under the artifact root with per-run directories.
- **Assurance → Trust:** Uploads never leave the host until `/v1/verify-and-permit-upload` returns `permitted=true`.
- **Publishing → Storage:** The `TransformArtifactPublisher` writes to raw prefixes first, then promotes to golden buckets within the S3-compatible layer.

## Manifest Verification & Execution

```mermaid
sequenceDiagram
    participant Caller
    participant Runner as CertusAssuranceRunner
    participant Fetcher as ManifestFetcher
    participant Cosign
    participant Runtime as security_module runtime

    Caller->>Runner: Provide manifest (inline, repo path, s3://, oci://)
    alt Remote manifest
        Runner->>Fetcher: fetch(uri, signature_uri)
        Fetcher-->>Runner: manifest.json + manifest.sig
    else Inline / repo path
        Runner->>Runner: read manifest + hash
    end
    opt Verification required
        Runner->>Cosign: verify_blob(manifest.json, manifest.sig, key_ref)
        Cosign-->>Runner: signature valid
    end
    Runner->>Runtime: execute scanners defined in manifest profile
    Runtime-->>Runner: findings, attestation, logs
    Runner->>Runner: emit structured events + build artifact bundle
```

Controls:

- `manifest_verification_required` enforces cosign verification before the runtime executes.
- The runner keeps manifests, logs, and bundles under a per-test folder, preventing cross-run contamination.
- When `security_module.runtime` is unavailable the `SampleSecurityScanner` runs against canned inputs so secrets are never fetched.

## Upload Gating & Publication

```mermaid
sequenceDiagram
    participant Runner as Upload Request Builder
    participant Trust as Certus-Trust
    participant Cosign
    participant S3 as S3-Compatible Layer
    participant Registry as Registry Publisher
    participant Transform as Certus-Transform

    Runner->>Trust: POST /v1/verify-and-permit-upload (artifacts, hashes, inner signature)
    alt Verification succeeds
        Trust-->>Runner: permitted=true + verification_proof + permission_id
        Runner->>Cosign: sign manifest/blob when registry push requires attestation
        Runner->>S3: stage bundle under raw prefix → copy to golden
        Runner->>Registry: push/mirror scan image + signatures
        S3-->>Transform: golden artifacts ready for ingestion
    else Verification fails
        Trust-->>Runner: permitted=false + reason
    end
```

Controls:

- Upload permissions include the manifest digest, git metadata, and signer identity. They are stored with the job record for downstream auditing.
- `TransformArtifactPublisher` copies files inside the S3 endpoint so data never traverses the public internet.
- Registry pushes can be routed through cosign for image and manifest signatures; credentials are injected at runtime and not stored on disk.
- WebSocket streams append `scan_complete` with the manifest digest so clients can confirm they are referencing the verified bundle.

## Residual Risks & Work in Progress

- Artifact storage currently resides on the same node that runs the FastAPI process. Harden this directory with disk encryption and prune old bundles automatically.
- Authentication/authorization middleware is still in progress; today’s dev builds rely on network isolation. Production deployments must enforce OIDC tokens or per-tenant API keys.
- The upload workflow retries LocalStack/S3 failures but not registry pushes; add exponential backoff before widening access.
- Managed runtime execution assumes the scanners themselves are safe. Consider sandboxing (Firecracker, containerized workers) when executing arbitrary manifests.
