"""Severity mapping for security tools.

Normalizes tool-specific severity levels to a standard set:
- CRITICAL: Immediate action required
- HIGH: Serious issue, fix soon
- MEDIUM: Moderate issue, should be addressed
- LOW: Minor issue, can be scheduled
- INFO: Informational, not a security issue

Each tool uses different severity levels, which are mapped to the standard
set using the mappings defined in this module.
"""

import structlog

logger = structlog.get_logger(__name__)

# Default mappings for common tools
# Add more tools as they're implemented

SEVERITY_MAPPINGS = {
    "sarif": {
        # SARIF spec uses note/warning/error, but many tools emit normalized HIGH/H/M/L.
        "ERROR": "HIGH",
        "WARNING": "MEDIUM",
        "NOTE": "LOW",
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
        "CRITICAL": "CRITICAL",
    },
    "bandit": {
        # Bandit uses: HIGH, MEDIUM, LOW
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
    },
    "opengrep": {
        # OpenGrep uses: ERROR, WARNING, etc.
        "ERROR": "HIGH",
        "WARNING": "MEDIUM",
    },
    "trivy": {
        # Trivy uses: CRITICAL, HIGH, MEDIUM, LOW, UNKNOWN
        "CRITICAL": "CRITICAL",
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
        "UNKNOWN": "INFO",
    },
}

# Standard severity levels
STANDARD_SEVERITIES = {"CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"}


def normalize_severity(
    severity: str | None,
    tool_name: str,
    default: str = "INFO",
) -> str:
    """Normalize tool-specific severity to standard level.

    Args:
        severity: Tool-specific severity string
        tool_name: Name of the tool (for mapping lookup)
        default: Default severity if input is None or unknown

    Returns:
        Normalized severity (CRITICAL, HIGH, MEDIUM, LOW, or INFO)
    """
    if severity is None:
        logger.debug("severity_normalization.missing_value", tool=tool_name, default=default)
        return default

    # Check if already standard
    if severity in STANDARD_SEVERITIES:
        return severity

    # Look up tool-specific mapping
    tool_mappings = SEVERITY_MAPPINGS.get(tool_name, {})
    normalized = tool_mappings.get(severity.upper(), default)

    if normalized == default and severity not in tool_mappings:
        logger.warning(
            "severity_normalization.unknown_level",
            tool=tool_name,
            input_severity=severity,
            normalized_to=normalized,
        )

    return normalized


def get_severity_mappings(tool_name: str) -> dict[str, str]:
    """Get severity mappings for a specific tool.

    Args:
        tool_name: Name of the tool

    Returns:
        Dictionary mapping tool severities to standard severities (copy)
    """
    return SEVERITY_MAPPINGS.get(tool_name, {}).copy()
