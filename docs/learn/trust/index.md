# Non-Repudiation & Security Scanning Tutorials

>**STATUS:Tutorial is currently in beta. If you have issues see our [Communication & Support guide](../../about/communication.md)**

Learn how to run security scans with non-repudiation guarantees, enabling compliance, audit trails, and forensic analysis.

## Tutorial Series

### 1. [Non-Repudiation Overview](overview.md)

Understand the concepts of non-repudiation in security scanning.

- What is non-repudiation and why it matters
- Dual-signature architecture (inner + outer)
- Free tier vs premium tier
- Compliance requirements
- When you need it vs when you don't

### 2. [Running a Security Scan with Provenance](security-scans.md)

Run security scans and capture provenance metadata.

- Setting up Certus-Assurance
- Running scans (Trivy, Bandit, Snyk)
- Understanding SARIF output
- Inner signatures and provenance
- S3 storage

### 3. [Passing Scans Through Certus-Trust](verify-trust.md)

Add verification layer and create non-repudiation chain.

- Starting Certus-Trust service
- Transform promotion with tier=premium
- Trust verification process
- Outer signatures
- Recording in Sigstore/Rekor transparency log
- Verification in Certus-Ask

### 4. [Forensic Queries & Audit Trail](audit-queries.md)

Leverage the audit trail for compliance and incident investigation.

- Neo4j graph structure with verification metadata
- Finding verified scans
- Timeline queries for incident investigation
- Chain of custody queries
- Compliance reporting
- Exporting audit trails

### 5. [Publishing Signed Compliance Reports](05-compliance-reporting.md) ⭐ NEW

Generate and publish compliance reports with digital signatures.

- Generating HTML, PDF, and JSON reports
- Signing reports with Cosign
- Publishing to S3 and web servers
- Executive summaries for stakeholders
- Auditor verification workflows
- Automated reporting schedules

### 6. [OCI Attestation Integration](oci-certus-assurance.md)

Integrate with OCI Registry and container attestations.

- Publishing signed artifacts to OCI Registry
- Cosign integration
- Container image signing
- In-toto provenance

---

## Legacy: Secure Scan Tutorial (Incubation)

This guide walks through the **Certus Assurance** prototype that now lives inside Certus TAP. The goal is to experiment with end‑to‑end security scanning (SAST, SBOM, DAST, signing) while we incubate the service in this repo. Everything runs locally, produces the artifact bundle defined in the [Certus Assurance Roadmap](../../../certus-assurance-roadmap.md), and is ready to break out into a standalone deployment later.

> **Heads‑up**: This is a self-contained module (`certus_assurance/`). It does **not** touch the existing ingestion services yet. Treat it as an independent service you can run next to TAP.

---

## 1. Prerequisites

- Python 3.11 virtualenv (`uv sync` or `pip install -e .[dev]`).
- Git installed locally.
- For now, no external scanners are invoked—the pipeline writes placeholder artifacts so the contract and storage layout are locked in.

Optional (once you wire real tools):

- Dagger CLI/engine.
- Trivy, Syft, OWASP ZAP, Cosign binaries on `$PATH`.

---

## 2. Triggering a Scan

Create a short driver script (or use the snippet below inside a notebook) to call the runner directly:

```python
from pathlib import Path

from certus_assurance import ScanRequest, CertusAssuranceRunner

runner = CertusAssuranceRunner(output_root=Path("certus-assurance-artifacts"))
request = ScanRequest(
    test_id="test_local_dev",
    workspace_id="security-demo",
    component_id="trust-smoke-repo",
    assessment_id="local-scan",
    git_url="/app/samples/trust-smoke-repo.git",
    branch="main",
    requested_by="dev@example.com",
    manifest_text='{"version": "1.0"}',
)

result = runner.run(request)
print(result.status)
print(f"Artifacts written to: {result.artifacts.root}")
```

The runner will:

1. Clone the repository into a temporary directory.
2. Generate placeholder SARIF, SBOM, DAST, and signing outputs.
3. Write metadata (`scan.json`) + logs under `certus-assurance-artifacts/scan_local_dev/…`.

You can safely point it at any Git URL (local path or remote). `branch` and `commit` fields are optional; omit them to scan HEAD.

---

## 3. Running the FastAPI Service

Phase 2 adds a thin API wrapper so you can operate Certus Assurance as its own microservice without touching TAP. Launch it with Uvicorn:

```bash
uvicorn certus_assurance.service:app --reload --port 8055
```

This starts a FastAPI app that exposes `POST /v1/security-scans` and `GET /v1/security-scans/{scan_id}`. The service keeps all work in the `certus_assurance/` module, so when you later split it into a standalone repo you can lift this package as-is.

### Configuration

Override settings via environment variables (prefixed with `CERTUS_ASSURANCE_`). Common tweaks during incubation:

