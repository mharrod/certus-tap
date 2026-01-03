from __future__ import annotations

from collections.abc import Sequence

import httpx

from certus_transform.core.config import settings


async def ingest_security_keys(workspace_id: str, keys: Sequence[str]) -> list[dict]:
    """Send golden keys to the SaaS security ingestion endpoint."""

    if not keys:
        return []

    headers = {}
    if settings.saas_api_key:
        headers["Authorization"] = f"Bearer {settings.saas_api_key}"

    async with httpx.AsyncClient(
        base_url=settings.saas_base_url,
        headers=headers,
        timeout=60.0,
        verify=settings.saas_verify_ssl,
    ) as client:
        results: list[dict] = []
        for key in keys:
            payload = {"bucket_name": settings.golden_bucket, "key": key}
            response = await client.post(
                f"/v1/{workspace_id}/index/security/s3",
                json=payload,
            )
            response.raise_for_status()
            results.append(response.json())
        return results
