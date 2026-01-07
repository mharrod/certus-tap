# Passing Scans Through Certus-Trust

>**STATUS:Tutorial is currently in beta. If you have issues see our [Communication & Support guide](../../about/communication.md)**

This guide walks you through the **verification-first** non-repudiation flow where Certus-Trust acts as a cryptographic gatekeeper, verifying scans before any artifacts are stored.

**How this fits with the other tutorials**

- Start with [`sign-attestations.md`](sign-attestations.md) to learn how vendors manually generate, sign, and push their SBOM/attestation/SARIF/provenance bundle to OCI.
- Use **this tutorial** to see how Certus-Assurance, Trust, and Transform automate that verification + upload process (S3 + OCI) without manual intervention.
- Finish with [`vendor-review.md`](vendor-review.md) to experience the customer/auditor workflow that pulls the Trust-approved OCI bundle, re-verifies it, ingests into TAP, and produces compliance evidence.

**Key Innovation: Verification Happens BEFORE Storage**

Unlike traditional promote-then-verify models, this design ensures:

- ✅ No unverified artifacts in storage
- ✅ Trust controls access to storage (gatekeeper)
- ✅ Complete audit trail (who verified, when, how)
- ✅ Non-repudiation (signatures prove chain of custody)

## Overview

In this tutorial, you'll:

1. Set up Certus-Trust service (verification gatekeeper)
2. Have Certus-Assurance request upload permission from Trust
3. Observe Trust verifying signatures and granting/denying permission
4. Have Certus-Transform execute uploads only after permission
5. Record signatures in Sigstore transparency log
6. Ingest verified findings into Certus-Ask

## Prerequisites

## Step 1. Setting Up the Stack

```bash
just up
```

### Verify All Services

```bash
# Assurance (port 8056)
curl http://localhost:8056/health

# Transform (port 8100)
curl http://localhost:8100/health

# Trust (port 8057)
curl http://localhost:8057/v1/health

# All should return healthy status
```

## Step 2. Understanding Verification Tiers

### Tier-Based Architecture

Certus supports two operational tiers:

#### Basic Tier

- Runs without Trust service
- No cryptographic verification
- Good for development/internal use
- Still includes inner signatures from Assurance
- No Sigstore recording

#### Verified Tier

- Requires Trust service
- Dual-signature model (inner + outer)
- Records in public transparency log
- Suitable for compliance/regulated environments
- Non-repudiation guarantees

### Decision: Which Tier to Use?

```
Do you need to prove findings to external auditors?
  ├─ Yes → Verified tier
  │   └─ Requires: Trust service, Sigstore access
  │
  └─ No → Basic tier
      └─ Works offline, no dependencies
```

## Step 3. Understanding Tier Details

Before proceeding with the upload workflow, let's examine the detailed tier behavior.

### Basic Tier

For basic tier, Trust verifies minimal information:

```json
{
  "scan_id": "scan_xyz789",
  "tier": "basic",
  "inner_signature": { ... },
  "artifacts": [ ... ],
  "metadata": { ... }
}
```

Trust response (always permits for basic):

```json
{
  "upload_permission_id": "perm_abc123",
  "scan_id": "scan_xyz789",
  "tier": "basic",
  "permitted": true,
  "reason": null,
  "verification_proof": {
    "chain_verified": true,
    "inner_signature_valid": true,
    "outer_signature_valid": false,
    "chain_unbroken": true,
    "signer_inner": "certus-assurance@certus.cloud",
    "signer_outer": null
  }
}
```

**Note:** No outer signature for basic tier (keeps it lightweight).

### Verified Tier

For verified tier, Trust performs full verification:

```json
{
  "scan_id": "scan_a1b2c3d4e5f6",
  "tier": "verified",
  "inner_signature": { ... },
  "artifacts": [ ... ],
  "metadata": { ... }
}
```

Trust response (only permits if verification passes):

```json
{
  "upload_permission_id": "perm_abc123",
  "scan_id": "scan_a1b2c3d4e5f6",
  "tier": "verified",
  "permitted": true,
  "reason": null,
  "verification_proof": {
    "chain_verified": true,
    "inner_signature_valid": true,
    "outer_signature_valid": true,
    "chain_unbroken": true,
    "signer_inner": "certus-assurance@certus.cloud",
    "signer_outer": "certus-trust@certus.cloud",
    "sigstore_timestamp": "2024-01-15T14:35:23Z",
    "verification_timestamp": "2024-01-15T14:35:25Z",
    "rekor_entry_uuid": "rekor-uuid-123",
    "cosign_signature": "cosign-sig-abc123"
  },
  "storage_config": {
    "raw_s3_bucket": "certus-raw-scans",
    "raw_s3_prefix": "github-com-example-repo/a1b2c3d4",
    "oci_registry": "registry.certus.cloud",
    "oci_repository": "scans/github-com-example-repo",
    "upload_to_s3": true,
    "upload_to_oci": true
  }
}
```

**Note:** Includes outer signature and storage configuration (sent to Transform).

Set `upload_to_s3` or `upload_to_oci` to `false` if you only want one destination. Leaving both `true` (default) keeps the dual-write behavior.

## Step 4. Initiate a Scan

First, create and submit a scan to Certus-Assurance. The API requires the workspace/component/assessment metadata **and** one manifest hint (`manifest`, `manifest_path`, or `manifest_uri`). The inline manifest below matches what our smoke tests use and is enough for the tutorial:

```bash
export SCAN_ID=$(curl -s -X POST http://localhost:8056/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
    "workspace_id": "tutorial-workspace",
    "component_id": "trust-smoke-repo",
    "assessment_id": "non-repudiation-demo",
    "git_url": "/app/samples/trust-smoke-repo.git",
    "branch": "main",
    "requested_by": "security-team@example.com",
    "manifest": {
      "version": "1.0"
    }
  }' | jq -r '.test_id')

echo "Scan submitted with ID: $SCAN_ID"
```

Wait for the scan to complete:

```bash
while true; do
  STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.status')
  echo "Scan status: $STATUS"
  [ "$STATUS" = "SUCCEEDED" ] && break
  sleep 2
done
```

## Step 5. Human Review and Approval

Before submitting the upload request to Trust, a human must review the scan results:

**View scan artifacts:**

```bash
ls -la ./certus-assurance-artifacts/$SCAN_ID/reports/
```

