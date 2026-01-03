"""Schema loader for JSONPath-based security tool parsing.

Loads and validates JSONPath schemas from the filesystem or user input.
Schemas define how to extract findings from custom security tool formats.
"""

import json
import os
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class SchemaLoader:
    """Load and validate JSONPath schemas for security tool parsing."""

    # Schema directory (configurable via environment variable)
    # Default: certus_ask/schemas/security_schemas
    # Override: export SECURITY_SCHEMA_DIR=/path/to/schemas
    _DEFAULT_SCHEMA_DIR = Path(__file__).parent.parent.parent / "schemas" / "security_schemas"
    SCHEMA_DIR = Path(os.getenv("SECURITY_SCHEMA_DIR", str(_DEFAULT_SCHEMA_DIR)))

    @classmethod
    def load_schema_by_name(cls, schema_name: str) -> dict[str, Any]:
        """Load a built-in schema by name.

        Built-in schemas are stored as JSON files in the schemas directory.
        The directory can be customized via the SECURITY_SCHEMA_DIR environment variable.

        Args:
            schema_name: Name of schema without .json extension
                        e.g., "bandit", "opengrep", "trivy"

        Returns:
            Schema dict

        Raises:
            FileNotFoundError: If schema file doesn't exist
            ValueError: If schema is invalid

        Examples:
            # Use default location (certus_ask/schemas/security_schemas)
            schema = SchemaLoader.load_schema_by_name("bandit")

            # With custom location via environment variable:
            # export SECURITY_SCHEMA_DIR=/external/schemas
            # schema = SchemaLoader.load_schema_by_name("bandit")
        """
        schema_path = cls.SCHEMA_DIR / f"{schema_name}_schema.json"

        if not schema_path.exists():
            logger.error(
                "schema_loader.schema_not_found",
                schema_name=schema_name,
                search_path=str(schema_path),
            )
            raise FileNotFoundError(f"Schema not found: {schema_name}")

        try:
            with open(schema_path) as f:
                schema = json.load(f)
            logger.info("schema_loader.schema_loaded", schema_name=schema_name)
            return schema
        except json.JSONDecodeError as e:
            logger.error(
                "schema_loader.invalid_json",
                schema_name=schema_name,
                error=str(e),
            )
            raise ValueError(f"Invalid JSON in schema: {e}") from e
        except Exception as e:
            logger.error(
                "schema_loader.load_error",
                schema_name=schema_name,
                error=str(e),
            )
            raise

    @classmethod
    def validate_schema(cls, schema: dict[str, Any]) -> bool:
        """Validate schema structure.

        Required fields:
        - tool_name: str
        - format.findings_path: str (JSONPath expression)
        - format.mapping: dict (field -> JSONPath expression)

        Args:
            schema: Schema dict to validate

        Returns:
            True if valid

        Raises:
            ValueError: If schema is invalid
        """
        # Check required top-level fields
        if "tool_name" not in schema:
            raise ValueError("Schema missing required field: tool_name")

        if "format" not in schema:
            raise ValueError("Schema missing required field: format")

        format_config = schema["format"]

        if "findings_path" not in format_config:
            raise ValueError("Schema format missing required field: findings_path")

        if "mapping" not in format_config:
            raise ValueError("Schema format missing required field: mapping")

        # Validate findings_path is a string
        if not isinstance(format_config["findings_path"], str):
            raise ValueError("findings_path must be a string")

        # Validate mapping is a dict
        if not isinstance(format_config["mapping"], dict):
            raise ValueError("mapping must be a dict")

        # Validate mapping values are strings or None
        for field, path in format_config["mapping"].items():
            if path is not None and not isinstance(path, str):
                raise ValueError(f"mapping.{field} must be a string or null, got {type(path)}")

        logger.info(
            "schema_loader.validation_success",
            tool_name=schema.get("tool_name"),
        )
        return True

    @classmethod
    def load_and_validate(cls, schema: dict[str, Any]) -> dict[str, Any]:
        """Load and validate a schema in one step.

        Args:
            schema: Schema dict to validate

        Returns:
            Validated schema

        Raises:
            ValueError: If schema is invalid
        """
        cls.validate_schema(schema)
        return schema

    @classmethod
    def list_available_schemas(cls) -> list[str]:
        """List all available built-in schemas.

        Returns:
            List of schema names (without .json extension)
        """
        if not cls.SCHEMA_DIR.exists():
            logger.warning("schema_loader.schema_dir_not_found", path=str(cls.SCHEMA_DIR))
            return []

        schemas = []
        for schema_file in cls.SCHEMA_DIR.glob("*_schema.json"):
            schema_name = schema_file.stem.replace("_schema", "")
            schemas.append(schema_name)

        logger.info("schema_loader.list_schemas", count=len(schemas), schemas=schemas)
        return sorted(schemas)

    @classmethod
    def get_schema_info(cls, schema_name: str) -> dict[str, Any]:
        """Get metadata about a schema.

        Args:
            schema_name: Name of schema

        Returns:
            Dict with schema info: tool_name, version, description

        Raises:
            FileNotFoundError: If schema doesn't exist
        """
        schema = cls.load_schema_by_name(schema_name)
        return {
            "tool_name": schema.get("tool_name"),
            "version": schema.get("version"),
            "description": schema.get("description"),
            "fields": list(schema.get("format", {}).get("mapping", {}).keys()),
        }
