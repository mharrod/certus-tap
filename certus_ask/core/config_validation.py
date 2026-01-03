"""Configuration validation for startup safety.

This module provides comprehensive validation of environment variables and configuration
at application startup, ensuring all critical values are present and valid before the
application begins serving requests.

Key Features:
- Fail-fast validation on startup
- Detailed error messages for missing/invalid config
- Separate critical vs optional config validation
- Environment variable loading with python-dotenv
- Pre-flight checks before main app initialization
"""

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Optional

from dotenv import load_dotenv
from pydantic import ValidationError as PydanticValidationError

from certus_ask.core.config import get_settings


@dataclass
class ValidationError:
    """Represents a configuration validation error."""

    field: str
    message: str
    is_critical: bool = True

    def __str__(self) -> str:
        severity = "CRITICAL" if self.is_critical else "WARNING"
        return f"[{severity}] {self.field}: {self.message}"


class ConfigurationValidator:
    """Validates application configuration at startup.

    Checks for:
    - Required environment variables present
    - Valid URL formats
    - Valid log levels
    - Port ranges
    - AWS credential validity
    - OpenSearch connectivity (optional check)
    """

    # Critical config that must be present for app to run
    CRITICAL_CONFIG: ClassVar[dict[str, str]] = {
        "opensearch_host": "OpenSearch cluster host (e.g., http://opensearch:9200)",
        "opensearch_index": "OpenSearch index name",
        "aws_access_key_id": "AWS access key ID",
        "aws_secret_access_key": "AWS secret access key",
        "s3_endpoint_url": "S3 endpoint URL (e.g., http://localstack:4566)",
        "aws_region": "AWS region (e.g., us-east-1)",
        "llm_model": "LLM model name (e.g., llama3.1:8b)",
        "llm_url": "LLM service URL (e.g., http://ollama:11434)",
        "mlflow_tracking_uri": "MLflow tracking server URI",
    }

    # Optional config with sensible defaults
    OPTIONAL_CONFIG: ClassVar[dict[str, Optional[str]]] = {
        "opensearch_http_auth_user": None,
        "opensearch_http_auth_password": None,
        "github_token": None,
        "log_level": "INFO",
        "log_json_output": "true",
        "send_logs_to_opensearch": "true",
        "opensearch_log_host": "localhost",
        "opensearch_log_port": "9200",
        "datalake_raw_bucket": "raw",
        "datalake_golden_bucket": "golden",
    }

    @staticmethod
    def load_env_file(env_path: Optional[str] = None) -> bool:
        """Load environment variables from .env file.

        Args:
            env_path: Path to .env file. Defaults to current directory.

        Returns:
            True if file was loaded, False if not found.
        """
        if env_path is None:
            # During pytest runs we want to rely solely on the patched environment
            # rather than the developer's real .env file bleeding into the tests.
            if os.environ.get("PYTEST_CURRENT_TEST") or "pytest" in sys.modules:
                return False
            env_path = ".env"

        env_file = Path(env_path)
        if env_file.exists():
            load_dotenv(env_file)
            return True
        return False

    @staticmethod
    def validate_url(url: str, field_name: str) -> Optional[ValidationError]:
        """Validate URL format."""
        if not url:
            return ValidationError(field_name, "URL is empty", is_critical=True)

        if not (url.startswith("http://") or url.startswith("https://")):
            return ValidationError(
                field_name,
                f"URL must start with http:// or https:// (got: {url})",
                is_critical=True,
            )

        return None

    @staticmethod
    def validate_log_level(level: str) -> Optional[ValidationError]:
        """Validate log level."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if level.upper() not in valid_levels:
            return ValidationError(
                "log_level",
                f"Invalid log level '{level}'. Must be one of: {', '.join(valid_levels)}",
                is_critical=False,
            )
        return None

    @staticmethod
    def validate_aws_region(region: str) -> Optional[ValidationError]:
        """Validate AWS region format."""
        # Basic validation: should be region-like (e.g., us-east-1)
        if not region or len(region) < 3:
            return ValidationError(
                "aws_region",
                f"Invalid AWS region format: '{region}'",
                is_critical=True,
            )
        return None

    @classmethod
    def check_critical_vars(cls) -> list[ValidationError]:
        """Check that all critical environment variables are present.

        Returns:
            List of validation errors (empty if all critical vars present).
        """
        errors: list[ValidationError] = []

        for var_name, description in cls.CRITICAL_CONFIG.items():
            env_var = var_name.upper()
            if env_var not in os.environ:
                errors.append(
                    ValidationError(
                        var_name,
                        f"Missing required environment variable: {env_var}. {description}",
                        is_critical=True,
                    )
                )

        return errors

    @classmethod
    def check_optional_vars(cls) -> list[ValidationError]:
        """Check optional variables and log warnings if missing.

        Returns:
            List of validation warnings (non-critical).
        """
        warnings: list[ValidationError] = []

        for var_name, default_value in cls.OPTIONAL_CONFIG.items():
            env_var = var_name.upper()
            if env_var not in os.environ and default_value is None:
                warnings.append(
                    ValidationError(
                        var_name,
                        f"Optional environment variable not set: {env_var}. Ensure this is intentional.",
                        is_critical=False,
                    )
                )

        return warnings

    @classmethod
    def validate_pydantic_settings(cls) -> list[ValidationError]:
        """Validate settings using pydantic.

        Returns:
            List of validation errors from pydantic.
        """
        errors_list: list[ValidationError] = []

        try:
            settings = get_settings()

            # Validate URL fields
            url_fields = {
                "opensearch_host": settings.opensearch_host,
                "s3_endpoint_url": settings.s3_endpoint_url,
                "llm_url": settings.llm_url,
                "mlflow_tracking_uri": settings.mlflow_tracking_uri,
            }

            for field_name, url_value in url_fields.items():
                if url_value:
                    error = cls.validate_url(url_value, field_name)
                    if error:
                        errors_list.append(error)

            # Validate log level
            if settings.log_level:
                error = cls.validate_log_level(settings.log_level)
                if error:
                    errors_list.append(error)

            # Validate AWS region
            error = cls.validate_aws_region(settings.aws_region)
            if error:
                errors_list.append(error)

        except PydanticValidationError as e:
            for error in e.errors():
                field = error.get("loc", ("unknown",))[0]
                message = error.get("msg", "Invalid value")
                errors_list.append(ValidationError(str(field), message, is_critical=True))

        return errors_list

    @classmethod
    def validate_all(cls, env_path: Optional[str] = None) -> tuple[list[ValidationError], list[ValidationError]]:
        """Run all validation checks.

        Args:
            env_path: Path to .env file to load.

        Returns:
            Tuple of (critical_errors, warnings).
        """
        # Load env file if it exists
        cls.load_env_file(env_path)

        # Check critical vars
        critical_errors = cls.check_critical_vars()

        # Check pydantic validation (only if no critical vars missing)
        if not critical_errors:
            critical_errors.extend(cls.validate_pydantic_settings())

        # Check optional vars
        warnings = cls.check_optional_vars()

        return critical_errors, warnings

    @classmethod
    def fail_fast(cls, env_path: Optional[str] = None) -> None:
        """Validate configuration and exit if critical errors found.

        This is the primary entry point for startup validation. Call this
        early in application initialization to fail fast if config is invalid.

        Args:
            env_path: Path to .env file to load.

        Raises:
            SystemExit: If critical errors found.
        """
        critical_errors, warnings = cls.validate_all(env_path)

        # Print warnings
        if warnings:
            print("\n" + "=" * 80)
            print("CONFIGURATION WARNINGS")
            print("=" * 80)
            for warning in warnings:
                print(f"  {warning}")
            print()

        # Print and fail on critical errors
        if critical_errors:
            print("\n" + "=" * 80)
            print("CONFIGURATION ERRORS - APPLICATION STARTUP FAILED")
            print("=" * 80)
            for error in critical_errors:
                print(f"  {error}")
            print("\nPlease fix the above errors and try again.")
            print("=" * 80 + "\n")
            sys.exit(1)

        # Success
        print("\n" + "=" * 80)
        print("CONFIGURATION VALIDATION PASSED")
        print("=" * 80)
        print("All critical configuration values are present and valid.")
        print("=" * 80 + "\n")