**Review SAST findings:**

```bash
cat ./certus-assurance-artifacts/$SCAN_ID/reports/sast/trivy.sarif.json | \
  jq '.runs[0].results[] | {ruleId, message, severity}' | head -20
```

**Review SBOM dependencies:**

```bash
cat ./certus-assurance-artifacts/$SCAN_ID/syft.spdx.json | \
  jq '.packages | length'
```

**Human Decision Options:**

- ✅ **Approve**: Findings are acceptable, proceed with verification and upload
- ❌ **Reject**: Block the upload if findings are unacceptable or require remediation
- 🔄 **Request Changes**: Require developers to fix issues before resubmitting

If approved, proceed to Step 3 below. If rejected or requesting changes, the scan is blocked and no upload request is submitted.

#### Step 6. Submit Upload Request to Trust

Once human review approves the scan, explicitly submit the upload request:

```bash
curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request \
  -H 'Content-Type: application/json' \
  -d '{
    "tier": "verified",
    "requested_by": "security-team@example.com"
  }'
```

This triggers the verification-first workflow:

1. **Assurance submits to Trust** via `/v1/verify-and-permit-upload`
2. **Trust verifies** the inner signature and artifact hashes
3. **Trust decides**: permit or deny
4. **IF permitted**: Trust calls Transform's `/v1/execute-upload` (async callback)
5. **Transform uploads** artifacts to S3 and OCI registry
6. **Transform confirms** completion

### Upload Request Structure

The upload request is created by Certus-Assurance and sent to Trust:

```json
{
  "scan_id": "scan_a1b2c3d4e5f6",
  "tier": "verified",
  "inner_signature": {
    "signer": "certus-assurance@certus.cloud",
    "timestamp": "2024-01-15T14:32:45Z",
    "signature": "MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQDZFv+Zb...",
    "algorithm": "SHA256-RSA",
    "certificate": "-----BEGIN CERTIFICATE-----\nMIIC5jCCAc4CCQDjxJZfDXtTuTA..."
  },
  "artifacts": [
    {
      "name": "trivy.json",
      "hash": "sha256:abc123def456789",
      "size": 15240
    },
    {
      "name": "syft.spdx.json",
      "hash": "sha256:def456ghi789",
      "size": 8920
    }
  ],
  "metadata": {
    "git_url": "https://github.com/example/repo",
    "branch": "main",
    "commit": "a1b2c3d4e5f6",
    "requested_by": "ci-bot"
  },
  "storage_destinations": {
    "raw_s3": true,
    "oci_registry": true
  }
}
```

**Fields:**

- `scan_id`: Unique scan identifier
- `tier`: "basic" (offline, no verification) or "verified" (Trust verification required)
- `inner_signature`: Proof that Assurance created this scan
- `artifacts`: What to upload (with SHA256 hashes)
- `metadata`: Audit trail (repo, commit, requester)
- `storage_destinations`: Where to store (S3, OCI registry, or both)

### Check Upload Status

After submitting the upload request, monitor the progress:

```bash
curl http://localhost:8056/v1/security-scans/$SCAN_ID | \
  jq '{status, upload_status, upload_permission_id}'
```

### Poll Until Complete

```bash
while true; do
  STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.upload_status')
  SCAN_STATUS=$(curl -s http://localhost:8056/v1/security-scans/$SCAN_ID | jq -r '.status')
  echo "Scan: $SCAN_STATUS | Upload: $STATUS"
  [ "$STATUS" != "pending" ] && break
  sleep 2
done
```

The `upload_status` field tells you:

- `"pending"` - Still waiting for Trust verification
- `"permitted"` - Trust approved, Transform/S3 uploads are in progress
- `"uploaded"` - Trust permitted and uploads completed (verification proof available)
- `"denied"` - Trust rejected (invalid signer, policy violation, etc.)

Once `upload_status` shows `"permitted"`, artifacts are being uploaded. When it advances to `"uploaded"`, everything (including `verification-proof.json`) is stored in S3.

### Step 6b. Verify Artifacts in S3 (LocalStack)

To verify that artifacts were actually uploaded, configure LocalStack S3 and inspect the stored files.

#### Ensure S3 Buckets Exist

S3 uploads are configured to use LocalStack. The `just up` command attempts to create the buckets automatically, but if they don't exist, create them manually:

```bash
# Check if buckets exist
aws s3 ls --endpoint-url http://localhost:4566
```

If no buckets are listed, create them

```bash
docker exec localstack awslocal s3 mb s3://raw
docker exec localstack awslocal s3 mb s3://golden
```

```bash
# Verify buckets were created
aws s3 ls --endpoint-url http://localhost:4566
```

**Expected output:**

```
2025-12-19 19:32:59 raw
2025-12-19 19:33:00 golden
```

**Configuration:**

- **Raw Bucket**: `raw` - Untrusted landing zone for scan artifacts
- **Golden Bucket**: `golden` - Verified, approved artifacts only
- **Prefix**: `security-scans`
- **Endpoint**: `http://localstack:4566` (internal Docker network)

#### Query S3 for Uploaded Artifacts

Assurance stores each scan under `security-scans/<scan_id>/incoming/` for raw artifacts. List everything for the current scan:

```bash
aws s3 ls s3://raw/security-scans/$SCAN_ID/incoming/ \
  --endpoint-url http://localhost:4566 \
  --recursive
```

**Expected output:**

```
2024-01-15 14:35:30        450 security-scans/test_09c8b2a7c003/incoming/verification-proof.json
2024-01-15 14:35:30       6445 security-scans/test_09c8b2a7c003/incoming/reports/sast/trivy.sarif.json
2024-01-15 14:35:30       6087 security-scans/test_09c8b2a7c003/incoming/syft.spdx.json
2024-01-15 14:35:30      22072 security-scans/test_09c8b2a7c003/incoming/reports/dast/zap-report.json
2024-01-15 14:35:30       2707 security-scans/test_09c8b2a7c003/incoming/scan.json
```

#### Download and Inspect Verification Proof

The verification proof contains Trust's signature and decision:

```bash
# Download verification proof
aws s3 cp s3://raw/security-scans/$SCAN_ID/incoming/verification-proof.json . \
  --endpoint-url http://localhost:4566

# View verification metadata
cat verification-proof.json | jq '{chain_verified, signer_inner, signer_outer, sigstore_timestamp}'
```

