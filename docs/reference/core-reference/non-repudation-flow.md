# Non-Repudiation Flow: Hybrid Architecture

## Executive Summary

This document describes the complete non-repudiation flow for CERTUS assessments using a hybrid storage approach (S3 + OCI Registry). Non-repudiation ensures that:

1. **Assessments cannot be denied** - Certus-Assurance (or equivalent service) cannot claim they didn't perform the assessment
2. **Results cannot be modified** - Signed artifacts prove data integrity
3. **Chain of custody is maintained** - Multiple cryptographic touchpoints
4. **Compliance is provable** - Regulators can verify the entire chain

> **Note:** In development/testing, `run_local_scan.py` serves as a mock/simulation of Certus-Assurance. In production, Certus-Assurance (cloud SaaS service) performs the same functions.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Assessment Non-Repudiation Chain              │
└─────────────────────────────────────────────────────────────────┘

Step 1: Assessment Execution & Immediate Signing
┌─────────────────────────────────────────────────┐
│  Certus-Assurance (Cloud SaaS)                  │
│  [Mock: run_local_scan.py for dev/testing]     │
├─────────────────────────────────────────────────┤
│ ✓ Executes SAST tools                           │
│ ✓ Generates provenance metadata                 │
│ ✓ Creates in-toto link files                    │
│ ✓ IMMEDIATELY SIGNS with cosign                 │ ← CRITICAL STEP
└─────────────────────────────────────────────────┘
           ↓
      [Signatures created]
      ├─ .sig files for each report
      ├─ .sig files for provenance
      └─ Cosign public key available


Step 2: Storage in S3 (On-Premises Archive)
┌─────────────────────────────────────┐
│  S3 Storage (Customer Infrastructure) │
├─────────────────────────────────────┤
│ Assessment UUID/                    │
│ ├─ SECURITY/                        │
│ │  ├─ trivy.json                   │
│ │  ├─ trivy.json.sig       ← signed │
│ │  ├─ semgrep.txt                  │
│ │  └─ semgrep.txt.sig      ← signed │
│ ├─ SUPPLY_CHAIN/                   │
│ │  ├─ sbom.spdx.json               │
│ │  └─ sbom.spdx.json.sig  ← signed │
│ ├─ PRIVACY/                        │
│ │  ├─ secrets-detection.json       │
│ │  └─ secrets-detection.json.sig   │
│ └─ provenance/                     │
│    ├─ layout.intoto.jsonl          │
│    ├─ layout.intoto.jsonl.sig ← signed │
│    ├─ trivy.intoto.jsonl          │
│    └─ trivy.intoto.jsonl.sig ← signed │
└─────────────────────────────────────┘
     ↓ (with signatures intact)


Step 3: Validation in Certus-Transform
┌─────────────────────────────────────┐
│  Certus-Transform (On-Premises)     │
├─────────────────────────────────────┤
│ 1. Verify all cosign signatures     │
│    ✓ For each .sig file:            │
│      cosign verify-blob \           │
│      --signature file.sig \         │
│      file.json                      │
│                                     │
│ 2. If ANY signature invalid:        │
│    ✗ REJECT entire assessment       │
│    ✗ Log security incident          │
│    ✗ Alert customer                 │
│                                     │
│ 3. If ALL signatures valid:         │
│    ✓ Proceed with sanitization      │
│    ✓ Check for PII/secrets          │
│    ✓ Redact sensitive paths         │
│    ✓ Create audit log entry         │
└─────────────────────────────────────┘
     ↓ (verified, sanitized)


Step 4: Push to OCI Registry (Cloud)
┌─────────────────────────────────────┐
│  OCI Registry (Cloud - Certus)      │
├─────────────────────────────────────┤
│ registry.example.com/certus/        │
│ assessments/client-abc:v1.0.0       │
│                                     │
│ Contains:                           │
│ ├─ Assessment artifact layers       │
│ ├─ All original .sig files (inner)  │
│ ├─ Manifest with digests            │
│ └─ Immutable versioning             │
└─────────────────────────────────────┘
     ↓ (immutable, versioned)


Step 5: Outer Signature by Certus-Trust
┌─────────────────────────────────────┐
│  Certus-Trust (Cloud SaaS)          │
├─────────────────────────────────────┤
│ 1. Verify inner signatures (Certus-Assurance)  │
│    ✓ Confirm assessment data valid   │
│                                     │
│ 2. Sign the artifact:               │
│    cosign sign-blob registry-artifact │
│                                     │
│ 3. Create Sigstore attestation:     │
│    "Certus-Trust verified this      │
│     assessment at timestamp X"      │
│                                     │
│ 4. Push signatures back to registry │
│    ├─ assessment.outer.sig          │
│    └─ attestation on transparency log │
└─────────────────────────────────────┘
     ↓ (dual-signed, attested)


Step 6: Enrichment in Certus-Ask
┌─────────────────────────────────────┐
│  Certus-Ask (Cloud Intelligence)    │
├─────────────────────────────────────┤
│ Stores in Neo4j + OpenSearch:      │
│                                     │
│ {                                   │
│   "assessment_id": "uuid",         │
│   "enriched_findings": {...},      │
│                                     │
│   "artifact_locations": {          │
│     "s3": "s3://bucket/uuid/",     │
│     "registry":                    │
│       "registry.../v1.0.0@sha256"  │
│   },                                │
│                                     │
│   "provenance": {                  │
│     "inner_signature": "valid",    │
│     "outer_signature": "valid",    │
│     "sigstore_attestation": "..."  │
│   }                                 │
│ }                                   │
└─────────────────────────────────────┘
     ↓ (enriched, fully attested)


Step 7: Client Verification
┌─────────────────────────────────────┐
│  Client Verification (Any Party)    │
├─────────────────────────────────────┤
│ 1. Query Certus-Ask for assessment  │
│    GET /api/v1/ask/assessment/{id}  │
│                                     │
│ 2. Receive both artifact locations  │
│    ├─ S3 URI (original)             │
│    └─ Registry URI (verified)       │
│                                     │
│ 3. Download and verify signatures   │
│    ├─ Download from S3              │
│    ├─ Download from Registry        │
│    ├─ Verify inner sig (Certus-Assurance)  │
│    ├─ Verify outer sig (Certus-Trust)     │
│    └─ Check Sigstore log            │
│                                     │
│ 4. Compare digests                  │
│    ✓ Prove both are identical       │
│    ✓ Establish chain of custody     │
└─────────────────────────────────────┘
```

---

## Detailed Step-by-Step Flow

### Step 1: Assessment Execution & Immediate Signing

**Service:** Certus-Assurance (Cloud SaaS) | Mock: `run_local_scan.py` (Development)

**Service Description:**

In production, **Certus-Assurance** is a cloud SaaS service that:

- Executes assessment scans on customer code/infrastructure
- Generates provenance metadata for audit trails
- Signs results immediately upon completion
- Returns signed artifacts

In development/testing, **`run_local_scan.py`** serves as a mock/simulation that mimics Certus-Assurance behavior exactly:

- Same SAST tools (Trivy, Semgrep, Bandit, Ruff, etc.)
- Same provenance structure (in-toto)
- Same immediate signing (cosign)
- Same output organization (SECURITY, SUPPLY_CHAIN, PRIVACY domains)

**What Happens (Production - Certus-Assurance):**

```bash
# 1. Certus-Assurance executes assessment
POST /api/v1/assurance/scan
{
  "client_id": "client-abc",
  "assessment_id": "uuid-123",
  "scan_target": "https://github.com/client-abc/repo",
  "tools": ["trivy", "semgrep", "bandit", "ruff"]
}