| Variable                                      | Purpose                                                  | Example                                                          |
| --------------------------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------- |
| `CERTUS_ASSURANCE_ARTIFACT_ROOT`              | Where to store local artifacts                           | `CERTUS_ASSURANCE_ARTIFACT_ROOT=/tmp/secure-scans`               |
| `CERTUS_ASSURANCE_MAX_WORKERS`                | Threaded worker count for job manager                    | `CERTUS_ASSURANCE_MAX_WORKERS=4`                                 |
| `CERTUS_ASSURANCE_ENABLE_S3_UPLOAD`           | Enable S3 uploads (`true/false`)                         | `CERTUS_ASSURANCE_ENABLE_S3_UPLOAD=true`                         |
| `CERTUS_ASSURANCE_S3_BUCKET`                  | Bucket to receive bundles (LocalStack or AWS)            | `CERTUS_ASSURANCE_S3_BUCKET=tap-secure-pipeline`              |
| `CERTUS_ASSURANCE_S3_ENDPOINT_URL`            | LocalStack endpoint (omit for AWS)                       | `CERTUS_ASSURANCE_S3_ENDPOINT_URL=http://localhost:4566`         |
| `CERTUS_ASSURANCE_ENABLE_REGISTRY_PUSH`       | Enable registry integration (mirror or Docker push)      | `CERTUS_ASSURANCE_ENABLE_REGISTRY_PUSH=true`                     |
| `CERTUS_ASSURANCE_REGISTRY_PUSH_STRATEGY`     | `mirror` (default) or `docker` for real registry pushes  | `CERTUS_ASSURANCE_REGISTRY_PUSH_STRATEGY=docker`                 |
| `CERTUS_ASSURANCE_REGISTRY`                   | Registry hostname (used for metadata + Docker pushes)    | `CERTUS_ASSURANCE_REGISTRY=localhost:5000`                       |
| `CERTUS_ASSURANCE_REGISTRY_REPOSITORY`        | Namespace/repo to store scans                            | `CERTUS_ASSURANCE_REGISTRY_REPOSITORY=certus-assurance`          |
| `CERTUS_ASSURANCE_REGISTRY_MIRROR_DIR`        | Where mirrored attestation/image refs land (mirror mode) | `CERTUS_ASSURANCE_REGISTRY_MIRROR_DIR=certus-assurance-registry` |
| `CERTUS_ASSURANCE_REGISTRY_USERNAME/PASSWORD` | Credentials for Docker registry pushes (optional)        | `CERTUS_ASSURANCE_REGISTRY_USERNAME=admin`                       |
| `CERTUS_ASSURANCE_COSIGN_ENABLED`             | Enable cosign signing/attestations                       | `CERTUS_ASSURANCE_COSIGN_ENABLED=true`                           |
| `CERTUS_ASSURANCE_COSIGN_KEY_REF`             | Path/URI to the cosign signing key                       | `CERTUS_ASSURANCE_COSIGN_KEY_REF=cosign.key`                     |
| `CERTUS_ASSURANCE_COSIGN_PASSWORD`            | Password for the cosign key (optional)                   | `CERTUS_ASSURANCE_COSIGN_PASSWORD=secret`                        |
| `CERTUS_ASSURANCE_COSIGN_PATH`                | Path to the cosign binary                                | `CERTUS_ASSURANCE_COSIGN_PATH=/usr/local/bin/cosign`             |

As long as you keep artifacts on disk, nothing flows into Haystack or other TAP services—perfect for customer-controlled deployments.

## 4. Submitting Scans via the API

Once the service is running you can queue scans end-to-end:

```bash
curl -X POST http://localhost:8056/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_id": "security-demo",
    "component_id": "trust-smoke-repo",
    "assessment_id": "initial-scan",
    "git_url": "/app/samples/trust-smoke-repo.git",
    "branch": "main",
    "requested_by": "dev@example.com",
    "manifest": {"version": "1.0"}
  }'
```

Response:

```json
{ "scan_id": "scan_d2e4b65c1234", "status": "QUEUED" }
```

Poll for status (and artifact pointers) until you see `SUCCEEDED` or `FAILED`:

```bash
curl http://localhost:8055/v1/security-scans/scan_d2e4b65c1234 | jq
```

While Phase 2 keeps artifact bundles on the local filesystem, the schema already matches the S3/registry contract from the roadmap. Swapping the storage layer later simply means uploading `certus-assurance-artifacts/<scan_id>/…` to your preferred bucket.

## 5. Shipping Artifacts to LocalStack S3

If you want the prototype to behave like a customer deployment, point Certus Assurance at LocalStack (or AWS) and enable uploads:

```bash
export CERTUS_ASSURANCE_ENABLE_S3_UPLOAD=true
export CERTUS_ASSURANCE_S3_BUCKET=tap-secure-pipeline
export CERTUS_ASSURANCE_S3_ENDPOINT_URL=http://localhost:4566
uvicorn certus_assurance.service:app --reload --port 8055
```

