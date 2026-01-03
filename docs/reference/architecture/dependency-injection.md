# Dependency Injection Patterns

This guide explains dependency injection patterns used in the Certus Ask service layer.

## Overview

Dependency injection (DI) is a design pattern where objects receive their dependencies from external sources rather than creating them internally. This makes code more testable, maintainable, and flexible.

## Why Dependency Injection?

### Without DI (Problematic)

```python
class BadService:
    """Service with hard-coded dependencies - difficult to test."""

    def __init__(self):
        # Hard-coded dependencies
        self.s3_client = boto3.client('s3')
        self.settings = Settings()  # Global import
        self.db = connect_to_database()

    async def process(self, data):
        # Can't easily test this without real S3, DB, etc.
        file = self.s3_client.get_object(...)
        self.db.save(file)
```

**Problems:**
- Can't test without real S3 and database
- Can't reuse with different configurations
- Hard to change implementations
- Violates Single Responsibility Principle

### With DI (Better)

```python
class GoodService:
    """Service with injected dependencies - easy to test."""

    def __init__(
        self,
        s3_client,
        document_store,
        settings: Settings | None = None,
    ):
        # Dependencies injected from outside
        self.s3_client = s3_client
        self.document_store = document_store
        self.settings = settings or Settings()

    async def process(self, data):
        # Same logic, but testable with mocks
        file = await self.s3_client.get_object(...)
        await self.document_store.save(file)
```

**Benefits:**
- Easy to test with mocks
- Flexible and reusable
- Clear dependencies
- Follows SOLID principles

## Constructor Injection Pattern

The primary DI pattern in Certus Ask is **constructor injection**.

### Basic Pattern

```python
from typing import Protocol


class DataStore(Protocol):
    """Protocol defining data store interface."""

    async def save(self, data: dict) -> str:
        ...

    async def load(self, id: str) -> dict:
        ...


class MyService:
    """Service that depends on a data store."""

    def __init__(
        self,
        data_store: DataStore,
        optional_dep: SomeType | None = None,
    ):
        """Initialize with dependencies.

        Args:
            data_store: Required dependency for data persistence
            optional_dep: Optional dependency with default None
        """
        self.data_store = data_store
        self.optional_dep = optional_dep
```

### Required vs Optional Dependencies

```python
class SecurityProcessor:
    """Example from actual codebase."""

    def __init__(
        self,
        # Optional dependencies (None when feature disabled)
        trust_client: TrustClient | None = None,
        neo4j_service: Neo4jService | None = None,
    ):
        """Initialize processor with optional services.

        Args:
            trust_client: Optional - only for premium tier
            neo4j_service: Optional - only when Neo4j enabled
        """
        self.trust_client = trust_client
        self.neo4j_service = neo4j_service

    async def process(self, file_bytes: bytes, tier: str, **kwargs):
        """Process file with conditional features."""
        # Use dependency if available
        if tier == "premium" and self.trust_client:
            await self.trust_client.verify(...)

        if self.neo4j_service:
            self.neo4j_service.load_data(...)
```

## Dependency Patterns in Routers

Routers create and inject dependencies into services.

### Pattern 1: Simple Dependency Creation

```python
@router.post("/v1/{workspace_id}/index/")
async def index_document(
    workspace_id: str,
    uploaded_file: UploadFile,
) -> DocumentIngestionResponse:
    """Router with simple dependency injection."""
    from certus_ask.services.ingestion import FileProcessor, StorageService

    # Create dependencies
    document_store = get_document_store_for_workspace(workspace_id)
    storage_service = StorageService()

    # Inject into service
    processor = FileProcessor(
        document_store=document_store,
        storage_service=storage_service,
    )

    # Use service
    result = await processor.process_file(...)

    return DocumentIngestionResponse(**result)
```

### Pattern 2: Conditional Dependencies

```python
@router.post("/v1/{workspace_id}/index/security")
async def index_security_file(
    workspace_id: str,
    tier: str = "free",
) -> SarifIngestionResponse:
    """Router with conditional dependency injection."""
    from certus_ask.services.ingestion import SecurityProcessor
    from certus_ask.core.config import Settings

    settings = Settings()

    # Create dependencies conditionally
    neo4j_service = None
    if settings.neo4j_enabled:
        from certus_ask.services.ingestion import Neo4jService
        neo4j_service = Neo4jService(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )

    trust_client = None
    if tier == "premium":
        trust_client = get_trust_client()

    # Inject dependencies
    processor = SecurityProcessor(
        trust_client=trust_client,
        neo4j_service=neo4j_service,
    )

    result = await processor.process(...)
    return SarifIngestionResponse(**result)
```

