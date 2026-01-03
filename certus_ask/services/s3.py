"""S3 client factory for AWS/LocalStack integration.

Provides cached S3 client configured from environment settings.
"""

from functools import lru_cache

import boto3
from botocore.client import BaseClient

from certus_ask.core.config import settings


@lru_cache(maxsize=1)
def get_s3_client() -> BaseClient:
    """Get or create cached S3 client.

    Returns a boto3 S3 client configured with settings from environment
    variables. The client is cached and reused across calls.

    Returns:
        Configured S3 client for accessing S3/LocalStack.

    Raises:
        ClientError: If connection to S3 endpoint fails during initialization.

    Example:
        >>> client = get_s3_client()
        >>> response = client.list_buckets()
    """
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )
