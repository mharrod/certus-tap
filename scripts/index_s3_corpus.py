#!/usr/bin/env python3
"""Index documents from S3 bucket using the backend API.

This script calls the backend endpoint to index all documents
from an S3 bucket/prefix into the specified workspace.
"""

import argparse
import json
import sys

import requests


def index_s3_corpus(
    base_url: str,
    workspace_id: str,
    bucket_name: str,
    prefix: str = "",
    verbose: bool = False,
) -> bool:
    """Index documents from S3 bucket.

    Args:
        base_url: Base URL of the backend (e.g., http://localhost:8000)
        workspace_id: Workspace ID to index documents into
        bucket_name: S3 bucket name
        prefix: S3 prefix/folder (optional)
        verbose: Print detailed output

    Returns:
        True if successful, False otherwise
    """
    if verbose:
        print("Indexing from S3:")
        print(f"  Bucket: {bucket_name}")
        print(f"  Prefix: {prefix or '(root)'}")
        print(f"  Workspace ID: {workspace_id}")
        print(f"  Backend URL: {base_url}")

    endpoint = f"{base_url}/v1/{workspace_id}/index/s3"

    payload = {
        "bucket_name": bucket_name,
        "prefix": prefix,
    }

    try:
        if verbose:
            print(f"\nSending request to: {endpoint}")
            print(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(
            endpoint,
            json=payload,
            timeout=600,  # 10 minute timeout for large batch indexing
        )

        if verbose:
            print(f"Status Code: {response.status_code}")

        response.raise_for_status()

        result = response.json()

        # Print results
        print("\n" + "=" * 60)
        print("INDEXING SUCCESSFUL")
        print("=" * 60)
        print(f"Ingestion ID: {result['ingestion_id']}")
        print(f"Message: {result['message']}")
        print("\nProcessing Stats:")
        print(f"  Processed Files: {result['processed_files']}")
        print(f"  Failed Files: {result['failed_files']}")
        if result.get("quarantined_documents"):
            print(f"  Quarantined Documents: {result['quarantined_documents']}")
        print(f"\nTotal Documents in Index: {result['document_count']}")

        if result.get("metadata_preview"):
            print("\nSample Metadata:")
            for item in result["metadata_preview"][:3]:
                if isinstance(item, dict):
                    print(f"  - {json.dumps(item, indent=4)}")
                else:
                    print(f"  - {item}")

        return True

    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to backend at {base_url}")
        print("Make sure the backend is running")
        return False
    except requests.exceptions.Timeout:
        print("Error: Request timed out. Large corpus may take longer.")
        print("Consider increasing timeout")
        return False
    except requests.exceptions.HTTPError:
        print(f"Error: HTTP {response.status_code}")
        try:
            error_detail = response.json()
            print(f"Detail: {json.dumps(error_detail, indent=2)}")
        except json.JSONDecodeError:
            print(f"Detail: {response.text}")
        return False
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Index S3 corpus documents using the backend API")
    parser.add_argument(
        "--url",
        default="http://localhost:8000",
        help="Backend base URL (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--workspace",
        default="default",
        help="Workspace ID (default: default)",
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket name",
    )
    parser.add_argument(
        "--prefix",
        default="",
        help="S3 prefix/folder (default: root)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    success = index_s3_corpus(
        base_url=args.url,
        workspace_id=args.workspace,
        bucket_name=args.bucket,
        prefix=args.prefix,
        verbose=args.verbose,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