### Pattern 3: Factory Functions

For complex dependency creation, use factory functions:

```python
def create_security_processor(
    workspace_id: str,
    tier: str,
) -> SecurityProcessor:
    """Factory function for SecurityProcessor.

    Args:
        workspace_id: Workspace identifier
        tier: Subscription tier (free/premium)

    Returns:
        Configured SecurityProcessor instance
    """
    settings = Settings()

    # Create Neo4j service if enabled
    neo4j_service = None
    if settings.neo4j_enabled:
        neo4j_service = Neo4jService(
            uri=settings.neo4j_uri,
            user=settings.neo4j_user,
            password=settings.neo4j_password,
        )

    # Create trust client for premium tier
    trust_client = None
    if tier == "premium":
        trust_client = get_trust_client()

    return SecurityProcessor(
        trust_client=trust_client,
        neo4j_service=neo4j_service,
    )


@router.post("/v1/{workspace_id}/index/security")
async def index_security_file(
    workspace_id: str,
    tier: str = "free",
):
    """Router using factory function."""
    processor = create_security_processor(workspace_id, tier)
    result = await processor.process(...)
    return SarifIngestionResponse(**result)
```

## Testing with Dependency Injection

DI makes testing straightforward by allowing mock injection.

### Unit Test Example

```python
import pytest
from unittest.mock import Mock, AsyncMock


class TestSecurityProcessor:
    """Tests using dependency injection."""

    @pytest.fixture
    def mock_trust_client(self):
        """Mock trust client."""
        client = AsyncMock()
        client.verify_signatures.return_value = {
            "verified": True,
            "trust_level": "high",
        }
        return client

    @pytest.fixture
    def mock_neo4j_service(self):
        """Mock Neo4j service."""
        service = Mock()
        service.load_sarif.return_value = "scan-id-123"
        return service

    @pytest.fixture
    def processor(self, mock_trust_client, mock_neo4j_service):
        """Create processor with mocked dependencies."""
        return SecurityProcessor(
            trust_client=mock_trust_client,
            neo4j_service=mock_neo4j_service,
        )

    async def test_premium_processing(self, processor, mock_trust_client):
        """Test premium tier processing with trust verification."""
        result = await processor.process(
            file_bytes=b"sarif content",
            tier="premium",
            signatures={"sig": "data"},
        )

        # Verify trust client was called
        mock_trust_client.verify_signatures.assert_awaited_once()
        assert result["verification_proof"] is not None

    async def test_without_neo4j(self):
        """Test processing without Neo4j service."""
        # Inject None for neo4j_service
        processor = SecurityProcessor(
            trust_client=None,
            neo4j_service=None,
        )

        result = await processor.process(
            file_bytes=b"content",
            tier="free",
        )

        # Should work without Neo4j
        assert "neo4j_scan_id" not in result or result["neo4j_scan_id"] is None
```

## Service Composition

Services can depend on other services.

### Pattern: Service Dependencies

```python
class FileProcessor:
    """Service that depends on another service."""

    def __init__(
        self,
        document_store: DocumentStore,
        storage_service: StorageService,
    ):
        self.document_store = document_store
        self.storage_service = storage_service

    async def process_file(
        self,
        file_content: bytes,
        filename: str,
        **kwargs
    ) -> dict:
        """Process file using injected services."""
        # Use storage service
        file_path = Path("uploads") / filename
        self.storage_service.save_file_locally(file_content, file_path)

        # Use document store
        # ... processing logic

        return {"status": "success"}
```

### Creating Service Chains

```python
# In router
document_store = get_document_store_for_workspace(workspace_id)
storage_service = StorageService()

# Create service with dependencies
file_processor = FileProcessor(
    document_store=document_store,
    storage_service=storage_service,
)

# Use the composed service
result = await file_processor.process_file(...)
```

## Common Dependency Types

### 1. Infrastructure Clients

```python
class MyService:
    def __init__(
        self,
        s3_client,  # boto3 client
        document_store: DocumentStore,  # OpenSearch/database
    ):
        self.s3_client = s3_client
        self.document_store = document_store
```

### 2. Configuration

```python
from certus_ask.core.config import Settings


class MyService:
    def __init__(
        self,
        settings: Settings | None = None,
    ):
        # Allow injection or use default
        self.settings = settings or Settings()
```

### 3. Other Services

```python
class HighLevelService:
    def __init__(
        self,
        file_processor: FileProcessor,
        security_processor: SecurityProcessor,
    ):
        self.file_processor = file_processor
        self.security_processor = security_processor
```

### 4. Optional Features