# 2. Certus-Assurance returns signed artifacts
{
  "assessment_id": "uuid-123",
  "artifacts": {
    "SECURITY/trivy.json": "signed",
    "SUPPLY_CHAIN/sbom.spdx.json": "signed",
    "PRIVACY/secrets-detection.json": "signed",
    "provenance/layout.intoto.jsonl": "signed"
  },
  "signer_key": "certus-assurance@certus.cloud",
  "timestamp": "2025-12-03T00:45:10Z"
}
```

**What Happens (Development - run_local_scan.py Mock):**

```bash
# 1. Developer runs scan locally
uv run python tools/sast/run_local_scan.py

# 2. Output includes provenance with signatures
build/sast-reports/
├── SECURITY/
│   ├── trivy.json
│   └── trivy.json.sig           ← SIGNED IMMEDIATELY
├── SUPPLY_CHAIN/
│   ├── sbom.spdx.json
│   └── sbom.spdx.json.sig       ← SIGNED IMMEDIATELY
├── PRIVACY/
│   ├── secrets-detection.json
│   └── secrets-detection.json.sig ← SIGNED IMMEDIATELY
└── provenance/
    ├── layout.intoto.jsonl
    ├── layout.intoto.jsonl.sig   ← SIGNED IMMEDIATELY
    └── *.intoto.jsonl.sig        ← ALL SIGNED IMMEDIATELY
```

**Why Immediate Signing Matters:**

- **Non-repudiation anchor point** - Timestamps the moment assessment completed
- **Tampering prevention** - Any modification after this point breaks the signature
- **Proof of execution** - Can't claim "someone else modified it in S3"

**Key Properties:**

| Property       | Value                                                      |
| -------------- | ---------------------------------------------------------- |
| **Signer**     | Certus-Assurance (prod) or run_local_scan.py (dev/mock)    |
| **Timestamp**  | UTC timestamp of scan completion                           |
| **Algorithm**  | ECDSA (cosign default)                                     |
| **Public Key** | Available for verification                                 |
| **Immutable**  | Once signed, cannot be modified without breaking signature |

**Non-Repudiation Claim at This Step:**

```
"This assessment happened at timestamp T, signed by Certus-Assurance.
 The service cannot deny it occurred or that it was unmodified."
```

---

### Step 2: Storage in S3 (On-Premises Archive)

**Location:** Customer on-premises S3 bucket

**What Happens:**

```bash
# Transform uploads everything to S3
aws s3 sync build/sast-reports/ \
  s3://customer-bucket/certus-assessments/uuid/

# Result in S3:
s3://customer-bucket/certus-assessments/uuid/
├── SECURITY/
│   ├── trivy.json
│   ├── trivy.json.sig                    ← Signature included
│   ├── semgrep.txt
│   ├── semgrep.txt.sig                   ← Signature included
│   ├── bandit.json
│   ├── bandit.json.sig                   ← Signature included
│   └── ruff.txt
│       └── ruff.txt.sig                  ← Signature included
├── SUPPLY_CHAIN/
│   ├── sbom.spdx.json
│   ├── sbom.spdx.json.sig                ← Signature included
│   ├── sbom.cyclonedx.json
│   ├── sbom.cyclonedx.json.sig           ← Signature included
│   ├── licenses.json
│   ├── licenses.json.sig                 ← Signature included
│   ├── dependency-check.json
│   └── dependency-check.json.sig         ← Signature included
├── PRIVACY/
│   ├── pii-detection.json
│   ├── pii-detection.json.sig            ← Signature included
│   ├── secrets-detection.json
│   └── secrets-detection.json.sig        ← Signature included
└── provenance/
    ├── layout.intoto.jsonl
    ├── layout.intoto.jsonl.sig           ← CRITICAL SIGNATURE
    ├── trivy.intoto.jsonl
    ├── trivy.intoto.jsonl.sig            ← CRITICAL SIGNATURE
    ├── semgrep.intoto.jsonl
    ├── semgrep.intoto.jsonl.sig          ← CRITICAL SIGNATURE
    └── ... (all link files with signatures)
```

**S3 Bucket Configuration (Security):**

```json
{
  "BucketName": "customer-bucket",
  "VersioningEnabled": true,
  "ServerSideEncryption": "AES256",
  "PublicAccessBlocked": true,
  "LifecyclePolicy": "Retain indefinitely (compliance)",
  "AccessLogging": "Enabled (audit trail)",
  "MFADeleteRequired": true,
  "ObjectLockEnabled": true,
  "RetentionDays": 2555  (7 years - compliance retention)
}
```

**Non-Repudiation at This Step:**

- **Custody chain established** - Signatures prove nothing modified in transit
- **Timestamped archive** - S3 version history shows when stored
- **Access logs** - Who accessed, when, from where
- **Immutable proof** - S3 Object Lock prevents deletion

**If Customer Claims Later:**

```
"I didn't run that assessment"
Proof: "Here's the S3 archive with cosign signatures from your key"

"Someone modified the assessment after I uploaded it"
Proof: "The signature doesn't match the modified version.
        Either it was modified (breaking the signature)
        OR the original in S3 is unmodified (which it is)"

"Transform modified it before pushing to registry"
Proof: "The S3 version has the same signature as registry version.
        If Transform modified it, signatures would differ.
        They don't, so nothing was changed."
```

---

### Step 3: Validation in Certus-Transform

**Location:** Customer on-premises

**What Happens:**

```python
# Certus-Transform receives ingest request
POST /api/v1/transform/ingest-scan-report
{
  "assessment_id": "uuid-123",
  "s3_uri": "s3://customer-bucket/certus-assessments/uuid-123/",
  "verify_signatures": true,
  "push_to_registry": true,
  "registry_namespace": "certus/assessments/client-abc"
}

# Transform processing:

# 1. Download from S3
print("Downloading assessment from S3...")
assessment_files = s3.download_directory("s3://customer-bucket/uuid-123/")

