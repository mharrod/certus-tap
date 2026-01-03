# ADR 0006: Verification-First Storage Architecture (Guardrail Model)

## Status
Proposed

## Context

Previously, the artifact storage workflow was:
1. Assurance scans code, creates artifacts, uploads to raw S3/OCI
2. Users submit promotion request to Transform
3. Transform optionally calls Trust for verification
4. Transform promotes to golden bucket

This model has issues:
- Unverified artifacts can exist in storage (repudiation risk)
- Verification happens AFTER storage (compliance gap)
- "Promotion" is a separate manual step
- No gatekeeper preventing bad artifacts from being stored

## Decision

Implement **verification-first storage architecture** where:

1. **Assurance** scans code and creates artifacts but does NOT upload directly
2. **Assurance** submits `UploadRequest` to Trust with:
   - Inner signature
   - Artifact hashes
   - Metadata (scan_id, branch, commit, etc.)
   - Requested storage destinations (raw S3, OCI registry)

3. **Trust** acts as gatekeeper:
   - Verifies inner signature validity
   - Checks artifact integrity (hashes match)
   - Creates outer signature with Cosign
   - Records verification in Sigstore/Rekor (for verified tier)
   - Returns `UploadPermission` or rejection

4. **Transform** executes uploads only with permission:
   - Receives `UploadPermission` from Trust
   - Uploads artifacts to raw S3 and/or OCI registry
   - Attaches verification metadata to artifacts
   - Runs Presidio screening on raw bucket
   - Promotes approved artifacts to golden bucket

## Benefits

### Security
- ✅ No unverified artifacts in storage
- ✅ Bad signatures = rejected before upload
- ✅ Complete non-repudiation chain
- ✅ Trust is cryptographic gatekeeper

### Compliance
- ✅ Verification proof attached to every artifact
- ✅ Sigstore record prevents denial of verification
- ✅ Audit trail: request → verify → permit → store
- ✅ No "reject after storage" scenarios

### Operations
- ✅ Simpler error handling (no cleanup needed)
- ✅ Implicit promotion (permission = automatic storage)
- ✅ Tier decision at verification time (not promotion time)
- ✅ Automatic retry support (Assurance can retry request)

## Implementation

### API Contracts

#### Certus-Assurance → Certus-Trust
**Endpoint**: `POST /v1/verify-and-permit-upload`

Request:
```json
{
  "scan_id": "scan_a1b2c3d4e5f6",
  "tier": "verified",  // or "basic"
  "inner_signature": {
    "signer": "certus-assurance@certus.cloud",
    "timestamp": "2024-01-15T14:32:45Z",
    "signature": "...",
    "algorithm": "SHA256-RSA"
  },
  "artifacts": [
    {
      "name": "trivy.sarif.json",
      "hash": "sha256:abc123def456",
      "size": 12345
    },
    {
      "name": "syft.spdx.json",
      "hash": "sha256:def456ghi789",
      "size": 67890
    }
  ],
  "metadata": {
    "git_url": "https://github.com/mharrod/certus-TAP.git",
    "branch": "main",
    "commit": "abc123def456789def456abc123def456",
    "requested_by": "security@example.com"
  },
  "storage_destinations": {
    "raw_s3": true,
    "oci_registry": true
  }
}
```

Response (Success):
```json
{
  "upload_permission_id": "perm_xyz123",
  "scan_id": "scan_a1b2c3d4e5f6",
  "tier": "verified",
  "permitted": true,
  "verification_proof": {
    "chain_verified": true,
    "inner_signature_valid": true,
    "outer_signature_valid": true,
    "signer_inner": "certus-assurance@certus.cloud",
    "signer_outer": "certus-trust@certus.cloud",
    "sigstore_timestamp": "2024-01-15T14:35:23Z",
    "rekor_entry_uuid": "abc123-def456-ghi789"
  },
  "storage_config": {
    "raw_s3_bucket": "raw",
    "raw_s3_prefix": "security-scans/scan_a1b2c3d4e5f6",
    "oci_registry": "registry.example.com",
    "oci_repository": "certus-assurance/scans"
  }
}
```

Response (Rejection):
```json
{
  "upload_permission_id": null,
  "scan_id": "scan_a1b2c3d4e5f6",
  "permitted": false,
  "reason": "inner_signature_verification_failed",
  "detail": "Signature did not verify against certificate"
}
```

#### Certus-Trust → Certus-Transform
**Endpoint**: `POST /v1/execute-upload` (called by Trust after successful verification)

Request:
```json
{
  "upload_permission_id": "perm_xyz123",
  "scan_id": "scan_a1b2c3d4e5f6",
  "verification_proof": { ... },
  "artifacts": [ ... ],
  "storage_destinations": {
    "raw_s3": true,
    "oci_registry": true
  }
}
```

### Service Responsibilities

**Certus-Assurance**:
- Scan code, create artifacts
- Calculate artifact hashes
- Create inner signature
- Submit `UploadRequest` to Trust
- Poll Trust for permission or receive callback
- Wait for `UploadPermission` before cleanup

**Certus-Trust**:
- Verify inner signature
- Verify artifact integrity
- Create outer signature (verified tier only)
- Record in Sigstore (verified tier only)
- Grant/deny `UploadPermission`
- Call Transform to execute upload (on success)

**Certus-Transform**:
- Receive upload execution request from Trust
- Upload to raw S3 bucket
- Push to OCI registry
- Run Presidio screening on raw bucket
- Promote approved artifacts to golden bucket
- Return confirmation to Trust

## Tier Behavior

### Basic Tier
- Trust skips cryptographic verification
- Still checks basic integrity (hash validation)
- No Sigstore recording
- Quick permission grant
- Upload proceeds immediately

### Verified Tier
- Trust fully verifies signature chain
- Creates outer signature with Cosign
- Records in Sigstore/Rekor
- Returns verification proof with permission
- Upload proceeds with proof attached

## Migration Path

1. Keep existing promotion API for backward compatibility
2. Add new verification-first API alongside
3. Update tutorials to use new flow
4. Eventually deprecate old promotion API

## Questions for Review

1. Should Transform call back to Trust after upload completes (confirmation)?
2. Should Assurance retry if Trust rejects (with backoff)?
3. Should there be a permission TTL (expires if not used)?
4. How long should Assurance keep artifacts locally waiting for permission?