**Expected output:**

```json
{
  "chain_verified": true,
  "signer_inner": "certus-assurance@certus.cloud",
  "signer_outer": "certus-trust@certus.cloud",
  "sigstore_timestamp": "2024-01-15T14:35:23Z"
}
```

#### Download and Inspect SARIF Findings

```bash
# Download SARIF report
aws s3 cp s3://raw/security-scans/$SCAN_ID/incoming/reports/sast/trivy.sarif.json . \
  --endpoint-url http://localhost:4566

# View findings summary
cat trivy.sarif.json | jq '.runs[0] | {tool: .tool.driver.name, results: (.results | length)}'
```

#### Download and Inspect SBOM

```bash
# Download SBOM
aws s3 cp s3://raw/security-scans/$SCAN_ID/incoming/reports/sbom/syft.spdx.json . \
  --endpoint-url http://localhost:4566

# View component count
cat syft.spdx.json | jq '.packages | length'
```

#### Verification Checklist

After running the above queries, you should confirm:

- ✅ Verification proof exists in S3
- ✅ `chain_verified: true` in the proof
- ✅ Both `signer_inner` and `signer_outer` are present
- ✅ SARIF file contains security findings
- ✅ SBOM file lists all dependencies
- ✅ Timestamps show when verification occurred

**If upload_status is "denied"**, artifacts will NOT be in S3:

- No verification proof stored
- No SARIF/SBOM in storage
- Gatekeeper blocked it successfully

## Step 7. Understanding the Verification Workflow

### The Verification Flow

```
Certus-Assurance
   │
   └─ POST /v1/verify-and-permit-upload
       │ {scan_id, tier, inner_signature, artifacts, metadata}
       │
       ▼
   Certus-Trust (GATEKEEPER)
       │
       ├─ 1. Load inner signature from request
       │
       ├─ 2. Verify inner signature cryptography
       │    └─ Valid? Proceed : Reject with reason
       │
       ├─ 3. Hash artifacts to verify integrity
       │
       ├─ 4. Compare provided hashes
       │    └─ Match? Proceed : Reject (tampering detected)
       │
       ├─ 5. Check chain continuity (basic/verified tier)
       │    └─ Unbroken? Proceed : Reject
       │
       ├─ 6. DECISION POINT
       │    ├─ If permitted=FALSE → Return rejection (STOP)
       │    │   └─ No artifacts uploaded anywhere
       │    │
       │    └─ If permitted=TRUE → Call Transform
       │        │ POST /v1/execute-upload (async callback)
       │        │ Trust does NOT wait for response
       │        │
       │        └─ For verified tier only:
       │            ├─ 7. Create outer signature with Cosign
       │            ├─ 8. Upload to Sigstore/Rekor
       │            └─ 9. Create VerificationProof
       │
       └─ Return UploadPermission
           ├─ upload_permission_id: "perm_..."
           ├─ permitted: true/false
           ├─ reason: "verification_failed" (if false)
           └─ verification_proof: {...} (if permitted)
```

**Key Differences from Traditional Workflows:**

1. **Verification → Permission** (not Verification → Storage)
   - Trust decides whether to ALLOW storage
   - Trust doesn't upload anything
   - Permission is passed to Transform

2. **Async Callback Model**
   - Trust returns immediately (202 Accepted)
   - Trust calls Transform in background
   - Assurance doesn't wait for storage

3. **Trust is Gatekeeper, Not Publisher**
   - Only permitted scans reach storage
   - Rejected scans leave no trace in storage
   - Complete non-repudiation (prove what was approved)

## Step 7b. Testing Rejection Scenarios

The verification-first workflow also handles **rejections** where Trust denies upload permission. This demonstrates the gatekeeper function in action.

### Scenario: Invalid Signer (Security Testing)

To test rejection, use the special test endpoint with an invalid signer:

```bash
# Use the same scan from Step 4 (or create a new one)
SCAN_ID="scan_abc123def456"  # From completed scan

# Submit upload-request with an invalid signer identity
curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request \
  -H 'Content-Type: application/json' \
  -d '{
    "tier": "verified",
    "signer": "untrusted-service@malicious.com"
  }'
```

**Response (DENIED):**

```json
{
  "upload_permission_id": "5f0b1215-f095-49be-9361-f87b488e34b8",
  "upload_status": "denied"
}
```

### What Happens During Rejection

When Trust denies the upload:

1. **Signature Validation Fails**
   - Expected signer: `certus-assurance@certus.cloud`
   - Actual signer: `untrusted-service@malicious.com` (from request override)
   - Result: Signature check fails

2. **Trust Denies Permission**
   - Returns `"upload_status": "denied"`
   - Does NOT call Transform service
   - Artifacts remain unverified in Assurance

3. **No Storage Occurs**
   - S3 is never called
   - OCI Registry is never called
   - Gatekeeper blocks storage completely

### Comparing Approved vs Rejected

**Side-by-side comparison:**

| Aspect               | Approved                                  | Rejected                                                            |
| -------------------- | ----------------------------------------- | ------------------------------------------------------------------- |
| **Endpoint**         | Same: `/upload-request`                   | Same: `/upload-request`                                             |
| **Request Body**     | `{"tier": "verified"}`                    | `{"tier": "verified", "signer": "untrusted-service@malicious.com"}` |
| **Signer Used**      | `certus-assurance@certus.cloud` (default) | `untrusted-service@malicious.com` (override)                        |
| **Status**           | `"permitted"`                             | `"denied"`                                                          |
| **Trust Decision**   | ✅ Signature valid                        | ❌ Signature invalid                                                |
| **Transform Called** | Yes (async)                               | No                                                                  |
| **Artifacts Stored** | Yes (S3/Registry)                         | No (blocked)                                                        |
| **Log Entry**        | "Upload permitted"                        | "Upload denied: invalid_signer"                                     |

### Real-World Rejection Reasons

In production, uploads can be rejected for:

- **Invalid Cryptographic Signature** - Signature doesn't match signer's key
- **Invalid Signer Identity** - Service not in trusted signer list
- **No Artifacts** - Upload request contains empty artifact list
- **Policy Violations** - Vulnerable dependencies, secrets detected, compliance failures
- **Repository Not Approved** - Repo not in organization's approved list
- **Insufficient Attestations** - Missing required attestation signatures