# 2. CRITICAL: Verify ALL signatures
print("Verifying cosign signatures...")

for file_path in assessment_files:
    if file_path.endswith('.sig'):
        continue  # Skip signature files

    sig_file = file_path + '.sig'

    # Verify signature
    result = subprocess.run([
        'cosign', 'verify-blob',
        '--signature', sig_file,
        file_path
    ], capture_output=True)

    if result.returncode != 0:
        print(f"❌ SIGNATURE VERIFICATION FAILED: {file_path}")
        print(f"   Rejecting entire assessment")

        # Security incident logging
        log_security_incident({
            "event": "signature_verification_failed",
            "assessment_id": "uuid-123",
            "failed_file": file_path,
            "timestamp": datetime.now(),
            "action": "rejected"
        })

        sys.exit(1)  # Reject entire batch
    else:
        print(f"✓ Verified: {file_path}")

print("✅ All signatures verified")

# 3. Verify in-toto chain
print("Verifying in-toto provenance chain...")

result = subprocess.run([
    'in-toto-verify',
    '-l', 'provenance/',
    '-k', 'public-key.pem',
    '--layout', 'layout.intoto'
], capture_output=True)

if result.returncode != 0:
    print("❌ IN-TOTO CHAIN VERIFICATION FAILED")
    log_security_incident({
        "event": "intoto_verification_failed",
        "assessment_id": "uuid-123",
        "timestamp": datetime.now(),
        "action": "rejected"
    })
    sys.exit(1)

print("✅ In-toto chain verified")

# 4. Sanitize for cloud storage
print("Sanitizing for cloud storage...")

sanitized = {
    "SECURITY": sanitize_paths(assessment["SECURITY"]),
    "SUPPLY_CHAIN": sanitize_paths(assessment["SUPPLY_CHAIN"]),
    "PRIVACY": redact_secrets(assessment["PRIVACY"]),
    "provenance": assessment["provenance"]  # Provenance not sanitized
}

# 5. Create audit entry
audit_log = {
    "assessment_id": "uuid-123",
    "timestamp": datetime.now(),
    "event": "signature_verified_and_sanitized",
    "verification_status": "all_signatures_valid",
    "in_toto_status": "chain_valid",
    "s3_digest": calculate_sha256_tree("s3://..."),
    "files_count": len(assessment_files),
    "sanitization": "completed"
}

# 6. Store locally
s3.put_object(
    bucket="customer-bucket",
    key="certus-assessments/uuid-123/audit-log.json",
    body=json.dumps(audit_log)
)

print("✅ Assessment validated and sanitized")
return {
    "status": "validated",
    "assessment_id": "uuid-123",
    "ready_for_registry": True
}
```

**Signature Verification Logic:**

```bash
# For each file, Transform runs:
cosign verify-blob \
  --signature file.json.sig \
  file.json

# What this does:
# 1. Reads the signature from file.json.sig
# 2. Extracts the public key used to sign
# 3. Verifies that file.json could only have been created
#    by the private key corresponding to that public key
# 4. Confirms the file hasn't been modified since signing

# If signature is INVALID:
# - File was modified AFTER signing, OR
# - Signature is corrupted, OR
# - Someone is lying about who signed it

# If signature is VALID:
# - File is exactly as it was when signed
# - Signer cannot deny they created/approved it
# - Timestamp proves when it happened
```

**Non-Repudiation at This Step:**

- **Trust checkpoint established** - Invalid signatures → rejected
- **Audit trail created** - Transform logs all verifications
- **Chain validation** - In-toto proves workflow integrity
- **Sanitization recorded** - Transform logs what was redacted

**Critical Guarantee:**

```
If Transform sends an assessment to registry:
"This assessment was verified by our signature process.
 All cosign signatures are valid.
 In-toto chain is unbroken.
 No files were modified between signing and here."
```

---

### Step 4: Push to OCI Registry (Cloud)

**Location:** Cloud (Certus infrastructure)

**What Happens:**

```bash
# Transform pushes sanitized assessment to registry
oci push registry.example.com/certus/assessments/client-abc:v1.0.0 \
  --input sanitized-bundle/ \
  --include-signatures

# Registry now contains:
registry.example.com/certus/assessments/client-abc:v1.0.0/
├── Manifest
│   ├── config.json (metadata)
│   └── layers:
│       ├── SECURITY/layer (trivy.json, semgrep.txt, etc.)
│       ├── SUPPLY_CHAIN/layer (sbom.json, licenses.json, etc.)
│       ├── PRIVACY/layer (secrets-detection.json, etc.)
│       └── provenance/layer (layout.intoto.jsonl, *.intoto.jsonl)
│
├── Signatures (original, from Certus-Assurance)
│   ├── SECURITY/trivy.json.sig
│   ├── SECURITY/semgrep.txt.sig
│   ├── SUPPLY_CHAIN/sbom.spdx.json.sig
│   ├── PRIVACY/secrets-detection.json.sig
│   └── provenance/layout.intoto.jsonl.sig
│
└── Metadata
    ├── Digest: sha256:abc123def456... (immutable)
    └── Tag: v1.0.0 (version)
```

**Registry Properties:**

| Property           | Value                                         |
| ------------------ | --------------------------------------------- |
| **Immutability**   | Blob can never be modified                    |
| **Versioning**     | Multiple versions kept (v1.0.0, v1.0.1, etc.) |
| **Digests**        | SHA256 of all content                         |
| **Access Control** | RBAC per namespace                            |
| **Audit Logs**     | All pushes/pulls logged                       |
| **Replication**    | Can mirror to other registries                |

**Non-Repudiation at This Step:**

- **Cloud timestamp** - Registry records exact push time
- **Immutable layers** - Digest proves content is unchanged
- **Version history** - All versions preserved
- **Original signatures included** - Certus-Assurance signatures included

**What's NOT in Registry:**

```
❌ Customer's file paths (sanitized)
❌ Actual secrets (redacted)
❌ Customer-specific metadata

✓ Assessment structure
✓ Findings summaries
✓ Provenance metadata
✓ Original signatures
✓ Tool versions used
```

---

### Step 5: Outer Signature by Certus-Trust

**Location:** Cloud (Certus infrastructure)

**What Happens:**

```python
# Certus-Trust receives signing request from Transform
POST /api/v1/trust/sign-artifact
{
  "registry_uri": "registry.example.com/certus/assessments/client-abc:v1.0.0",
  "assessment_id": "uuid-123",
  "client_id": "client-abc",
  "verify_inner_signatures": true
}

# Certus-Trust processing:

# 1. Pull artifact from registry
print("Pulling artifact from registry...")
artifact = registry.pull("registry.example.com/certus/assessments/client-abc:v1.0.0")

