"""Unit tests for configuration validation.

Tests validation logic for configuration and environment variables.
"""

from certus_ask.core.config_validation import ConfigurationValidator, ValidationError


class TestValidationError:
    """Tests for ValidationError dataclass."""

    def test_validation_error_creation(self):
        """Test creating a ValidationError."""
        error = ValidationError(field="test_field", message="Test error message", is_critical=True)

        assert error.field == "test_field"
        assert error.message == "Test error message"
        assert error.is_critical is True

    def test_validation_error_default_is_critical(self):
        """Test that ValidationError is critical by default."""
        error = ValidationError(field="test", message="test")
        assert error.is_critical is True

    def test_validation_error_str_critical(self):
        """Test string representation of critical error."""
        error = ValidationError(field="db_host", message="Missing host", is_critical=True)
        error_str = str(error)

        assert "[CRITICAL]" in error_str
        assert "db_host" in error_str
        assert "Missing host" in error_str

    def test_validation_error_str_warning(self):
        """Test string representation of warning."""
        error = ValidationError(field="optional_field", message="Not set", is_critical=False)
        error_str = str(error)

        assert "[WARNING]" in error_str
        assert "optional_field" in error_str
        assert "Not set" in error_str


class TestValidateUrl:
    """Tests for URL validation."""

    def test_validate_url_valid_http(self):
        """Test validation of valid HTTP URL."""
        result = ConfigurationValidator.validate_url("http://localhost:9200", "opensearch_host")
        assert result is None  # No error

    def test_validate_url_valid_https(self):
        """Test validation of valid HTTPS URL."""
        result = ConfigurationValidator.validate_url("https://example.com:443", "api_endpoint")
        assert result is None

    def test_validate_url_empty_string(self):
        """Test validation of empty URL."""
        result = ConfigurationValidator.validate_url("", "test_url")

        assert isinstance(result, ValidationError)
        assert result.field == "test_url"
        assert "empty" in result.message.lower()
        assert result.is_critical is True

    def test_validate_url_missing_protocol(self):
        """Test validation of URL without protocol."""
        result = ConfigurationValidator.validate_url("localhost:9200", "opensearch_host")

        assert isinstance(result, ValidationError)
        assert result.field == "opensearch_host"
        assert "http://" in result.message or "https://" in result.message
        assert result.is_critical is True

    def test_validate_url_invalid_protocol(self):
        """Test validation of URL with invalid protocol."""
        result = ConfigurationValidator.validate_url("ftp://example.com", "test_url")

        assert isinstance(result, ValidationError)
        assert "http://" in result.message or "https://" in result.message

    def test_validate_url_with_port(self):
        """Test validation of URL with port number."""
        result = ConfigurationValidator.validate_url("http://localhost:8080", "api_url")
        assert result is None

    def test_validate_url_with_path(self):
        """Test validation of URL with path."""
        result = ConfigurationValidator.validate_url("http://example.com/api/v1", "api_endpoint")
        assert result is None


class TestValidateLogLevel:
    """Tests for log level validation."""

    def test_validate_log_level_valid_debug(self):
        """Test validation of DEBUG log level."""
        result = ConfigurationValidator.validate_log_level("DEBUG")
        assert result is None

    def test_validate_log_level_valid_info(self):
        """Test validation of INFO log level."""
        result = ConfigurationValidator.validate_log_level("INFO")
        assert result is None

    def test_validate_log_level_valid_warning(self):
        """Test validation of WARNING log level."""
        result = ConfigurationValidator.validate_log_level("WARNING")
        assert result is None

    def test_validate_log_level_valid_error(self):
        """Test validation of ERROR log level."""
        result = ConfigurationValidator.validate_log_level("ERROR")
        assert result is None

    def test_validate_log_level_valid_critical(self):
        """Test validation of CRITICAL log level."""
        result = ConfigurationValidator.validate_log_level("CRITICAL")
        assert result is None

    def test_validate_log_level_case_insensitive(self):
        """Test that log level validation is case insensitive."""
        assert ConfigurationValidator.validate_log_level("debug") is None
        assert ConfigurationValidator.validate_log_level("Debug") is None
        assert ConfigurationValidator.validate_log_level("DEBUG") is None
        assert ConfigurationValidator.validate_log_level("info") is None
        assert ConfigurationValidator.validate_log_level("Info") is None

    def test_validate_log_level_invalid(self):
        """Test validation of invalid log level."""
        result = ConfigurationValidator.validate_log_level("INVALID")

        assert isinstance(result, ValidationError)
        assert result.field == "log_level"
        assert "INVALID" in result.message
        assert result.is_critical is False  # Log level is not critical

    def test_validate_log_level_empty_string(self):
        """Test validation of empty log level."""
        result = ConfigurationValidator.validate_log_level("")

        assert isinstance(result, ValidationError)


