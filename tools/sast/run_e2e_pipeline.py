#!/usr/bin/env python3
"""Run SAST scans, ingest SARIF/SBOM outputs into Certus, execute queries, and produce a Markdown report."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import textwrap
from pathlib import Path
from typing import Any

import requests

try:  # Optional dependency (installed in project env)
    from neo4j import GraphDatabase  # type: ignore
except ImportError:  # pragma: no cover - fallback when driver unavailable
    GraphDatabase = None  # type: ignore


def run_scan(export_dir: Path, tools: str | None, fail_on_findings: bool) -> None:
    export_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "tools/sast/run_local_scan.py", "--export-dir", str(export_dir)]
    if tools:
        cmd.extend(["--tools", tools])
    if fail_on_findings:
        cmd.append("--fail-on-findings")
    print(f"[scan] Running SAST pipeline -> {export_dir}")
    subprocess.run(cmd, check=True)


def upload_artifact(
    workspace: str,
    base_url: str,
    file_path: Path,
    format_hint: str | None = None,
) -> dict[str, Any]:
    if not file_path.exists():
        raise FileNotFoundError(f"Missing artifact: {file_path}")
    url = f"{base_url.rstrip('/')}/v1/{workspace}/index/security"
    data: dict[str, str] = {}
    if format_hint:
        data["format"] = format_hint
    with file_path.open("rb") as fh:
        files = {"uploaded_file": (file_path.name, fh, "application/json")}
        response = requests.post(url, files=files, data=data, timeout=300)
    try:
        payload = response.json()
    except json.JSONDecodeError:
        payload = {"raw": response.text}
    if response.status_code >= 400:
        raise RuntimeError(f"HTTP {response.status_code}: {payload}")
    return payload


def keyword_snapshot(workspace: str, opensearch_url: str, size: int = 5) -> list[dict[str, Any]]:
    query = {
        "size": size,
        "sort": [{"meta.ingested_at.keyword": {"order": "desc"}}],
        "query": {
            "bool": {
                "filter": [
                    {"term": {"workspace_id.keyword": workspace}},
                ]
            }
        },
    }
    headers = {"Content-Type": "application/json"}
    indices = ["security-findings", f"ask_certus_{workspace}"]
    for index in indices:
        url = f"{opensearch_url.rstrip('/')}/{index}/_search"
        resp = requests.post(url, headers=headers, json=query, timeout=60)
        if resp.status_code != 200:
            continue
        hits = resp.json().get("hits", {}).get("hits", [])
        if hits:
            results = []
            for hit in hits:
                src = hit.get("_source", {})
                results.append({
                    "rule_id": src.get("rule_id"),
                    "severity": src.get("severity"),
                    "source_location": src.get("source_location"),
                    "message": src.get("content") or src.get("message"),
                })
            return results
    return []


def semantic_summary(workspace: str, base_url: str, question: str) -> dict[str, Any]:
    url = f"{base_url.rstrip('/')}/v1/{workspace}/ask"
    resp = requests.post(url, json={"question": question}, timeout=120)
    if resp.status_code >= 400:
        return {"error": resp.text}
    return resp.json()


def graph_snapshot(
    scan_id: str | None,
    neo4j_uri: str,
    user: str,
    password: str,
) -> dict[str, Any]:
    """Query Neo4j for comprehensive security analysis.

    Returns:
        Dictionary with severity counts, top findings, affected files, and rule breakdown
    """
    if not scan_id or not GraphDatabase:
        return {}

    driver = GraphDatabase.driver(neo4j_uri, auth=(user, password))

    try:
        with driver.session() as session:
            # Query 1: Severity distribution
            severity_query = textwrap.dedent(
                """
                MATCH (:SecurityScan {id: $scan_id})-[:CONTAINS]->(f:Finding)-[:HAS_SEVERITY]->(s:Severity)
                RETURN s.level AS severity, count(*) AS count
                ORDER BY count DESC
                """
            )
            severity_counts = session.run(severity_query, scan_id=scan_id).data()

            # Query 2: Top 10 critical/high findings
            top_findings_query = textwrap.dedent(
                """
                MATCH (:SecurityScan {id: $scan_id})-[:CONTAINS]->(f:Finding)-[:HAS_SEVERITY]->(s:Severity)
                WHERE s.level IN ['CRITICAL', 'HIGH']
                RETURN f.rule_id AS rule_id, f.message AS message, s.level AS severity,
                       f.location AS location
                ORDER BY
                    CASE s.level
                        WHEN 'CRITICAL' THEN 1
                        WHEN 'HIGH' THEN 2
                        ELSE 3
                    END
                LIMIT 10
                """
            )
            top_findings = session.run(top_findings_query, scan_id=scan_id).data()

            # Query 3: Most affected files
            affected_files_query = textwrap.dedent(
                """
                MATCH (:SecurityScan {id: $scan_id})-[:CONTAINS]->(f:Finding)
                WHERE f.location IS NOT NULL
                WITH split(f.location, ':')[0] AS file_path, count(*) AS issue_count
                RETURN file_path, issue_count
                ORDER BY issue_count DESC
                LIMIT 10
                """
            )
            affected_files = session.run(affected_files_query, scan_id=scan_id).data()

            # Query 4: Rule/CWE breakdown
            rule_breakdown_query = textwrap.dedent(
                """
                MATCH (:SecurityScan {id: $scan_id})-[:CONTAINS]->(f:Finding)
                RETURN f.rule_id AS rule, count(*) AS occurrences
                ORDER BY occurrences DESC
                LIMIT 10
                """
            )
            rule_breakdown = session.run(rule_breakdown_query, scan_id=scan_id).data()

            # Query 5: Scan metadata
            scan_meta_query = textwrap.dedent(
                """
                MATCH (s:SecurityScan {id: $scan_id})
                RETURN s.tool AS tool, s.timestamp AS timestamp, s.total_findings AS total
                """
            )
            scan_meta = session.run(scan_meta_query, scan_id=scan_id).data()

            return {
                "severity_counts": severity_counts,
                "top_findings": top_findings,
                "affected_files": affected_files,
                "rule_breakdown": rule_breakdown,
                "scan_metadata": scan_meta[0] if scan_meta else {},
            }
    finally:
        driver.close()


def safe_relpath(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def parse_sbom(sbom_path: Path) -> dict[str, Any]:
    """Parse SBOM file and extract package summary.

    Args:
        sbom_path: Path to SBOM SPDX JSON file

    Returns:
        Dictionary with package counts and top packages
    """
    if not sbom_path.exists():
        return {"error": "SBOM file not found"}

    try:
        with open(sbom_path, encoding="utf-8") as f:
            sbom = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        return {"error": f"Failed to parse SBOM: {e}"}

    packages = sbom.get("packages", [])

    if not packages:
        return {"total_packages": 0, "packages": []}

    # Group by package type/source and collect metadata
    python_packages = {}  # Use dict to track versions and detect duplicates
    github_actions = []
    binaries = []
    licenses = {}
    duplicates = []

    for pkg in packages:
        name = pkg.get("name", "unknown")
        version = pkg.get("versionInfo", "unknown")
        source = pkg.get("sourceInfo", "")
        license_declared = pkg.get("licenseDeclared", "NOASSERTION")
        license_concluded = pkg.get("licenseConcluded", "NOASSERTION")

        # Track licenses - prefer declared, fall back to concluded
        license_to_use = None
        if license_declared and license_declared != "NOASSERTION":
            license_to_use = license_declared
        elif license_concluded and license_concluded != "NOASSERTION":
            license_to_use = license_concluded

        if license_to_use:
            licenses[license_to_use] = licenses.get(license_to_use, 0) + 1
        else:
            licenses["Unknown"] = licenses.get("Unknown", 0) + 1

        # Categorize packages and detect duplicates
        if "python package" in source.lower() or "pypi" in source.lower():
            if name in python_packages:
                # Duplicate detected
                if python_packages[name] != version:
                    duplicates.append({"name": name, "versions": [python_packages[name], version]})
            else:
                python_packages[name] = version
        elif "github action" in source.lower():
            github_actions.append({"name": name, "version": version})
        elif "binary" in source.lower():
            binaries.append({"name": name, "version": version})

    # Convert dict to list for top packages
    top_python = [{"name": name, "version": ver} for name, ver in list(python_packages.items())[:10]]

    # Sort licenses by count
    sorted_licenses = sorted(licenses.items(), key=lambda x: x[1], reverse=True)

    # Identify concerning licenses
    restrictive_licenses = ["GPL-3.0", "AGPL-3.0", "GPL-2.0", "LGPL-3.0"]
    concerning = {lic: count for lic, count in sorted_licenses if lic in restrictive_licenses}
    unknown_count = licenses.get("Unknown", 0)

    return {
        "total_packages": len(packages),
        "python_packages": len(python_packages),
        "github_actions": len(github_actions),
        "binaries": len(binaries),
        "other": len(packages) - len(python_packages) - len(github_actions) - len(binaries),
        "top_python": top_python,
        "licenses": sorted_licenses[:10],  # Top 10 licenses
        "license_count": len(licenses),
        "unknown_licenses": unknown_count,
        "restrictive_licenses": concerning,
        "duplicates": duplicates[:10],  # Top 10 duplicates
        "duplicate_count": len(duplicates),
    }


def write_report(
    report_path: Path,
    build_id: str,
    workspace: str,
    artifacts: list[dict[str, Any]],
    keyword_hits: list[dict[str, Any]],
    semantic_result: dict[str, Any],
    graph_result: dict[str, Any],
    sbom_summary: dict[str, Any] | None = None,
) -> None:
    lines = [f"# Certus SAST Report ({build_id})", ""]
    lines.append(f"- Workspace: `{workspace}`")
    lines.append(f"- Generated: {dt.datetime.utcnow().isoformat()}Z")
    lines.append("")

    lines.append("## Ingested Artifacts")
    if artifacts:
        lines.append("| Tool | File | Ingestion ID | Neo4j Scan ID | Message |")
        lines.append("| --- | --- | --- | --- | --- |")
        for art in artifacts:
            msg = (art.get("message") or "").replace("|", "/")
            lines.append(
                f"| {art['tool']} | {art['file']} | {art.get('ingestion_id', '-')} | "
                f"{art.get('neo4j_scan_id', '-')} | {msg} |"
            )
    else:
        lines.append("No artifacts ingested.")
    lines.append("")

    lines.append("## Keyword Snapshot (OpenSearch)")
    if keyword_hits:
        for hit in keyword_hits:
            lines.append(
                f"- **Rule:** {hit.get('rule_id')} | Severity: {hit.get('severity')} | Location: {hit.get('source_location')}"
            )
            if hit.get("message"):
                lines.append(f"  - {hit['message']}")
    else:
        lines.append("No keyword hits (index may still be building).")
    lines.append("")

    lines.append("## Semantic Summary (/ask)")
    if "answer" in semantic_result:
        lines.append(f"**Question:** {semantic_result.get('question') or 'N/A'}")
        lines.append(semantic_result.get("answer", "No answer returned."))
    else:
        lines.append(f"Semantic query failed: {semantic_result}")
    lines.append("")

    lines.append("## Security Analysis (Neo4j Graph Database)")
    if graph_result and graph_result.get("severity_counts"):
        # Scan metadata
        scan_meta = graph_result.get("scan_metadata", {})
        if scan_meta:
            lines.append(f"**Scan Tool:** {scan_meta.get('tool', 'N/A')}")
            lines.append(f"**Total Findings:** {scan_meta.get('total', 'N/A')}")
            lines.append("")

        # Severity distribution
        severity_counts = graph_result.get("severity_counts", [])
        if severity_counts:
            lines.append("### Severity Distribution")
            lines.append("| Severity | Count |")
            lines.append("| --- | --- |")
            for row in severity_counts:
                lines.append(f"| {row.get('severity', '-')} | {row.get('count', '-')} |")
            lines.append("")

        # Top critical/high findings
        top_findings = graph_result.get("top_findings", [])
        if top_findings:
            lines.append("### Critical & High Severity Findings")
            for finding in top_findings:
                severity = finding.get("severity", "UNKNOWN")
                rule_id = finding.get("rule_id", "N/A")
                location = finding.get("location", "N/A")
                message = finding.get("message", "No description")[:100]
                lines.append(f"- **[{severity}]** {rule_id}")
                lines.append(f"  - Location: `{location}`")
                lines.append(f"  - {message}")
            lines.append("")

        # Most affected files
        affected_files = graph_result.get("affected_files", [])
        if affected_files:
            lines.append("### Most Affected Files")
            lines.append("| File | Issues |")
            lines.append("| --- | --- |")
            for file_info in affected_files:
                lines.append(f"| {file_info.get('file_path', 'N/A')} | {file_info.get('issue_count', 0)} |")
            lines.append("")

        # Rule breakdown
        rule_breakdown = graph_result.get("rule_breakdown", [])
        if rule_breakdown:
            lines.append("### Top Security Rules Triggered")
            lines.append("| Rule ID | Occurrences |")
            lines.append("| --- | --- |")
            for rule in rule_breakdown:
                lines.append(f"| {rule.get('rule', 'N/A')} | {rule.get('occurrences', 0)} |")
            lines.append("")
    else:
        lines.append("No graph data available.")
    lines.append("")

    # SBOM Summary Section
    lines.append("## Software Bill of Materials (SBOM)")
    if sbom_summary and "error" not in sbom_summary:
        total = sbom_summary.get("total_packages", 0)
        lines.append(f"**Total Packages:** {total}")
        lines.append("")

        if total > 0:
            lines.append("**Package Breakdown:**")
            lines.append(f"- Python Packages: {sbom_summary.get('python_packages', 0)}")
            lines.append(f"- GitHub Actions: {sbom_summary.get('github_actions', 0)}")
            lines.append(f"- Binaries: {sbom_summary.get('binaries', 0)}")
            lines.append(f"- Other: {sbom_summary.get('other', 0)}")
            lines.append("")

            top_python = sbom_summary.get("top_python", [])
            if top_python:
                lines.append("**Top Python Dependencies:**")
                for pkg in top_python:
                    lines.append(f"- {pkg['name']} ({pkg['version']})")
                lines.append("")

            # License Analysis
            licenses = sbom_summary.get("licenses", [])
            if licenses:
                lines.append("### License Analysis")
                lines.append(f"**Unique Licenses:** {sbom_summary.get('license_count', 0)}")
                lines.append("")
                lines.append("**Top Licenses:**")
                for lic, count in licenses:
                    lines.append(f"- {lic}: {count} packages")
                lines.append("")

                # Warnings for concerning licenses
                restrictive = sbom_summary.get("restrictive_licenses", {})
                unknown = sbom_summary.get("unknown_licenses", 0)
                if restrictive or unknown > 0:
                    lines.append("**⚠️ License Concerns:**")
                    if restrictive:
                        for lic, count in restrictive.items():
                            lines.append(f"- {lic}: {count} packages (restrictive license)")
                    if unknown > 0:
                        lines.append(f"- Unknown/Missing: {unknown} packages")
                    lines.append("")

            # Duplicate Detection
            duplicates = sbom_summary.get("duplicates", [])
            dup_count = sbom_summary.get("duplicate_count", 0)
            if dup_count > 0:
                lines.append("### Duplicate Packages")
                lines.append(f"**Total Duplicates:** {dup_count}")
                lines.append("")
                if duplicates:
                    lines.append("**Packages with Multiple Versions:**")
                    for dup in duplicates:
                        versions_str = ", ".join(dup["versions"])
                        lines.append(f"- {dup['name']}: {versions_str}")
                    lines.append("")
    elif sbom_summary and "error" in sbom_summary:
        lines.append(f"SBOM parsing failed: {sbom_summary['error']}")
    else:
        lines.append("No SBOM data available.")
    lines.append("")

    report_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[report] Wrote {report_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run SAST scans, ingest artifacts, and produce Certus report.")
    parser.add_argument("--workspace", default="sast-workspace", help="Workspace ID.")
    parser.add_argument("--build-id", default=None, help="Optional build identifier (defaults to timestamp).")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Certus TAP API base URL.")
    parser.add_argument("--opensearch-url", default="http://localhost:9200", help="OpenSearch URL.")
    parser.add_argument("--neo4j-uri", default="neo4j://localhost:7687", help="Neo4j Bolt URI.")
    parser.add_argument("--neo4j-user", default="neo4j", help="Neo4j username.")
    parser.add_argument("--neo4j-password", default="password", help="Neo4j password.")
    parser.add_argument(
        "--export-dir", default=None, help="Override export directory (default build/sast-reports/<build_id>)."
    )
    parser.add_argument("--tools", default=None, help="Subset of tools to run (passed to run_local_scan).")
    parser.add_argument("--skip-scan", action="store_true", help="Reuse existing artifacts (skip running scan).")
    parser.add_argument("--skip-ingest", action="store_true", help="Skip uploading SARIF/SBOM artifacts into Certus.")
    parser.add_argument(
        "--semantic-question",
        default="Summarize the highest severity findings from the latest scan.",
        help="Question for the semantic /ask endpoint.",
    )
    parser.add_argument(
        "--fail-on-findings",
        action="store_true",
        help="Propagate --fail-on-findings to the underlying scan step.",
    )
    args = parser.parse_args()

    build_id = args.build_id or dt.datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    export_dir = Path(args.export_dir or f"build/sast-reports/{build_id}")
    report_path = export_dir / f"CERTUS_SCAN_REPORT_{build_id}.md"

    if not args.skip_scan:
        run_scan(export_dir, args.tools, args.fail_on_findings)
    else:
        print(f"[scan] Skipping scan, using artifacts in {export_dir}")

    sarif_targets = [
        ("Trivy", export_dir / "SECURITY" / "trivy.sarif.json", None),
        ("Semgrep", export_dir / "SECURITY" / "semgrep.sarif.json", None),
        ("Bandit", export_dir / "SECURITY" / "bandit.sarif.json", None),
    ]
    sbom_target = ("SBOM", export_dir / "SUPPLY_CHAIN" / "sbom.spdx.json", "spdx")

    artifacts_info: list[dict[str, Any]] = []
    if args.skip_ingest:
        print("[ingest] Skipping ingestion.")
    else:
        for tool, path, fmt in [*sarif_targets, sbom_target]:
            entry = {"tool": tool, "file": safe_relpath(path, export_dir.parent)}
            try:
                response = upload_artifact(args.workspace, args.base_url, path, format_hint=fmt)
                entry["ingestion_id"] = response.get("ingestion_id")
                entry["neo4j_scan_id"] = response.get("neo4j_scan_id")
                entry["message"] = response.get("message")
            except Exception as exc:
                entry["message"] = f"FAILED: {exc}"
                print(f"[ingest] {tool}: {exc}")
            artifacts_info.append(entry)

    try:
        keyword_hits = keyword_snapshot(args.workspace, args.opensearch_url)
    except Exception as exc:
        print(f"[opensearch] keyword query failed: {exc}")
        keyword_hits = []

    try:
        semantic_result = semantic_summary(args.workspace, args.base_url, args.semantic_question)
    except Exception as exc:
        semantic_result = {"error": str(exc)}

    neo4j_scan_id = next((art.get("neo4j_scan_id") for art in artifacts_info if art.get("neo4j_scan_id")), None)
    try:
        graph_result = graph_snapshot(neo4j_scan_id, args.neo4j_uri, args.neo4j_user, args.neo4j_password)
    except Exception as exc:
        print(f"[neo4j] query failed: {exc}")
        graph_result = {}

    # Parse SBOM for package summary
    sbom_path = export_dir / "SUPPLY_CHAIN" / "sbom.spdx.json"
    sbom_summary = parse_sbom(sbom_path)

    report_path.parent.mkdir(parents=True, exist_ok=True)
    write_report(
        report_path, build_id, args.workspace, artifacts_info, keyword_hits, semantic_result, graph_result, sbom_summary
    )


if __name__ == "__main__":
    main()