# 2. Verify inner signatures (Certus-Assurance's signatures)
print("Verifying inner signatures...")
for sig_file in artifact.signatures:
    result = cosign.verify_blob(
        signature=artifact.read(sig_file),
        blob=artifact.read(sig_file.replace('.sig', ''))
    )
    if not result.valid:
        print(f"❌ Inner signature verification failed: {sig_file}")
        log_trust_incident(...)
        sys.exit(1)

print("✓ All inner signatures verified")

# 3. Calculate artifact digest
artifact_digest = calculate_sha256(artifact.blob)

# 4. Sign the artifact with Certus-Trust key
print("Creating Certus-Trust signature...")
signature = cosign.sign_blob(
    blob=artifact.blob,
    key=certus_trust_private_key,
    keyless=False  # Use organizational key, not keyless
)

print("✓ Artifact signed by Certus-Trust")

# 5. Create Sigstore attestation
print("Creating Sigstore attestation...")
attestation = {
    "_type": "attestation",
    "predicateType": "https://cosign.sigstore.dev/attestation/v1",
    "subject": {
        "name": "registry.example.com/certus/assessments/client-abc:v1.0.0",
        "digest": {
            "sha256": artifact_digest
        }
    },
    "predicate": {
        "timestamp": datetime.now().isoformat(),
        "verifier": "certus-trust@certus.cloud",
        "verification_status": "verified",
        "inner_signatures_verified": True,
        "message": "Assessment artifact verified by Certus-Trust signature process"
    }
}

# Push attestation to Sigstore transparency log
sigstore_entry = sigstore.upload_attestation(attestation)

print("✓ Attestation uploaded to Sigstore transparency log")

# 6. Push signature back to registry
print("Pushing signature to registry...")
registry.push_signature(
    artifact_uri="registry.example.com/certus/assessments/client-abc:v1.0.0",
    signature=signature,
    tag="v1.0.0.sig"
)

print("✓ Signature pushed to registry")

# 7. Return verification information
print("✅ Assessment signed and attested")
return {
    "status": "signed",
    "assessment_id": "uuid-123",
    "artifact_uri": "registry.example.com/certus/assessments/client-abc:v1.0.0@sha256:abc123",
    "signature_uri": "registry.example.com/certus/assessments/client-abc:v1.0.0.sig",
    "sigstore_transparency_log": f"https://rekor.sigstore.dev/...",
    "signed_at": datetime.now(),
    "signer": "certus-trust@certus.cloud",
    "verification_status": "all_signatures_verified"
}
```

**Dual Signature Structure:**

```
Assessment Artifact
│
├─ Inner Signature (from Certus-Assurance)
│  ├─ Signer: Certus-Assurance (cloud service)
│  ├─ Timestamp: When assessment completed
│  ├─ Proves: "Assessment happened, Certus-Assurance performed it"
│  └─ Algorithm: ECDSA (cosign)
│
├─ Outer Signature (from Certus-Trust)
│  ├─ Signer: certus-trust@certus.cloud
│  ├─ Timestamp: When Certus-Trust verified it
│  ├─ Proves: "Certus-Trust verified the inner signature is valid"
│  └─ Algorithm: ECDSA (cosign)
│
└─ Sigstore Attestation
   ├─ Transparency Log Entry: https://rekor.sigstore.dev/...
   ├─ Timestamp: Exact moment attestation published
   ├─ Proves: "This attestation is publicly logged and timestamped"
   └─ Verifiable: Anyone can check the log
```

**Non-Repudiation at This Step:**

- **Dual-signature structure** - Two parties sign, both committed
- **Sigstore transparency** - Public timestamp authority
- **Chain of verification** - Certus-Trust verified inner sigs
- **Immutable attestation** - In transparency log forever

**Guarantee Provided:**

```
"Certus-Trust verified this assessment on [date/time]:
 1. Inner signature (run_local_scan) is valid
 2. Assessment data has not been modified
 3. Consultant X cannot deny they performed the assessment

This assertion is timestamped in Sigstore's public transparency log."
```

---

### Step 6: Enrichment in Certus-Ask

**Location:** Cloud (Certus infrastructure)

**What Happens:**

```python
# Transform sends enriched data to Certus-Ask
POST /api/v1/ask/ingest-assessment
{
  "assessment_id": "uuid-123",
  "client_id": "client-abc",

  "enriched_findings": {
    "security": [
      {
        "cve_id": "CVE-2024-1234",
        "severity": "CRITICAL",
        "tool": "trivy",
        "affected_component": "package-x",
        "nvd_severity": "9.2",
        "patch_available": true
      }
    ],
    "supply_chain": [...],
    "privacy": [...]
  },

  "artifact_locations": {
    "s3": {
      "uri": "s3://customer-bucket/certus-assessments/uuid-123/",
      "digest": "sha256:s3digest...",
      "verified_at": "2025-12-03T00:45:10Z"
    },
    "registry": {
      "uri": "registry.example.com/certus/assessments/client-abc:v1.0.0@sha256:regdigest...",
      "tag": "v1.0.0",
      "pushed_at": "2025-12-03T01:15:30Z"
    }
  },

  "provenance": {
    "layout": {...layout.intoto.jsonl...},
    "links": {
      "trivy": {...trivy.intoto.jsonl...},
      "semgrep": {...semgrep.intoto.jsonl...},
      ...
    },
    "signatures": {
      "inner": {
        "signer": "run-local-scan",
        "timestamp": "2025-12-03T00:45:10Z",
        "algorithm": "ECDSA",
        "status": "verified"
      },
      "outer": {
        "signer": "certus-trust@certus.cloud",
        "timestamp": "2025-12-03T01:30:00Z",
        "algorithm": "ECDSA",
        "status": "verified"
      },
      "sigstore": {
        "entry_id": "rekor-entry-12345",
        "log_url": "https://rekor.sigstore.dev/...",
        "timestamp": "2025-12-03T01:30:05Z"
      }
    }
  },

  "source_validation": {
    "s3_digest": "sha256:s3digest...",
    "registry_digest": "sha256:regdigest...",
    "digests_match": true,
    "consistency_verified": true
  }
}

# Certus-Ask stores in Neo4j + OpenSearch:

# Neo4j graph structure:
(Assessment)-[:CONTAINS]->(Finding)
(Assessment)-[:STORED_IN_S3]->(S3Location)
(Assessment)-[:STORED_IN_REGISTRY]->(RegistryLocation)
(Finding)-[:SIGNED_BY]->(Signature)
(Signature)-[:VERIFIED_BY]->(VerificationService)
(Finding)-[:VIOLATES]->(Regulation)
(Finding)-[:REQUIRES]->(Remediation)

