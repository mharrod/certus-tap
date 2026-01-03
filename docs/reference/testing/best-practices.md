# Testing Best Practices

Guidelines and patterns for writing high-quality tests in Certus-TAP.

## Test Design Principles

### 1. One Assertion Per Test (Logically Related)

Good:
```python
def test_document_creation(document_factory):
    """Test document creation sets all fields."""
    doc = document_factory.create(content="test")
    assert doc["content"] == "test"
    assert "metadata" in doc
    assert "embedding" in doc
```

Bad:
```python
def test_everything():
    doc = create_document()
    assert doc is not None

    user = create_user()
    assert user is not None

    result = search()
    assert result is not None
```

### 2. Descriptive Test Names

Good:
```python
def test_analyze_clean_document_returns_empty_list():
    pass

def test_anonymize_preserves_document_structure():
    pass

def test_upload_missing_file_raises_file_not_found():
    pass
```

Bad:
```python
def test_analyze():
    pass

def test_it_works():
    pass

def test_error():
    pass
```

### 3. Arrange-Act-Assert Pattern

```python
def test_document_indexing(mock_opensearch_client, document_factory):
    """Test indexing document."""
    # Arrange
    doc = document_factory.create(content="test")

    # Act
    mock_opensearch_client.index(index="test", body=doc)

    # Assert
    assert mock_opensearch_client.index.called
```

### 4. Test Isolation

Each test should:
- Be independent
- Not depend on other tests
- Not modify global state
- Not share fixtures (use function scope)

```python
# Good - isolated
def test_bucket_creation(mock_s3_client):
    """Each test creates fresh client."""
    mock_s3_client.create_bucket(Bucket="test1")
    assert mock_s3_client.create_bucket.called

def test_another_operation(mock_s3_client):
    """Independent of other tests."""
    # Fresh mock_s3_client
    pass

# Bad - shared state
shared_client = None

def test_first():
    global shared_client
    shared_client = mock_s3_client

def test_second():
    # Depends on test_first running first
    shared_client.create_bucket(...)
```

### 5. Meaningful Assertions

Good:
```python
def test_pii_detection(privacy_logger, mock_analysis_results):
    incident = privacy_logger.log_pii_detection(
        "doc-123",
        "test.pdf",
        mock_analysis_results
    )
    assert incident.pii_entity_count == 3  # Specific value
    assert incident.action == "ANONYMIZED"  # Specific action
```

Bad:
```python
def test_pii_detection(privacy_logger, mock_analysis_results):
    incident = privacy_logger.log_pii_detection(...)
    assert incident is not None  # Too vague
    assert len(mock_analysis_results) > 0  # Tests fixture, not code
```

## Fixture Best Practices

### Fixture Scope

Use appropriate scope:
```python
# Function scope - fresh for each test (default)
@pytest.fixture
def mock_s3_client():
    with mock_aws():
        yield boto3.client("s3")

# Class scope - shared within class
@pytest.fixture(scope="class")
def expensive_setup():
    yield setup()

# Module scope - shared across module
@pytest.fixture(scope="module")
def database():
    yield connect()

# Session scope - shared across all tests
@pytest.fixture(scope="session")
def app():
    yield create_app()
```

### Fixture Organization

```python
# Group related fixtures
@pytest.fixture
def document_fixtures(sample_text_document, sample_text_with_pii):
    """Group related document fixtures."""
    return {
        "clean": sample_text_document,
        "with_pii": sample_text_with_pii
    }

def test_documents(document_fixtures):
    clean = document_fixtures["clean"]
    with_pii = document_fixtures["with_pii"]
```

### Fixture Composition

```python
# Build complex fixtures from simpler ones
@pytest.fixture
def s3_with_data(s3_with_buckets, sample_text_document):
    """Compose fixtures - depends on s3_with_buckets."""
    s3_with_buckets.put_object(
        Bucket="raw-bucket",
        Key="test.txt",
        Body=sample_text_document.encode()
    )
    return s3_with_buckets

def test_with_s3_data(s3_with_data):
    """Uses composed fixture."""
    obj = s3_with_data.get_object(Bucket="raw-bucket", Key="test.txt")
    assert obj["Body"].read() is not None
```

## Mocking Best Practices

### Mock Where It's Used, Not Where It's Defined

Good:
```python
def test_ingestion(mocker):
    """Mock where the dependency is used."""
    mock_store = mocker.patch(
        "certus_ask.routers.ingestion.get_document_store"
    )
    # Now test ingestion router
```

Bad:
```python
def test_ingestion(mocker):
    """Mocking in wrong place."""
    mock_store = mocker.patch(
        "certus_ask.services.opensearch.OpenSearch"
    )
    # Router might not use this path
```

### Use Fixtures for Standard Mocks

Good:
```python
def test_service(mock_opensearch_client):  # Use fixture
    """Uses pre-configured mock from conftest."""
    result = my_service.search()

def test_another(mock_opensearch_client):
    """Same mock, different test."""
    result = my_service.index()
```

Bad:
```python
@patch("certus_ask.services.opensearch.OpenSearch")
def test_service(mock_os):  # Decorating each test
    pass

@patch("certus_ask.services.opensearch.OpenSearch")
def test_another(mock_os):  # Duplication
    pass
```

