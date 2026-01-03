# Adding a New Ingestion Service

This guide explains how to add a new ingestion service to the Certus Ask service layer architecture.

## Overview

The service layer in `certus_ask/services/ingestion/` contains reusable business logic for document ingestion. Routers are thin HTTP handlers that delegate to these services.

## Service Layer Architecture

```
certus_ask/
├── routers/
│   └── ingestion.py          # HTTP handlers (thin)
├── services/
│   └── ingestion/
│       ├── __init__.py        # Public exports
│       ├── file_processor.py  # File processing service
│       ├── security_processor.py  # Security scan processing
│       ├── neo4j_service.py   # Neo4j integration
│       ├── storage_service.py # File storage operations
│       └── utils.py           # Utility functions
└── tests/
    └── test_services/
        └── test_ingestion/    # Service layer tests
```

## Steps to Add a New Service

### 1. Create the Service Class

Create a new file in `certus_ask/services/ingestion/` following this template:

```python
"""Service for [describe purpose]."""

import structlog
from typing import Any

logger = structlog.get_logger(__name__)


class MyNewService:
    """Service for [describe what this service does].

    This service handles [specific responsibility].
    It coordinates [list key operations].

    Attributes:
        dependency1: Description of first dependency
        dependency2: Description of second dependency
    """

    def __init__(
        self,
        dependency1: SomeType,
        dependency2: AnotherType | None = None,
    ):
        """Initialize the service with its dependencies.

        Args:
            dependency1: Description and purpose
            dependency2: Optional description
        """
        self.dependency1 = dependency1
        self.dependency2 = dependency2

    async def process(
        self,
        input_data: dict[str, Any],
        **kwargs,
    ) -> dict[str, Any]:
        """Main orchestration method for this service.

        Args:
            input_data: Input data to process
            **kwargs: Additional parameters

        Returns:
            Dictionary with processing results:
            - result_key1: Description
            - result_key2: Description

        Raises:
            CustomException: When specific error occurs
        """
        logger.info(
            "process.start",
            operation="my_operation",
            **kwargs
        )

        try:
            # Business logic here
            result = await self._do_something(input_data)

            logger.info(
                "process.complete",
                operation="my_operation",
                result_count=len(result),
            )

            return result

        except Exception as exc:
            logger.error(
                "process.failed",
                operation="my_operation",
                error=str(exc),
            )
            raise

    async def _do_something(self, data: dict) -> dict:
        """Private helper method.

        Helper methods should be private (prefixed with _) and focused
        on a single responsibility.
        """
        # Implementation
        pass
```

### 2. Export from `__init__.py`

Add your service to `certus_ask/services/ingestion/__init__.py`:

```python
from certus_ask.services.ingestion.my_new_service import MyNewService

__all__ = [
    # ... existing exports
    "MyNewService",
]
```

### 3. Update Router to Use Service

Modify the router in `certus_ask/routers/ingestion.py` to use your service:

```python
@router.post("/my-endpoint")
async def my_endpoint(
    workspace_id: str,
    request_data: MyRequest,
) -> MyResponse:
    """Endpoint documentation.

    Args:
        workspace_id: Workspace identifier
        request_data: Request payload

    Returns:
        Response with processing results
    """
    from certus_ask.services.ingestion import MyNewService

    # Initialize dependencies
    dependency1 = get_dependency1()
    dependency2 = get_dependency2() if condition else None

    # Initialize service
    service = MyNewService(
        dependency1=dependency1,
        dependency2=dependency2,
    )

    # Delegate to service
    result = await service.process(
        input_data=request_data.model_dump(),
        workspace_id=workspace_id,
    )

    # Format HTTP response
    return MyResponse(
        request_id=get_request_id(),
        message="Processing complete",
        **result,
    )
```

### 4. Write Tests

Create comprehensive tests in `tests/test_services/test_ingestion/test_my_new_service.py`:

```python
"""Tests for MyNewService."""

import pytest
from certus_ask.services.ingestion import MyNewService


class TestMyNewService:
    """Test suite for MyNewService."""

    @pytest.fixture
    def service(self):
        """Create service instance for testing."""
        dependency1 = MockDependency1()
        return MyNewService(dependency1=dependency1)

    async def test_process_success(self, service):
        """Test successful processing."""
        input_data = {"key": "value"}

        result = await service.process(input_data)

        assert result["result_key1"] is not None
        assert result["result_key2"] == expected_value

    async def test_process_handles_error(self, service):
        """Test error handling."""
        invalid_input = {}

        with pytest.raises(CustomException) as exc_info:
            await service.process(invalid_input)

        assert "expected error message" in str(exc_info.value)
```

## Best Practices

### Service Design

1. **Single Responsibility**: Each service should have one clear purpose
2. **Dependency Injection**: Accept dependencies via `__init__`, not globals
3. **Async First**: Use `async def` for I/O operations
4. **Type Hints**: Fully type all method signatures
5. **Logging**: Use structlog with structured fields

### Orchestration Pattern

Services should follow this pattern:

```python
async def process(...) -> dict[str, Any]:
    """Main entry point - orchestrates the workflow."""
    # 1. Validate inputs
    self._validate_input(data)

    # 2. Coordinate steps
    step1_result = await self._step1(data)
    step2_result = await self._step2(step1_result)

    # 3. Return structured result
    return {
        "key1": step1_result,
        "key2": step2_result,
    }
```

### Error Handling

- Raise specific exceptions from `certus_ask.core.exceptions`
- Log errors with context before raising
- Let exceptions propagate to router for HTTP error handling

```python
try:
    result = await risky_operation()
except ValueError as exc:
    logger.error(
        "operation.failed",
        error=str(exc),
        context=additional_context,
    )
    raise ValidationError(
        message="Invalid input",
        error_code="invalid_format",
        details={"field": "value"},
    ) from exc
```

### Testing Strategy

1. **Unit Tests**: Test service logic in isolation with mocks
2. **Integration Tests**: Test service with real dependencies
3. **Router Tests**: Test HTTP layer separately

See [Testing Service Layer Code](testing-service-layer.md) for details.

## Example: SecurityProcessor

The `SecurityProcessor` is a good reference implementation:

- **Location**: `certus_ask/services/ingestion/security_processor.py`
- **Purpose**: Process security scan files (SARIF, SPDX)
- **Pattern**: Master `process()` method orchestrates workflow
- **Dependencies**: Injected via `__init__` (trust_client, neo4j_service)

Key features:
- Format detection
- Trust verification (premium tier)
- Neo4j loading
- Document creation
- Embedding generation

## Common Pitfalls

1. **Don't put business logic in routers** - Routers should only:
   - Validate HTTP request
   - Call service
   - Format HTTP response

2. **Don't use global state** - Pass dependencies explicitly

3. **Don't mix concerns** - Keep services focused on one domain

4. **Don't skip tests** - Services must have comprehensive test coverage

## Related Guides

- [Testing Service Layer Code](testing-service-layer.md)
- [Dependency Injection Patterns](dependency-injection.md)
- [Architecture Documentation](../../framework/architecture/certus-ask/)

## Getting Help

- Review existing services in `certus_ask/services/ingestion/`
- Check test examples in `tests/test_services/test_ingestion/`
- Consult the team for architectural questions