class TestValidateAwsRegion:
    """Tests for AWS region validation."""

    def test_validate_aws_region_valid(self):
        """Test validation of valid AWS regions."""
        valid_regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "us-gov-west-1"]

        for region in valid_regions:
            result = ConfigurationValidator.validate_aws_region(region)
            assert result is None, f"Region {region} should be valid"

    def test_validate_aws_region_empty_string(self):
        """Test validation of empty AWS region."""
        result = ConfigurationValidator.validate_aws_region("")

        assert isinstance(result, ValidationError)
        assert result.field == "aws_region"
        assert result.is_critical is True

    def test_validate_aws_region_too_short(self):
        """Test validation of too-short AWS region."""
        result = ConfigurationValidator.validate_aws_region("us")

        assert isinstance(result, ValidationError)
        assert result.field == "aws_region"

    def test_validate_aws_region_none(self):
        """Test validation of None AWS region."""
        # None should return a validation error
        error = ConfigurationValidator.validate_aws_region(None)  # type: ignore
        assert error is not None
        assert error.is_critical is True


class TestCriticalConfig:
    """Tests for critical configuration constants."""

    def test_critical_config_contains_required_fields(self):
        """Test that CRITICAL_CONFIG contains expected required fields."""
        critical = ConfigurationValidator.CRITICAL_CONFIG

        assert "opensearch_host" in critical
        assert "opensearch_index" in critical
        assert "aws_access_key_id" in critical
        assert "aws_secret_access_key" in critical
        assert "s3_endpoint_url" in critical
        assert "aws_region" in critical
        assert "llm_model" in critical
        assert "llm_url" in critical
        assert "mlflow_tracking_uri" in critical

    def test_critical_config_has_descriptions(self):
        """Test that all critical config entries have descriptions."""
        for _field, description in ConfigurationValidator.CRITICAL_CONFIG.items():
            assert isinstance(description, str)
            assert len(description) > 0


class TestOptionalConfig:
    """Tests for optional configuration constants."""

    def test_optional_config_contains_expected_fields(self):
        """Test that OPTIONAL_CONFIG contains expected fields."""
        optional = ConfigurationValidator.OPTIONAL_CONFIG

        assert "opensearch_http_auth_user" in optional
        assert "opensearch_http_auth_password" in optional
        assert "github_token" in optional
        assert "log_level" in optional
        assert "log_json_output" in optional

    def test_optional_config_default_values(self):
        """Test that optional config has appropriate defaults."""
        optional = ConfigurationValidator.OPTIONAL_CONFIG

        # Some should have None (truly optional)
        assert optional["opensearch_http_auth_user"] is None
        assert optional["github_token"] is None

        # Some should have defaults
        assert optional["log_level"] == "INFO"
        assert optional["log_json_output"] == "true"


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_validate_url_with_query_parameters(self):
        """Test URL validation with query parameters."""
        result = ConfigurationValidator.validate_url("http://example.com/api?key=value", "api_url")
        assert result is None

    def test_validate_url_with_fragment(self):
        """Test URL validation with fragment."""
        result = ConfigurationValidator.validate_url("http://example.com/page#section", "page_url")
        assert result is None

    def test_validate_url_localhost_without_port(self):
        """Test URL validation for localhost without port."""
        result = ConfigurationValidator.validate_url("http://localhost", "local_service")
        assert result is None

    def test_validate_url_ip_address(self):
        """Test URL validation with IP address."""
        result = ConfigurationValidator.validate_url("http://192.168.1.1:8080", "service_url")
        assert result is None
