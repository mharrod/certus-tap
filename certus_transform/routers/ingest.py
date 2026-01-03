from fastapi import APIRouter
from pydantic import BaseModel, Field, validator

from certus_transform.core.config import settings
from certus_transform.services.saas import ingest_security_keys

router = APIRouter(prefix="/v1/ingest", tags=["ingestion"])


class SecurityIngestRequest(BaseModel):
    workspace_id: str | None = Field(
        default=None,
        description="Workspace in the SaaS backend. Defaults to DEFAULT_WORKSPACE_ID.",
    )
    keys: list[str] = Field(
        ..., description="Golden bucket keys (e.g., scans/bandit.sarif) to ingest using the security parser."
    )

    @validator("keys")
    def _require_keys(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("keys cannot be empty")
        return value


class SecurityIngestResponse(BaseModel):
    workspace_id: str
    responses: list[dict]


@router.post(
    "/security",
    response_model=SecurityIngestResponse,
    summary="Send golden keys to the SaaS security ingestion endpoint",
)
async def ingest_security(request: SecurityIngestRequest) -> SecurityIngestResponse:
    workspace = request.workspace_id or settings.default_workspace_id
    responses = await ingest_security_keys(workspace, request.keys)
    return SecurityIngestResponse(workspace_id=workspace, responses=responses)