# OpenSearch indexing:
{
  "assessment_id": "uuid-123",
  "client_id": "client-abc",
  "findings_count": 42,
  "critical_count": 5,

  "artifact_uris": [
    "s3://...",
    "registry.example.com/..."
  ],

  "signatures_verified": true,
  "signature_verification_timestamp": "2025-12-03T01:30:00Z",

  "provenance_valid": true,
  "in_toto_chain_verified": true,

  "searchable_findings": [...]
}
```

**Non-Repudiation at This Step:**

- **Dual location references** - Both S3 and registry URIs stored
- **Signature verification recorded** - Timestamps when verified
- **Graph relationships** - Links findings to signatures
- **Immutable storage** - Neo4j has audit logs

**What Ask Guarantees:**

```
"This assessment is queryable because:
 1. Signatures were verified at ingest time
 2. Both storage locations are referenced
 3. Provenance metadata is complete and linked
 4. Client can independently verify everything"
```

---

### Step 7: Client Verification

**Location:** Client infrastructure (any location)

**What Happens:**

```bash
# 1. Client queries Certus-Ask
curl -X GET https://ask.certus.cloud/api/v1/ask/assessment/uuid-123 \
  -H "Authorization: Bearer ${API_KEY}"

# Response includes complete verification information:
{
  "assessment_id": "uuid-123",
  "enriched_findings": {
    "total_findings": 42,
    "critical": 5,
    "high": 12,
    "findings": [...]
  },

  "artifact_locations": {
    "s3": "s3://customer-bucket/certus-assessments/uuid-123/",
    "registry": "registry.example.com/certus/assessments/client-abc:v1.0.0@sha256:abc123"
  },

  "verification_instructions": {
    "step_1_download_s3": "aws s3 cp s3://customer-bucket/uuid-123/ ./s3-copy --recursive",
    "step_2_download_registry": "oci pull registry.example.com/certus/assessments/client-abc:v1.0.0",
    "step_3_verify_signatures": {
      "inner_signature": "cosign verify-blob --cert s3-copy/SECURITY/trivy.json.sig s3-copy/SECURITY/trivy.json",
      "outer_signature": "cosign verify-blob --cert certus-trust.crt registry-copy/SECURITY/trivy.json.sig registry-copy/SECURITY/trivy.json",
      "provenance": "in-toto-verify -l s3-copy/provenance/ -k pubkey.pem --layout layout.intoto"
    },
    "step_4_verify_sigstore": "curl https://rekor.sigstore.dev/api/v1/log/entries/[entry_id]",
    "step_5_compare_digests": {
      "s3_digest": "sha256:s3digest...",
      "registry_digest": "sha256:regdigest...",
      "action": "Compare digests - they should match"
    }
  }
}

# 2. Client downloads from S3
aws s3 cp s3://customer-bucket/certus-assessments/uuid-123/ ./s3-copy --recursive

# 3. Client downloads from registry
oci pull registry.example.com/certus/assessments/client-abc:v1.0.0

# 4. Client verifies inner signature (Certus-Assurance)
cosign verify-blob \
  --signature ./s3-copy/SECURITY/trivy.json.sig \
  ./s3-copy/SECURITY/trivy.json

# Output: Verified signature from [public-key]
# Proves: "This file was signed by Certus-Assurance's key"

# 5. Client verifies outer signature (Certus-Trust)
cosign verify-blob \
  --signature ./registry-copy/SECURITY/trivy.json.sig \
  ./registry-copy/SECURITY/trivy.json

# Output: Verified signature from certus-trust@certus.cloud
# Proves: "Certus-Trust verified this assessment"

# 6. Client verifies provenance chain
in-toto-verify \
  -l ./s3-copy/provenance/ \
  -k run-local-scan-pubkey.pem \
  --layout layout.intoto

# Output: Verification succeeded
# Proves: "All assessment steps are linked correctly"

# 7. Client verifies Sigstore transparency log
curl -s https://rekor.sigstore.dev/api/v1/log/entries/[entry_id] | jq .

# Output: Entry found with exact timestamp and attestation
# Proves: "Sigstore publicly attested this on [date/time]"

# 8. Client compares digests
sha256sum s3-copy/SECURITY/trivy.json
sha256sum registry-copy/SECURITY/trivy.json

# Output: sha256:abc123... (both should match)
# Proves: "S3 and registry contain identical assessment"
```

**Complete Verification Output:**

```
✓ Step 1: Downloaded from S3
✓ Step 2: Downloaded from registry
✓ Step 3: Inner signature valid (run_local_scan)
✓ Step 4: Outer signature valid (Certus-Trust)
✓ Step 5: In-toto chain valid (all steps linked)
✓ Step 6: Sigstore transparency log entry found
✓ Step 7: Digests match (S3 == registry)

=== VERIFICATION COMPLETE ===
This assessment is non-repudiate because:
1. run_local_scan's signature proves they created it
2. Certus-Trust's signature proves they verified it
3. Sigstore's timestamp proves exactly when
4. Both storage locations contain identical data
5. Provenance chain is unbroken
6. No step can be repudiated
```

**Non-Repudiation Guaranteed:**

```
Certus-Assurance cannot claim:
❌ "I didn't create this assessment"
   Proof: Valid signature from Certus-Assurance key

❌ "Someone modified it after I signed"
   Proof: Registry copy matches S3 copy,
          both have valid original signature

❌ "I don't know when this happened"
   Proof: Sigstore transparency log timestamp

❌ "The steps were done differently"
   Proof: In-toto chain shows exact commands

❌ "Certus-Trust modified something"
   Proof: Inner signature unchanged,
          outer signature on top
```

---

## Non-Repudiation Guarantees Summary

### For the Assessment Creator (Consultant)

```
You CANNOT claim:
1. "I didn't perform this assessment"
   → Signature with your key proves you did

2. "The results were modified"
   → Signature verification proves they weren't

3. "This happened at a different time"
   → Sigstore timestamp is public and verifiable

4. "Someone else did the assessment"
   → Only your key could create your signature

5. "I don't know what was scanned"
   → In-toto provenance shows exact steps
```

### For the Organization (Certus)

```
We CAN prove:
1. Assessment integrity
   → Dual signatures prove no modification

2. Assessment authenticity
   → Sigstore transparency log is public

3. Assessment timing
   → Timestamp is cryptographically bound

4. Assessment provenance
   → In-toto shows complete chain

5. Consultant accountability
   → Signature is tied to specific key/identity
```

### For Regulators/Auditors

```
You CAN verify:
1. Assessment happened
   → Check Sigstore transparency log

2. Nothing was modified
   → Verify signatures on both locations

3. Chain of custody maintained
   → Check in-toto link files

4. Consultant accountability
   → Verify signature key ownership

5. Complete audit trail
   → Access logs on S3, registry, Sigstore
