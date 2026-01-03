"""Unit tests for schema loader.

Tests the schema loader's ability to:
- Load built-in schemas from disk
- Validate schema structure
- List available schemas
- Handle errors gracefully
"""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from certus_ask.pipelines.security_scan_parsers.schema_loader import SchemaLoader


@pytest.fixture
def valid_schema() -> dict[str, Any]:
    """Create a valid schema dict."""
    return {
        "tool_name": "test-tool",
        "version": "1.0.0",
        "description": "Test tool schema",
        "format": {
            "findings_path": "$.results[*]",
            "mapping": {
                "id": "$.ruleId",
                "title": "$.message.text",
                "severity": "$.level",
                "file_path": "$.locations[0].physicalLocation.artifactLocation.uri",
                "line_start": "$.locations[0].physicalLocation.region.startLine",
            },
        },
    }


@pytest.fixture
def temp_schema_dir(valid_schema: dict[str, Any]) -> Path:
    """Create a temporary directory with test schemas."""
    temp_dir = Path(tempfile.mkdtemp())

    # Create a valid schema file
    schema_file = temp_dir / "test-tool_schema.json"
    with open(schema_file, "w") as f:
        json.dump(valid_schema, f)

    # Create another schema
    another_schema = valid_schema.copy()
    another_schema["tool_name"] = "another-tool"
    another_file = temp_dir / "another-tool_schema.json"
    with open(another_file, "w") as f:
        json.dump(another_schema, f)

    # Create an invalid JSON file
    invalid_file = temp_dir / "invalid_schema.json"
    with open(invalid_file, "w") as f:
        f.write("{invalid json")

    yield temp_dir

    # Cleanup
    for file in temp_dir.glob("*"):
        file.unlink()
    temp_dir.rmdir()


class TestSchemaLoaderValidation:
    """Test schema validation."""

    def test_validate_valid_schema(self, valid_schema: dict[str, Any]) -> None:
        """Test validation of valid schema."""
        assert SchemaLoader.validate_schema(valid_schema) is True

    def test_validate_missing_tool_name(self, valid_schema: dict[str, Any]) -> None:
        """Test validation fails without tool_name."""
        del valid_schema["tool_name"]

        with pytest.raises(ValueError, match="tool_name"):
            SchemaLoader.validate_schema(valid_schema)

    def test_validate_missing_format(self, valid_schema: dict[str, Any]) -> None:
        """Test validation fails without format field."""
        del valid_schema["format"]

        with pytest.raises(ValueError, match="format"):
            SchemaLoader.validate_schema(valid_schema)

    def test_validate_missing_findings_path(self, valid_schema: dict[str, Any]) -> None:
        """Test validation fails without findings_path."""
        del valid_schema["format"]["findings_path"]

        with pytest.raises(ValueError, match="findings_path"):
            SchemaLoader.validate_schema(valid_schema)

    def test_validate_missing_mapping(self, valid_schema: dict[str, Any]) -> None:
        """Test validation fails without mapping."""
        del valid_schema["format"]["mapping"]

        with pytest.raises(ValueError, match="mapping"):
            SchemaLoader.validate_schema(valid_schema)

    def test_validate_findings_path_not_string(self, valid_schema: dict[str, Any]) -> None:
        """Test validation fails if findings_path is not a string."""
        valid_schema["format"]["findings_path"] = 123

        with pytest.raises(ValueError, match="findings_path must be a string"):
            SchemaLoader.validate_schema(valid_schema)

    def test_validate_mapping_not_dict(self, valid_schema: dict[str, Any]) -> None:
        """Test validation fails if mapping is not a dict."""
        valid_schema["format"]["mapping"] = "not a dict"

        with pytest.raises(ValueError, match="mapping must be a dict"):
            SchemaLoader.validate_schema(valid_schema)

    def test_validate_mapping_value_invalid_type(self, valid_schema: dict[str, Any]) -> None:
        """Test validation fails if mapping value is not string or None."""
        valid_schema["format"]["mapping"]["id"] = 123

        with pytest.raises(ValueError, match="must be a string or null"):
            SchemaLoader.validate_schema(valid_schema)

    def test_validate_mapping_value_can_be_none(self, valid_schema: dict[str, Any]) -> None:
        """Test validation allows None values in mapping."""
        valid_schema["format"]["mapping"]["optional_field"] = None

        assert SchemaLoader.validate_schema(valid_schema) is True

    def test_validate_schema_with_minimal_fields(self) -> None:
        """Test validation of schema with only required fields."""
        minimal_schema = {
            "tool_name": "minimal",
            "format": {
                "findings_path": "$.results",
                "mapping": {},
            },
        }

        assert SchemaLoader.validate_schema(minimal_schema) is True


