"""Feature detection system for optional dependencies.

This module detects which optional features are available based on
installed packages. It allows the application to gracefully handle
missing optional dependencies and provide helpful error messages.

Usage:
    >>> from certus_ask.core.features import Features
    >>>
    >>> if Features.WEB_SCRAPING:
    ...     from certus_ask.routers import web
    ...     app.include_router(web.router)
    >>>
    >>> if not Features.EVALUATION:
    ...     logger.warning("Evaluation features not available")
"""

from importlib.util import find_spec
from typing import ClassVar, Optional

import structlog

logger = structlog.get_logger(__name__)


class Features:
    """Feature availability detection based on installed packages.

    This class checks for the presence of optional dependencies and
    provides information about which features are available.

    Features are lazily evaluated on first access and cached.

    Examples:
        >>> # Check if web scraping is available
        >>> if Features.WEB_SCRAPING:
        ...     crawl_website("https://example.com")

        >>> # Get installation command for missing feature
        >>> if not Features.EVALUATION:
        ...     cmd = Features.install_command("eval")
        ...     logger.error(f"Install with: {cmd}")
    """

    # Feature flags - checked on first access
    _WEB_SCRAPING: Optional[bool] = None
    _DOCUMENTS: Optional[bool] = None
    _EVALUATION: Optional[bool] = None
    _LLM_LOCAL: Optional[bool] = None
    _GIT_INTEGRATION: Optional[bool] = None

    # Mapping of feature names to package names
    _FEATURE_PACKAGES: ClassVar[dict[str, list[str]]] = {
        "WEB_SCRAPING": ["scrapy", "playwright"],
        "DOCUMENTS": ["pypdf", "docx", "pptx"],
        "EVALUATION": ["deepeval", "mlflow"],
        "LLM_LOCAL": ["ollama_haystack"],
        "GIT_INTEGRATION": ["git"],
    }

    # Mapping of feature names to extras group names
    _FEATURE_EXTRAS: ClassVar[dict[str, str]] = {
        "WEB_SCRAPING": "web",
        "DOCUMENTS": "documents",
        "EVALUATION": "eval",
        "LLM_LOCAL": "llm",
        "GIT_INTEGRATION": "git",
    }

    @classmethod
    def _check_feature(cls, feature_name: str) -> bool:
        """Check if a feature is available.

        Args:
            feature_name: Name of the feature to check (e.g., "WEB_SCRAPING")

        Returns:
            True if all required packages for the feature are installed
        """
        required_packages = cls._FEATURE_PACKAGES.get(feature_name, [])
        available = all(find_spec(pkg) is not None for pkg in required_packages)

        if available:
            logger.debug(
                "feature.detected",
                feature=feature_name,
                packages=required_packages,
            )
        else:
            logger.debug(
                "feature.not_available",
                feature=feature_name,
                missing_packages=[pkg for pkg in required_packages if find_spec(pkg) is None],
            )

        return available

    @classmethod
    def _reset_cache(cls) -> None:
        """Reset the feature detection cache.

        Useful for testing or if dependencies are installed at runtime.
        """
        cls._WEB_SCRAPING = None
        cls._DOCUMENTS = None
        cls._EVALUATION = None
        cls._LLM_LOCAL = None
        cls._GIT_INTEGRATION = None

    @classmethod
    def WEB_SCRAPING(cls) -> bool:
        """Check if web scraping features are available.

        Requires: scrapy, playwright, trafilatura, etc.
        Install with: pip install 'certus-tap[web]'

        Returns:
            True if web scraping dependencies are installed
        """
        if cls._WEB_SCRAPING is None:
            cls._WEB_SCRAPING = cls._check_feature("WEB_SCRAPING")
        return cls._WEB_SCRAPING

    @classmethod
    def DOCUMENTS(cls) -> bool:
        """Check if advanced document processing is available.

        Requires: pypdf, python-docx, python-pptx, etc.
        Install with: pip install 'certus-tap[documents]'

        Returns:
            True if document processing dependencies are installed
        """
        if cls._DOCUMENTS is None:
            cls._DOCUMENTS = cls._check_feature("DOCUMENTS")
        return cls._DOCUMENTS

    @classmethod
    def EVALUATION(cls) -> bool:
        """Check if evaluation features are available.

        Requires: deepeval, mlflow
        Install with: pip install 'certus-tap[eval]'

        Returns:
            True if evaluation dependencies are installed
        """
        if cls._EVALUATION is None:
            cls._EVALUATION = cls._check_feature("EVALUATION")
        return cls._EVALUATION

    @classmethod
    def LLM_LOCAL(cls) -> bool:
        """Check if local LLM features are available.

        Requires: ollama-haystack, spacy
        Install with: pip install 'certus-tap[llm]'

        Returns:
            True if local LLM dependencies are installed
        """
        if cls._LLM_LOCAL is None:
            cls._LLM_LOCAL = cls._check_feature("LLM_LOCAL")
        return cls._LLM_LOCAL

    @classmethod
    def GIT_INTEGRATION(cls) -> bool:
        """Check if Git integration features are available.

        Requires: gitpython
        Install with: pip install 'certus-tap[git]'

        Returns:
            True if Git dependencies are installed
        """
        if cls._GIT_INTEGRATION is None:
            cls._GIT_INTEGRATION = cls._check_feature("GIT_INTEGRATION")
        return cls._GIT_INTEGRATION

    @classmethod
    def DATALAKE(cls) -> bool:
        """Check if datalake features are available.

        Requires: Same as DOCUMENTS (pypdf, python-docx, etc.)
        Install with: pip install 'certus-tap[documents]'

        Returns:
            True if datalake dependencies are installed
        """
        return cls.DOCUMENTS()

    @classmethod
    def install_command(cls, feature: str) -> str:
        """Get the pip install command for a missing feature.

        Args:
            feature: Feature name (uppercase, e.g., "WEB_SCRAPING")

        Returns:
            pip install command as a string

        Examples:
            >>> Features.install_command("WEB_SCRAPING")
            "pip install 'certus-tap[web]'"

            >>> Features.install_command("EVALUATION")
            "pip install 'certus-tap[eval]'"
        """
        extras = cls._FEATURE_EXTRAS.get(feature)
        if not extras:
            return "pip install 'certus-tap[all]'"
        return f"pip install 'certus-tap[{extras}]'"

    @classmethod
    def get_available_features(cls) -> dict[str, bool]:
        """Get availability of all features.

        Returns:
            Dictionary mapping feature names to availability status

        Examples:
            >>> Features.get_available_features()
            {
                'WEB_SCRAPING': False,
                'DOCUMENTS': True,
                'EVALUATION': False,
                'LLM_LOCAL': False,
                'GIT_INTEGRATION': True,
                'DATALAKE': True
            }
        """
        return {
            "WEB_SCRAPING": cls.WEB_SCRAPING(),
            "DOCUMENTS": cls.DOCUMENTS(),
            "EVALUATION": cls.EVALUATION(),
            "LLM_LOCAL": cls.LLM_LOCAL(),
            "GIT_INTEGRATION": cls.GIT_INTEGRATION(),
            "DATALAKE": cls.DATALAKE(),
        }

    @classmethod
    def log_feature_summary(cls) -> None:
        """Log a summary of available features at startup."""
        features = cls.get_available_features()
        available = [name for name, available in features.items() if available]
        unavailable = [name for name, available in features.items() if not available]

        logger.info(
            "features.summary",
            available_features=available,
            unavailable_features=unavailable,
            total_available=len(available),
        )

        if unavailable:
            logger.debug(
                "features.installation_hints",
                missing_features={feature: cls.install_command(feature) for feature in unavailable},
            )