Every scan now mirrors its bundle under `s3://tap-secure-pipeline/security-scans/<scan_id>/…`. The API response includes a `remote_artifacts` map so you can confirm the exact object URIs without hitting OpenSearch or Haystack. Because uploads run through boto3, the same code works against AWS by dropping the LocalStack endpoint variables.

## 6. Mirroring or Pushing to Registries

There are two ways to surface signing outputs without touching the rest of TAP:

### Mirror mode (default)

```bash
export CERTUS_ASSURANCE_ENABLE_REGISTRY_PUSH=true
export CERTUS_ASSURANCE_REGISTRY_PUSH_STRATEGY=mirror
export CERTUS_ASSURANCE_REGISTRY_MIRROR_DIR=certus-assurance-registry
```

After each scan finishes you’ll find `image.txt`, `image.digest`, and `reports/signing/cosign.attestation.jsonl` copied under `certus-assurance-registry/<scan_id>/…`. This is perfect when you want a filesystem drop that mimics a registry+attestation store.

### Docker registry mode

To exercise the actual registry you already use for other services, flip to Docker pushes:

```bash
export CERTUS_ASSURANCE_ENABLE_REGISTRY_PUSH=true
export CERTUS_ASSURANCE_REGISTRY_PUSH_STRATEGY=docker
export CERTUS_ASSURANCE_REGISTRY=localhost:5000
export CERTUS_ASSURANCE_REGISTRY_REPOSITORY=certus_assurance
# Optional if your registry requires auth
export CERTUS_ASSURANCE_REGISTRY_USERNAME=admin
export CERTUS_ASSURANCE_REGISTRY_PASSWORD=secret

# Make sure your local Docker daemon is logged in to the registry first
docker login localhost:5000 -u admin -p secret

uvicorn certus_assurance.service:app --reload --port 8055
```

Certus Assurance will build a tiny `FROM scratch` image that embeds each scan’s metadata, tag it using the same registry namespace as the roadmap contract, and push it to `localhost:5000/certus_assurance/<repo>:<commit>`. Because this still runs inside the incubating module, you can test registry ingestion without coupling to the rest of TAP.

### Cosign signing + in-toto attestations

To exercise provenance ahead of real scanners, enable cosign alongside the Docker push mode:

```bash
export CERTUS_ASSURANCE_COSIGN_ENABLED=true
export CERTUS_ASSURANCE_COSIGN_KEY_REF=$HOME/.cosign/cosign.key
export CERTUS_ASSURANCE_COSIGN_PASSWORD=localpass
export CERTUS_ASSURANCE_COSIGN_PATH=$(which cosign)
```

Every pushed image is now signed with cosign, and the same `scan.json` predicate is uploaded as an in-toto attestation (`cosign attest --predicate scan.json --type https://slsa.dev/provenance/v1`). You can verify directly via cosign:

```bash
IMAGE=$(curl -s http://localhost:8055/v1/security-scans/$SCAN_ID | jq -r '.registry.image_reference')
COSIGN_PASSWORD=$CERTUS_ASSURANCE_COSIGN_PASSWORD cosign verify --key $CERTUS_ASSURANCE_COSIGN_KEY_REF $IMAGE
COSIGN_PASSWORD=$CERTUS_ASSURANCE_COSIGN_PASSWORD cosign verify-attestation --type https://slsa.dev/provenance/v1 --key $CERTUS_ASSURANCE_COSIGN_KEY_REF $IMAGE
```

The API response’s `registry.cosign` block also reports whether cosign ran successfully and where the predicate lives on disk.

## 7. Artifact Layout

After a run finishes, inspect `certus-assurance-artifacts/<scan_id>/`:

```
scan_local_dev/
├── artifacts/
│   ├── image.digest
│   └── image.txt
├── logs/runner.log
├── reports/
│   ├── dast/zap-report.{html,json}
│   ├── sast/trivy.sarif.json
│   ├── sbom/syft.spdx.json
│   └── signing/cosign.attestation.jsonl
└── scan.json
```

`scan.json` mirrors the future API contract and includes pointers to every file so they can be uploaded to S3 or returned via presigned URLs.

---

## 8. Next Steps

Phase 1 stops at producing artifacts. The upcoming milestones will:

- Streamline the API worker (swap the threadpool job manager for Celery or an external queue).
- Push artifacts to S3 / registry and expose presigned URLs.
- Stream logs over WebSockets and offer a minimal UI.

While those pieces are under construction, you can already:

- Verify the artifact schema with downstream systems.
- Build ingestion jobs that watch `certus-assurance-artifacts/` (or a future S3 bucket) and feed SARIF/SBOM data back into TAP.
- Swap in real scanners inside `certus_assurance/pipeline.py` step-by-step.

If you want to experiment with S3 uploads or a command-line wrapper now, create a thin script that copies `certus-assurance-artifacts/<scan_id>/` to your preferred storage. The rest of TAP remains untouched until we wire the official API in Phase 2.