```python
class MyService:
    def __init__(
        self,
        # Required
        document_store: DocumentStore,
        # Optional features
        cache: Cache | None = None,
        metrics_client: MetricsClient | None = None,
    ):
        self.document_store = document_store
        self.cache = cache
        self.metrics_client = metrics_client

    async def get_data(self, key: str):
        # Use cache if available
        if self.cache:
            cached = self.cache.get(key)
            if cached:
                return cached

        # Fetch from store
        data = await self.document_store.load(key)

        # Cache if available
        if self.cache:
            self.cache.set(key, data)

        return data
```

## Anti-Patterns to Avoid

### ❌ Don't: Import and Create Inside Methods

```python
class BadService:
    async def process(self, data):
        # DON'T create dependencies inside methods
        from certus_ask.core.config import Settings
        settings = Settings()

        import boto3
        s3_client = boto3.client('s3')

        # This makes testing difficult
```

### ✅ Do: Inject Dependencies

```python
class GoodService:
    def __init__(self, s3_client, settings: Settings):
        # DO inject dependencies in constructor
        self.s3_client = s3_client
        self.settings = settings

    async def process(self, data):
        # Use injected dependencies
        await self.s3_client.get_object(...)
```

### ❌ Don't: Use Global State

```python
# DON'T use module-level globals
GLOBAL_CLIENT = boto3.client('s3')


class BadService:
    async def process(self, data):
        # Using global state
        GLOBAL_CLIENT.get_object(...)
```

### ✅ Do: Pass Dependencies Explicitly

```python
class GoodService:
    def __init__(self, s3_client):
        # DO pass dependencies explicitly
        self.s3_client = s3_client
```

### ❌ Don't: Mix Construction and Business Logic

```python
class BadService:
    async def process(self, data):
        # DON'T mix dependency creation with business logic
        if some_condition:
            client = create_client_a()
        else:
            client = create_client_b()

        # Business logic mixed with construction
        result = await client.process(data)
```

### ✅ Do: Inject Pre-Configured Dependencies

```python
class GoodService:
    def __init__(self, client):
        # DO inject pre-configured dependency
        self.client = client

    async def process(self, data):
        # Pure business logic
        result = await self.client.process(data)
```

## Best Practices

1. **Inject All Dependencies**: Don't create dependencies inside services
2. **Use Protocols**: Define interfaces for dependencies when appropriate
3. **Optional Dependencies**: Use `Type | None = None` for optional features
4. **Constructor Only**: Initialize dependencies in `__init__`, not elsewhere
5. **Keep It Simple**: Don't over-engineer - inject what you need
6. **Document Dependencies**: Clearly document what each dependency does

## Example: Complete Service with DI

```python
"""Complete example showing dependency injection."""

from typing import Protocol
import structlog

logger = structlog.get_logger(__name__)


# Define protocols for dependencies
class DataStore(Protocol):
    async def save(self, key: str, data: dict) -> None: ...
    async def load(self, key: str) -> dict: ...


class Cache(Protocol):
    def get(self, key: str) -> dict | None: ...
    def set(self, key: str, data: dict, ttl: int = 300) -> None: ...


# Service with dependency injection
class DataService:
    """Service demonstrating dependency injection patterns.

    Attributes:
        data_store: Required data persistence layer
        cache: Optional caching layer
        enable_metrics: Whether to emit metrics
    """

    def __init__(
        self,
        data_store: DataStore,
        cache: Cache | None = None,
        enable_metrics: bool = False,
    ):
        """Initialize service with dependencies.

        Args:
            data_store: Data persistence layer (required)
            cache: Optional caching layer for performance
            enable_metrics: Whether to emit performance metrics
        """
        self.data_store = data_store
        self.cache = cache
        self.enable_metrics = enable_metrics

    async def get_data(self, key: str) -> dict:
        """Retrieve data with optional caching.

        Args:
            key: Data identifier

        Returns:
            Retrieved data
        """
        # Try cache if available
        if self.cache:
            cached = self.cache.get(key)
            if cached:
                logger.info("cache.hit", key=key)
                return cached

        # Load from data store
        data = await self.data_store.load(key)

        # Update cache if available
        if self.cache:
            self.cache.set(key, data)

        # Emit metrics if enabled
        if self.enable_metrics:
            logger.info("data.loaded", key=key, size=len(data))

        return data
```

## Related Guides

- [Adding a New Ingestion Service](adding-ingestion-service.md)
- [Testing Service Layer Code](testing-service-layer.md)

## Further Reading

- [Dependency Injection Principles](https://en.wikipedia.org/wiki/Dependency_injection)
- [SOLID Principles](https://en.wikipedia.org/wiki/SOLID)
- [Python Protocols (PEP 544)](https://peps.python.org/pep-0544/)
