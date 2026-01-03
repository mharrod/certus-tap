"""Security scan parser framework.

Provides pluggable parsers for security tools. All parsers convert tool-specific
formats to UnifiedSecurityScan for consistent indexing.

Supported parsers:
- SARIF (Security Analysis Results Interchange Format)
- Bandit (Python security scanner)
- OpenGrep (semantic code scanning)
- Trivy (container/artifact/dependency scanner)
- JSONPath (generic custom tool mapping)
"""

from certus_ask.pipelines.security_scan_parsers.jsonpath_parser import JSONPathParser
from certus_ask.pipelines.security_scan_parsers.registry import (
    ParserRegistry,
    get_parser_registry,
    parse_security_scan,
    register_parser,
)
from certus_ask.pipelines.security_scan_parsers.sarif_parser import SarifParser
from certus_ask.pipelines.security_scan_parsers.schema_loader import SchemaLoader

# Register built-in parsers at import time
_registry = get_parser_registry()
_registry.register(SarifParser())

# Auto-load and register built-in JSONPath schemas
try:
    schema_loader = SchemaLoader()
    for schema_name in ["bandit", "opengrep", "trivy"]:
        try:
            schema = schema_loader.load_schema_by_name(schema_name)
            parser = JSONPathParser(schema)
            _registry.register(parser)
        except Exception as e:
            # Log but don't fail if a schema can't be loaded
            import structlog

            logger = structlog.get_logger(__name__)
            logger.warning(
                "parser_registration.schema_failed",
                schema_name=schema_name,
                error=str(e),
            )
except Exception as e:
    # Don't fail startup if schema registration has issues
    import structlog

    logger = structlog.get_logger(__name__)
    logger.warning(
        "parser_registration.failed",
        error=str(e),
    )

__all__ = [
    "JSONPathParser",
    "ParserRegistry",
    "SarifParser",
    "SchemaLoader",
    "get_parser_registry",
    "parse_security_scan",
    "register_parser",
]
