# Testing Fixtures Guide

Complete reference for all 26+ pytest fixtures available in Certus-TAP.

## Quick Reference

### Document Fixtures

```python
def test_with_documents(
    sample_text_document,           # General text
    sample_text_with_pii,           # Contains PII
    sample_clean_document,          # No PII
    sample_markdown_document,       # Markdown format
    sample_pdf_document             # PDF binary
):
    pass
```

### AWS/S3 Fixtures

```python
def test_with_s3(
    mock_s3_client,                 # Basic mocked client
    s3_with_buckets,                # Pre-created buckets
    s3_with_documents,              # Pre-loaded files
    override_s3_settings            # ENV setup
):
    pass
```

### OpenSearch Fixtures

```python
def test_with_opensearch(
    mock_opensearch_client,         # Mocked client
    opensearch_test_index           # Test index
):
    pass
```

### Service Fixtures

```python
def test_with_services(
    presidio_analyzer,              # Analyzer instance
    presidio_anonymizer,            # Anonymizer instance
    mock_analysis_results           # Mock results
):
    pass
```

### FastAPI Fixtures

```python
def test_with_fastapi(
    test_app,                       # FastAPI app
    test_client,                    # Sync client
    async_client                    # Async client
):
    pass
```

## Detailed Fixture Reference

### Document Fixtures

#### sample_text_document
- **Purpose**: General text document
- **Returns**: `str`
- **Use**: General processing tests

#### sample_text_with_pii
- **Purpose**: Document containing PII
- **Returns**: `str` with names, emails, phones, SSN, credit cards
- **Use**: Privacy and anonymization tests

#### sample_clean_document
- **Purpose**: Document with NO sensitive information
- **Returns**: `str` (technical content)
- **Use**: Verify clean documents pass through

#### sample_markdown_document
- **Purpose**: Markdown-formatted document
- **Returns**: `str` with markdown syntax
- **Use**: Format-specific tests

#### sample_pdf_document
- **Purpose**: PDF binary content
- **Returns**: `bytes`
- **Use**: PDF upload and binary handling

### AWS/S3 Fixtures

#### mock_s3_client
- **Purpose**: Mocked S3 client
- **Tool**: moto
- **Scope**: function
- **Use**: All S3 operation tests

#### s3_with_buckets
- **Purpose**: Pre-created bucket structure
- **Includes**: raw-bucket, golden-bucket, folder structure
- **Scope**: function
- **Use**: Tests needing buckets

#### s3_with_documents
- **Purpose**: S3 with sample documents
- **Includes**: Pre-loaded sample.txt, sample.md
- **Scope**: function
- **Use**: Tests needing existing files

#### override_s3_settings
- **Purpose**: Override S3 environment variables
- **Sets**: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION
- **Scope**: function
- **Use**: Ensure consistent S3 config

### OpenSearch Fixtures

#### mock_opensearch_client
- **Purpose**: Mocked OpenSearch client
- **Tool**: unittest.mock
- **Scope**: function
- **Pre-configured**: index, get, search, count, delete

#### opensearch_test_index
- **Purpose**: Test index with client
- **Returns**: Dict with client and index_name
- **Scope**: function

### Service Fixtures

#### presidio_analyzer
- **Purpose**: Presidio analyzer instance
- **Scope**: function
- **Fallback**: MagicMock if initialization fails

#### presidio_anonymizer
- **Purpose**: Presidio anonymizer instance
- **Scope**: function
- **Fallback**: MagicMock if initialization fails

#### mock_analysis_results
- **Purpose**: Mock analysis results
- **Includes**: 3 results (PERSON, EMAIL, PHONE_NUMBER)
- **Scope**: function

### FastAPI Fixtures

#### test_app
- **Purpose**: FastAPI test application
- **Configuration**: Mocked OpenSearch, S3, overridden settings
- **Scope**: function

#### test_client
- **Purpose**: Synchronous test client
- **Type**: `TestClient`
- **Scope**: function
- **Use**: Endpoint testing

#### async_client
- **Purpose**: Asynchronous test client
- **Type**: `AsyncClient`
- **Scope**: function
- **Use**: Async endpoint testing

### Settings Fixtures

#### override_app_settings
- **Purpose**: Override all app settings
- **Scope**: function
- **Use**: Ensure consistent test environment

#### test_settings
- **Purpose**: Settings object with test defaults
- **Type**: Settings instance
- **Scope**: function

#### override_settings_values
- **Purpose**: Override specific settings
- **Type**: Callable
- **Scope**: function
- **Use**: Per-test overrides

### Logging Fixtures

#### capture_logs
- **Purpose**: Capture structlog output
- **Type**: LogCapture handler
- **Scope**: function
- **Use**: Verify logging

#### mock_opensearch_logging
- **Purpose**: Mock OpenSearch for logging
- **Pre-configured**: index() operation
- **Scope**: function

### Privacy Fixtures

#### privacy_logger
- **Purpose**: Privacy logger (lenient mode)
- **Mode**: strict_mode=False (anonymize)
- **Scope**: function

#### privacy_logger_strict
- **Purpose**: Privacy logger (strict mode)
- **Mode**: strict_mode=True (reject)
- **Scope**: function

### Factory Fixtures

#### document_factory
- **Type**: DocumentFactory
- **Methods**: create(), create_batch()
- **Scope**: function
- **Use**: Dynamic document generation

#### analysis_result_factory
- **Type**: AnalysisResultFactory
- **Methods**: create(), create_batch()
- **Scope**: function
- **Use**: Dynamic analysis result generation

## Common Patterns

### Service Testing
```python
def test_service(mock_opensearch_client, document_factory):
    doc = document_factory.create()
    mock_opensearch_client.index(index="test", body=doc)
    assert mock_opensearch_client.index.called
```

### Endpoint Testing
```python
def test_endpoint(test_client, sample_pdf_document):
    response = test_client.post(
        "/v1/index/",
        files={"file": sample_pdf_document}
    )
    assert response.status_code == 200
```

### Privacy Testing
```python
def test_privacy(privacy_logger, analysis_result_factory):
    results = analysis_result_factory.create_batch(3)
    incident = privacy_logger.log_pii_detection(
        "doc-123", "test.pdf", results
    )
    assert incident.pii_entity_count == 3
```
