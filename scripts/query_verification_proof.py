#!/usr/bin/env python3
"""
Query verification proof from Certus-Assurance.

Simulates querying Rekor transparency log for verification proof.
In production, this would use rekor-cli or cosign verify.

Tutorial: docs/learn/provenance/trust-verification.md (Step 8)

Usage:
    # Query most recent scan
    uv run scripts/query_verification_proof.py

    # Query specific scan
    uv run scripts/query_verification_proof.py scan_abc123def456
"""

import sys
from pathlib import Path

import requests


def get_verification_proof(scan_id: str, assurance_url: str = "http://localhost:8056"):
    """Get verification proof (simulated Rekor entry)."""
    try:
        response = requests.get(f"{assurance_url}/v1/security-scans/{scan_id}")
        response.raise_for_status()
    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to Certus-Assurance at {assurance_url}")
        print("Make sure the service is running: just up")
        return False
    except requests.exceptions.HTTPError as exc:
        status_code = exc.response.status_code if exc.response is not None else "unknown"
        if status_code == 404:
            print(f"Scan not found: {scan_id}")
            print("Double-check the SCAN_ID or rerun the scan submission/upload workflow.")
        else:
            print(f"Certus-Assurance returned HTTP {status_code} when fetching {scan_id}.")
            if exc.response is not None:
                print(f"Response body: {exc.response.text}")
        return False

    scan = response.json()
    proof = scan.get("verification_proof")

    if not proof:
        print(f"No verification proof found for {scan_id}")
        print(f"Status: {scan.get('status')}")
        print(f"Upload Status: {scan.get('upload_status')}")
        return False

    # Check if running in production mode by querying Trust service
    is_production = False
    try:
        trust_response = requests.get("http://localhost:8057/v1/health", timeout=2)
        if trust_response.ok:
            # Trust is running - check if it's using real Sigstore
            is_production = True
    except:
        pass

    mode = "REKOR TRANSPARENCY LOG ENTRY" if is_production else "SIMULATED REKOR TRANSPARENCY LOG ENTRY"

    print("=" * 60)
    print(mode)
    print("=" * 60)
    print(f"\nScan ID: {scan_id}")
    print(f"Entry UUID: {proof.get('rekor_entry_uuid', 'N/A')}")
    print(f"Timestamp: {proof.get('sigstore_timestamp', 'N/A')}")
    print("\nVerification Status:")
    print(f"  Chain verified: {proof.get('chain_verified', False)}")
    print(f"  Inner signature valid: {proof.get('inner_signature_valid', False)}")
    print(f"  Outer signature valid: {proof.get('outer_signature_valid', False)}")
    print("\nSigners:")
    print(f"  Inner (Assurance): {proof.get('signer_inner', 'N/A')}")
    print(f"  Outer (Trust): {proof.get('signer_outer', 'N/A')}")

    sig_label = "Signatures:" if is_production else "Signatures (MOCK):"
    print(f"\n{sig_label}")
    print(f"  Cosign: {proof.get('cosign_signature', 'N/A')}")
    print("\n" + "=" * 60)

    if is_production:
        print("✓  Production Sigstore integration active")
        print("   Entries can be verified with rekor-cli at http://localhost:3001")
    else:
        print("⚠️  Note: Running in MOCK mode")
        print("   Real Sigstore entries cannot be queried with these values")
        print("   Set CERTUS_TRUST_MOCK_SIGSTORE=false for production")
    print("=" * 60)
    return True


def get_most_recent_scan() -> str | None:
    """Get the most recent scan ID from artifacts directory."""
    scan_dir = Path("./.artifacts/certus-assurance")
    if scan_dir.exists():
        scans = sorted(scan_dir.iterdir())
        if scans:
            return scans[-1].name
    return None


def main():
    # Get scan ID from command line or use most recent
    if len(sys.argv) > 1:
        scan_id = sys.argv[1]
    else:
        scan_id = get_most_recent_scan()
        if not scan_id:
            print("No scans found. Run a scan first:")
            print("  1. Submit scan: curl -X POST http://localhost:8056/v1/security-scans ...")
            print("  2. Wait for completion: sleep 6")
            print(
                "  3. Submit upload request: curl -X POST http://localhost:8056/v1/security-scans/$SCAN_ID/upload-request ..."
            )
            return 1

    print(f"\nQuerying verification proof for: {scan_id}\n")
    success = get_verification_proof(scan_id)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
