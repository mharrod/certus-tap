#!/usr/bin/env python3
"""
Verify the integrity of evidence bundles by checking content hashes.
"""

import hashlib
import json
from pathlib import Path


def verify_bundle(file_path: Path) -> bool:
    """Verify a single evidence bundle's content hash."""
    with open(file_path) as f:
        bundle = json.load(f)

    # Recompute content hash
    decision_json = json.dumps(bundle["decision"], sort_keys=True, separators=(",", ":"))
    computed_hash = hashlib.sha256(decision_json.encode()).hexdigest()

    # Compare with stored hash
    stored_hash = bundle["content_hash"]

    return computed_hash == stored_hash


def main():
    script_dir = Path(__file__).parent

    print("Verifying evidence bundle integrity...\n")

    verified = 0
    failed = 0

    for file_path in sorted(script_dir.glob("*.json")):
        try:
            if verify_bundle(file_path):
                verified += 1
                print(f"✓ {file_path.name}")
            else:
                failed += 1
                print(f"✗ {file_path.name} - HASH MISMATCH!")
        except Exception as e:
            failed += 1
            print(f"✗ {file_path.name} - ERROR: {e}")

    print(f"\n{'=' * 70}")
    print("Verification complete:")
    print(f"  Verified: {verified}")
    print(f"  Failed:   {failed}")
    print(f"{'=' * 70}\n")

    if failed > 0:
        exit(1)


if __name__ == "__main__":
    main()
