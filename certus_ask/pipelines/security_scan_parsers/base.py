"""Base class for security scan parsers.

All security tool parsers must inherit from SecurityScanParser and implement
the parse() and validate() methods.
"""

from abc import ABC, abstractmethod
from typing import Any

import structlog

from certus_ask.schemas.unified_security_scan import UnifiedSecurityScan

logger = structlog.get_logger(__name__)


class SecurityScanParser(ABC):
    """Base class for all security tool parsers.

    Each parser converts a tool's native JSON format to UnifiedSecurityScan.

    Attributes:
        tool_name: Unique identifier for this tool (e.g., "sarif", "bandit")
        supported_versions: List of tool versions this parser supports
    """

    tool_name: str
    supported_versions: list[str] = []

    @abstractmethod
    def parse(self, raw_json: dict[str, Any]) -> UnifiedSecurityScan:
        """Parse tool JSON into UnifiedSecurityScan format.

        Args:
            raw_json: Raw JSON data from the security tool

        Returns:
            UnifiedSecurityScan with normalized findings

        Raises:
            ValueError: If JSON structure is invalid
            KeyError: If required fields are missing
        """
        pass

    @abstractmethod
    def validate(self, raw_json: dict[str, Any]) -> bool:
        """Check if JSON matches this tool's format.

        This is used for auto-detection. Should return True if the JSON
        appears to be from this tool.

        Args:
            raw_json: Raw JSON data to check

        Returns:
            True if JSON matches this tool's format, False otherwise
        """
        pass

    def __repr__(self) -> str:
        """String representation."""
        return f"{self.__class__.__name__}(tool_name={self.tool_name!r})"
