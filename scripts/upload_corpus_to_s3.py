#!/usr/bin/env python3
"""Upload corpus_data to S3 bucket.

This script uploads all documents from the local corpus_data folder to S3,
preserving the directory structure.
"""

import argparse
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def upload_corpus_to_s3(
    corpus_path: str,
    bucket: str,
    s3_prefix: str = "corpus",
    aws_access_key: str | None = None,
    aws_secret_key: str | None = None,
    s3_endpoint_url: str | None = None,
    aws_region: str = "us-east-1",
    verbose: bool = False,
) -> bool:
    """Upload corpus documents to S3.

    Args:
        corpus_path: Path to local corpus_data folder
        bucket: S3 bucket name
        s3_prefix: S3 prefix/folder (default: corpus)
        aws_access_key: AWS access key (uses env var if not provided)
        aws_secret_key: AWS secret key (uses env var if not provided)
        s3_endpoint_url: Custom S3 endpoint URL (for MinIO, etc.)
        aws_region: AWS region
        verbose: Print detailed output

    Returns:
        True if successful, False otherwise
    """
    corpus_path = Path(corpus_path).expanduser().resolve()

    if not corpus_path.is_dir():
        print(f"Error: Corpus path is not a valid directory: {corpus_path}")
        return False

    if verbose:
        print(f"Local corpus path: {corpus_path}")
        print(f"S3 bucket: {bucket}")
        print(f"S3 prefix: {s3_prefix}")
        if s3_endpoint_url:
            print(f"S3 endpoint: {s3_endpoint_url}")
        print(f"AWS region: {aws_region}")

    try:
        # Create S3 client
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            endpoint_url=s3_endpoint_url,
            region_name=aws_region,
        )

        # Check if bucket exists
        try:
            s3_client.head_bucket(Bucket=bucket)
            if verbose:
                print(f"✓ Bucket '{bucket}' exists")
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                print(f"Error: Bucket '{bucket}' does not exist")
                return False
            raise

        # Upload files
        uploaded_count = 0
        failed_count = 0
        total_size = 0

        print(f"\nUploading files from {corpus_path}...")

        for file_path in corpus_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Calculate relative path for S3 key
            relative_path = file_path.relative_to(corpus_path)
            s3_key = f"{s3_prefix}/{relative_path}".replace("\\", "/")

            try:
                file_size = file_path.stat().st_size
                if verbose:
                    print(f"  Uploading: {relative_path} ({file_size} bytes)")

                s3_client.upload_file(str(file_path), bucket, s3_key)
                uploaded_count += 1
                total_size += file_size

            except Exception as e:
                print(f"  Error uploading {relative_path}: {e}")
                failed_count += 1
                continue

        # Print summary
        print("\n" + "=" * 60)
        print("UPLOAD COMPLETE")
        print("=" * 60)
        print(f"Uploaded: {uploaded_count} files")
        if failed_count:
            print(f"Failed: {failed_count} files")
        print(f"Total size: {total_size / (1024 * 1024):.2f} MB")
        print(f"\nS3 Location: s3://{bucket}/{s3_prefix}/")

        return failed_count == 0

    except NoCredentialsError:
        print("Error: AWS credentials not found")
        print("Set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables")
        return False
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Upload corpus documents to S3")
    parser.add_argument(
        "--corpus",
        default="samples/corpus_data",
        help="Path to corpus_data folder (default: samples/corpus_data)",
    )
    parser.add_argument(
        "--bucket",
        required=True,
        help="S3 bucket name",
    )
    parser.add_argument(
        "--prefix",
        default="corpus",
        help="S3 prefix/folder (default: corpus)",
    )
    parser.add_argument(
        "--access-key",
        help="AWS access key (uses AWS_ACCESS_KEY_ID env var if not provided)",
    )
    parser.add_argument(
        "--secret-key",
        help="AWS secret key (uses AWS_SECRET_ACCESS_KEY env var if not provided)",
    )
    parser.add_argument(
        "--endpoint-url",
        help="Custom S3 endpoint URL (for MinIO, etc.)",
    )
    parser.add_argument(
        "--region",
        default="us-east-1",
        help="AWS region (default: us-east-1)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print verbose output",
    )

    args = parser.parse_args()

    success = upload_corpus_to_s3(
        corpus_path=args.corpus,
        bucket=args.bucket,
        s3_prefix=args.prefix,
        aws_access_key=args.access_key,
        aws_secret_key=args.secret_key,
        s3_endpoint_url=args.endpoint_url,
        aws_region=args.region,
        verbose=args.verbose,
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
