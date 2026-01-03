#!/usr/bin/env python3
"""
Generate realistic sample evidence bundles for Certus Integrity tutorials.

This script creates evidence bundles representing an automated scraper attack
scenario on December 15, 2025, showing how the integrity middleware detects
and blocks malicious traffic while allowing legitimate users.
"""

import base64
import hashlib
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal


def generate_trace_id() -> str:
    """Generate a 32-character hex trace ID (OpenTelemetry format)."""
    return uuid.uuid4().hex


def generate_span_id() -> str:
    """Generate a 16-character hex span ID (OpenTelemetry format)."""
    return uuid.uuid4().hex[:16]


def generate_content_hash(content: dict[str, Any]) -> str:
    """Generate SHA256 hash of canonical JSON."""
    canonical_json = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode()).hexdigest()


def generate_mock_signature() -> str:
    """Generate a mock base64-encoded signature (~512 chars)."""
    # Simulates a 384-byte signature (ECDSA P-384 or RSA-3072)
    random_bytes = bytes([random.randint(0, 255) for _ in range(384)])
    return base64.b64encode(random_bytes).decode("ascii")


def generate_mock_certificate() -> str:
    """Generate a mock PEM certificate snippet."""
    return """-----BEGIN CERTIFICATE-----
MIIDQTCCAimgAwIBAgITBmyfz5m/jAo54vB4ikPmljZbyjANBgkqhkiG9w0BAQsF
ADA/MSQwIgYDVQQKExtEaWdpdGFsIFNpZ25hdHVyZSBUcnVzdCBDby4xFzAVBgNV
BAMTDkRTVCBSb290IENBIFgzMB4XDTIxMDEyMDE5MTQwM1oXDTI0MDkzMDE4MTQw
M1owTzELMAkGA1UEBhMCVVMxKTAnBgNVBAoTIEludGVybmV0IFNlY3VyaXR5IFJl
c2VhcmNoIEdyb3VwMRUwEwYDVQQDEwxJU1JHIFJvb3QgWDEwggEiMA0GCSqGSIb3
DQEBAQUAA4IBDwAwggEKAoIBAQCt6CRz9BQ385ueK1coHIe+3LffOJCMbjzmV6B4
93XCOVfp2BG/z0jZrcuJ8L/RWWAgx0mPf0gzsUbFKLJZSAaJxAgTCWx2e/RMaEkS
-----END CERTIFICATE-----"""


def generate_transparency_log_entry() -> dict[str, Any]:
    """Generate a mock Rekor transparency log entry."""
    return {
        "uuid": str(uuid.uuid4()),
        "log_index": random.randint(10000000, 99999999),
        "log_id": "c0d23d6ad406973f9559f3ba2d1ca01f84147d8ffc5b8445c224f98b9591801d",
        "integrated_time": int(datetime.now().timestamp()),
        "inclusion_proof": {
            "tree_size": random.randint(100000000, 999999999),
            "root_hash": hashlib.sha256(str(random.random()).encode()).hexdigest(),
            "log_index": random.randint(10000000, 99999999),
            "hashes": [hashlib.sha256(str(random.random()).encode()).hexdigest() for _ in range(5)],
        },
    }


