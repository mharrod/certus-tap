from pydantic import BaseModel, Field


class UploadRequest(BaseModel):
    source_path: str = Field(..., description="Path to a file or directory that should be ingested.")
    target_folder: str = Field(..., description="Destination folder inside the raw bucket.")


class PreprocessRequest(BaseModel):
    source_key: str = Field(..., description="Object key in the raw bucket to promote to the golden bucket.")
    destination_prefix: str | None = Field(
        None, description="Optional prefix inside the golden bucket. Defaults to the same as the source key."
    )


class BatchPreprocessRequest(BaseModel):
    source_prefix: str = Field(
        ...,
        description="Prefix inside the raw bucket. All objects under this prefix will be promoted.",
        min_length=1,
    )
    destination_prefix: str | None = Field(
        None,
        description="Optional prefix inside the golden bucket. Defaults to the same as the source prefix.",
    )


class S3IngestRequest(BaseModel):
    bucket: str | None = Field(
        None,
        description="S3 bucket name. Defaults to DATALAKE_RAW_BUCKET.",
    )
    key: str = Field(
        ...,
        description="Object key to ingest.",
        min_length=1,
    )


class BatchS3IngestRequest(BaseModel):
    bucket: str | None = Field(
        None,
        description="S3 bucket name. Defaults to DATALAKE_RAW_BUCKET.",
    )
    prefix: str = Field(
        ...,
        description="Prefix to ingest. All objects under this prefix will be processed.",
        min_length=1,
    )
