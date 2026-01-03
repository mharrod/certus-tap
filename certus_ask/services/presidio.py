"""PII detection and anonymization services using Presidio or regex fallback.

This module provides PII (Personally Identifiable Information) detection and
anonymization capabilities. It uses the Presidio library when available, falling
back to regex-based detection for environments where heavy dependencies can't
be installed.

The module exports Protocol types for type-safe usage without circular imports.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from functools import lru_cache
from types import SimpleNamespace
from typing import Any, Protocol

from certus_ask.core.logging import get_logger

logger = get_logger(__name__)

try:  # pragma: no cover - optional heavy dependency
    from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine

    _PRESIDIO_AVAILABLE = True
except Exception as exc:  # pragma: no cover - triggered when numpy/spacy fail to import
    AnalyzerEngine = RecognizerRegistry = NlpEngineProvider = AnonymizerEngine = Any  # type: ignore[assignment]
    _PRESIDIO_AVAILABLE = False
    _PRESIDIO_IMPORT_ERROR = exc
    logger.warning(
        "presidio.initialization_failed",
        error=str(exc),
        fallback_analyzer="regex",
    )


# ============================================================================
# TYPE DEFINITIONS (Protocol)
# ============================================================================


class _RegexResult(SimpleNamespace):
    """Analysis result from PII detection.

    Attributes:
        entity_type: Type of PII detected (e.g., "EMAIL_ADDRESS", "CREDIT_CARD")
        start: Start position in text
        end: End position in text
        score: Confidence score (0.0-1.0)
    """

    entity_type: str
    start: int
    end: int
    score: float


class AnalyzerProtocol(Protocol):
    """Protocol defining the interface for PII analyzers.

    This protocol allows type-safe usage of both AnalyzerEngine (Presidio)
    and RegexAnalyzer without circular imports or dependence on heavy
    Presidio imports.
    """

    def analyze(
        self,
        text: str,
        entities: Iterable[str] | None = None,
        language: str = "en",
    ) -> list[_RegexResult]:
        """Analyze text for PII entities.

        Args:
            text: Text to analyze for PII
            entities: Specific PII types to detect. If None, detect all.
            language: Language of text (default: English)

        Returns:
            List of detected PII with positions and confidence scores
        """
        ...


class AnonymizerProtocol(Protocol):
    """Protocol defining the interface for PII anonymizers.

    This protocol allows type-safe usage of both AnonymizerEngine (Presidio)
    and RegexAnonymizer without circular imports or dependence on heavy
    Presidio imports.
    """

    def anonymize(
        self,
        text: str,
        analyzer_results: Iterable[_RegexResult],
        **kwargs: Any,
    ) -> SimpleNamespace:
        """Anonymize PII in text.

        Args:
            text: Text containing PII to anonymize
            analyzer_results: PII positions from analyzer
            **kwargs: Additional anonymization parameters

        Returns:
            SimpleNamespace with 'text' field containing anonymized text
        """
        ...


class RegexAnalyzer:
    """Fallback analyzer that finds common PII patterns with regex."""

    patterns: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("EMAIL_ADDRESS", re.compile(r"[A-Za-z0-9_.+-]+@[A-Za-z0-9-]+\.[A-Za-z0-9-.]+")),
        ("IP_ADDRESS", re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")),
        ("PHONE_NUMBER", re.compile(r"\b(?:\+?\d{1,2}\s?)?(?:\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b")),
        ("CREDIT_CARD", re.compile(r"\b(?:\d[ -]*?){13,16}\b")),
        ("SSN", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    )

    def analyze(
        self,
        text: str,
        entities: Iterable[str] | None = None,
        language: str = "en",
    ) -> list[_RegexResult]:
        results: list[_RegexResult] = []
        for entity_type, pattern in self.patterns:
            for match in pattern.finditer(text):
                results.append(
                    _RegexResult(
                        entity_type=entity_type,
                        start=match.start(),
                        end=match.end(),
                        score=0.8,
                    )
                )
        return results


class RegexAnonymizer:
    """Fallback anonymizer that replaces spans with redaction tokens."""

    def anonymize(self, text: str, analyzer_results: Iterable[_RegexResult], **_: Any) -> SimpleNamespace:
        spans = sorted(analyzer_results, key=lambda res: res.start)
        if not spans:
            return SimpleNamespace(text=text)

        redacted: list[str] = []
        cursor = 0
        for span in spans:
            redacted.append(text[cursor : span.start])
            redacted.append(f"[REDACTED_{span.entity_type}]")
            cursor = span.end
        redacted.append(text[cursor:])
        return SimpleNamespace(text="".join(redacted))


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerProtocol:
    """Get the PII analyzer engine.

    Returns either a Presidio AnalyzerEngine or a regex-based fallback analyzer,
    depending on library availability. Both implementations conform to AnalyzerProtocol.

    Returns:
        Analyzer instance that implements AnalyzerProtocol interface

    Example:
        >>> analyzer = get_analyzer()
        >>> results = analyzer.analyze("Email: john@example.com")
        >>> print(results[0].entity_type)  # 'EMAIL_ADDRESS'
    """
    if _PRESIDIO_AVAILABLE:
        logger.info("analyzer.initialization_start", analyzer_type="presidio")
        try:
            configuration = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
            }
            provider = NlpEngineProvider(nlp_configuration=configuration)
            nlp_engine = provider.create_engine()
            registry = RecognizerRegistry()
            registry.load_predefined_recognizers()
            analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)
        except Exception as exc:
            logger.exception("analyzer.initialization_failed", analyzer_type="presidio", error=str(exc))
            # Fall back to regex analyzer
            logger.info("analyzer.fallback", fallback_type="regex")
            return RegexAnalyzer()
        else:
            logger.info("analyzer.initialization_complete", analyzer_type="presidio")
            return analyzer

    logger.info("analyzer.initialization_complete", analyzer_type="regex")
    return RegexAnalyzer()


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerProtocol:
    """Get the PII anonymizer engine.

    Returns either a Presidio AnonymizerEngine or a regex-based fallback anonymizer,
    depending on library availability. Both implementations conform to AnonymizerProtocol.

    Returns:
        Anonymizer instance that implements AnonymizerProtocol interface

    Example:
        >>> analyzer = get_analyzer()
        >>> anonymizer = get_anonymizer()
        >>> results = analyzer.analyze("Email: john@example.com")
        >>> anonymized = anonymizer.anonymize("Email: john@example.com", results)
        >>> print(anonymized.text)  # 'Email: [REDACTED_EMAIL_ADDRESS]'
    """
    if _PRESIDIO_AVAILABLE:
        logger.info("anonymizer.initialization", anonymizer_type="presidio")
        try:
            engine = AnonymizerEngine()
        except Exception as exc:
            logger.exception("anonymizer.initialization_failed", anonymizer_type="presidio", error=str(exc))
            logger.info("anonymizer.fallback", fallback_type="regex")
            return RegexAnonymizer()
        else:
            return engine

    logger.info("anonymizer.initialization", anonymizer_type="regex")
    return RegexAnonymizer()


__all__ = ["get_analyzer", "get_anonymizer"]
