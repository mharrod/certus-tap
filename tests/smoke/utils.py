from __future__ import annotations

from pathlib import Path

from botocore.client import BaseClient
from requests import Session


def upload_directory_to_s3(
    s3_client: BaseClient,
    bucket: str,
    prefix: str,
    directory: Path,
) -> list[str]:
    """
    Upload all files from `directory` to S3 under `prefix`.

    Returns the list of object keys created.
    """
    base = prefix.strip().rstrip("/")
    uploaded_keys: list[str] = []

    for file_path in directory.rglob("*"):
        if not file_path.is_file():
            continue
        relative = file_path.relative_to(directory).as_posix()
        key = f"{base}/{relative}".strip("/")
        s3_client.upload_file(str(file_path), bucket, key)
        uploaded_keys.append(key)

    return uploaded_keys


def post_file(
    session: Session,
    url: str,
    file_path: Path,
    timeout: int,
) -> dict:
    """Upload a file via multipart/form-data and return JSON response."""
    with file_path.open("rb") as handle:
        files = {"uploaded_file": (file_path.name, handle, "application/json")}
        response = session.post(url, files=files, timeout=timeout * 2)
    response.raise_for_status()
    return response.json()