### Optional Request Parameters

The `/upload-request` endpoint supports optional parameters for testing:

```bash
# Default behavior (approved)
curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request \
  -H 'Content-Type: application/json' \
  -d '{"tier": "verified"}'

# Test rejection with invalid signer
curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request \
  -H 'Content-Type: application/json' \
  -d '{
    "tier": "verified",
    "signer": "untrusted-service@malicious.com"
  }'
```

**Parameters:**

- `tier` (required): `"basic"` or `"verified"`
- `signer` (optional): Override signer identity. Defaults to `"certus-assurance@certus.cloud"`

### Why Rejection Matters

The ability to **reject** is critical for security:

- ✅ **Gatekeeper enforces policy** - Invalid requests are blocked
- ✅ **Supply chain security** - Only approved artifacts reach storage
- ✅ **Auditability** - Every denial is logged with reason
- ✅ **Non-repudiation** - Proves what was explicitly rejected
- ✅ **Compliance** - Satisfies "verify before store" requirements

## Step 8. Querying Verification Proof

### Production Sigstore Integration

**Certus-Trust supports both mock and production Sigstore integration** controlled by the `CERTUS_TRUST_MOCK_SIGSTORE` environment variable:

#### Current Configuration

Check your current mode:

```bash
docker exec certus-trust env | grep MOCK_SIGSTORE
```

- `CERTUS_TRUST_MOCK_SIGSTORE=false` → **Production mode** (real Rekor/Fulcio)
- `CERTUS_TRUST_MOCK_SIGSTORE=true` → **Mock mode** (simulated transparency log)

#### Production Mode (Default)

**Production mode is enabled by default when you run `just up`.** The command automatically starts:

- ✅ Sigstore infrastructure (Rekor, Fulcio, Trillian)
- ✅ Initializes Trillian log
- ✅ All application services with production Sigstore integration

**Verify Sigstore is running:**

```bash
# Check Rekor transparency log
curl http://localhost:3001/api/v1/log/publicKey

# Check containers
docker ps --filter "name=rekor" --filter "name=fulcio"
```

**Production mode provides:**

- ✅ Real Rekor transparency log entries
- ✅ Cryptographically verifiable signatures
- ✅ `rekor-cli` compatible entries
- ✅ `cosign verify` support
- ✅ Full non-repudiation with external auditability

#### Mock Mode (Development)

If you don't need full cryptographic verification:

```bash
# Switch to mock mode
docker exec certus-trust sh -c 'export CERTUS_TRUST_MOCK_SIGSTORE=true'
# Restart the service
docker restart certus-trust
```

**Mock mode provides:**

- ✅ Verification proof structure matches production
- ✅ Fast development/testing without infrastructure
- ✅ Good for understanding the workflow
- ❌ Signatures are simulated (not cryptographically real)
- ❌ Cannot verify entries with external tools

### Querying Verification Proof from Trust API

For now, query the verification proof directly from Trust (populated once the upload request has been **permitted** and S3 upload has moved the status to `"uploaded"`). If `upload_status` is still `"pending"` or the scan used the basic tier, this field shows `null`—wait until it finishes or read the proof from the S3 object (`verification-proof.json`).

```bash
# After running a scan through the verification-first workflow,
# get the verification proof from the scan status

curl http://localhost:8056/v1/security-scans/$SCAN_ID | jq '.verification_proof'
```

Example verification proof:

```json
{
  "chain_verified": true,
  "inner_signature_valid": true,
  "outer_signature_valid": true,
  "chain_unbroken": true,
  "signer_inner": "certus-assurance@certus.cloud",
  "signer_outer": "certus-trust@certus.cloud",
  "sigstore_timestamp": "2024-01-15T14:35:23Z",
  "verification_timestamp": "2024-01-15T14:35:25Z",
  "rekor_entry_uuid": "550e8400-e29b-41d4-a716-446655440000",
  "cosign_signature": "MEUCIQD..."
}
```

**Fields explained:**

- `chain_verified`: Complete chain is valid (inner + outer signatures)
- `inner_signature_valid`: Assurance's signature verified
- `outer_signature_valid`: Trust's signature created
- `signer_inner`: Who created the inner signature (Assurance)
- `signer_outer`: Who verified (Trust)
- `sigstore_timestamp`: When recorded in transparency log
- `rekor_entry_uuid`: Rekor entry ID (real in production, simulated in mock)
- `cosign_signature`: Cosign signature (real in production, simulated in mock)

### Querying Verification Proof with Helper Script

A helper script is provided to query verification proofs from Certus-Assurance:

```bash
# Query the scan
uv run scripts/query_verification_proof.py $SCAN_ID
```

**Expected output (production mode):**

```
============================================================
REKOR TRANSPARENCY LOG ENTRY
============================================================

Scan ID: scan_abc123def456
Entry UUID: 550e8400-e29b-41d4-a716-446655440000
Timestamp: 2024-01-15T14:35:23Z

Verification Status:
  Chain verified: True
  Inner signature valid: True
  Outer signature valid: True

Signers:
  Inner (Assurance): certus-assurance@certus.cloud
  Outer (Trust): certus-trust@certus.cloud

Signatures:
  Cosign: MEUCIQD...

============================================================
✓  Production Sigstore integration active
   Entries can be verified with rekor-cli and cosign
============================================================
```

**Expected output (mock mode):**

```
============================================================
SIMULATED REKOR TRANSPARENCY LOG ENTRY
============================================================

Scan ID: scan_abc123def456
Entry UUID: 550e8400-e29b-41d4-a716-446655440000

⚠️  Note: Running in MOCK mode
   Real Sigstore entries cannot be queried with these values
   Set CERTUS_TRUST_MOCK_SIGSTORE=false for production
============================================================
```

**Script location:** `scripts/query_verification_proof.py`

This script:

- Queries the most recent scan automatically
- Accepts optional scan ID argument
- Displays verification proof in a readable format
- Shows both inner (Assurance) and outer (Trust) signatures
- Indicates whether running in mock or production mode
- Handles errors gracefully (e.g., if service not running)

### Verifying Entries with Rekor CLI (Production Mode Only)

If running in production mode with Sigstore infrastructure, you can verify entries externally using the Sigstore CLI tools.

**Prerequisites:**