```

---

## Security Scenarios

### Scenario 1: Consultant Claims "I Didn't Run This"

```
Consultant: "I never ran a scan on that client"

Evidence:
1. S3 contains files signed with consultant's key
2. Cosign verification succeeds
3. Sigstore log shows consultant's signature
4. In-toto chain shows consultant's commands

Result: Consultant is liable (non-repudiation proven)
```

### Scenario 2: Registry Was Hacked

```
Attacker: "I modified the assessment in the registry"

Defense:
1. S3 has original with valid signature
2. Registry digest != S3 digest (caught)
3. In-toto signature breaks (inner sig fails)
4. Alert triggered (modification detected)

Result: Original in S3 is trusted version
```

### Scenario 3: S3 Was Deleted

```
Customer: "We accidentally deleted S3"

Recovery:
1. Registry contains identical copy
2. Signatures on registry copy match original
3. Sigstore log proves both were valid
4. Replication/backup restores S3

Result: No loss of evidence
```

### Scenario 4: Certus-Trust Made an Error

```
Analyst: "Certus-Trust signed something that shouldn't be signed"

Accountability:
1. Inner signature (run_local_scan) is unchanged
2. Outer signature (Certus-Trust) is separate
3. Transform's audit log shows what was verified
4. Sigstore proves exact timestamp

Result: Can identify exactly which step failed
```

---

## Implementation Checklist

- [ ] **run_local_scan.py**
  - [ ] Signs provenance immediately after generation
  - [ ] Creates .sig files for all reports
  - [ ] Includes public key information
  - [ ] Logs signing timestamps

- [ ] **Certus-Transform**
  - [ ] Downloads entire assessment with signatures
  - [ ] Verifies ALL cosign signatures before proceeding
  - [ ] Verifies in-toto chain
  - [ ] Rejects invalid signatures (security incident)
  - [ ] Sanitizes while preserving signatures
  - [ ] Creates audit log of verification
  - [ ] Pushes to OCI registry with signatures intact

- [ ] **OCI Registry**
  - [ ] Stores original .sig files
  - [ ] Maintains immutable digests
  - [ ] Logs all push/pull operations
  - [ ] Enables signature inspection

- [ ] **Certus-Trust**
  - [ ] Verifies inner signatures on receipt
  - [ ] Creates outer signatures
  - [ ] Uploads to Sigstore transparency log
  - [ ] Returns verification proofs

- [ ] **Certus-Ask**
  - [ ] Stores both S3 and registry URIs
  - [ ] Records signature verification timestamps
  - [ ] Links findings to signatures
  - [ ] Provides complete verification instructions
  - [ ] Returns digest comparison data

- [ ] **Client Verification Tools**
  - [ ] Provides cosign, in-toto, oci CLI instructions
  - [ ] Documents verification steps
  - [ ] Explains each signature layer
  - [ ] Links to Sigstore transparency log

---

## Step 8: Enrichment & Intelligence in Certus-Ask

**Location:** Cloud (Certus infrastructure)

**Service Description:**

Certus-Ask is a knowledge base + RAG (Retrieval-Augmented Generation) system that:

- Stores assessment findings in Neo4j (graph) and OpenSearch (full-text search)
- Maintains dual references to both S3 and OCI Registry artifact locations
- Enables querying across anonymized past findings to identify patterns and trends
- Powers intelligent recommendations based on assessment history

**Non-Repudiation Flow:**

```
Assessment enters Certus-Ask:
├─ Artifact URIs verified
│  ├─ S3: s3://customer-bucket/uuid-123/
│  └─ Registry: registry.example.com/certus/assessments/client-abc:v1.0.0@sha256:...
│
├─ Signatures validated on ingest
│  ├─ Inner signatures (Certus-Assurance) verified
│  ├─ Outer signatures (Certus-Trust) verified
│  └─ Sigstore attestation checked
│
├─ Provenance metadata stored
│  ├─ In-toto chain linked in graph
│  ├─ All signature verification timestamps recorded
│  └─ Signer identities linked to findings
│
├─ Findings enriched with intelligence
│  ├─ CVE/vulnerability data cross-referenced
│  ├─ Pattern matching against anonymized past findings
│  ├─ Trend analysis (vulnerability discovery vs remediation)
│  └─ Regulatory compliance mapping stored
│
└─ Complete audit trail maintained
   ├─ Who accessed the assessment
   ├─ When findings were queried
   ├─ Which intelligence was applied
   └─ All changes timestamped and logged
```

**Implementation:**

```python
# Certus-Ask ingest endpoint
POST /api/v1/ask/ingest-assessment
{
  "assessment_id": "uuid-123",
  "client_id": "client-abc",

  # Artifact location references (immutable)
  "artifact_locations": {
    "s3": {
      "uri": "s3://customer-bucket/certus-assessments/uuid-123/",
      "digest": "sha256:s3digest...",
      "verified_at": "2025-12-03T00:45:10Z"
    },
    "registry": {
      "uri": "registry.example.com/certus/assessments/client-abc:v1.0.0@sha256:regdigest...",
      "tag": "v1.0.0",
      "pushed_at": "2025-12-03T01:15:30Z"
    }
  },

  # Complete provenance chain
  "provenance": {
    "layout": {...layout.intoto.jsonl...},
    "links": {
      "trivy": {...trivy.intoto.jsonl...},
      "semgrep": {...semgrep.intoto.jsonl...}
    },
    "signatures": {
      "inner": {
        "signer": "certus-assurance@certus.cloud",
        "timestamp": "2025-12-03T00:45:10Z",
        "status": "verified"
      },
      "outer": {
        "signer": "certus-trust@certus.cloud",
        "timestamp": "2025-12-03T01:30:00Z",
        "status": "verified"
      },
      "sigstore": {
        "entry_id": "rekor-entry-12345",
        "timestamp": "2025-12-03T01:30:05Z"
      }
    }
  },

  # Enriched findings with provenance links
  "findings": [
    {
      "finding_id": "finding-001",
      "type": "CVE",
      "cve_id": "CVE-2024-1234",
      "severity": "CRITICAL",
      "tool": "trivy",

      # Link back to source
      "provenance_link": {
        "intoto_link_id": "trivy.intoto",
        "assessment_id": "uuid-123",
        "signer": "certus-assurance@certus.cloud"
      },

      # Enrichment metadata
      "enrichment": {
        "nvd_severity": "9.2",
        "patch_available": true,
        "similar_findings_count": 42,
        "client_pattern": "Common in fintech sector",
        "remediation_time_estimate": "3-5 days"
      }
    }
  ]
}

# Certus-Ask stores in Neo4j:
(Assessment)-[:CONTAINS]->(Finding)
  -[:VERIFIED_BY]->(Signature)
  -[:ATTESTED_BY]->(SigstoreEntry)

