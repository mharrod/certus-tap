"""Tests for configuration validation module.

Tests cover:
- Critical environment variable detection
- Optional environment variable handling
- URL format validation
- Log level validation
- AWS region validation
- Pydantic settings validation
- Fail-fast behavior
- Environment loading from .env file
"""

import os
import tempfile
from unittest.mock import patch

import pytest

from certus_ask.core.config_validation import (
    ConfigurationValidator,
    ValidationError,
)


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_validation_error_critical(self) -> None:
        """Test creating critical validation error."""
        error = ValidationError("opensearch_host", "Missing required host", is_critical=True)
        assert error.field == "opensearch_host"
        assert error.message == "Missing required host"
        assert error.is_critical is True
        assert "[CRITICAL]" in str(error)

    def test_validation_error_warning(self) -> None:
        """Test creating non-critical validation error."""
        error = ValidationError("github_token", "Optional token not set", is_critical=False)
        assert error.field == "github_token"
        assert error.message == "Optional token not set"
        assert error.is_critical is False
        assert "[WARNING]" in str(error)


class TestEnvironmentLoading:
    """Tests for loading environment variables from .env file."""

    def test_load_env_file_exists(self) -> None:
        """Test loading environment variables from existing .env file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("TEST_VAR=test_value\n")
            f.write("ANOTHER_VAR=another_value\n")
            env_file = f.name

        try:
            result = ConfigurationValidator.load_env_file(env_file)
            assert result is True
            assert os.environ.get("TEST_VAR") == "test_value"
            assert os.environ.get("ANOTHER_VAR") == "another_value"
        finally:
            os.unlink(env_file)
            # Clean up env vars
            os.environ.pop("TEST_VAR", None)
            os.environ.pop("ANOTHER_VAR", None)

    def test_load_env_file_not_found(self) -> None:
        """Test loading from non-existent .env file returns False."""
        result = ConfigurationValidator.load_env_file("/nonexistent/path/.env")
        assert result is False

    def test_load_env_file_default_path(self) -> None:
        """Test loading from default path."""
        # Should return False if .env doesn't exist in current directory
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                result = ConfigurationValidator.load_env_file()
                assert result is False
            finally:
                os.chdir(old_cwd)


class TestURLValidation:
    """Tests for URL format validation."""

    def test_validate_url_valid_http(self) -> None:
        """Test validation of valid HTTP URL."""
        error = ConfigurationValidator.validate_url("http://opensearch:9200", "opensearch_host")
        assert error is None

    def test_validate_url_valid_https(self) -> None:
        """Test validation of valid HTTPS URL."""
        error = ConfigurationValidator.validate_url("https://api.example.com", "llm_url")
        assert error is None

    def test_validate_url_missing_protocol(self) -> None:
        """Test validation fails for URL without protocol."""
        error = ConfigurationValidator.validate_url("opensearch:9200", "opensearch_host")
        assert error is not None
        assert "must start with http:// or https://" in error.message

    def test_validate_url_empty(self) -> None:
        """Test validation fails for empty URL."""
        error = ConfigurationValidator.validate_url("", "opensearch_host")
        assert error is not None
        assert "empty" in error.message.lower()

    def test_validate_url_invalid_protocol(self) -> None:
        """Test validation fails for invalid protocol."""
        error = ConfigurationValidator.validate_url("ftp://example.com", "opensearch_host")
        assert error is not None


class TestLogLevelValidation:
    """Tests for log level validation."""

    @pytest.mark.parametrize(
        "level",
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "debug", "info", "warning"],
    )
    def test_validate_log_level_valid(self, level: str) -> None:
        """Test validation of valid log levels."""
        error = ConfigurationValidator.validate_log_level(level)
        assert error is None

    @pytest.mark.parametrize(
        "level",
        ["INVALID", "TRACE", "VERBOSE", "QUIET", ""],
    )
    def test_validate_log_level_invalid(self, level: str) -> None:
        """Test validation fails for invalid log levels."""
        error = ConfigurationValidator.validate_log_level(level)
        assert error is not None
        assert "Invalid log level" in error.message


class TestAWSRegionValidation:
    """Tests for AWS region validation."""

    @pytest.mark.parametrize(
        "region",
        ["us-east-1", "eu-west-1", "ap-southeast-1", "us-west-2"],
    )
    def test_validate_aws_region_valid(self, region: str) -> None:
        """Test validation of valid AWS regions."""
        error = ConfigurationValidator.validate_aws_region(region)
        assert error is None

    @pytest.mark.parametrize(
        "region",
        ["", "x", "xx"],
    )
    def test_validate_aws_region_invalid(self, region: str) -> None:
        """Test validation fails for invalid AWS regions."""
        error = ConfigurationValidator.validate_aws_region(region)
        assert error is not None


class TestCriticalVarsCheck:
    """Tests for checking critical environment variables."""

    def test_check_critical_vars_all_present(self) -> None:
        """Test all critical vars present returns empty error list."""
        # Mock environment with all critical vars
        critical_vars = {
            "OPENSEARCH_HOST": "http://opensearch:9200",
            "OPENSEARCH_INDEX": "ask_certus",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "S3_ENDPOINT_URL": "http://localstack:4566",
            "AWS_REGION": "us-east-1",
            "LLM_MODEL": "llama3.1:8b",
            "LLM_URL": "http://localhost:11434",
            "MLFLOW_TRACKING_URI": "http://mlflow:5001",
        }

        with patch.dict(os.environ, critical_vars):
            errors = ConfigurationValidator.check_critical_vars()
            assert len(errors) == 0

    def test_check_critical_vars_missing_single(self) -> None:
        """Test detection of missing single critical var."""
        # All vars except OPENSEARCH_HOST
        critical_vars = {
            "OPENSEARCH_INDEX": "ask_certus",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "S3_ENDPOINT_URL": "http://localstack:4566",
            "AWS_REGION": "us-east-1",
            "LLM_MODEL": "llama3.1:8b",
            "LLM_URL": "http://localhost:11434",
            "MLFLOW_TRACKING_URI": "http://mlflow:5001",
        }

        with patch.dict(os.environ, critical_vars, clear=False):
            # Remove OPENSEARCH_HOST if it exists
            os.environ.pop("OPENSEARCH_HOST", None)
            errors = ConfigurationValidator.check_critical_vars()

            assert len(errors) > 0
            error_fields = [e.field for e in errors]
            assert "opensearch_host" in error_fields

    def test_check_critical_vars_missing_multiple(self) -> None:
        """Test detection of multiple missing critical vars."""
        with patch.dict(os.environ, {}, clear=True):
            errors = ConfigurationValidator.check_critical_vars()
            assert len(errors) == len(ConfigurationValidator.CRITICAL_CONFIG)
            assert all(e.is_critical for e in errors)


class TestOptionalVarsCheck:
    """Tests for checking optional environment variables."""

    def test_check_optional_vars_all_present(self) -> None:
        """Test all optional vars present returns empty warnings."""
        optional_vars = {
            "OPENSEARCH_LOG_USERNAME": "user",
            "OPENSEARCH_LOG_PASSWORD": "pass",
            "GITHUB_TOKEN": "token",
        }

        with patch.dict(os.environ, optional_vars):
            warnings = ConfigurationValidator.check_optional_vars()
            # Should only warn about truly missing ones with no default
            assert not any(not w.is_critical for w in warnings if "github" in w.field.lower())

    def test_check_optional_vars_missing(self) -> None:
        """Test detection of missing optional vars."""
        with patch.dict(os.environ, {}, clear=True):
            warnings = ConfigurationValidator.check_optional_vars()
            # Should have warnings for optional vars with None defaults
            assert len(warnings) > 0
            assert all(not w.is_critical for w in warnings)


class TestPydanticValidation:
    """Tests for pydantic Settings validation."""

    def test_validate_pydantic_settings_with_valid_config(self) -> None:
        """Test pydantic validation with valid settings."""
        valid_env = {
            "OPENSEARCH_HOST": "http://opensearch:9200",
            "OPENSEARCH_INDEX": "ask_certus",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "S3_ENDPOINT_URL": "http://localstack:4566",
            "AWS_REGION": "us-east-1",
            "LLM_MODEL": "llama3.1:8b",
            "LLM_URL": "http://localhost:11434",
            "MLFLOW_TRACKING_URI": "http://mlflow:5001",
        }

        with patch.dict(os.environ, valid_env):
            # Clear cached settings
            from certus_ask.core.config import get_settings

            get_settings.cache_clear()

            errors = ConfigurationValidator.validate_pydantic_settings()
            assert len(errors) == 0

    def test_validate_pydantic_settings_invalid_log_level(self) -> None:
        """Test pydantic validation catches invalid log level."""
        invalid_env = {
            "OPENSEARCH_HOST": "http://opensearch:9200",
            "OPENSEARCH_INDEX": "ask_certus",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "S3_ENDPOINT_URL": "http://localstack:4566",
            "AWS_REGION": "us-east-1",
            "LLM_MODEL": "llama3.1:8b",
            "LLM_URL": "http://localhost:11434",
            "MLFLOW_TRACKING_URI": "http://mlflow:5001",
            "LOG_LEVEL": "INVALID",
        }

        with patch.dict(os.environ, invalid_env):
            from certus_ask.core.config import get_settings

            get_settings.cache_clear()

            errors = ConfigurationValidator.validate_pydantic_settings()
            # Should have error for invalid log level
            log_level_errors = [e for e in errors if "log_level" in e.field.lower()]
            assert len(log_level_errors) > 0


class TestValidateAll:
    """Tests for comprehensive validation."""

    def test_validate_all_success(self) -> None:
        """Test successful validation of all config."""
        valid_env = {
            "OPENSEARCH_HOST": "http://opensearch:9200",
            "OPENSEARCH_INDEX": "ask_certus",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "S3_ENDPOINT_URL": "http://localstack:4566",
            "AWS_REGION": "us-east-1",
            "LLM_MODEL": "llama3.1:8b",
            "LLM_URL": "http://localhost:11434",
            "MLFLOW_TRACKING_URI": "http://mlflow:5001",
        }

        with patch.dict(os.environ, valid_env):
            from certus_ask.core.config import get_settings

            get_settings.cache_clear()

            critical_errors, _warnings = ConfigurationValidator.validate_all()
            assert len(critical_errors) == 0

    def test_validate_all_with_errors_and_warnings(self) -> None:
        """Test validation returns both errors and warnings."""
        partial_env = {
            "OPENSEARCH_INDEX": "ask_certus",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "S3_ENDPOINT_URL": "http://localstack:4566",
            "AWS_REGION": "us-east-1",
            "LLM_MODEL": "llama3.1:8b",
            "LLM_URL": "http://localhost:11434",
            "MLFLOW_TRACKING_URI": "http://mlflow:5001",
        }

        with patch.dict(os.environ, partial_env, clear=False):
            os.environ.pop("OPENSEARCH_HOST", None)

            from certus_ask.core.config import get_settings

            get_settings.cache_clear()

            critical_errors, _warnings = ConfigurationValidator.validate_all()
            # Should have critical error for missing OPENSEARCH_HOST
            assert len(critical_errors) > 0
            assert any("opensearch_host" in e.field.lower() for e in critical_errors)


class TestFailFast:
    """Tests for fail-fast behavior."""

    def test_fail_fast_success(self, capsys) -> None:
        """Test fail-fast exits successfully with valid config."""
        valid_env = {
            "OPENSEARCH_HOST": "http://opensearch:9200",
            "OPENSEARCH_INDEX": "ask_certus",
            "AWS_ACCESS_KEY_ID": "test",
            "AWS_SECRET_ACCESS_KEY": "test",
            "S3_ENDPOINT_URL": "http://localstack:4566",
            "AWS_REGION": "us-east-1",
            "LLM_MODEL": "llama3.1:8b",
            "LLM_URL": "http://localhost:11434",
            "MLFLOW_TRACKING_URI": "http://mlflow:5001",
        }

        with patch.dict(os.environ, valid_env):
            from certus_ask.core.config import get_settings

            get_settings.cache_clear()

            # Should not raise SystemExit
            ConfigurationValidator.fail_fast()

    def test_fail_fast_missing_critical(self) -> None:
        """Test fail-fast exits with status code 1 on missing critical config."""
        with patch.dict(os.environ, {}, clear=True):
            from certus_ask.core.config import get_settings

            get_settings.cache_clear()

            with pytest.raises(SystemExit) as exc_info:
                ConfigurationValidator.fail_fast()

            assert exc_info.value.code == 1

    def test_fail_fast_with_env_file(self) -> None:
        """Test fail-fast loads and validates .env file."""
        valid_env_content = """OPENSEARCH_HOST=http://opensearch:9200
OPENSEARCH_INDEX=ask_certus
AWS_ACCESS_KEY_ID=test
AWS_SECRET_ACCESS_KEY=test
S3_ENDPOINT_URL=http://localstack:4566
AWS_REGION=us-east-1
LLM_MODEL=llama3.1:8b
LLM_URL=http://localhost:11434
MLFLOW_TRACKING_URI=http://mlflow:5001
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write(valid_env_content)
            env_file = f.name

        try:
            from certus_ask.core.config import get_settings

            get_settings.cache_clear()

            # Should not raise SystemExit
            ConfigurationValidator.fail_fast(env_file)
        finally:
            os.unlink(env_file)