Install the Sigstore CLI tools:

```bash
# Install rekor-cli
brew install rekor-cli  # macOS
# OR
go install github.com/sigstore/rekor/cmd/rekor-cli@latest

# Install cosign
brew install cosign  # macOS
# OR
go install github.com/sigstore/cosign/v2/cmd/cosign@latest
```

**Verification commands:**

```bash
# Extract Rekor UUID from verification proof
export REKOR_ENTRY_UUID=$(aws s3 cp s3://golden/security-scans/$SCAN_ID/golden/verification-proof.json - \
  --endpoint-url http://localhost:4566 | jq -r '.rekor_entry_uuid')

echo "Rekor Entry UUID: $REKOR_ENTRY_UUID"

# Get specific entry with proof
rekor-cli get --rekor_server http://localhost:3001 \
  --uuid "$REKOR_ENTRY_UUID" --format json

# Verify the entry exists and shows the signature
rekor-cli get --rekor_server http://localhost:3001 \
  --uuid "$REKOR_ENTRY_UUID" --format json | jq '{LogIndex, IntegratedTime, UUID}'
```

**Note:** These commands only work in production mode (`CERTUS_TRUST_MOCK_SIGSTORE=false`) with Sigstore services running and the CLI tools installed.

## Step 9. Promote to Golden Bucket

Once verification is complete, artifacts flow through S3 buckets following the data lake pattern: **Raw → Quarantine → Golden → Ingestion**.

### Understanding the File Structure

After a scan completes, files are stored in the raw bucket with this structure:

```
s3://raw/security-scans/<SCAN_ID>/
└── incoming/                      # Raw scan results
    ├── verification-proof.json    # Trust verification
    ├── scan.json                  # Scan metadata
    ├── syft.spdx.json            # SBOM/dependencies
    ├── reports/
    │   ├── sast/trivy.sarif.json  # SAST findings
    │   └── dast/zap-report.json   # DAST findings
    ├── artifacts/
    │   ├── image.txt
    │   └── image.digest
    ├── logs/runner.log
    └── (other scan artifacts)
```

**Target golden structure** after promotion:

```
s3://golden/security-scans/<SCAN_ID>/golden/
├── verification-proof.json
├── scan.json
├── syft.spdx.json
├── reports/
│   ├── sast/trivy.sarif.json
│   └── dast/zap-report.json
└── (other approved artifacts)
```

### Option 1: Automated Promotion (Recommended)

Use the provided script to promote all artifacts in one command:

```bash
# Promote all artifacts from quarantine to golden
./scripts/promote_security_scans.sh $SCAN_ID
```

**What the script does:**

1. ✅ Verifies scan exists in raw bucket
2. ✅ Checks for verification-proof.json
3. ✅ Lists artifacts in quarantine
4. ✅ Copies scan results from `raw/security-scans/$SCAN_ID/quarantine/` → `golden/security-scans/$SCAN_ID/golden/`
5. ✅ Copies verification proof from `raw/security-scans/$SCAN_ID/$SCAN_ID/` → `golden/security-scans/$SCAN_ID/golden/`
6. ✅ Verifies all files copied successfully

**Example output:**

```
=== Promoting Security Scan: scan_73c5ff9a4478 ===
✓ Scan found in raw bucket
✓ Verification proof found

Step 4: Promoting artifacts to golden bucket...
  Promoting: trivy.sarif.json
    ✓ Copied to golden bucket
  Promoting: syft.spdx.json
    ✓ Copied to golden bucket
  Promoting: cosign.attestation.jsonl
    ✓ Copied to golden bucket

=== Promotion Summary ===
Promoted: 8 files
Failed: 0 files
✓ Promotion completed successfully!
```

### Option 2: Manual Promotion (Step-by-Step)

If you need more control, promote files manually:

**Step 1: View incoming contents**

```bash
aws s3 ls s3://raw/security-scans/$SCAN_ID/incoming/ \
  --endpoint-url http://localhost:4566 \
  --recursive
```

**Step 2: Promote key artifacts**

```bash
ENDPOINT="http://localhost:4566"

# Promote SARIF file
aws s3 cp \
  s3://raw/security-scans/$SCAN_ID/incoming/reports/sast/trivy.sarif.json \
  s3://golden/security-scans/$SCAN_ID/golden/reports/sast/trivy.sarif.json \
  --endpoint-url $ENDPOINT

# Promote SBOM file
aws s3 cp \
  s3://raw/security-scans/$SCAN_ID/incoming/reports/sbom/syft.spdx.json \
  s3://golden/security-scans/$SCAN_ID/golden/reports/sbom/syft.spdx.json \
  --endpoint-url $ENDPOINT

# Promote verification proof
aws s3 cp \
  s3://raw/security-scans/$SCAN_ID/incoming/verification-proof.json \
  s3://golden/security-scans/$SCAN_ID/golden/verification-proof.json \
  --endpoint-url $ENDPOINT

# Promote scan metadata
aws s3 cp \
  s3://raw/security-scans/$SCAN_ID/incoming/scan.json \
  s3://golden/security-scans/$SCAN_ID/golden/scan.json \
  --endpoint-url $ENDPOINT
```

**Step 3: Verify golden artifacts**

```bash
aws s3 ls s3://golden/security-scans/$SCAN_ID/golden/ \
  --endpoint-url http://localhost:4566 \
  --recursive
```

Expected output:

```
2025-12-11 17:40:10       6444 trivy.sarif.json
2025-12-11 17:40:10       6106 syft.spdx.json
2025-12-11 17:40:10        450 verification-proof.json
2025-12-11 17:40:10        312 cosign.attestation.jsonl
```

### Privacy Screening (Optional)

If your artifacts may contain PII, run privacy screening before promotion:

```bash
# Option A: Python script
PYTHONPATH=. uv run python scripts/privacy_scan_s3.py \
  --scan-id $SCAN_ID \
  --endpoint http://localhost:4566 \
  --report-path /tmp/privacy_scan_$SCAN_ID.txt

# Option B: API endpoint
curl -X POST http://localhost:8100/v1/privacy/scan \
  -H "Content-Type: application/json" \
  -d '{
    "scan_id": "'$SCAN_ID'",
    "report_key": "security-scans/'$SCAN_ID'/privacy-scan-report.txt"
  }'
```

