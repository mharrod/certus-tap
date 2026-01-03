# OCI Attestations for Product Acquisition Review

This folder contains mock OCI artifacts (SBOMs, attestations, scan results) that demonstrate how to verify signed security data from an OCI registry during a product acquisition review.

## Overview

The attestation workflow:

```
[Generate mock artifacts]
    ↓
[Sign with cosign]
    ↓
[Push to local OCI registry]
    ↓
[Verify signatures during acquisition review]
    ↓
[Ingest verified data into Certus TAP]
```

## Quick Start

### 1. Generate Attestations

```bash
python scripts/oci-attestations.py generate \
  --output samples/oci-attestations/artifacts \
  --product "Acme Product" \
  --version "1.0.0"
```

Generates:

- SPDX Software Bill of Materials (SBOM)
- in-toto build attestation
- SARIF security scan results

### 2. Generate/Load Cosign Keys

```bash
# Generate test cosign key pair (if not exists)
python scripts/oci-attestations.py setup-keys \
  --key-path samples/oci-attestations/keys/cosign.key

# Public key is auto-saved to cosign.pub
```

### 3. Sign Artifacts

```bash
python scripts/oci-attestations.py sign \
  --artifacts-dir samples/oci-attestations/artifacts \
  --key-path samples/oci-attestations/keys/cosign.key
```

Creates `.sig` files for each artifact.

### 4. Push to OCI Registry

```bash
python scripts/oci-attestations.py push \
  --artifacts-dir samples/oci-attestations/artifacts \
  --registry http://localhost:5000 \
  --repo product-acquisition/acme
```

### 5. Verify from OCI Registry

```bash
python scripts/oci-attestations.py verify \
  --registry http://localhost:5000 \
  --repo product-acquisition/acme \
  --key-path samples/oci-attestations/keys/cosign.pub
```

## Folder Structure

```
samples/oci-attestations/
├── README.md                          # This file
├── artifacts/
│   ├── sbom/
│   │   ├── product.spdx.json          # Generated SPDX SBOM
│   │   └── product.spdx.json.sig      # Cosign signature
│   ├── attestations/
│   │   ├── build.intoto.json          # Generated in-toto attestation
│   │   └── build.intoto.json.sig      # Cosign signature
│   ├── scans/
│   │   ├── vulnerability.sarif        # Generated SARIF scan results
│   │   └── vulnerability.sarif.sig    # Cosign signature
│   ├── privacy/
│   │   ├── privacy-scan.json          # Presidio privacy scan summary
│   │   └── privacy-scan.json.sig      # Cosign signature
│   └── provenance/
│       ├── slsa-provenance.json       # Generated SLSA v1.0 provenance (with embedded SBOM)
│       └── slsa-provenance.json.sig   # Cosign signature
└── keys/
    ├── cosign.key                     # Test signing key (GITIGNORE)
    └── cosign.pub                     # Public key for verification
```

## Configuration

Edit `scripts/oci_attestations_config.yaml`:

```yaml
registry:
  url: http://localhost:5000
  username: ''
  password: ''
  default_repo: product-acquisition/attestations

product:
  name: 'Acme Product'
  version: '1.0.0'
  vendor: 'ACME Corp'
  org: 'acme-org'
  repo: 'acme-product'

cosign:
  key_file: samples/oci-attestations/keys/cosign.key
  pub_key: samples/oci-attestations/keys/cosign.pub
```

## What Gets Generated

### SPDX SBOM (Software Bill of Materials)

Provides complete package inventory with versions:

```json
{
  "spdxVersion": "SPDX-2.3",
  "creationInfo": {
    "created": "2024-11-20T...",
    "creators": ["Tool: oci-attestations"]
  },
  "packages": [
    {
      "name": "flask",
      "version": "2.3.0",
      "downloadLocation": "https://pypi.org/project/flask",
      "filesAnalyzed": false
    }
  ]
}
```

### in-toto Attestation

Cryptographically signs the build process:

```json
{
  "_type": "link",
  "name": "build",
  "materials": {},
  "products": {
    "sbom.json": {
      "sha256": "abc123..."
    }
  },
  "byproducts": {
    "stdout": "Build successful",
    "version": "1.0.0"
  },
  "environment": {},
  "command": ["make", "build"],
  "return-value": 0
}
```

### SARIF Scan Results

Security vulnerability findings:

```json
{
  "version": "2.1.0",
  "runs": [
    {
      "tool": {
        "driver": {
          "name": "MockScanner",
          "version": "1.0"
        }
      },
      "results": [
        {
          "ruleId": "CWE-89",
          "level": "error",
          "message": {
            "text": "SQL Injection vulnerability"
          },
          "locations": [...]
        }
      ]
    }
  ]
}
```

### Privacy Scan Evidence (Presidio)

Demonstrates that sensitive data was scanned and either redacted or flagged:

```json
{
  "scanner": {
    "name": "Presidio Analyzer",
    "version": "2.3.0",
    "ruleset": "default-sensitive"
  },
  "summary": {
    "status": "passed",
    "totalFindings": 2,
    "redactedCount": 1,
    "policyVersion": "privacy-baseline-2024.11"
  },
  "findings": [
    {
      "entityType": "EMAIL_ADDRESS",
      "actionTaken": "redacted",
      "location": {
        "file": "contracts/vendor-onboarding.docx",
        "page": 3
      }
    }
  ]
}
```