### Mock Return Values Explicitly

Good:
```python
def test_search(mock_opensearch_client):
    """Set explicit return value."""
    mock_opensearch_client.search.return_value = {
        "hits": {"total": {"value": 2}, "hits": [...]}
    }
    result = search()
    assert result["hits"]["total"]["value"] == 2
```

Bad:
```python
def test_search(mock_opensearch_client):
    """Relies on mock default."""
    result = search()
    # What does result contain? Unclear.
```

## Test Data Best Practices

### Use Factories for Dynamic Data

Good:
```python
def test_batch_processing(document_factory):
    """Use factory for varied data."""
    docs = document_factory.create_batch(count=10)
    for doc in docs:
        assert "content" in doc
```

Bad:
```python
def test_batch_processing():
    """Hardcoded test data."""
    docs = [
        {"content": "doc1"},
        {"content": "doc2"},
        # ... 8 more ...
    ]
```

### Use Fixtures for Common Data

Good:
```python
def test_with_pii(sample_text_with_pii, privacy_logger):
    """Use fixture for common data."""
    assert "John Smith" in sample_text_with_pii
```

Bad:
```python
def test_with_pii():
    """Duplicate data setup."""
    text = """...copy of PII document..."""
```

## Error Testing Best Practices

### Test Error Cases Explicitly

Good:
```python
def test_missing_file_error(mock_s3_client):
    """Test error handling."""
    from botocore.exceptions import ClientError

    mock_s3_client.get_object.side_effect = ClientError(
        {"Error": {"Code": "NoSuchKey"}},
        "GetObject"
    )

    with pytest.raises(ClientError):
        my_service.get_file()

def test_retry_on_timeout(mocker):
    """Test retry logic."""
    mock_func = mocker.MagicMock()
    mock_func.side_effect = [
        TimeoutError("failed"),
        TimeoutError("failed"),
        {"result": "success"}
    ]

    # Verify retry logic works
    result = retry_function(mock_func)
    assert result["result"] == "success"
    assert mock_func.call_count == 3
```

Bad:
```python
def test_success_only():
    """Only test happy path."""
    result = my_service.do_something()
    assert result is not None
    # No error testing
```

## Documentation Best Practices

### Write Clear Docstrings

Good:
```python
def test_anonymize_with_multiple_pii_types(presidio_anonymizer, mock_analysis_results):
    """
    Test anonymization with various PII types.

    Given multiple PII entities of different types,
    When anonymizing the text,
    Then all entities should be masked.
    """
    pass
```

Bad:
```python
def test_anonymize(presidio_anonymizer, mock_analysis_results):
    """Test anonymization."""  # Too vague
    pass
```

### Use Comments for Complex Logic

Good:
```python
def test_privacy_workflow(privacy_logger, analysis_result_factory):
    """Test privacy incident workflow."""
    # Create results with varied confidences
    high_conf = analysis_result_factory.create(confidence=0.95)
    low_conf = analysis_result_factory.create(confidence=0.70)
    results = [high_conf, low_conf]

    # Log and verify high confidence is tracked
    incident = privacy_logger.log_pii_detection(...)
    assert incident.has_high_confidence_pii is True
```

## Performance Best Practices

### Keep Tests Fast

Good:
```python
def test_search(mock_opensearch_client):
    """Fast - uses mock."""
    result = mock_opensearch_client.search(index="test", body={})
    assert result["hits"]["total"]["value"] == 0
```

Bad:
```python
@pytest.mark.slow
def test_search():
    """Slow - makes real call."""
    result = opensearch.search(index="test", body={})
    time.sleep(5)  # Unnecessary delay
```

### Mark Slow Tests

Good:
```python
@pytest.mark.slow
def test_large_batch_processing():
    """Process 10K documents."""
    for i in range(10000):
        process_document(i)

# Run with: pytest -m "not slow"
```

### Use Parametrization for Multiple Inputs

Good:
```python
@pytest.mark.parametrize("entity_type,confidence", [
    ("PERSON", 0.95),
    ("EMAIL", 0.98),
    ("PHONE", 0.87),
])
def test_entity_detection(analysis_result_factory, entity_type, confidence):
    """Test multiple entity types."""
    result = analysis_result_factory.create(entity_type, confidence)
    assert result.entity_type == entity_type
    assert result.score == confidence
```

Bad:
```python
def test_person_entity():
    pass

def test_email_entity():
    pass

def test_phone_entity():
    pass
# Repetitive
```

## Summary: Do's and Don'ts

### ✅ Do

- ✅ Use descriptive test names
- ✅ Test one thing per test
- ✅ Use fixtures for setup
- ✅ Mock external dependencies
- ✅ Test happy path AND errors
- ✅ Mark slow tests
- ✅ Keep tests independent
- ✅ Document complex tests
- ✅ Use parametrization for variations
- ✅ Keep tests fast

### ❌ Don't

- ❌ Test implementation details
- ❌ Depend on test order
- ❌ Use hardcoded paths
- ❌ Make real API calls
- ❌ Sleep in tests
- ❌ Create files on disk
- ❌ Test third-party libs
- ❌ Share state
- ❌ Write vague assertions
- ❌ Test everything in one test