**Note**: This moves PII-containing files back to quarantine. Review and remediate before re-promoting.

### S3 Data Lifecycle Benefits

- ✅ **Raw bucket** = Untrusted landing zone (all artifacts initially)
- ✅ **Quarantine folder** = Human review checkpoint (blocks sensitive data)
- ✅ **Golden bucket** = Approved, curated artifacts only
- ✅ **Audit trail** = Complete history of what was quarantined/approved
- ✅ **Downstream safety** = Only golden artifacts flow to Neo4j

## Step 10. Ingesting from Golden Bucket

After artifacts are promoted to the golden bucket (from Part 7), they're ready for safe ingestion into Certus-Ask.

### Ingest from Golden Bucket

The artifacts in the golden bucket have been:

- ✅ Verified (Trust service checked signatures)
- ✅ Privacy screened (Presidio checked for PII)
- ✅ Human approved (Analyst reviewed and promoted)

**Ingest security scan files (SARIF/SPDX) with Neo4j support:**

```bash
# Set ASSESSMENT_ID to match SCAN_ID for this tutorial
# This ID will be used to query SecurityScan nodes in Neo4j later
export ASSESSMENT_ID="$SCAN_ID"

# Verify the assessment ID is set
echo "Using ASSESSMENT_ID: ${ASSESSMENT_ID}"

# Ingest SARIF file with Neo4j + OpenSearch indexing
curl -X POST "http://localhost:8000/v1/default/index/security/s3" \
  -H "Content-Type: application/json" \
  -d "{
    \"bucket_name\": \"golden\",
    \"key\": \"security-scans/${SCAN_ID}/golden/reports/sast/trivy.sarif.json\",
    \"format\": \"sarif\",
    \"tier\": \"premium\",
    \"assessment_id\": \"${ASSESSMENT_ID}\",
    \"signatures\": {
      \"signer_inner\": \"certus-assurance@certus.cloud\",
      \"signer_outer\": \"certus-trust@certus.cloud\"
    },
    \"artifact_locations\": {
      \"s3\": {
        \"bucket\": \"golden\",
        \"key\": \"security-scans/${SCAN_ID}/golden/reports/sast/trivy.sarif.json\"
      }
    }
  }"

# Ingest SPDX/SBOM file
curl -X POST "http://localhost:8000/v1/default/index/security/s3" \
  -H "Content-Type: application/json" \
  -d "{
    \"bucket_name\": \"golden\",
    \"key\": \"security-scans/${SCAN_ID}/golden/reports/sbom/syft.spdx.json\",
    \"format\": \"spdx\",
    \"tier\": \"premium\",
    \"assessment_id\": \"${ASSESSMENT_ID}\",
    \"signatures\": {
      \"signer_inner\": \"certus-assurance@certus.cloud\",
      \"signer_outer\": \"certus-trust@certus.cloud\"
    },
    \"artifact_locations\": {
      \"s3\": {
        \"bucket\": \"golden\",
        \"key\": \"security-scans/${SCAN_ID}/golden/reports/sbom/syft.spdx.json\"
      }
    }
  }"
```

**Note:** Use `/v1/{workspace_id}/index/security/s3` for security files (SARIF/SPDX) that need Neo4j indexing. The generic `/v1/datalake/ingest/batch` endpoint only supports OpenSearch indexing and cannot create `SecurityScan` nodes in Neo4j.

**What happens during ingestion:**

```
Golden S3 Artifacts
        │
        ├─ SARIF file
        ├─ SBOM file
        └─ Verification proof
        │
        ▼
Certus-Transform
        │
        ├─ Download from golden bucket
        ├─ Presidio anonymization (2nd pass - mask any residual PII)
        ├─ Parse SARIF findings
        ├─ Parse SBOM components
        ├─ Link verification metadata
        │
        ▼
    Neo4j (Storage)
        │
        ├─ SecurityScan node (with verification metadata)
        ├─ Finding nodes (from SARIF)
        ├─ Component nodes (from SBOM)
        ├─ Edges linking all together
        │
        ▼
    Ready for Queries
```

**Response (SARIF ingestion):**

```json
{
  "ingestion_id": "550e8400-e29b-41d4-a716-446655440000",
  "message": "Indexed 24 items from trivy.sarif.json (Neo4j + OpenSearch)",
  "findings_indexed": 24,
  "document_count": 598,
  "metadata_preview": [],
  "neo4j_scan_id": "scan_420a8659eb4a",
  "neo4j_sbom_id": null
}
```

**Response (SPDX ingestion):**

```json
{
  "ingestion_id": "550e8400-e29b-41d4-a716-446655440001",
  "message": "Indexed 156 items from syft.spdx.json (Neo4j + OpenSearch)",
  "findings_indexed": 156,
  "document_count": 754,
  "metadata_preview": [],
  "neo4j_scan_id": null,
  "neo4j_sbom_id": "scan_420a8659eb4a"
}
```

## Where This Fits in the End-to-End Story

Treat the provenance tutorials as a sequence:

- [`sign-attestations.md`](sign-attestations.md) — Manual vendor workflow. A supplier generates SBOM, in-toto, SARIF, and SLSA artifacts, signs them with cosign, and pushes the bundle to an OCI registry so customers can pull it. Use this to understand how the artifacts are built and signed.
- **`verify-trust.md` (this guide)** — Automated gatekeeper workflow. Certus-Assurance submits the scan, Certus-Trust verifies signatures/policies, and Certus-Transform writes the permitted artifacts into LocalStack S3 and republishes them to the OCI registry. This is the verification-first pipeline you run day-to-day.
- [`vendor-review.md`](vendor-review.md) — Auditor/customer workflow. A reviewer pulls the Trust-approved OCI bundle, re-verifies the signatures and SLSA provenance independently, ingests the artifacts into Certus TAP, and produces a signed compliance report.

Follow them in order to see the full lifecycle: **generate → verify → consume**. In production you’ll lean on the Trust pipeline, but the manual tutorial remains a useful reference for how vendors produce the bundle and how auditors can verify it on their own.

**Key safety checks:**

- ✅ Only golden bucket artifacts ingested (raw/quarantine excluded)
- ✅ Verification metadata linked to findings
- ✅ Presidio runs 2nd sanitization pass before Neo4j storage
- ✅ Sensitive data is masked, not deleted
- ✅ Complete audit trail from scan → verification → ingestion

