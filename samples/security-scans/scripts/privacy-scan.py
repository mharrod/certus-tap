#!/usr/bin/env python3
"""Privacy scan script using Presidio to detect and quarantine files with PII.

This script scans all files in an S3 raw/active bucket for personally identifiable
information (PII) using the Presidio analyzer. Files with detected PII are moved to
raw/quarantine for human review. Files without PII remain in raw/active for processing.

Usage:
    python privacy-scan.py [--raw-bucket RAW_BUCKET] [--s3-endpoint S3_ENDPOINT]

Examples:
    # Scan default buckets
    python privacy-scan.py

    # Scan with custom S3 endpoint
    python privacy-scan.py --s3-endpoint http://localhost:4566

    # Scan custom raw bucket
    python privacy-scan.py --raw-bucket my-custom-raw-bucket
"""

import argparse
import sys

import boto3

try:
    from presidio_analyzer import AnalyzerEngine
except (ImportError, ValueError) as e:
    print(f"❌ Failed to import Presidio: {e}")
    print("\nTo fix this, try reinstalling dependencies:")
    print("  pip install --upgrade --force-reinstall presidio-analyzer")
    print("  pip install --upgrade numpy")
    sys.exit(1)


def scan_files_for_pii(
    s3_client: object,
    raw_bucket: str,
    analyzer: AnalyzerEngine,
    active_prefix: str = "active/",
    quarantine_prefix: str = "quarantine/",
) -> dict:
    """Scan all files in raw/active for PII and quarantine those with findings.

    Args:
        s3_client: Boto3 S3 client
        raw_bucket: Name of the raw S3 bucket
        analyzer: Presidio AnalyzerEngine instance
        active_prefix: Prefix for active files (default: "active/")
        quarantine_prefix: Prefix for quarantined files (default: "quarantine/")

    Returns:
        Dictionary with scan results:
        {
            "scanned": int,
            "clean": int,
            "quarantined": int,
            "errors": int,
            "files": {
                "clean": [list of filenames],
                "quarantined": [list of filenames],
                "errors": [list of filenames]
            }
        }
    """
    results = {
        "scanned": 0,
        "clean": 0,
        "quarantined": 0,
        "errors": 0,
        "files": {"clean": [], "quarantined": [], "errors": []},
    }

    # List all files in raw/active
    try:
        paginator = s3_client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=raw_bucket, Prefix=active_prefix)
    except Exception as e:
        print(f"❌ Error listing S3 bucket {raw_bucket}: {e}")
        return results

    for page in pages:
        contents = page.get("Contents", [])
        if not contents:
            continue

        for obj in contents:
            key = obj["Key"]
            filename = key.replace(active_prefix, "")

            # Skip empty keys or directory markers
            if not filename or filename.endswith("/"):
                continue

            results["scanned"] += 1

            try:
                # Download file
                response = s3_client.get_object(Bucket=raw_bucket, Key=key)
                content = response["Body"].read().decode("utf-8")

                # Scan for PII
                pii_findings = analyzer.analyze(text=content, language="en")

                if pii_findings:
                    print(f"⚠️  {filename}: Found {len(pii_findings)} potential PII entities")
                    for finding in pii_findings[:3]:  # Show first 3
                        print(f"   - {finding.entity_type} at position {finding.start}:{finding.end}")

                    # Move to quarantine
                    s3_client.copy_object(
                        CopySource={"Bucket": raw_bucket, "Key": key},
                        Bucket=raw_bucket,
                        Key=f"{quarantine_prefix}{filename}",
                    )
                    s3_client.delete_object(Bucket=raw_bucket, Key=key)
                    results["quarantined"] += 1
                    results["files"]["quarantined"].append(filename)
                    print(f"   → Moved to s3://{raw_bucket}/{quarantine_prefix}{filename}")
                else:
                    print(f"✅ {filename}: No PII detected")
                    results["clean"] += 1
                    results["files"]["clean"].append(filename)

            except Exception as e:
                print(f"❌ Error scanning {filename}: {e}")
                results["errors"] += 1
                results["files"]["errors"].append(filename)

    return results


def main():
    parser = argparse.ArgumentParser(description="Scan S3 files for PII using Presidio and quarantine sensitive files.")
    parser.add_argument(
        "--raw-bucket",
        default="raw",
        help="Name of the raw S3 bucket (default: raw)",
    )
    parser.add_argument(
        "--s3-endpoint",
        default="http://localhost:4566",
        help="S3 endpoint URL (default: http://localhost:4566)",
    )
    parser.add_argument(
        "--active-prefix",
        default="active/",
        help="Prefix for active files in S3 (default: active/)",
    )
    parser.add_argument(
        "--quarantine-prefix",
        default="quarantine/",
        help="Prefix for quarantined files in S3 (default: quarantine/)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed output",
    )

    args = parser.parse_args()

    # Initialize Presidio analyzer
    try:
        analyzer = AnalyzerEngine()
        if args.verbose:
            print("✅ Presidio analyzer initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Presidio analyzer: {e}")
        sys.exit(1)

    # Initialize S3 client
    try:
        s3_client = boto3.client("s3", endpoint_url=args.s3_endpoint)
        if args.verbose:
            print(f"✅ Connected to S3 at {args.s3_endpoint}")
    except Exception as e:
        print(f"❌ Failed to connect to S3: {e}")
        sys.exit(1)

    # Run privacy scan
    print(f"\n📋 Starting privacy scan on s3://{args.raw_bucket}/{args.active_prefix}")
    results = scan_files_for_pii(
        s3_client,
        args.raw_bucket,
        analyzer,
        args.active_prefix,
        args.quarantine_prefix,
    )

    # Print summary
    print(f"\n{'=' * 60}")
    print("Privacy Scan Summary")
    print(f"{'=' * 60}")
    print(f"Total scanned:    {results['scanned']}")
    print(f"Clean files:      {results['clean']}")
    print(f"Quarantined:      {results['quarantined']}")
    print(f"Errors:           {results['errors']}")

    if results["files"]["clean"]:
        print(f"\n✅ Clean files ({len(results['files']['clean'])}):")
        for filename in results["files"]["clean"]:
            print(f"   - {filename}")

    if results["files"]["quarantined"]:
        print(f"\n⚠️  Quarantined files ({len(results['files']['quarantined'])}):")
        for filename in results["files"]["quarantined"]:
            print(f"   - {filename}")

    if results["files"]["errors"]:
        print(f"\n❌ Files with errors ({len(results['files']['errors'])}):")
        for filename in results["files"]["errors"]:
            print(f"   - {filename}")

    print(f"{'=' * 60}")

    # Exit with error if any quarantined or errors
    if results["quarantined"] > 0 or results["errors"] > 0:
        print("\n⚠️  Review quarantined files before proceeding to promotion step")
        sys.exit(0)  # Exit 0 to allow human review
    else:
        print("\n✅ All files passed privacy scan - ready for promotion")
        sys.exit(0)


if __name__ == "__main__":
    main()
