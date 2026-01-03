#!/usr/bin/env python3
"""Enforce manifest policy thresholds - standalone version."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SEVERITY_ORDER = ("critical", "high", "medium", "low")


def _init_counts() -> dict[str, int]:
    return dict.fromkeys(SEVERITY_ORDER, 0)


def collect_severity_counts(artifact_root: Path) -> dict[str, int]:
    counts = _init_counts()
    counts = _collect_bandit(artifact_root, counts)
    counts = _collect_sarif(artifact_root / "trivy.sarif.json", counts)
    counts = _collect_sarif(artifact_root / "opengrep.sarif.json", counts)
    counts = _collect_detect_secrets(artifact_root / "detect-secrets.json", counts)
    counts = _collect_dast(artifact_root / "dast-results.json", counts)
    return counts


def evaluate_thresholds(
    thresholds: dict[str, int] | None,
    counts: dict[str, int],
) -> list[str]:
    if not thresholds:
        return []

    violations: list[str] = []
    for severity, limit in thresholds.items():
        normalized = severity.lower()
        if normalized not in SEVERITY_ORDER:
            continue
        observed = counts.get(normalized, 0)
        if observed > int(limit):
            violations.append(
                f"{normalized} findings exceeded threshold ({observed} > {limit})",
            )
    return violations


def enforce_thresholds(
    artifact_root: Path,
    thresholds: dict[str, int] | None,
) -> list[str]:
    counts = collect_severity_counts(artifact_root)
    return evaluate_thresholds(thresholds, counts)


def _collect_bandit(root: Path, counts: dict[str, int]) -> dict[str, int]:
    target = root / "bandit.json"
    if not target.exists():
        return counts
    try:
        data = json.loads(target.read_text())
    except json.JSONDecodeError:
        return counts
    for finding in data.get("results", []):
        severity = str(finding.get("issue_severity", "")).lower()
        if severity in counts:
            counts[severity] += 1
    return counts


def _collect_sarif(path: Path, counts: dict[str, int]) -> dict[str, int]:
    if not path.exists():
        return counts
    try:
        sarif = json.loads(path.read_text())
    except json.JSONDecodeError:
        return counts
    for run in sarif.get("runs", []):
        for result in run.get("results", []):
            severity = _sarif_severity(result)
            if severity in counts:
                counts[severity] += 1
    return counts


def _sarif_severity(result: dict[str, Any]) -> str:
    props = result.get("properties") or {}
    if isinstance(props, dict):
        severity = props.get("security-severity") or props.get("problem.severity")
        if severity:
            normalized = str(severity).lower()
            if normalized in SEVERITY_ORDER:
                return normalized
            if normalized in {"error", "err"}:
                return "high"
            if normalized in {"warning", "warn"}:
                return "medium"
            if normalized in {"note", "information"}:
                return "low"
    level = result.get("level")
    if isinstance(level, str):
        normalized = level.lower()
        if normalized in {"error", "err"}:
            return "high"
        if normalized in {"warning", "warn"}:
            return "medium"
        if normalized in {"note", "information"}:
            return "low"
    return "low"


def _collect_detect_secrets(path: Path, counts: dict[str, int]) -> dict[str, int]:
    if not path.exists():
        return counts
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return counts
    total = 0
    if isinstance(data, dict):
        for entries in data.values():
            if isinstance(entries, list):
                total += len(entries)
    if total:
        counts["medium"] += total
    return counts


def _collect_dast(path: Path, counts: dict[str, int]) -> dict[str, int]:
    if not path.exists():
        return counts
    try:
        report = json.loads(path.read_text())
    except json.JSONDecodeError:
        return counts
    findings = report.get("findings")
    if isinstance(findings, list):
        for finding in findings:
            severity = str(finding.get("severity", "medium")).lower()
            counts[severity if severity in counts else "medium"] += 1
    return counts


def main(artifact_root: str, thresholds_json: str) -> int:
    root_path = Path(artifact_root)
    thresholds = json.loads(thresholds_json) if thresholds_json else {}
    counts = collect_severity_counts(root_path)
    violations = evaluate_thresholds(thresholds, counts)

    # Write policy results to file for calling pipeline to inspect
    policy_result = {
        "passed": len(violations) == 0,
        "thresholds": thresholds,
        "counts": counts,
        "violations": violations,
    }

    policy_file = root_path / "policy-result.json"
    policy_file.write_text(json.dumps(policy_result, indent=2))

    # Log violations but don't fail - let calling pipeline decide
    if violations:
        for violation in violations:
            print(f"[policy] {violation}", file=sys.stderr)
        print(f"[policy] Results written to {policy_file}", file=sys.stderr)

    # Always return 0 - artifacts will be exported
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <artifact_root> <thresholds_json>", file=sys.stderr)
        sys.exit(1)
    status = main(sys.argv[1], sys.argv[2])
    sys.exit(status)
