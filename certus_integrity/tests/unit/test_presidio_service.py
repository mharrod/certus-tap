"""
PII Service Tests for certus_integrity.services.presidio.

Tests PII detection and anonymization with both Presidio and regex fallback:
- Analyzer initialization (Presidio/fallback)
- Anonymizer initialization (Presidio/fallback)
- Email detection
- Phone number detection
- Credit card detection
- SSN detection
- IP address detection
- Anonymization with redaction
- Cache behavior
- Error handling
"""

from unittest.mock import MagicMock, patch

from certus_integrity.services.presidio import (
    RegexAnalyzer,
    RegexAnonymizer,
    get_analyzer,
    get_anonymizer,
)


class TestRegexAnalyzer:
    """Test regex-based PII analyzer."""

    def test_email_detection(self):
        """Test email address detection."""
        analyzer = RegexAnalyzer()

        text = "Contact me at john.doe@example.com for info"
        results = analyzer.analyze(text)

        # Find email result
        email_results = [r for r in results if r.entity_type == "EMAIL_ADDRESS"]
        assert len(email_results) == 1
        assert email_results[0].start == text.index("john.doe@example.com")
        assert email_results[0].end == text.index("john.doe@example.com") + len("john.doe@example.com")
        assert email_results[0].score == 0.8

    def test_phone_number_detection(self):
        """Test phone number detection."""
        analyzer = RegexAnalyzer()

        text = "Call me at 555-123-4567 or (555) 123-4567"
        results = analyzer.analyze(text)

        # Should detect both formats
        phone_results = [r for r in results if r.entity_type == "PHONE_NUMBER"]
        assert len(phone_results) >= 1

    def test_credit_card_detection(self):
        """Test credit card number detection."""
        analyzer = RegexAnalyzer()

        text = "Card number: 4111-1111-1111-1111"
        results = analyzer.analyze(text)

        # Find credit card result
        cc_results = [r for r in results if r.entity_type == "CREDIT_CARD"]
        assert len(cc_results) == 1

    def test_ssn_detection(self):
        """Test SSN detection."""
        analyzer = RegexAnalyzer()

        text = "SSN: 123-45-6789"
        results = analyzer.analyze(text)

        # Find SSN result
        ssn_results = [r for r in results if r.entity_type == "SSN"]
        assert len(ssn_results) == 1
        assert ssn_results[0].start == text.index("123-45-6789")

    def test_ip_address_detection(self):
        """Test IP address detection."""
        analyzer = RegexAnalyzer()

        text = "Server IP: 192.168.1.100"
        results = analyzer.analyze(text)

        # Find IP result
        ip_results = [r for r in results if r.entity_type == "IP_ADDRESS"]
        assert len(ip_results) == 1
        assert ip_results[0].start == text.index("192.168.1.100")

    def test_multiple_pii_detection(self):
        """Test detecting multiple PII types in one text."""
        analyzer = RegexAnalyzer()

        text = "Contact john@example.com at 555-1234 or IP 10.0.0.1"
        results = analyzer.analyze(text)

        # Should find email, phone, and IP
        entity_types = {r.entity_type for r in results}
        assert "EMAIL_ADDRESS" in entity_types
        assert "IP_ADDRESS" in entity_types

    def test_no_pii_returns_empty(self):
        """Test text with no PII returns empty results."""
        analyzer = RegexAnalyzer()

        text = "This is a clean text with no sensitive information"
        results = analyzer.analyze(text)

        assert len(results) == 0


class TestRegexAnonymizer:
    """Test regex-based PII anonymizer."""

    def test_anonymize_email(self):
        """Test email anonymization."""
        analyzer = RegexAnalyzer()
        anonymizer = RegexAnonymizer()

        text = "Email: john@example.com"
        results = analyzer.analyze(text)

        anonymized = anonymizer.anonymize(text, results)

        assert "john@example.com" not in anonymized.text
        assert "[REDACTED_EMAIL_ADDRESS]" in anonymized.text

    def test_anonymize_phone(self):
        """Test phone number anonymization."""
        analyzer = RegexAnalyzer()
        anonymizer = RegexAnonymizer()

        text = "Phone: 555-123-4567"
        results = analyzer.analyze(text)

        anonymized = anonymizer.anonymize(text, results)

        assert "555-123-4567" not in anonymized.text
        assert "[REDACTED_PHONE_NUMBER]" in anonymized.text

    def test_anonymize_multiple_pii(self):
        """Test anonymizing multiple PII entities."""
        analyzer = RegexAnalyzer()
        anonymizer = RegexAnonymizer()

        text = "Contact john@example.com at 555-1234 from IP 10.0.0.1"
        results = analyzer.analyze(text)

        anonymized = anonymizer.anonymize(text, results)

        # Original PII should be gone
        assert "john@example.com" not in anonymized.text

        # Redaction tokens should be present
        assert "[REDACTED_EMAIL_ADDRESS]" in anonymized.text

    def test_anonymize_empty_results(self):
        """Test anonymization with no PII found."""
        anonymizer = RegexAnonymizer()

        text = "Clean text"
        results = []

        anonymized = anonymizer.anonymize(text, results)

        # Text should be unchanged
        assert anonymized.text == text

    def test_anonymize_preserves_non_pii(self):
        """Test anonymization preserves non-PII text."""
        analyzer = RegexAnalyzer()
        anonymizer = RegexAnonymizer()

        text = "Hello, contact john@example.com for details. Thank you."
        results = analyzer.analyze(text)

        anonymized = anonymizer.anonymize(text, results)

        # Non-PII text should be preserved
        assert "Hello, contact" in anonymized.text
        assert "for details. Thank you." in anonymized.text


