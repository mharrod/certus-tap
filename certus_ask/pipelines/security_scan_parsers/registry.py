"""Registry for security scan parsers.

Manages parser discovery, registration, and selection. Provides:
- Central registry of all available parsers
- Auto-detection of tool format
- Parser selection and execution
"""

from typing import Any

import structlog

from certus_ask.core.exceptions import ValidationError
from certus_ask.pipelines.security_scan_parsers.base import SecurityScanParser
from certus_ask.schemas.unified_security_scan import UnifiedSecurityScan

logger = structlog.get_logger(__name__)


class ParserRegistry:
    """Registry for security scan parsers.

    Manages parser registration and provides methods to:
    - Register new parsers
    - Auto-detect tool format from JSON
    - Parse JSON using appropriate parser
    """

    def __init__(self) -> None:
        """Initialize empty registry."""
        self._parsers: dict[str, SecurityScanParser] = {}

    def register(self, parser: SecurityScanParser) -> None:
        """Register a parser.

        Args:
            parser: SecurityScanParser instance to register

        Raises:
            ValueError: If parser with same tool_name already registered
        """
        if parser.tool_name in self._parsers:
            logger.warning(
                "parser.already_registered",
                tool_name=parser.tool_name,
                replacing=True,
            )
            # Allow re-registration for JSONPath parsers (schemas may change)
            if not hasattr(parser, "schema"):
                raise ValueError(f"Parser for tool '{parser.tool_name}' already registered")

        self._parsers[parser.tool_name] = parser
        logger.info("parser.registered", tool_name=parser.tool_name, parser=parser)

    def get(self, tool_name: str) -> SecurityScanParser | None:
        """Get a parser by tool name.

        Args:
            tool_name: Name of the tool

        Returns:
            Parser instance or None if not registered
        """
        return self._parsers.get(tool_name)

    def list_parsers(self) -> dict[str, SecurityScanParser]:
        """Get all registered parsers.

        Returns:
            Dictionary mapping tool names to parser instances
        """
        return self._parsers.copy()

    def auto_detect(self, raw_json: dict[str, Any]) -> str | None:
        """Auto-detect tool format from JSON.

        Tries each registered parser's validate() method until one matches.

        Args:
            raw_json: Raw JSON data to identify

        Returns:
            Tool name if detected, None if no match
        """
        logger.debug("parser.auto_detect.start", parser_count=len(self._parsers))

        for tool_name, parser in self._parsers.items():
            try:
                if parser.validate(raw_json):
                    logger.info("parser.auto_detect.match", tool_name=tool_name)
                    return tool_name
            except Exception as exc:
                logger.warning(
                    "parser.auto_detect.validation_error",
                    tool_name=tool_name,
                    error=str(exc),
                )

        logger.warning("parser.auto_detect.no_match")
        return None

    def register_schema(self, schema: dict[str, Any]) -> None:
        """Register a JSONPath parser from a schema.

        Args:
            schema: JSONPath schema dict

        Raises:
            ValueError: If schema is invalid
        """
        from certus_ask.pipelines.security_scan_parsers.jsonpath_parser import (
            JSONPathParser,
        )
        from certus_ask.pipelines.security_scan_parsers.schema_loader import (
            SchemaLoader,
        )

        # Validate schema
        SchemaLoader.validate_schema(schema)

        # Create and register parser
        parser = JSONPathParser(schema)
        self.register(parser)
        logger.info(
            "parser.schema_registered",
            tool_name=schema.get("tool_name"),
        )

    def parse(
        self,
        raw_json: dict[str, Any],
        tool_hint: str | None = None,
    ) -> UnifiedSecurityScan:
        """Parse JSON to UnifiedSecurityScan.

        Args:
            raw_json: Raw JSON data from security tool
            tool_hint: Optional tool name hint (skips auto-detection)

        Returns:
            UnifiedSecurityScan with normalized findings

        Raises:
            ValidationError: If tool cannot be determined or parsing fails
        """
        # Determine which parser to use
        if tool_hint:
            parser = self.get(tool_hint)
            if parser is None:
                raise ValidationError(
                    message=f"Unknown tool format: {tool_hint}",
                    error_code="unknown_tool",
                    details={"tool_hint": tool_hint, "available_tools": list(self._parsers.keys())},
                )
            tool_name = tool_hint
        else:
            # Auto-detect
            tool_name = self.auto_detect(raw_json)
            if tool_name is None:
                raise ValidationError(
                    message="Could not auto-detect security tool format",
                    error_code="unknown_format",
                    details={"available_tools": list(self._parsers.keys())},
                )
            parser = self.get(tool_name)

        # Parse using selected parser
        try:
            logger.info("parser.parsing_start", tool_name=tool_name)
            result = parser.parse(raw_json)
            logger.info(
                "parser.parsing_complete",
                tool_name=tool_name,
                finding_count=len(result.findings),
            )
            return result
        except Exception as exc:
            logger.error(
                "parser.parsing_error",
                tool_name=tool_name,
                error=str(exc),
                exc_info=True,
            )
            raise ValidationError(
                message=f"Failed to parse {tool_name} format",
                error_code="parse_error",
                details={"tool_name": tool_name, "error": str(exc)},
            ) from exc


# Global registry instance
_registry: ParserRegistry | None = None


def get_parser_registry() -> ParserRegistry:
    """Get or create the global parser registry.

    Returns:
        Global ParserRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = ParserRegistry()
    return _registry


def register_parser(parser: SecurityScanParser) -> None:
    """Register a parser in the global registry.

    Args:
        parser: SecurityScanParser instance to register
    """
    get_parser_registry().register(parser)


def parse_security_scan(
    raw_json: dict[str, Any],
    tool_hint: str | None = None,
) -> UnifiedSecurityScan:
    """Parse security scan JSON to UnifiedSecurityScan.

    Entry point for parsing. Uses global registry.

    Args:
        raw_json: Raw JSON data from security tool
        tool_hint: Optional tool name (skips auto-detection)

    Returns:
        UnifiedSecurityScan with normalized findings

    Raises:
        ValidationError: If parsing fails
    """
    return get_parser_registry().parse(raw_json, tool_hint=tool_hint)