(Finding)-[:LINKED_TO_PROVENANCE]->(InTotoLink)
  -[:SIGNED_BY]->(CertusAssurance)

(Finding)-[:PART_OF_ARTIFACT]->(ArtifactLocation)
  -[:STORED_IN]->(S3 | Registry)

(Finding)-[:MATCHES_PATTERN]->(HistoricalFinding)
  -[:IN_CLIENT_SECTOR]->(IndustryPattern)
```

**Non-Repudiation Guarantees for Certus-Ask:**

1. **Immutable Artifact References**
   - S3 and Registry URIs cannot be modified without detection
   - Digests prove exact artifact content
   - Both locations must be identical

2. **Verified Signatures on Ingest**
   - All findings linked to verified signatures
   - If signature invalid, entire assessment rejected
   - Signature verification timestamp recorded

3. **Complete Provenance Chain**
   - In-toto links preserved and queryable
   - Each finding traceable to exact tool/step that produced it
   - Signer identities immutably linked to findings

4. **Audit Trail for Enrichment**
   - Pattern matching logged with timestamps
   - Intelligence applied tracked
   - Client cannot claim they didn't receive enrichment

5. **Access Accountability**
   - All queries logged
   - Who accessed assessment findings recorded
   - When intelligence was applied timestamped

**Example Query with Audit Trail:**

```python
# Query: Find all CVE-2024-1234 findings across clients
GET /api/v1/ask/findings/search
{
  "query": "CVE-2024-1234",
  "filter_anonymized": true
}

# Response includes:
{
  "results": [
    {
      "finding_id": "finding-001",
      "assessment_id": "uuid-123",
      "artifact_location": "s3://...",
      "signer": "certus-assurance@certus.cloud",
      "signature_verified": true,
      "signature_timestamp": "2025-12-03T00:45:10Z",

      # Audit metadata
      "query_metadata": {
        "queried_by": "analyst@certus.cloud",
        "queried_at": "2025-12-03T10:15:30Z",
        "query_id": "query-abc123",
        "pattern_type": "CVE_TREND_ANALYSIS"
      }
    }
  ],

  "pattern_analysis": {
    "total_occurrences": 42,
    "affected_sectors": ["fintech", "healthcare", "retail"],
    "trend": "5 new instances in last 30 days",
    "recommendation": "Critical patch required for all instances"
  }
}

# Audit entry created:
{
  "event_type": "pattern_analysis_query",
  "analyst": "analyst@certus.cloud",
  "timestamp": "2025-12-03T10:15:30Z",
  "findings_accessed": 42,
  "all_findings_verified": true,
  "findings_artifact_locations": ["s3://...", "registry://..."],
  "recommendations_provided": true
}
```

---

## Step 9: Reporting & Integrations in Certus-Insights

**Location:** Cloud (Certus infrastructure)

**Service Description:**

Certus-Insights is a reporting and integration hub that:

- Generates comprehensive assessment reports, threat models, and dashboards
- Integrates with client tools (Jira, Azure DevOps, GitHub, etc.)
- Provides visibility into assessment scope, findings, and remediation progress
- Enables automated workflows for tracking findings across the client ecosystem

**Non-Repudiation in Reporting:**

```
Certus-Insights report generation:
├─ Report pulls data from Certus-Ask
│  ├─ Verified findings only (signatures checked)
│  ├─ All sources traceable back to assessment
│  └─ Provenance chain included in report
│
├─ Report generation logged
│  ├─ Who requested the report
│  ├─ When it was generated
│  ├─ Which findings included
│  └─ What filters/transformations applied
│
├─ Report signed for authenticity
│  ├─ Sigstore signature on report
│  ├─ Timestamp of report generation
│  └─ Signer: Certus-Insights service
│
├─ Client integrations tracked
│  ├─ Findings pushed to Jira/Azure/GitHub
│  ├─ Issue creation logged with timestamps
│  ├─ Finding-to-issue mapping maintained
│  └─ Sync operations audited
│
└─ Report storage immutable
   ├─ PDF signed and timestamped
   ├─ JSON export signed and versioned
   └─ All previous versions preserved
```

**Implementation:**

```python
# Certus-Insights report generation
POST /api/v1/insights/generate-report
{
  "assessment_id": "uuid-123",
  "client_id": "client-abc",
  "report_type": "executive_summary",  # or "detailed", "threat_model", etc.
  "include_recommendations": true,
  "export_format": "pdf"  # or "json"
}

# Processing:

# 1. Retrieve verified findings from Certus-Ask
findings = ask_client.get_verified_findings(
  assessment_id="uuid-123",
  verification_required=True,  # Only verified findings
  include_provenance=True
)

# 2. Verify all findings are still valid
for finding in findings:
    # Check signature still valid
    if not verify_signature(finding.signature):
        log_incident("Finding signature invalid on report generation")
        raise SecurityException()

    # Check artifact location still accessible
    if not verify_artifact_location(finding.s3_uri, finding.registry_uri):
        log_incident("Artifact location inaccessible")
        raise SecurityException()

# 3. Generate report with provenance tracking
report = {
    "report_id": "report-xyz789",
    "assessment_id": "uuid-123",
    "generated_at": datetime.now(),
    "generated_by": "certus-insights@certus.cloud",

    # Include full traceability
    "executive_summary": {
        "total_findings": 42,
        "critical": 5,
        "high": 12,
        "medium": 15,
        "low": 10,

        "all_findings_verified": true,
        "verification_timestamp": "2025-12-03T10:15:30Z",

        "provenance_summary": {
            "assessment_signed_by": "certus-assurance@certus.cloud",
            "assessment_signed_at": "2025-12-03T00:45:10Z",
            "trusted_by": "certus-trust@certus.cloud",
            "chain_of_custody": "Complete and unbroken"
        }
    },

    # Detailed findings with full provenance
    "findings": [
        {
            "finding_id": "finding-001",
            "type": "CVE",
            "cve_id": "CVE-2024-1234",
            "severity": "CRITICAL",

            # Complete provenance for this finding
            "provenance": {
                "discovered_by": "trivy",
                "assessment_id": "uuid-123",
                "assessment_signer": "certus-assurance@certus.cloud",
                "signature_verified": true,
                "signature_timestamp": "2025-12-03T00:45:10Z",
                "artifact_locations": {
                    "s3": "s3://customer-bucket/uuid-123/SECURITY/trivy.json",
                    "registry": "registry.example.com/.../v1.0.0@sha256:..."
                }
            },

            # Enrichment applied by Certus-Ask
            "enrichment": {
                "applied_by": "certus-ask@certus.cloud",
                "applied_at": "2025-12-03T02:00:00Z",
                "nvd_severity": "9.2",
                "patch_available": true,
                "fix_url": "https://nvd.nist.gov/...",
                "pattern_matches": "Found in 42 other assessments"
            },

            # Recommendation from this report
            "recommendation": "Apply critical patch immediately",
            "remediation_time_estimate": "3-5 days",
            "business_impact": "Production outage risk"
        }
    ],

    # Threat model (auto-generated from findings)
    "threat_model": {
        "data_flows": [...],
        "stride_analysis": [...],
        "attack_surface": {...}
    }
}

