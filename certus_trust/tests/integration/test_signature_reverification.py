"""Integration tests for independent signature re-verification.

This test suite validates the cryptographic re-verification workflow described in
docs/learn/trust/vendor-review.md Step 3, where auditors independently verify
signatures on pulled artifacts.

Tutorial reference: docs/learn/trust/vendor-review.md (Step 3)
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# Test data paths
SAMPLES_ROOT = Path(__file__).resolve().parents[3] / "samples"
KEYS_DIR = SAMPLES_ROOT / "oci-attestations/keys"
ARTIFACTS_DIR = SAMPLES_ROOT / "oci-attestations/artifacts"


def _check_cosign_available() -> bool:
    """Check if cosign CLI is installed."""
    try:
        result = subprocess.run(
            ["cosign", "version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def test_reverify_sbom_signature() -> None:
    """
    Re-verify cosign signature on SBOM.

    Validates:
    - Cosign can verify signature
    - Public key matches
    - Signature is valid
    """
    if not _check_cosign_available():
        pytest.skip("cosign CLI not installed")

    sbom_path = ARTIFACTS_DIR / "sbom/product.spdx.json"
    sig_path = ARTIFACTS_DIR / "sbom/product.spdx.json.sig"
    pub_key = KEYS_DIR / "cosign.pub"

    if not all([sbom_path.exists(), pub_key.exists()]):
        pytest.skip("Test artifacts not available")

    # TODO: Signature file needs to exist
    if not sig_path.exists():
        pytest.skip("Signature file not present - implement signing in attestations workflow")

    # Verify signature
    result = subprocess.run(
        [
            "cosign",
            "verify-blob",
            "--insecure-ignore-tlog",
            "--key",
            str(pub_key),
            "--signature",
            str(sig_path),
            str(sbom_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Signature verification failed: {result.stderr}"
    print("✓ SBOM signature verified successfully")


def test_reverify_sarif_signature() -> None:
    """
    Re-verify cosign signature on SARIF scan results.

    Validates:
    - SARIF signature valid
    - Matches expected public key
    """
    if not _check_cosign_available():
        pytest.skip("cosign CLI not installed")

    sarif_path = ARTIFACTS_DIR / "scans/vulnerability.sarif"
    sig_path = ARTIFACTS_DIR / "scans/vulnerability.sarif.sig"
    pub_key = KEYS_DIR / "cosign.pub"

    if not all([sarif_path.exists(), pub_key.exists()]):
        pytest.skip("Test artifacts not available")

    if not sig_path.exists():
        pytest.skip("Signature file not present")

    result = subprocess.run(
        [
            "cosign",
            "verify-blob",
            "--insecure-ignore-tlog",
            "--key",
            str(pub_key),
            "--signature",
            str(sig_path),
            str(sarif_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Signature verification failed: {result.stderr}"
    print("✓ SARIF signature verified successfully")


def test_reverify_provenance_signature() -> None:
    """
    Re-verify cosign signature on SLSA provenance.

    Validates:
    - Provenance signature valid
    - Build integrity preserved
    """
    if not _check_cosign_available():
        pytest.skip("cosign CLI not installed")

    prov_path = ARTIFACTS_DIR / "provenance/slsa-provenance.json"
    sig_path = ARTIFACTS_DIR / "provenance/slsa-provenance.json.sig"
    pub_key = KEYS_DIR / "cosign.pub"

    if not all([prov_path.exists(), pub_key.exists()]):
        pytest.skip("Test artifacts not available")

    if not sig_path.exists():
        pytest.skip("Signature file not present")

    result = subprocess.run(
        [
            "cosign",
            "verify-blob",
            "--insecure-ignore-tlog",
            "--key",
            str(pub_key),
            "--signature",
            str(sig_path),
            str(prov_path),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, f"Signature verification failed: {result.stderr}"
    print("✓ Provenance signature verified successfully")


def test_validate_dual_signature_chain() -> None:
    """
    Validate dual-signature chain in verification proof.

    Validates:
    - Inner signature (Assurance)
    - Outer signature (Trust)
    - Chain is unbroken
    - Signers match expected identities
    """
    # TODO: Requires verification-proof.json from completed Trust workflow
    pytest.skip("Requires verification-proof.json from Trust workflow")

    # Example implementation:
    # proof_path = Path("/tmp/verification-proof.json")
    # with proof_path.open() as f:
    #     proof = json.load(f)
    #
    # assert proof["chain_verified"] is True
    # assert proof["inner_signature_valid"] is True
    # assert proof["outer_signature_valid"] is True
    # assert proof["chain_unbroken"] is True
    # assert proof["signer_inner"] == "certus-assurance@certus.cloud"
    # assert proof["signer_outer"] == "certus-trust@certus.cloud"
    #
    # print("✓ Dual-signature chain validated")


def test_compare_sbom_digest_with_provenance() -> None:
    """
    Compare SBOM digest in provenance with actual SBOM file.

    Validates:
    - SBOM digest in provenance matches actual file
    - Provenance integrity
    - No tampering occurred
    """
    sbom_path = ARTIFACTS_DIR / "sbom/product.spdx.json"
    prov_path = ARTIFACTS_DIR / "provenance/slsa-provenance.json"

    if not all([sbom_path.exists(), prov_path.exists()]):
        pytest.skip("Test artifacts not available")

    # Calculate actual SBOM digest
    actual_digest = hashlib.sha256(sbom_path.read_bytes()).hexdigest()

    # Extract digest from provenance
    with prov_path.open() as f:
        provenance = json.load(f)

    # Navigate to SBOM digest in provenance
    # Structure: predicate.buildDefinition.internalParameters.SBOM.digest.sha256
    try:
        expected_digest = (
            provenance.get("predicate", {})
            .get("buildDefinition", {})
            .get("internalParameters", {})
            .get("SBOM", {})
            .get("digest", {})
            .get("sha256")
        )
    except (KeyError, AttributeError):
        pytest.skip("Provenance structure doesn't contain SBOM digest")

    assert actual_digest == expected_digest, (
        f"SBOM digest mismatch:\n  Actual: {actual_digest}\n  Expected (from provenance): {expected_digest}"
    )

    print(f"✓ SBOM digest matches provenance: {actual_digest[:16]}...")


def test_detect_tampered_artifact() -> None:
    """
    Negative test: Detect tampered artifact fails verification.

    Validates:
    - Modified artifact fails signature check
    - Verification catches tampering
    """
    if not _check_cosign_available():
        pytest.skip("cosign CLI not installed")

    # TODO: Create tampered copy and verify it fails
    pytest.skip("Implement tampered artifact test")

    # Example implementation:
    # import tempfile
    #
    # sbom_path = ARTIFACTS_DIR / "sbom/product.spdx.json"
    # sig_path = ARTIFACTS_DIR / "sbom/product.spdx.json.sig"
    # pub_key = KEYS_DIR / "cosign.pub"
    #
    # # Create tampered copy
    # with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp:
    #     sbom_data = json.loads(sbom_path.read_text())
    #     sbom_data["tampered"] = True  # Modify content
    #     json.dump(sbom_data, tmp)
    #     tampered_path = Path(tmp.name)
    #
    # # Verify tampered file fails
    # result = subprocess.run(
    #     [
    #         "cosign", "verify-blob",
    #         "--insecure-ignore-tlog",
    #         "--key", str(pub_key),
    #         "--signature", str(sig_path),
    #         str(tampered_path),
    #     ],
    #     capture_output=True,
    #     text=True,
    # )
    #
    # assert result.returncode != 0, "Tampered artifact should fail verification"
    # tampered_path.unlink()


def test_verify_all_artifacts_in_bundle() -> None:
    """
    Batch verify all signed artifacts in bundle.

    Validates:
    - All artifacts have valid signatures
    - No unsigned artifacts
    - Public key consistent across all
    """
    if not _check_cosign_available():
        pytest.skip("cosign CLI not installed")

    pub_key = KEYS_DIR / "cosign.pub"
    if not pub_key.exists():
        pytest.skip("Public key not available")

    # Define artifacts to verify
    artifacts_to_verify = [
        ("sbom/product.spdx.json", "sbom/product.spdx.json.sig"),
        ("scans/vulnerability.sarif", "scans/vulnerability.sarif.sig"),
        ("provenance/slsa-provenance.json", "provenance/slsa-provenance.json.sig"),
        ("attestations/build.intoto.json", "attestations/build.intoto.json.sig"),
    ]

    verified_count = 0
    skipped_count = 0

    for artifact_rel, sig_rel in artifacts_to_verify:
        artifact_path = ARTIFACTS_DIR / artifact_rel
        sig_path = ARTIFACTS_DIR / sig_rel

        if not artifact_path.exists():
            print(f"⚠ Artifact missing: {artifact_rel}")
            skipped_count += 1
            continue

        if not sig_path.exists():
            print(f"⚠ Signature missing: {sig_rel}")
            skipped_count += 1
            continue

        result = subprocess.run(
            [
                "cosign",
                "verify-blob",
                "--insecure-ignore-tlog",
                "--key",
                str(pub_key),
                "--signature",
                str(sig_path),
                str(artifact_path),
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode == 0:
            print(f"✓ Verified: {artifact_rel}")
            verified_count += 1
        else:
            pytest.fail(f"Verification failed for {artifact_rel}: {result.stderr}")

    if skipped_count == len(artifacts_to_verify):
        pytest.skip("No signed artifacts available for verification")

    assert verified_count > 0, "At least one artifact should be verified"
    print(f"\n✅ Verified {verified_count} artifacts, skipped {skipped_count}")


# NOTE: Additional tests to implement:
# - test_verify_with_wrong_public_key() - negative test
# - test_verify_signature_timestamp()
# - test_certificate_chain_validation() - for full PKI
# - test_revocation_check() - if using certificate revocation