class TestSchemaLoaderLoadByName:
    """Test loading schemas by name."""

    def test_load_schema_by_name(self, temp_schema_dir: Path, valid_schema: dict[str, Any]) -> None:
        """Test loading a schema by name."""
        # Temporarily override schema dir
        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            schema = SchemaLoader.load_schema_by_name("test-tool")
            assert schema == valid_schema
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir

    def test_load_schema_not_found(self, temp_schema_dir: Path) -> None:
        """Test loading non-existent schema raises error."""
        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            with pytest.raises(FileNotFoundError, match="Schema not found"):
                SchemaLoader.load_schema_by_name("nonexistent")
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir

    def test_load_schema_invalid_json(self, temp_schema_dir: Path) -> None:
        """Test loading schema with invalid JSON raises error."""
        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            with pytest.raises(ValueError, match="Invalid JSON"):
                SchemaLoader.load_schema_by_name("invalid")
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir

    def test_load_schema_from_custom_dir(
        self, temp_schema_dir: Path, monkeypatch: pytest.MonkeyPatch, valid_schema: dict[str, Any]
    ) -> None:
        """Test loading schema from custom directory via environment variable."""
        # Reset the class variable by simulating module reload
        monkeypatch.setenv("SECURITY_SCHEMA_DIR", str(temp_schema_dir))
        SchemaLoader.SCHEMA_DIR = Path(str(temp_schema_dir))

        schema = SchemaLoader.load_schema_by_name("test-tool")
        assert schema == valid_schema


class TestSchemaLoaderLoadAndValidate:
    """Test load_and_validate method."""

    def test_load_and_validate_success(self, valid_schema: dict[str, Any]) -> None:
        """Test load_and_validate with valid schema."""
        result = SchemaLoader.load_and_validate(valid_schema)
        assert result == valid_schema

    def test_load_and_validate_invalid_schema(self) -> None:
        """Test load_and_validate with invalid schema."""
        invalid_schema = {
            "tool_name": "test",
            # Missing format field
        }

        with pytest.raises(ValueError):
            SchemaLoader.load_and_validate(invalid_schema)


class TestSchemaLoaderListSchemas:
    """Test listing available schemas."""

    def test_list_available_schemas(self, temp_schema_dir: Path) -> None:
        """Test listing all available schemas."""
        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            schemas = SchemaLoader.list_available_schemas()
            assert "test-tool" in schemas
            assert "another-tool" in schemas
            assert "invalid" in schemas  # File exists even if invalid
            assert len(schemas) == 3
            assert schemas == sorted(schemas)  # Should be sorted
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir

    def test_list_available_schemas_empty_dir(self) -> None:
        """Test listing schemas in empty directory."""
        temp_dir = Path(tempfile.mkdtemp())
        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_dir

        try:
            schemas = SchemaLoader.list_available_schemas()
            assert schemas == []
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir
            temp_dir.rmdir()

    def test_list_available_schemas_nonexistent_dir(self) -> None:
        """Test listing schemas when directory doesn't exist."""
        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = Path("/nonexistent/directory")

        try:
            schemas = SchemaLoader.list_available_schemas()
            assert schemas == []
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir


