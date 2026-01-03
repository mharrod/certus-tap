# Non-Repudiation Overview

This guide explains the concept of non-repudiation in security scanning and why it matters for compliance and audit trails.

## What is Non-Repudiation?

Non-repudiation means that a party cannot deny having created, signed, or verified something. In the context of security assessments, it provides cryptographic proof that:

1. **A scan was actually performed** - Certus-Assurance signed the security scan results
2. **The scan was verified** - Certus-Trust verified the scan and confirmed it wasn't tampered with
3. **An independent timestamp exists** - Sigstore recorded when the verification happened in a public transparency log

This creates an **unbreakable chain of evidence** that can be used in legal proceedings, compliance audits, or incident investigations.

## The Problem Without Non-Repudiation

Without signatures and verification, security scans are just data files:

```
❌ Problem: Who says this SARIF file is real?
├─ File could have been modified after scanning
├─ Scanners could be compromised
├─ No proof that findings are legitimate
└─ Unacceptable for compliance (SOC 2, ISO27001, PCI-DSS)
```

Example: After a security incident, you want to prove "we scanned for vulnerability XYZ before the breach." Without non-repudiation, an attacker can claim the scan was fabricated after the fact.

## The Solution: Dual-Signature Model

Certus implements a **dual-signature architecture**:

```
Scan Results
    ↓
[Inner Signature from Certus-Assurance]
    ↓ (This is the scanning layer proof)
    ↓
Certus-Trust Verification
    ↓
[Outer Signature from Certus-Trust]
    ↓ (This is the verification layer proof)
    ↓
Sigstore/Rekor Transparency Log
    ↓
[Public Timestamp Authority]
    ↓ (This is the independent proof)
    ↓
✓ Non-Repudiation Guarantee Established
```

### How It Works

**Stage 1: Inner Signature (Assurance)**

- Certus-Assurance runs security scans (Trivy, Bandit, Snyk, etc.)
- Results are signed with an inner signature proving "we scanned this code"
- Signature anchors the scan at the moment it was created
- Example: `signer: certus-assurance@certus.cloud`

**Stage 2: Outer Signature (Trust)**

- Certus-Transform promotes scan to golden bucket
- Certus-Trust receives the scan and verifies the inner signature
- Trust creates an outer signature proving "we verified this scan is legitimate"
- Signature is recorded in Sigstore/Rekor transparency log
- Example: `signer: certus-trust@certus.cloud`

**Stage 3: Public Timestamp (Sigstore)**

- Rekor transparency log records the verification in a Merkle tree
- Public timestamp authority (Sigstore) provides independent proof
- Anyone can verify the timestamp (no private key needed)
- Chain of custody is immutable

### Analogy

Think of it like a notarized document:

```
You write a document
    ↓
[You sign it] ← Inner signature (proof you wrote it)
    ↓
Notary receives it and verifies it's really you
    ↓
[Notary stamps it] ← Outer signature (proof notary verified it)
    ↓
Notary records it in public records
    ↓
[Public record entry] ← Timestamp authority (independent proof)
    ↓
✓ Non-Repudiation established - you can't deny writing it
```

## Free Tier vs Premium Tier

### Free Tier (No Non-Repudiation)

```
Your Scan → Index → Store
   ✓ No verification overhead
   ✓ Fast ingestion
   ✓ Good for internal use
   ✗ No cryptographic proof
   ✗ No audit trail
   ✗ Not compliance-ready
```

**Good for:**

- Development/testing
- Internal vulnerability tracking
- Teams that don't need legal proof
- Proof-of-concept deployments

### Premium Tier (Full Non-Repudiation)

```
Your Scan → Trust Verification → Trust Signing → Sigstore Recording → Index → Store
   ✓ Cryptographic proof
   ✓ Audit trail
   ✓ Compliance-ready
   ✓ Legal defensibility
   ✗ Slightly slower (verification overhead)
   ✗ Requires Trust service
```

**Good for:**

- Regulatory compliance (SOC 2, ISO27001, PCI-DSS)
- Legal proceedings
- High-security environments
- Incident investigations
- Vendor security assessments

## Why Non-Repudiation Matters

### Compliance

Many compliance frameworks require non-repudiation:

