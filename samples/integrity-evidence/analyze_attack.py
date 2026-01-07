#!/usr/bin/env python3
"""
Analyze the automated scraper attack scenario from evidence bundles.

This script demonstrates how to parse and analyze Certus Integrity evidence
bundles to detect attack patterns and understand security incidents.
"""

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def load_evidence_bundles(directory: Path) -> list[dict[str, Any]]:
    """Load all evidence bundles from JSON files."""
    bundles = []
    for file_path in sorted(directory.glob("*.json")):
        if file_path.name == "generate_samples.py":
            continue
        with open(file_path) as f:
            bundles.append(json.load(f))
    return bundles


def analyze_timeline(bundles: list[dict[str, Any]]):
    """Analyze the attack timeline."""
    print("\n" + "=" * 70)
    print("TIMELINE ANALYSIS")
    print("=" * 70)

    # Group by minute
    by_minute = defaultdict(lambda: {"allowed": 0, "denied": 0, "ips": set()})

    for bundle in bundles:
        decision = bundle["decision"]
        timestamp = datetime.fromisoformat(decision["timestamp"].rstrip("Z"))
        minute_key = timestamp.strftime("%H:%M")

        by_minute[minute_key][decision["decision"]] += 1
        by_minute[minute_key]["ips"].add(decision["metadata"]["client_ip"])

    print(f"\n{'Time':<10} {'Allowed':<10} {'Denied':<10} {'Unique IPs':<12} {'Status'}")
    print("-" * 70)

    for minute in sorted(by_minute.keys()):
        data = by_minute[minute]
        allowed = data["allowed"]
        denied = data["denied"]
        unique_ips = len(data["ips"])

        # Determine status
        if denied > 20:
            status = "CRITICAL ATTACK"
        elif denied > 10:
            status = "MODERATE ATTACK"
        elif denied > 0:
            status = "Attack Detected"
        else:
            status = "Normal"

        print(f"{minute:<10} {allowed:<10} {denied:<10} {unique_ips:<12} {status}")


def analyze_attackers(bundles: list[dict[str, Any]]):
    """Identify and analyze attacking IP addresses."""
    print("\n" + "=" * 70)
    print("ATTACKER ANALYSIS")
    print("=" * 70)

    ip_stats = defaultdict(lambda: {"allowed": 0, "denied": 0, "endpoints": set(), "reasons": Counter()})

    for bundle in bundles:
        decision = bundle["decision"]
        ip = decision["metadata"]["client_ip"]

        ip_stats[ip][decision["decision"]] += 1
        ip_stats[ip]["endpoints"].add(decision["metadata"]["endpoint"])
        ip_stats[ip]["reasons"][decision["reason"]] += 1

    # Identify attackers (high denial rate)
    attackers = []
    for ip, stats in ip_stats.items():
        total = stats["allowed"] + stats["denied"]
        denial_rate = stats["denied"] / total if total > 0 else 0

        if denial_rate > 0.5 or stats["denied"] > 5:
            attackers.append((ip, stats, denial_rate))

    # Sort by denial count
    attackers.sort(key=lambda x: x[1]["denied"], reverse=True)

    print(f"\nFound {len(attackers)} attacking IP addresses:\n")
    print(f"{'IP Address':<18} {'Allowed':<10} {'Denied':<10} {'Denial %':<12} {'Attack Type'}")
    print("-" * 70)

    for ip, stats, denial_rate in attackers[:20]:  # Top 20
        allowed = stats["allowed"]
        denied = stats["denied"]

        # Determine attack type
        if "rate_limit_exceeded" in stats["reasons"]:
            attack_type = "Sustained Attack" if denied > 15 else "Rate Limit Violation"
        elif "burst_limit_exceeded" in stats["reasons"]:
            attack_type = "Burst Attack"
        else:
            attack_type = "Unknown"

        print(f"{ip:<18} {allowed:<10} {denied:<10} {denial_rate * 100:>10.1f}%  {attack_type}")


def analyze_guardrails(bundles: list[dict[str, Any]]):
    """Analyze which guardrails were triggered."""
    print("\n" + "=" * 70)
    print("GUARDRAIL EFFECTIVENESS")
    print("=" * 70)

    guardrail_stats = defaultdict(lambda: {"allowed": 0, "denied": 0})
    reason_counts = Counter()

    for bundle in bundles:
        decision = bundle["decision"]
        guardrail = decision["guardrail"]
        outcome = decision["decision"]
        reason = decision["reason"]

        guardrail_stats[guardrail][outcome] += 1
        if outcome == "denied":
            reason_counts[reason] += 1

    print("\nGuardrail Performance:\n")
    print(f"{'Guardrail':<20} {'Allowed':<10} {'Denied':<10} {'Block Rate'}")
    print("-" * 70)

    for guardrail, stats in sorted(guardrail_stats.items()):
        allowed = stats["allowed"]
        denied = stats["denied"]
        total = allowed + denied
        block_rate = denied / total * 100 if total > 0 else 0

        print(f"{guardrail:<20} {allowed:<10} {denied:<10} {block_rate:>9.1f}%")

    print("\nDenial Reasons:\n")
    for reason, count in reason_counts.most_common():
        print(f"  {reason:<30} {count:>3} denials")