## Step 11. Querying Verification Proof in Neo4j

### Verify SCAN_ID Environment Variable

Before querying Neo4j, ensure your `SCAN_ID` environment variable is set. This should have been set in Step 4 when you initiated the scan:

```bash
# Check if SCAN_ID is set
echo "SCAN_ID: ${SCAN_ID:-NOT SET}"

# If not set, you can either:
# 1. Use the ASSESSMENT_ID you set during ingestion in Step 10
#export SCAN_ID="${ASSESSMENT_ID}"

# 2. Or set it to a specific scan/assessment ID
# export SCAN_ID="your-assessment-id-here"
```

#### Discover Available Scans in Neo4j

If you don't know what assessment IDs exist, query Neo4j to list all available scans:

```bash
# List all SecurityScan nodes with their assessment IDs
cypher-shell -u neo4j -p password \
  "MATCH (s:SecurityScan) RETURN s.id, s.assessment_id, s.timestamp ORDER BY s.timestamp DESC LIMIT 10"
```

This shows you what scans are available. Pick the `assessment_id` you want to query and set it:

```bash
# Example output might show:
# s.id                    | s.assessment_id      | s.timestamp
# "compliance-2025-q1"    | "compliance-2025-q1" | 2025-12-06T02:48:40Z

# Set SCAN_ID to the assessment_id you want to investigate
export SCAN_ID="compliance-2025-q1"
```

### Connect to Neo4j

Start Neo4j browser (or use cypher-shell):

```bash
# Via Neo4j browser: http://localhost:7474
# Or via CLI:
cypher-shell -u neo4j -p password
```

### Set the Scan Parameter (Interactive Shell)

If using `cypher-shell` interactively, define the `SCAN_ID` parameter once per session so the following queries can reuse it:

```cypher
# Replace with your actual SCAN_ID value from the environment variable check above
:param SCAN_ID => "compliance-2025-q1";

# Or if your shell has $SCAN_ID exported, reference it directly:
# :param SCAN_ID => "$SCAN_ID";
```

**Note:** The parameter value must match what you set as `ASSESSMENT_ID` in Step 10 (or what was generated as `SCAN_ID` in Step 4).

### Automate Parameter Passing from the Shell

To avoid retyping the scan ID, feed the exported environment variable into `cypher-shell` and keep the query body clean. The example below pulls the current `$SCAN_ID`, sets the parameter implicitly, and runs the query in one shot:

```bash
cypher-shell -u neo4j -p password \
  --param "SCAN_ID => '$SCAN_ID'" <<'CYPHER'
MATCH (s:SecurityScan {assessment_id: $SCAN_ID})
RETURN s.chain_verified,
       s.signer_inner,
       s.signer_outer,
       s.sigstore_timestamp,
       s.verification_timestamp;
CYPHER
```

Note the quoted heredoc marker (`<<'CYPHER'`), which prevents the shell from stripping the `$SCAN_ID` placeholder inside the query. The `--param "SCAN_ID => '$SCAN_ID'"` flag resolves the environment variable once in your shell and hands the literal string to Neo4j, so the Cypher placeholder stays intact.

### Query 1: View Scan with Verification

```bash
cypher-shell -u neo4j -p password \
  --param "SCAN_ID => '$SCAN_ID'" <<'CYPHER'
MATCH (s:SecurityScan {assessment_id: $SCAN_ID})
RETURN s.chain_verified,
       s.signer_inner,
       s.signer_outer,
       s.sigstore_timestamp,
       s.verification_timestamp;
CYPHER
```

Output:

```
s.chain_verified, s.signer_inner, s.signer_outer, s.sigstore_timestamp, s.verification_timestamp
TRUE, "certus-assurance@certus.cloud", "certus-trust@certus.cloud", "2025-12-06T03:13:12.033417Z", 2025-12-06T03:13:12.100343Z
```

### Query 2: View Findings Linked to Scan

```bash
cypher-shell -u neo4j -p password \
  --param "SCAN_ID => '$SCAN_ID'" <<'CYPHER'
MATCH (s:SecurityScan {assessment_id: $SCAN_ID})-[:CONTAINS]->(f:Finding)
RETURN f.severity, f.message, f.rule_id
LIMIT 10;
CYPHER
```

### Query 3: Count Findings by Severity

```bash
cypher-shell -u neo4j -p password \
  --param "SCAN_ID => '$SCAN_ID'" <<'CYPHER'
MATCH (s:SecurityScan {assessment_id: $SCAN_ID})-[:CONTAINS]->(f:Finding)
RETURN f.severity, count(f) as count
ORDER BY count DESC;
CYPHER
```

### Query 4: Verify Unbroken Chain

```bash
cypher-shell -u neo4j -p password \
  --param "SCAN_ID => '$SCAN_ID'" <<'CYPHER'
MATCH (s:SecurityScan {assessment_id: $SCAN_ID})
RETURN s.chain_unbroken,
       s.inner_signature_valid,
       s.outer_signature_valid;
CYPHER
```

Output shows all three are `true` - chain is verified!

### Query 5: View Tool Used

```bash
cypher-shell -u neo4j -p password \
  --param "SCAN_ID => '$SCAN_ID'" <<'CYPHER'
MATCH (s:SecurityScan {assessment_id: $SCAN_ID})-[:SCANNED_WITH]->(t:Tool)
RETURN t.name, t.version;
CYPHER
```

### Query 6: Find All Verified Scans

```bash
cypher-shell -u neo4j -p password <<'CYPHER'
MATCH (s:SecurityScan)
WHERE s.chain_verified = true AND s.outer_signature_valid = true
RETURN s.assessment_id,
       s.signer_outer,
       s.verification_timestamp
ORDER BY s.verification_timestamp DESC;
CYPHER
```

### Query 7: Complete Assessment Overview

```bash
cypher-shell -u neo4j -p password \
  --param "SCAN_ID => '$SCAN_ID'" <<'CYPHER'
MATCH (s:SecurityScan {assessment_id: $SCAN_ID})
OPTIONAL MATCH (s)-[:CONTAINS]->(f:Finding)
OPTIONAL MATCH (s)-[:SCANNED_WITH]->(t:Tool)
RETURN s.id as scan_id,
       s.assessment_id as assessment,
       s.chain_verified as verified,
       t.name as tool,
       count(f) as total_findings;
CYPHER
```