| Framework     | Requirement                                              |
| ------------- | -------------------------------------------------------- |
| **SOC 2**     | Verify that security assessments were actually performed |
| **ISO 27001** | Maintain audit trail of security controls                |
| **PCI-DSS**   | Prove scans were completed before certification          |
| **HIPAA**     | Document security assessments for audit                  |

### Incident Investigation

When a breach happens, you need to prove what you knew:

```
Breach Timeline:
├─ Jan 15: CVE-2024-1234 published
├─ Jan 16: You claim "we scanned on Jan 16"
├─ Jan 17: Breach discovered
└─ Jan 20: Audit investigation

With Non-Repudiation:
  ✓ Sigstore timestamp proves scan was Jan 16 at 14:32:45 UTC
  ✓ Impossible to forge (protected by public transparency log)
  ✓ Independent proof (not your system)

Without Non-Repudiation:
  ✗ "We scanned" is just a claim
  ✗ Could have been done retroactively
  ✗ No independent verification
```

### Supply Chain Security

For vendors assessing your code:

```
Customer: "Did you really scan our code?"

With Non-Repudiation:
  You: "Here's the Sigstore timestamp. You can verify it yourself."
  Customer: ✓ Satisfied

Without Non-Repudiation:
  You: "We scanned it, trust us."
  Customer: ✗ Not acceptable for enterprise contracts
```

## Architecture Components

The non-repudiation flow involves four services:

### 1. Certus-Assurance

- Runs security scanners
- Creates SARIF results
- Signs with inner signature
- Stores in S3 raw bucket

### 2. Certus-Transform

- Promotes scans from raw to golden bucket
- Optional: Calls Trust verification for premium tier
- Routes scanned artifacts to appropriate storage

### 3. Certus-Trust (Premium Tier Only)

- Verifies inner signatures
- Creates outer signature
- Records in Sigstore/Rekor
- Returns verification proof

### 4. Certus-Ask

- Ingests findings with verification metadata
- Stores in Neo4j graph with signature info
- Enables forensic queries by signer
- Supports audit trail searches

## Key Concepts

### Chain of Custody

The complete path from scanning to verification:

```
Code → Scan → Inner Signature → Transform → Trust Verification → Outer Signature → Rekor → Neo4j
```

If any step breaks, the chain is broken and non-repudiation is lost.

### Verification Proof

The metadata stored with each scan:

```json
{
  "chain_verified": true,
  "inner_signature_valid": true,
  "outer_signature_valid": true,
  "chain_unbroken": true,
  "signer_inner": "certus-assurance@certus.cloud",
  "signer_outer": "certus-trust@certus.cloud",
  "sigstore_timestamp": "2024-01-15T14:32:45Z"
}
```

### Forensic Queries

In premium tier, you can query Neo4j to find:

- All scans signed by a specific signer
- All verified scans in a time range
- Scans that failed verification
- Complete chain of custody for an assessment

### Build Provenance (SLSA & in-toto)

Beyond scan result non-repudiation, vendors can provide build provenance to prove **how** the software was built:

**SLSA Provenance (Supply-chain Levels for Software Artifacts)**

SLSA provenance documents the build process with cryptographic proof:

```json
{
  "buildType": "https://slsa.dev/build-type/github-actions/v1",
  "builder": {
    "id": "https://github.com/certus-cloud/certus-assurance-pipeline@v1.2.0"
  },
  "buildDefinition": {
    "externalParameters": {
      "repository": "https://github.com/vendor/product",
      "ref": "refs/heads/main",
      "commit": "abc123..."
    },
    "resolvedDependencies": [
      {
        "uri": "pkg:docker/aquasec/trivy@0.45.0",
        "digest": { "sha256": "..." }
      }
    ]
  },
  "runDetails": {
    "byproducts": [
      {
        "uri": "file:///reports/trivy.sarif.json",
        "digest": { "sha256": "..." }
      }
    ]
  }
}
```

**What it proves:**

- ✓ Builder identity (who ran the build)
- ✓ Source repository and exact commit
- ✓ All dependencies used (with hashes)
- ✓ Build outputs (SARIF, SBOM) with digests

**in-toto Attestations**

in-toto provides step-by-step attestations of the build pipeline:

```jsonl
{"_type":"https://in-toto.io/Statement/v1","predicate":{"name":"checkout",...}}
{"_type":"https://in-toto.io/Statement/v1","predicate":{"name":"sbom-generation",...}}
{"_type":"https://in-toto.io/Statement/v1","predicate":{"name":"sast-scan-trivy",...}}
```

