#!/usr/bin/env python3
"""
Reusable helper to scan S3 prefixes with Presidio and quarantine objects that contain PII.

This script mirrors the inline tutorial snippet that previously lived in docs.
"""

from __future__ import annotations

import argparse
import os
from collections.abc import Iterable
from pathlib import Path

import boto3

# Ensure FastAPI/Ask logging does not try to reach container-only hostnames.
os.environ.setdefault("DISABLE_OPENSEARCH_LOGGING", "true")

from certus_ask.services.presidio import get_analyzer

# Metadata artifacts that should never be quarantined even if they contain PII-like strings.
SKIP_FILE_BASENAMES = {
    "verification-proof.json",
    "scan.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan S3 prefix for PII and quarantine hits.")
    parser.add_argument(
        "--bucket",
        default="raw",
        help="S3 bucket to scan (default: raw)",
    )
    parser.add_argument(
        "--prefix",
        help="S3 prefix to scan (e.g., security-scans/scan_abc123/).",
    )
    parser.add_argument(
        "--scan-id",
        help="Convenience flag that sets prefix to security-scans/<scan_id>/",
    )
    parser.add_argument(
        "--quarantine-prefix",
        help="Quarantine prefix. Defaults to <prefix>/quarantine/.",
    )
    parser.add_argument(
        "--endpoint",
        default="http://localhost:4566",
        help="S3 endpoint URL (default: http://localhost:4566 for LocalStack).",
    )
    parser.add_argument(
        "--aws-access-key",
        default=os.environ.get("AWS_ACCESS_KEY_ID", "test"),
        help="AWS access key (default: env or 'test').",
    )
    parser.add_argument(
        "--aws-secret-key",
        default=os.environ.get("AWS_SECRET_ACCESS_KEY", "test"),
        help="AWS secret key (default: env or 'test').",
    )
    parser.add_argument(
        "--region",
        default=os.environ.get("AWS_REGION", "us-east-1"),
        help="AWS region (default: env or us-east-1).",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        help="Optional path to write a scan report. If omitted, report prints to stdout only.",
    )
    args = parser.parse_args()

    if not args.prefix and not args.scan_id:
        parser.error("You must pass either --prefix or --scan-id.")

    if args.scan_id:
        args.prefix = f"security-scans/{args.scan_id.rstrip('/')}/"

    if not args.prefix.endswith("/"):
        args.prefix += "/"

    if args.quarantine_prefix:
        args.quarantine_prefix = args.quarantine_prefix.rstrip("/") + "/"
    else:
        args.quarantine_prefix = args.prefix.rstrip("/") + "/quarantine/"

    return args


def iter_objects(s3_client, bucket: str, prefix: str) -> Iterable[dict]:
    paginator = s3_client.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        yield from page.get("Contents", [])


def main() -> None:
    args = parse_args()

    analyzer = get_analyzer()
    s3 = boto3.client(
        "s3",
        endpoint_url=args.endpoint,
        aws_access_key_id=args.aws_access_key,
        aws_secret_access_key=args.aws_secret_key,
        region_name=args.region,
    )

    report_lines: list[str] = []
    blocked = 0
    clean = 0

    for item in iter_objects(s3, args.bucket, args.prefix):
        key = item["Key"]
        if key.endswith("/") or key.startswith(args.quarantine_prefix):
            continue

        basename = Path(key).name
        if not basename or basename in SKIP_FILE_BASENAMES:
            continue

        obj = s3.get_object(Bucket=args.bucket, Key=key)
        text = obj["Body"].read().decode("utf-8", errors="ignore")
        findings = analyzer.analyze(text=text, entities=[], language="en")

        if findings:
            blocked += 1
            report_lines.append(f"[BLOCK - PII DETECTED] s3://{args.bucket}/{key}\n")
            quarantine_key = key.replace(args.prefix, args.quarantine_prefix, 1)
            s3.copy_object(
                Bucket=args.bucket,
                CopySource={"Bucket": args.bucket, "Key": key},
                Key=quarantine_key,
            )
            s3.delete_object(Bucket=args.bucket, Key=key)
        else:
            clean += 1
            report_lines.append(f"[OK] s3://{args.bucket}/{key}\n")

    report = "".join(report_lines) or "No objects scanned.\n"

    if args.report_path:
        args.report_path.parent.mkdir(parents=True, exist_ok=True)
        args.report_path.write_text(report)
        print(f"Privacy scan report written to {args.report_path}")

    print("Privacy scan report:")
    print(report)
    print(f"Summary: {clean} clean, {blocked} quarantined.")


if __name__ == "__main__":
    main()
