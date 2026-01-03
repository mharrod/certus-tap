from fastapi import APIRouter, File, HTTPException, UploadFile

from certus_transform.core.config import settings
from certus_transform.services import get_s3_client

router = APIRouter(prefix="/v1/uploads", tags=["uploads"])


@router.post("/raw", summary="Upload a document into the raw/active prefix")
async def upload_raw_document(
    file: UploadFile = File(...),
    prefix: str = "active/",
) -> dict[str, str]:
    """Persist an uploaded file into the raw bucket."""

    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename")

    key = f"{prefix.rstrip('/')}/{file.filename}".lstrip("/")
    s3_client = get_s3_client()

    s3_client.upload_fileobj(file.file, settings.raw_bucket, key)

    return {"bucket": settings.raw_bucket, "key": key}