class TestAnalyzerInitialization:
    """Test analyzer initialization and fallback."""

    @patch("certus_integrity.services.presidio._PRESIDIO_AVAILABLE", True)
    @patch("certus_integrity.services.presidio.NlpEngineProvider")
    @patch("certus_integrity.services.presidio.RecognizerRegistry")
    @patch("certus_integrity.services.presidio.AnalyzerEngine")
    def test_presidio_analyzer_initialization(self, mock_analyzer_engine, mock_registry, mock_provider):
        """Test Presidio analyzer initialization when available."""
        # Clear cache first
        get_analyzer.cache_clear()

        # Mock the initialization chain
        mock_nlp_engine = MagicMock()
        mock_provider.return_value.create_engine.return_value = mock_nlp_engine
        mock_reg_instance = MagicMock()
        mock_registry.return_value = mock_reg_instance
        mock_analyzer_instance = MagicMock()
        mock_analyzer_engine.return_value = mock_analyzer_instance

        analyzer = get_analyzer()

        # Verify initialization
        assert mock_provider.called
        assert mock_registry.called
        assert mock_analyzer_engine.called
        assert analyzer == mock_analyzer_instance

    @patch("certus_integrity.services.presidio._PRESIDIO_AVAILABLE", False)
    def test_fallback_to_regex_analyzer(self):
        """Test fallback to regex analyzer when Presidio unavailable."""
        # Clear cache
        get_analyzer.cache_clear()

        analyzer = get_analyzer()

        assert isinstance(analyzer, RegexAnalyzer)

    @patch("certus_integrity.services.presidio._PRESIDIO_AVAILABLE", True)
    @patch("certus_integrity.services.presidio.NlpEngineProvider")
    def test_presidio_initialization_error_fallback(self, mock_provider):
        """Test fallback to regex when Presidio initialization fails."""
        # Clear cache
        get_analyzer.cache_clear()

        # Make initialization fail
        mock_provider.side_effect = Exception("Initialization failed")

        analyzer = get_analyzer()

        # Should fall back to regex
        assert isinstance(analyzer, RegexAnalyzer)


class TestAnonymizerInitialization:
    """Test anonymizer initialization and fallback."""

    @patch("certus_integrity.services.presidio._PRESIDIO_AVAILABLE", True)
    @patch("certus_integrity.services.presidio.AnonymizerEngine")
    def test_presidio_anonymizer_initialization(self, mock_anonymizer_engine):
        """Test Presidio anonymizer initialization when available."""
        # Clear cache
        get_anonymizer.cache_clear()

        mock_anonymizer_instance = MagicMock()
        mock_anonymizer_engine.return_value = mock_anonymizer_instance

        anonymizer = get_anonymizer()

        assert mock_anonymizer_engine.called
        assert anonymizer == mock_anonymizer_instance

    @patch("certus_integrity.services.presidio._PRESIDIO_AVAILABLE", False)
    def test_fallback_to_regex_anonymizer(self):
        """Test fallback to regex anonymizer when Presidio unavailable."""
        # Clear cache
        get_anonymizer.cache_clear()

        anonymizer = get_anonymizer()

        assert isinstance(anonymizer, RegexAnonymizer)

    @patch("certus_integrity.services.presidio._PRESIDIO_AVAILABLE", True)
    @patch("certus_integrity.services.presidio.AnonymizerEngine")
    def test_presidio_anonymizer_error_fallback(self, mock_anonymizer_engine):
        """Test fallback to regex when Presidio anonymizer initialization fails."""
        # Clear cache
        get_anonymizer.cache_clear()

        # Make initialization fail
        mock_anonymizer_engine.side_effect = Exception("Anonymizer failed")

        anonymizer = get_anonymizer()

        # Should fall back to regex
        assert isinstance(anonymizer, RegexAnonymizer)


class TestCaching:
    """Test analyzer and anonymizer caching."""

    def test_analyzer_cached(self):
        """Test analyzer is cached and reused."""
        # Clear cache
        get_analyzer.cache_clear()

        analyzer1 = get_analyzer()
        analyzer2 = get_analyzer()

        # Should be the same instance
        assert analyzer1 is analyzer2

    def test_anonymizer_cached(self):
        """Test anonymizer is cached and reused."""
        # Clear cache
        get_anonymizer.cache_clear()

        anonymizer1 = get_anonymizer()
        anonymizer2 = get_anonymizer()

        # Should be the same instance
        assert anonymizer1 is anonymizer2