Share this artifact as signed evidence that Presidio privacy checks ran on the supplied documents.

### SLSA v1.0 Provenance

Supply chain provenance with embedded SBOM, following the [Supply Chain Levels for Software Artifacts (SLSA)](https://slsa.dev) framework:

```json
{
  "_type": "https://in-toto.io/Statement/v0.1",
  "predicateType": "https://slsa.dev/provenance/v1.0",
  "subject": [
    {
      "name": "Acme Product-1.0.0.tar.gz",
      "digest": {
        "sha256": "abc123..."
      }
    }
  ],
  "predicate": {
    "buildDefinition": {
      "buildType": "https://github.com/Certus/build-system/v1.0",
      "externalParameters": {
        "repository": "https://github.com/acme-org/acme-product",
        "ref": "refs/heads/main",
        "revision": "def456..."
      },
      "internalParameters": {
        "SBOM": {
          "embedded": true,
          "format": "spdx",
          "digest": { "sha256": "sbom-hash..." }
        }
      },
      "resolvedDependencies": [
        {
          "uri": "pkg:pypi/flask@2.3.0",
          "digest": { "sha256": "..." }
        }
      ]
    },
    "runDetails": {
      "builder": {
        "id": "https://github.com/Certus/build-system/runner/v1.0",
        "version": "1.0.0"
      },
      "metadata": {
        "invocationId": "uuid-...",
        "startTime": "2024-11-20T...",
        "finishTime": "2024-11-20T...",
        "completeness": {
          "parameters": true,
          "environment": false,
          "materials": true
        },
        "reproducible": true
      },
      "byproducts": {
        "logLocation": "https://github.com/certus-org/certus-product/actions/runs/12345",
        "logContent": "Build completed successfully. All tests passed. SBOM generated."
      }
    }
  }
}
```

**SLSA Provenance Contents:**

- **Build Definition**: What was built, from where, and with what dependencies
- **Embedded SBOM**: Complete package inventory signed as part of provenance
- **Run Details**: Who/what built it, when, and proof it was reproducible
- **Resolved Dependencies**: All dependencies with cryptographic hashes
- **Completeness**: Marks which aspects of the build are fully documented

## Verification in Acquisition Review

### Using Cosign CLI

```bash
# Verify a single artifact
cosign verify-blob \
  --key samples/oci-attestations/keys/cosign.pub \
  --signature samples/oci-attestations/artifacts/sbom/product.spdx.json.sig \
  samples/oci-attestations/artifacts/sbom/product.spdx.json
```

### Using the Script

```bash
python scripts/oci-attestations.py verify \
  --artifacts-dir samples/oci-attestations/artifacts \
  --key-path samples/oci-attestations/keys/cosign.pub
```

### Output

```
✓ Verifying artifacts...
✓ sbom/product.spdx.json (valid signature)
✓ attestations/build.intoto.json (valid signature)
✓ scans/vulnerability.sarif (valid signature)
✓ provenance/slsa-provenance.json (valid signature)

All artifacts verified successfully.

Supply Chain Verification Summary:
- SBOM verified and signed
- Build process attested (in-toto)
- Security scans signed
- SLSA provenance verified (with embedded SBOM)
- All dependencies cryptographically verified

Artifacts are safe to ingest into Certus TAP.
```

## Integration with Capstone Tutorial

Once verified, ingest artifacts into the acquisition review:

```bash
# Ingest SBOM
curl -X POST http://localhost:8000/v1/product-acquisition-review/index/ \
  -F "uploaded_file=@samples/oci-attestations/artifacts/sbom/product.spdx.json"

# Ingest attestation
curl -X POST http://localhost:8000/v1/product-acquisition-review/index/ \
  -F "uploaded_file=@samples/oci-attestations/artifacts/attestations/build.intoto.json"

# Ingest scan results
curl -X POST http://localhost:8000/v1/product-acquisition-review/index/security \
  -F "uploaded_file=@samples/oci-attestations/artifacts/scans/vulnerability.sarif"
```

## Just Commands

```bash
# Generate all attestations
just generate-attestations

# Sign with cosign
just sign-attestations

# Push to OCI registry
just push-to-registry

# Verify attestations
just verify-attestations

# Full workflow (generate → sign → push)
just attestations-workflow
```

## Important Notes

⚠️ **This is a Mock Service**

- Generated attestations contain synthetic data for demonstration
- Signed with a test cosign key, not a real vendor key
- Suitable for learning and testing the workflow
- Not for production acquisition reviews of real products

✓ **What's Real**

- Cosign signatures are cryptographically valid
- OCI artifact format is compliant
- Local registry storage is genuine
- Verification process matches real supply chain verification

## Troubleshooting

**OCI registry not starting**

```bash
docker compose up registry
```

**Cosign not found**

```bash
# Install cosign
brew install sigstore/tap/cosign

# Or via Docker
docker run --rm gcr.io/projectsigstore/cosign:latest version
```

**Permission denied on keys**

```bash
chmod 600 samples/oci-attestations/keys/cosign.key
```

## Next Steps

1. Run the generation and verification workflow
2. Push artifacts to the local OCI registry
3. Integrate verification into the capstone tutorial (Step 5.5)
4. Update security review report with attestation verification results

---

**Generated:** Mock OCI Attestation Service
**Format:** SBOM (SPDX 2.3), Attestations (in-toto), Scans (SARIF 2.1)
**Signing:** Cosign + Ed25519 keys