# 4. Sign the report
report_signature = cosign.sign_blob(
    blob=json.dumps(report),
    key=certus_insights_private_key
)

# 5. Store report immutably
reports_storage.store(
    report_id="report-xyz789",
    content=report,
    signature=report_signature,
    timestamp=datetime.now()
)

# 6. Log report generation
audit_log.create({
    "event_type": "report_generated",
    "report_id": "report-xyz789",
    "assessment_id": "uuid-123",
    "generated_by": "analyst@certus.cloud",
    "generated_at": datetime.now(),
    "findings_included": 42,
    "all_findings_verified": true,
    "report_signed": true,
    "provenance_chain": "Complete"
})

response = {
    "report_id": "report-xyz789",
    "status": "generated",
    "download_url": "/api/v1/insights/reports/report-xyz789/download",
    "signature_url": "/api/v1/insights/reports/report-xyz789/signature",
    "generated_at": datetime.now(),
    "signer": "certus-insights@certus.cloud",
    "verification_instructions": "Use cosign verify-blob with certus-insights public key"
}
```

**Integration with Issue Tracking:**

```python
# Push findings to client's Jira
POST /api/v1/insights/sync-to-jira
{
  "report_id": "report-xyz789",
  "assessment_id": "uuid-123",
  "jira_project": "SEC",
  "jira_url": "https://client.atlassian.net",
  "create_issues": true,
  "auto_link_to_sprints": true
}

# Processing:

# 1. Verify all findings still valid
for finding in report.findings:
    assert verify_signature(finding.signature)
    assert verify_artifact_location(finding.s3_uri, finding.registry_uri)

# 2. Create Jira issues with full traceability
jira_issues = []
for finding in report.findings:
    issue = jira.create_issue(
        project="SEC",
        summary=f"{finding.type}: {finding.cve_id}",
        description=f"""
## Finding Details
- Finding ID: {finding.finding_id}
- Assessment ID: {finding.assessment_id}
- Severity: {finding.severity}

## Provenance & Non-Repudiation
- Discovered by: {finding.discovered_by}
- Signed by: {finding.assessment_signer}
- Signature timestamp: {finding.signature_timestamp}
- Signature status: VERIFIED

## Artifact Locations (Immutable)
- S3: {finding.s3_uri}
- Registry: {finding.registry_uri}

## Verification
Findings can be independently verified using cosign and the artifact locations above.
        """,
        labels=["security", "certus-assessment", finding.cve_id],
        customfield_provenance={
            "finding_id": finding.finding_id,
            "assessment_id": finding.assessment_id,
            "signer": finding.assessment_signer,
            "signature_verified": true,
            "artifact_s3": finding.s3_uri,
            "artifact_registry": finding.registry_uri
        }
    )
    jira_issues.append(issue)

# 3. Log the integration
integration_log.create({
    "event_type": "jira_sync",
    "report_id": "report-xyz789",
    "issues_created": len(jira_issues),
    "synced_at": datetime.now(),
    "all_findings_verified": true,
    "artifact_locations_immutable": true,
    "jira_project": "SEC"
})

response = {
    "sync_status": "success",
    "issues_created": len(jira_issues),
    "issue_links": [
        f"https://client.atlassian.net/browse/SEC-{issue.key}"
        for issue in jira_issues
    ],
    "sync_audit_id": "sync-abc123"
}
```

**Non-Repudiation Guarantees for Certus-Insights:**

1. **Report Authenticity**
   - Reports signed by Certus-Insights service
   - Timestamp proves when generated
   - Cannot deny report was created or modified after

2. **Finding Traceability**
   - Every finding in report links back to verified assessment
   - Provenance chain included in report
   - Readers can verify findings independently

3. **Integration Audit Trail**
   - All pushes to Jira/Azure/GitHub logged
   - Issue creation timestamps recorded
   - Finding-to-issue mapping maintained
   - Can prove exactly what was communicated to client

4. **Report Immutability**
   - PDF signed with timestamp
   - JSON versions tagged with report ID
   - Previous versions preserved
   - Cannot claim report was modified

5. **Compliance Proof**
   - Regulatory mapping shows what standards covered
   - Threat models link findings to compliance requirements
   - Reports can be presented to auditors with full chain of custody

**Example: Auditor Verification of Report**

```bash
# 1. Download report and signature
curl https://certus.cloud/api/v1/insights/reports/report-xyz789/download \
  -o assessment-report.pdf

curl https://certus.cloud/api/v1/insights/reports/report-xyz789/signature \
  -o assessment-report.pdf.sig

# 2. Verify report signature
cosign verify-blob \
  --signature assessment-report.pdf.sig \
  --key https://certus.cloud/keys/certus-insights.pub \
  assessment-report.pdf

# Output: Verified signature from certus-insights@certus.cloud
# Proves: Report was created by Certus-Insights and hasn't been modified

# 3. Check report generation timestamp
jq '.generated_at' assessment-report.json
# Output: 2025-12-03T10:15:30Z

# 4. Download and verify original assessment
aws s3 cp s3://customer-bucket/uuid-123/ ./assessment --recursive
cosign verify-blob \
  --signature ./assessment/SECURITY/trivy.json.sig \
  ./assessment/SECURITY/trivy.json

# Output: Verified signature from certus-assurance@certus.cloud
# Proves: Original assessment was created by Certus-Assurance

# 5. Verify all findings in report have valid signatures
for file in ./assessment/**/*.sig; do
  cosign verify-blob \
    --signature "$file" \
    "${file%.sig}"
done

# Output: All signatures verified
# Conclusion: Report is trustworthy and non-repudiate-able
```

---

## Conclusion

The complete non-repudiation architecture provides:

1. **Immediate anchoring** - Signatures created at scan time by Certus-Assurance
2. **Layered verification** - Inner (Certus-Assurance) and outer (Certus-Trust) signatures
3. **Public attestation** - Sigstore transparency log
4. **Dual storage** - S3 (original) + Registry (verified)
5. **Intelligence layer** - Certus-Ask enriches with verified patterns and trends
6. **Reporting layer** - Certus-Insights generates signed reports with complete traceability
7. **Integration layer** - All client communications (Jira, Azure, etc.) audited and immutable
8. **Complete audit trail** - Every step logged and verifiable

This ensures that **assessments, enrichment, reports, and all communications are legally defensible, auditable, and non-repudiate-able throughout the entire platform.**