def create_evidence_bundle(
    timestamp: datetime,
    client_ip: str,
    endpoint: str,
    decision: Literal["allowed", "denied"],
    reason: str,
    guardrail: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Create a complete signed evidence bundle."""

    # Generate decision content
    decision_id = str(uuid.uuid4())
    trace_id = generate_trace_id()
    span_id = generate_span_id()

    decision_content = {
        "decision_id": decision_id,
        "timestamp": timestamp.isoformat() + "Z",
        "trace_id": trace_id,
        "span_id": span_id,
        "service": "certus-ask",
        "decision": decision,
        "reason": reason,
        "guardrail": guardrail,
        "metadata": {"client_ip": client_ip, "endpoint": endpoint, "shadow_mode": False, **metadata},
    }

    # Generate content hash
    content_hash = generate_content_hash(decision_content)

    # Create signed evidence bundle
    evidence = {
        "evidence_id": decision_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "decision": decision_content,
        "content_hash": content_hash,
        "signature": generate_mock_signature(),
        "signer_certificate": generate_mock_certificate(),
        "transparency_log_entry": generate_transparency_log_entry(),
        "verification_status": "signed",
    }

    return evidence


def save_evidence(evidence: dict[str, Any], output_dir: Path, prefix: str, index: int):
    """Save evidence bundle to JSON file."""
    filename = f"{prefix}_{index:03d}_{evidence['evidence_id']}.json"
    file_path = output_dir / filename

    with open(file_path, "w") as f:
        json.dump(evidence, f, indent=2)

    print(f"Created: {filename}")


def main():
    """Generate all evidence bundles for the attack scenario."""
    output_dir = Path(__file__).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    base_time = datetime(2025, 12, 15, 14, 25, 0)

    print("\n=== Generating Scenario: Automated Scraper Attack (2025-12-15) ===\n")

    # 1. Normal Traffic (15 bundles) - 14:25:00 to 14:31:00
    print("1. Generating Normal Traffic (15 bundles)...")
    endpoints = ["/v1/default/ask", "/v1/health", "/v1/workspaces"]

    for i in range(15):
        ip = f"192.168.1.{100 + i}"
        endpoint = random.choice(endpoints)
        requests_in_window = random.randint(5, 40)
        timestamp = base_time + timedelta(seconds=i * 24)  # Spread over 6 minutes

        evidence = create_evidence_bundle(
            timestamp=timestamp,
            client_ip=ip,
            endpoint=endpoint,
            decision="allowed",
            reason="within_rate_limit",
            guardrail="rate_limit",
            metadata={
                "requests_in_window": requests_in_window,
                "limit": 100,
                "burst_limit": 20,
                "duration_ms": round(random.uniform(5.0, 25.0), 2),
            },
        )

        save_evidence(evidence, output_dir, "01_normal", i + 1)

    # 2. Attack Beginning (5 bundles) - 14:30:00 to 14:31:30
    print("\n2. Generating Attack Beginning (5 bundles)...")
    attack_ip = "203.0.113.50"
    attack_start = base_time + timedelta(minutes=5)

    for i in range(5):
        requests_in_window = 60 + (i * 7)  # 60, 67, 74, 81, 88, 95
        timestamp = attack_start + timedelta(seconds=i * 18)

        evidence = create_evidence_bundle(
            timestamp=timestamp,
            client_ip=attack_ip,
            endpoint="/v1/default/ask",
            decision="allowed",
            reason="within_rate_limit",
            guardrail="rate_limit",
            metadata={
                "requests_in_window": requests_in_window,
                "limit": 100,
                "burst_limit": 20,
                "duration_ms": round(random.uniform(8.0, 15.0), 2),
            },
        )

        save_evidence(evidence, output_dir, "02_attack_begin", i + 1)

    # 3. Rate Limit Triggered (20 bundles) - 14:32:00 to 14:34:30
    print("\n3. Generating Rate Limit Blocks (20 bundles)...")
    rate_limit_start = base_time + timedelta(minutes=7)

    for i in range(20):
        requests_in_window = 101 + (i * 5)  # 101 to 196
        timestamp = rate_limit_start + timedelta(seconds=i * 7.5)

        evidence = create_evidence_bundle(
            timestamp=timestamp,
            client_ip=attack_ip,
            endpoint="/v1/default/ask",
            decision="denied",
            reason="rate_limit_exceeded",
            guardrail="rate_limit",
            metadata={
                "requests_in_window": requests_in_window,
                "limit": 100,
                "burst_limit": 20,
                "duration_ms": round(random.uniform(2.0, 8.0), 2),
                "retry_after": 60,
            },
        )

        save_evidence(evidence, output_dir, "03_rate_limit_denied", i + 1)

    # 4. Burst Attack (10 bundles) - 14:35:00 to 14:35:10
    print("\n4. Generating Burst Attack (10 bundles)...")
    burst_ip = "198.51.100.25"
    burst_start = base_time + timedelta(minutes=10)

    for i in range(10):
        recent_count = 21 + i  # 21 to 30
        timestamp = burst_start + timedelta(seconds=i)

        evidence = create_evidence_bundle(
            timestamp=timestamp,
            client_ip=burst_ip,
            endpoint="/v1/default/query",
            decision="denied",
            reason="burst_limit_exceeded",
            guardrail="rate_limit",
            metadata={
                "recent_count": recent_count,
                "burst_limit": 20,
                "burst_window_seconds": 10,
                "requests_in_window": random.randint(15, 30),
                "limit": 100,
                "duration_ms": round(random.uniform(1.5, 4.0), 2),
                "retry_after": 10,
            },
        )

        save_evidence(evidence, output_dir, "04_burst_attack", i + 1)

    # 5. Distributed Attack (15 bundles) - 14:36:00 to 14:38:00
    print("\n5. Generating Distributed Attack (15 bundles)...")
    distributed_start = base_time + timedelta(minutes=11)

    for i in range(15):
        ip = f"45.76.132.{10 + i}"
        timestamp = distributed_start + timedelta(seconds=i * 8)

        # First 5 requests from each IP are allowed, then denied
        if i % 3 == 0:  # Mix some allowed
            decision = "allowed"
            reason = "within_rate_limit"
            requests = random.randint(40, 70)
        else:
            decision = "denied"
            reason = "rate_limit_exceeded"
            requests = random.randint(101, 150)

        evidence = create_evidence_bundle(
            timestamp=timestamp,
            client_ip=ip,
            endpoint="/v1/default/ask",
            decision=decision,
            reason=reason,
            guardrail="rate_limit",
            metadata={
                "requests_in_window": requests,
                "limit": 100,
                "burst_limit": 20,
                "duration_ms": round(random.uniform(3.0, 12.0), 2),
                "attack_pattern": "distributed",
                "retry_after": 60 if decision == "denied" else None,
            },
        )

        save_evidence(evidence, output_dir, "05_distributed_attack", i + 1)

    # 6. Post-Attack Normal (10 bundles) - 14:40:00 onwards
    print("\n6. Generating Post-Attack Normal Traffic (10 bundles)...")
    normal_start = base_time + timedelta(minutes=15)

    legitimate_ips = [
        "192.168.1.200",
        "192.168.1.201",
        "192.168.1.202",
        "192.168.1.203",
        "10.0.0.50",
        "10.0.0.51",
        "172.16.0.100",
        "172.16.0.101",
        "192.168.2.10",
        "192.168.2.11",
    ]

    for i in range(10):
        ip = legitimate_ips[i]
        endpoint = random.choice(endpoints)
        timestamp = normal_start + timedelta(seconds=i * 20)
        requests_in_window = random.randint(5, 35)

        evidence = create_evidence_bundle(
            timestamp=timestamp,
            client_ip=ip,
            endpoint=endpoint,
            decision="allowed",
            reason="within_rate_limit",
            guardrail="rate_limit",
            metadata={
                "requests_in_window": requests_in_window,
                "limit": 100,
                "burst_limit": 20,
                "duration_ms": round(random.uniform(6.0, 18.0), 2),
            },
        )

        save_evidence(evidence, output_dir, "06_post_attack_normal", i + 1)

    print(f"\n=== Complete! Generated 75 evidence bundles in {output_dir} ===")
    print("\nSummary:")
    print("  - 15 Normal Traffic (allowed)")
    print("  - 5 Attack Beginning (allowed, approaching limit)")
    print("  - 20 Rate Limit Blocks (denied)")
    print("  - 10 Burst Attack (denied)")
    print("  - 15 Distributed Attack (mixed)")
    print("  - 10 Post-Attack Normal (allowed)")


if __name__ == "__main__":
    main()
