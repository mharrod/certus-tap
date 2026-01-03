#!/usr/bin/env python3
"""Upload all documents from samples/corpus_data to the Certus backend.

This script ingests all documents in the corpus_data folder (and subfolders)
into the specified workspace using the batch folder upload endpoint.
"""

import argparse
import json
import sys
from pathlib import Path

import requests


def upload_corpus(
    base_url: str,
    workspace_id: str,
    corpus_path: str,
    verbose: bool = False,
) -> bool:
    """Upload all documents from corpus_data folder.

    Args:
        base_url: Base URL of the backend (e.g., http://localhost:8000)
        workspace_id: Workspace ID to upload documents to
        corpus_path: Path to corpus_data folder
        verbose: Print detailed output

    Returns:
        True if successful, False otherwise
    """
    corpus_path = Path(corpus_path).expanduser().resolve()

    if not corpus_path.is_dir():
        print(f"Error: Corpus path is not a valid directory: {corpus_path}")
        return False

    if verbose:
        print(f"Uploading documents from: {corpus_path}")
        print(f"Workspace ID: {workspace_id}")
        print(f"Backend URL: {base_url}")

    endpoint = f"{base_url}/v1/{workspace_id}/index_folder/"

    payload = {"local_directory": str(corpus_path)}

    try:
        if verbose:
            print(f"\nSending request to: {endpoint}")
            print(f"Payload: {json.dumps(payload, indent=2)}")

        response = requests.post(
            endpoint,
            json=payload,
            timeout=300,  # 5 minute timeout for large batch uploads
        )

        if verbose:
            print(f"Status Code: {response.status_code}")

        response.raise_for_status()

        result = response.json()

        # Print results
        print("\n" + "=" * 60)
        print("UPLOAD SUCCESSFUL")
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
                print(f"  - {item}")

        return True

    except requests.exceptions.ConnectionError:
        print(f"Error: Could not connect to backend at {base_url}")
        print("Make sure the backend is running: `python -m certus_ask.main`")
        return False
    except requests.exceptions.Timeout:
        print("Error: Request timed out. Large corpus may take longer.")
        print("Consider increasing timeout or uploading in smaller batches.")
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
    parser = argparse.ArgumentParser(description="Upload corpus documents to Certus backend")
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
        "--corpus",
        default="samples/corpus_data",
        help="Path to corpus_data folder (default: samples/corpus_data)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    success = upload_corpus(
        base_url=args.url,
        workspace_id=args.workspace,
        corpus_path=args.corpus,
        verbose=args.verbose,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