## Summary: What We Accomplished

```
1. Assurance ──────────────────────┐
   Creates inner signature          │
   Scans code                       │
   Generates SARIF + SBOM           │
                                    │
2. Transform ──────────────────────┤
   Receives scan                    │
   Decides premium tier             │
   Sends to Trust                   │
                                    │
3. Trust ───────────────────────────┤
   Verifies inner signature         │
   Creates outer signature          │
   Records in Sigstore              │
   Returns verification proof       │
                                    │
4. Ask ─────────────────────────────┤
   Receives verified findings       │
   Stores in Neo4j                  │
   Links verification metadata      │
                                    │
5. Audit ────────────────────────────┘
   Query verification chain
   Prove scan authenticity
   Show non-repudiation
```

### Verify Non-Repudiation Guarantee

You've now created a non-repudiation chain:

```
✅ Assurance signed: "This scan happened"
✅ Trust verified: "That signature is real"
✅ Trust signed: "I verified it"
✅ Sigstore recorded: "This verification happened" (immutable)
✅ Neo4j stored: "Here's the proof"

Result: No one can deny the scan happened!
```

## Part 11: Troubleshooting

### Trust Service Connection Failed

```bash
# Check Trust is running
curl http://localhost:8057/v1/health

# Check logs
tail -f logs/trust-service.log

# Verify configuration
export CERTUS_TRUST_BASE_URL="http://localhost:8057"
```

### Verification Failed

```bash
# Check Transform logs for verification error
tail -f logs/transform.log | grep "verification_failed"

# Verify artifacts still exist
ls -la certus-assurance-artifacts/$SCAN_ID/reports/
```

### Sigstore Connection Issues

**If Sigstore services aren't running:**

```bash
# Check if Sigstore services are running
docker ps --filter "name=rekor" --filter "name=fulcio"

# If not running, restart the full stack (this starts Sigstore automatically)
just up

# Verify Rekor is accessible
curl http://localhost:3001/api/v1/log/publicKey
```

**If you don't need real Sigstore integration:**

```bash
# Switch to mock mode for development
docker stop certus-trust
docker run -d --name certus-trust \
  -e CERTUS_TRUST_MOCK_SIGSTORE=true \
  -p 8057:8888 \
  --network certus-network \
  certus-trust:latest

# This creates simulated signatures without requiring Sigstore infrastructure
```

### Basic Tier Still Works

If Trust service is down but you used basic tier:

```bash
# Basic tier promotion should still succeed
curl -X POST http://localhost:8056/v1/promote-to-golden \
  -H 'Content-Type: application/json' \
  -d @promote_basic.json

# Note: Basic tier has no verification_proof, that's normal
```

## Part 12: Comparing Tier Results

### Basic Tier Flow

```json
{
  "tier": "basic",
  "verification_proof": null,
  "promoted_at": "2024-01-15T14:35:00Z"
}
```

**Characteristics:**

- ✓ Works offline
- ✓ Fast
- ✗ No cryptographic proof
- ✗ No Sigstore recording
- ✗ No non-repudiation

### Verified Tier Flow

```json
{
  "tier": "verified",
  "verification_proof": {
    "chain_verified": true,
    "signer_outer": "certus-trust@certus.cloud",
    "sigstore_timestamp": "2024-01-15T14:35:23Z",
    "rekor_entry_uuid": "abc123..."
  },
  "promoted_at": "2024-01-15T14:35:25Z"
}
```

**Characteristics:**

- ✓ Cryptographically verified
- ✓ Recorded in Sigstore
- ✓ Non-repudiation guaranteed
- ✗ Requires Trust service
- ✗ Slightly slower

## Key Takeaways

✓ **Dual signatures**: Inner (Assurance) + Outer (Trust) create chain
✓ **Tier-based approach**: Basic works offline, Verified gets cryptographic proof
✓ **Sigstore immutability**: Public log proves verification happened
✓ **Neo4j forensics**: Query complete audit trail anytime
✓ **Non-repudiation**: Cryptographic proof answers "did this happen?"
✓ **Artifact distribution**: S3 for operations, OCI Registry for compliance
✓ **Compliance-ready**: Suitable for regulated environments

## Next Steps

1. **Next Tutorial**: [Forensic Queries & Audit Trail](audit-queries.md)
   - Deep dive into Neo4j queries
   - Investigate scans
   - Generate compliance reports

2. **Advanced Topics**:
   - Integrate into CI/CD pipeline
   - Automate promotion workflow
   - Scale to multiple teams
   - Set up custom Sigstore instance

3. **Production Deployment**:
   - Deploy Trust service
   - Configure Sigstore
   - Set up audit logging
   - Enable compliance reporting

## Complete Architecture

You now understand the full stack:

```
Code Repository
      │
      ├─ Branch triggers
      │
      ▼
Certus-Assurance (Scanning)
      │
      ├─ Runs: Trivy, Syft, ZAP
      ├─ Creates: SARIF, SBOM, metadata
      ├─ Signs: inner_signature
      │
      ▼
Certus-Transform (Routing)
      │
      ├─ Receives: scan artifacts
      ├─ Decides: basic vs verified tier
      ├─ Promotes: to golden assessment
      │
      ├─ (Basic tier) ─────────────────┐
      │   └─ Direct to Ask            │
      │                               │
      ├─ (Verified tier)              │
      │   └─ Send to Trust────────────┤
      │                               │
      ▼                               │
Certus-Trust (Verification)          │
      │                              │
      ├─ Verifies: signatures        │
      ├─ Creates: outer_signature    │
      ├─ Records: in Sigstore        │
      ├─ Returns: verification_proof │
      │                              │
      └──────────────────────────────┘
                    │
                    ▼
            Certus-Ask (Storage)
                    │
                    ├─ Ingests: findings
                    ├─ Stores: Neo4j
                    ├─ Links: verification
                    │
                    ▼
            Forensic Queries
                    │
                    ├─ Audit trail
                    ├─ Compliance
                    ├─ Investigation
```

Congratulations! You've implemented non-repudiation for your security scanning pipeline.

## Step 6: Cleaning Up

```bash
just down          # stop containers, keep volumes
just cleanup       # stop + remove containers, keep volumes
just destroy       # full tear-down (volumes removed)
```
