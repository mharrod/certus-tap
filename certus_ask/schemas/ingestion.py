from typing import Any

from pydantic import BaseModel, Field


class IndexFolderRequest(BaseModel):
    local_directory: str = Field(..., description="Absolute or relative path to the folder containing documents.")


class S3IndexRequest(BaseModel):
    bucket_name: str = Field(..., description="S3 bucket name to scan for documents.")
    prefix: str = Field("", description="Optional prefix to filter objects.")


class S3UploadRequest(BaseModel):
    local_directory: str = Field(..., description="Path to the local directory that should be uploaded.")
    bucket: str = Field(..., description="Destination S3 bucket name.")
    s3_prefix: str = Field("", description="Optional prefix for uploaded keys.")
    create_bucket: bool = Field(False, description="Create the bucket if it does not already exist.")


class GitRepositoryRequest(BaseModel):
    repo_url: str = Field(..., description="HTTPS URL to the Git repository.")
    branch: str | None = Field(None, description="Optional branch or tag to checkout.")
    include_globs: list[str] | None = Field(
        None,
        description="Glob patterns to include (default covers code and documentation files).",
    )
    exclude_globs: list[str] | None = Field(
        None,
        description="Glob patterns to exclude (default skips .git, caches, node_modules, etc.).",
    )
    max_file_size_kb: int = Field(
        256,
        ge=1,
        description="Maximum file size (KB) per file to ingest from the repository.",
    )


class WebIngestionRequest(BaseModel):
    urls: list[str] = Field(..., description="List of web page URLs to ingest.")
    render: bool = Field(
        False,
        description="Render JavaScript (requires headless browser via requests-html/pyppeteer).",
    )


class WebCrawlRequest(BaseModel):
    seed_urls: list[str] = Field(..., description="Seed URLs to start crawling from.")
    allowed_domains: list[str] | None = Field(
        None,
        description="Restrict crawling to these domains (defaults to domains extracted from seed URLs).",
    )
    allow_patterns: list[str] | None = Field(
        None,
        description="Regex patterns that URLs must match to be crawled.",
    )
    deny_patterns: list[str] | None = Field(
        None,
        description="Regex patterns that URLs must NOT match.",
    )
    max_pages: int = Field(100, ge=1, description="Maximum number of pages to crawl.")
    max_depth: int = Field(1, ge=0, description="Maximum crawl depth from each seed URL.")
    render: bool = Field(
        False,
        description="Enable Playwright for JavaScript-heavy sites (slower but more complete).",
    )


class SecurityIngestionRequest(BaseModel):
    """Request model for security scan file ingestion with optional JSONPath schema.

    Supports uploading security scan results (SARIF, SPDX, or custom JSON formats)
    with optional JSONPath-based schema for parsing custom tool formats.
    """

    format: str = Field(
        "auto",
        description="Expected format: 'auto' (auto-detect), 'sarif', 'spdx', or 'jsonpath' for custom schema-based parsing",
    )
    schema_dict: dict[str, Any] | None = Field(
        None,
        description="Optional JSONPath schema for parsing custom tool formats. Required if format='jsonpath'. "
        "Schema should contain: tool_name, version, format.findings_path, format.mapping",
    )
    tool_hint: str | None = Field(
        None,
        description="Optional tool name hint (e.g., 'bandit', 'trivy', 'opengrep'). "
        "Used for format detection if auto-detect fails or to force specific parser.",
    )
