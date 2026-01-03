from functools import lru_cache

import boto3

from certus_transform.core.config import settings


@lru_cache(maxsize=1)
def get_s3_client() -> boto3.client:  # type: ignore[name-defined]
    """Return a memoized S3 client pinned to the customer's LocalStack."""

    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        region_name=settings.aws_region,
    )