Each line documents:

- **Materials** (inputs): Source code, dependencies
- **Products** (outputs): Generated artifacts with hashes
- **Command** executed
- **Environment** metadata

**Why it matters:**

Together, SLSA + in-toto provide **build reproducibility** - you can verify that scan results came from a legitimate build process, not fabricated artifacts. This is critical for:

- Supply chain security (preventing tampered builds)
- Vendor certification (proving build integrity)
- Compliance (SOC 2, ISO 27001 build attestation requirements)

See [sign-attestations.md](sign-attestations.md) for hands-on examples of generating and verifying SLSA provenance and in-toto attestations.

## Decision Tree: Do You Need Non-Repudiation?

```
Does your compliance framework require audit trails?
├─ YES → Use Premium Tier (non-repudiation)
└─ NO → Can use Free Tier

Are you subject to legal discovery or audits?
├─ YES → Use Premium Tier
└─ NO → Can use Free Tier

Do you need to prove you scanned before a security event?
├─ YES → Use Premium Tier (timestamp matters)
└─ NO → Can use Free Tier

Are you selling your service to enterprises?
├─ YES → Use Premium Tier (requirement)
└─ NO → Can use Free Tier
```

## What You'll Learn in This Series

1. **[This guide](overview.md)** - Understand non-repudiation concepts and architecture
2. **[sign-attestations.md](sign-attestations.md)** - Vendor workflow: Generate, sign, and push security artifacts (SBOM, SARIF, SLSA provenance, in-toto attestations) to OCI registry
3. **[verify-trust.md](verify-trust.md)** - Automated verification pipeline: Pass scans through Certus-Trust gateway for cryptographic verification
4. **[vendor-review.md](vendor-review.md)** - Customer/auditor workflow: Pull vendor artifacts from OCI, re-verify independently, and generate compliance reports
5. **[audit-queries.md](audit-queries.md)** - Forensic queries: Leverage Neo4j audit trail for compliance and incident investigation
6. **[security-scans.md](security-scans.md)** - (Optional) Advanced security scanning workflows and custom scanner integration

## Tutorial Workflow

The tutorials build on each other to show the complete non-repudiation lifecycle:

```
┌─────────────────────────────────────────────────────────────────────┐
│                    Complete Non-Repudiation Flow                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  1. VENDOR (sign-attestations.md)                                  │
│     ├─ Generate security scans (Trivy, Semgrep, Bandit, etc.)     │
│     ├─ Create SBOM (Syft)                                          │
│     ├─ Generate SLSA provenance & in-toto attestations             │
│     ├─ Sign artifacts with cosign                                  │
│     └─ Push to OCI registry                                        │
│                    ↓                                                │
│  2. AUTOMATED PIPELINE (verify-trust.md)                           │
│     ├─ Certus-Assurance scans code                                 │
│     ├─ Inner signature applied                                     │
│     ├─ Certus-Trust verifies signature                             │
│     ├─ Outer signature applied                                     │
│     ├─ Sigstore/Rekor timestamp recorded                           │
│     └─ Promoted to golden bucket                                   │
│                    ↓                                                │
│  3. CUSTOMER/AUDITOR (vendor-review.md)                            │
│     ├─ Pull artifacts from OCI registry                            │
│     ├─ Re-verify signatures independently                          │
│     ├─ Validate SLSA provenance                                    │
│     ├─ Ingest into Certus TAP                                      │
│     └─ Generate signed compliance report                           │
│                    ↓                                                │
│  4. FORENSICS (audit-queries.md)                                   │
│     ├─ Query Neo4j for verified scans                              │
│     ├─ Cross-check with Sigstore timestamps                        │
│     ├─ Generate audit trails for compliance                        │
│     └─ Investigate security incidents                              │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## Next Steps

**Choose your path:**

- **Start with the vendor workflow**: [sign-attestations.md](sign-attestations.md) - Learn how vendors generate and sign security artifacts
- **Start with automation**: [verify-trust.md](verify-trust.md) - See the automated Trust verification pipeline in action
- **Jump to forensics**: [audit-queries.md](audit-queries.md) - Standalone tutorial for querying the audit trail

**Need architectural details?** See [CERTUS_TRUST_IMPLEMENTATION_PLAN.md](../../../architecture/CERTUS_TRUST_IMPLEMENTATION_PLAN.md).