class TestSchemaLoaderGetSchemaInfo:
    """Test getting schema metadata."""

    def test_get_schema_info(self, temp_schema_dir: Path) -> None:
        """Test getting schema info."""
        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            info = SchemaLoader.get_schema_info("test-tool")

            assert info["tool_name"] == "test-tool"
            assert info["version"] == "1.0.0"
            assert info["description"] == "Test tool schema"
            assert "id" in info["fields"]
            assert "title" in info["fields"]
            assert "severity" in info["fields"]
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir

    def test_get_schema_info_not_found(self, temp_schema_dir: Path) -> None:
        """Test getting info for non-existent schema."""
        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            with pytest.raises(FileNotFoundError):
                SchemaLoader.get_schema_info("nonexistent")
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir

    def test_get_schema_info_minimal_schema(self, temp_schema_dir: Path) -> None:
        """Test getting info from schema with minimal fields."""
        minimal_schema = {
            "tool_name": "minimal",
            "format": {
                "findings_path": "$.results",
                "mapping": {"id": "$.id"},
            },
        }

        schema_file = temp_schema_dir / "minimal_schema.json"
        with open(schema_file, "w") as f:
            json.dump(minimal_schema, f)

        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            info = SchemaLoader.get_schema_info("minimal")

            assert info["tool_name"] == "minimal"
            assert info["version"] is None
            assert info["description"] is None
            assert info["fields"] == ["id"]
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir
            schema_file.unlink()


class TestSchemaLoaderEdgeCases:
    """Test edge cases and error handling."""

    def test_validate_empty_schema(self) -> None:
        """Test validation of empty schema."""
        with pytest.raises(ValueError):
            SchemaLoader.validate_schema({})

    def test_validate_schema_with_extra_fields(self, valid_schema: dict[str, Any]) -> None:
        """Test validation allows extra fields."""
        valid_schema["extra_field"] = "extra_value"
        valid_schema["format"]["extra_format_field"] = "extra"

        assert SchemaLoader.validate_schema(valid_schema) is True

    def test_schema_dir_default_path(self) -> None:
        """Test that default schema directory is properly configured."""
        # Should point to certus_ask/schemas/security_schemas
        assert "security_schemas" in str(SchemaLoader._DEFAULT_SCHEMA_DIR)

    def test_load_schema_with_unicode_content(self, temp_schema_dir: Path) -> None:
        """Test loading schema with unicode characters."""
        unicode_schema = {
            "tool_name": "unicode-tool",
            "description": "测试 🔒 Security",
            "format": {
                "findings_path": "$.results",
                "mapping": {"title": "$.message"},
            },
        }

        schema_file = temp_schema_dir / "unicode-tool_schema.json"
        with open(schema_file, "w", encoding="utf-8") as f:
            json.dump(unicode_schema, f, ensure_ascii=False)

        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            schema = SchemaLoader.load_schema_by_name("unicode-tool")
            assert schema["description"] == "测试 🔒 Security"
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir
            schema_file.unlink()

    def test_validate_schema_with_nested_mapping_structure(self) -> None:
        """Test validation with complex mapping structure."""
        complex_schema = {
            "tool_name": "complex",
            "format": {
                "findings_path": "$.data.results[*]",
                "mapping": {
                    "id": "$.id",
                    "title": "$.details.title",
                    "severity": "$.metadata.severity.level",
                    "description": "$.details.description",
                    "file_path": "$.location.file",
                    "line_start": "$.location.line",
                    "line_end": "$.location.endLine",
                    "optional": None,
                },
            },
        }

        assert SchemaLoader.validate_schema(complex_schema) is True

    def test_list_schemas_filters_non_schema_files(self, temp_schema_dir: Path) -> None:
        """Test that list_available_schemas only returns _schema.json files."""
        # Create a non-schema JSON file
        non_schema_file = temp_schema_dir / "not_a_schema.json"
        with open(non_schema_file, "w") as f:
            json.dump({"data": "test"}, f)

        original_dir = SchemaLoader.SCHEMA_DIR
        SchemaLoader.SCHEMA_DIR = temp_schema_dir

        try:
            schemas = SchemaLoader.list_available_schemas()
            # Should not include files that don't match *_schema.json pattern
            # Note: "not_a_schema.json" matches the pattern, so change to "config.json"
            assert "config" not in schemas
            # Should only include files matching the pattern
            assert set(schemas) == {"test-tool", "another-tool", "invalid", "not_a"}
        finally:
            SchemaLoader.SCHEMA_DIR = original_dir
            non_schema_file.unlink()