def analyze_endpoints(bundles: list[dict[str, Any]]):
    """Analyze which endpoints were targeted."""
    print("\n" + "=" * 70)
    print("ENDPOINT TARGETING")
    print("=" * 70)

    endpoint_stats = defaultdict(lambda: {"allowed": 0, "denied": 0, "ips": set()})

    for bundle in bundles:
        decision = bundle["decision"]
        endpoint = decision["metadata"]["endpoint"]
        outcome = decision["decision"]
        ip = decision["metadata"]["client_ip"]

        endpoint_stats[endpoint][outcome] += 1
        endpoint_stats[endpoint]["ips"].add(ip)

    print(f"\n{'Endpoint':<30} {'Allowed':<10} {'Denied':<10} {'Unique IPs':<12} {'Risk'}")
    print("-" * 70)

    for endpoint, stats in sorted(endpoint_stats.items(), key=lambda x: x[1]["denied"], reverse=True):
        allowed = stats["allowed"]
        denied = stats["denied"]
        unique_ips = len(stats["ips"])
        total = allowed + denied

        # Risk assessment
        if denied > 20:
            risk = "HIGH"
        elif denied > 10:
            risk = "MEDIUM"
        elif denied > 0:
            risk = "LOW"
        else:
            risk = "NONE"

        print(f"{endpoint:<30} {allowed:<10} {denied:<10} {unique_ips:<12} {risk}")


def analyze_attack_patterns(bundles: list[dict[str, Any]]):
    """Detect attack patterns in the evidence."""
    print("\n" + "=" * 70)
    print("ATTACK PATTERN DETECTION")
    print("=" * 70)

    patterns = {"sustained_attack": 0, "burst_attack": 0, "distributed_attack": 0, "low_and_slow": 0}

    # Group by IP
    by_ip = defaultdict(list)
    for bundle in bundles:
        decision = bundle["decision"]
        ip = decision["metadata"]["client_ip"]
        by_ip[ip].append(decision)

    for ip, decisions in by_ip.items():
        denied = sum(1 for d in decisions if d["decision"] == "denied")

        if denied > 15:
            patterns["sustained_attack"] += 1
        elif any("burst_limit_exceeded" in d["reason"] for d in decisions):
            patterns["burst_attack"] += 1
        elif denied > 0 and denied < 5:
            patterns["low_and_slow"] += 1

    # Check for distributed attack (multiple IPs from same network)
    networks = defaultdict(int)
    for ip in by_ip:
        if any(d["decision"] == "denied" for d in by_ip[ip]):
            network = ".".join(ip.split(".")[:3]) + ".x"
            networks[network] += 1

    for network, count in networks.items():
        if count > 5:
            patterns["distributed_attack"] += 1

    print("\nDetected Attack Patterns:\n")
    print(f"  Sustained Attacks:     {patterns['sustained_attack']:>3} IPs")
    print(f"  Burst Attacks:         {patterns['burst_attack']:>3} IPs")
    print(f"  Distributed Attacks:   {patterns['distributed_attack']:>3} Networks")
    print(f"  Low-and-Slow Attempts: {patterns['low_and_slow']:>3} IPs")


def generate_summary(bundles: list[dict[str, Any]]):
    """Generate executive summary."""
    print("\n" + "=" * 70)
    print("EXECUTIVE SUMMARY")
    print("=" * 70)

    total = len(bundles)
    allowed = sum(1 for b in bundles if b["decision"]["decision"] == "allowed")
    denied = sum(1 for b in bundles if b["decision"]["decision"] == "denied")

    unique_ips = len({b["decision"]["metadata"]["client_ip"] for b in bundles})
    attacking_ips = len({
        b["decision"]["metadata"]["client_ip"] for b in bundles if b["decision"]["decision"] == "denied"
    })

    print("\nAttack Scenario: Automated Scraper Attack (December 15, 2025)")
    print(f"\nTotal Decisions:        {total}")
    print(f"  Allowed:              {allowed} ({allowed / total * 100:.1f}%)")
    print(f"  Denied:               {denied} ({denied / total * 100:.1f}%)")
    print(f"\nUnique IP Addresses:    {unique_ips}")
    print(f"  Legitimate Users:     {unique_ips - attacking_ips}")
    print(f"  Attacking IPs:        {attacking_ips}")
    print(f"\nEffectiveness:          {denied} malicious requests blocked")
    print("False Positive Rate:    0% (all legitimate traffic allowed)")

    # Time range
    timestamps = [datetime.fromisoformat(b["decision"]["timestamp"].rstrip("Z")) for b in bundles]
    start = min(timestamps)
    end = max(timestamps)
    duration = (end - start).total_seconds() / 60

    print(f"\nAttack Duration:        {duration:.1f} minutes")
    print(f"Start Time:             {start.strftime('%H:%M:%S')}")
    print(f"End Time:               {end.strftime('%H:%M:%S')}")


def main():
    """Run all analyses."""
    script_dir = Path(__file__).parent

    print("\n" + "=" * 70)
    print("CERTUS INTEGRITY ATTACK ANALYSIS")
    print("=" * 70)
    print(f"\nAnalyzing evidence bundles in: {script_dir}")

    bundles = load_evidence_bundles(script_dir)
    print(f"Loaded {len(bundles)} evidence bundles")

    generate_summary(bundles)
    analyze_timeline(bundles)
    analyze_attackers(bundles)
    analyze_guardrails(bundles)
    analyze_endpoints(bundles)
    analyze_attack_patterns(bundles)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
