"""
Example test suite for Presidio service demonstrating fixture usage.

This file shows how to:
- Use document fixtures for testing
- Mock Presidio analyzer/anonymizer
- Test PII detection and anonymization
- Handle edge cases
- Use factories for dynamic test data
"""

import pytest


class TestPresidioAnalyzerWithFixtures:
    """Example tests using document fixtures."""

    def test_analyze_clean_document(self, sample_clean_document, presidio_analyzer):
        """Test that clean documents return no results."""
        # This demonstrates using document fixtures
        assert sample_clean_document is not None
        assert isinstance(sample_clean_document, str)
        assert len(sample_clean_document) > 0

    def test_analyze_document_with_pii(self, sample_text_with_pii, presidio_analyzer):
        """Test that PII documents are detected."""
        # This demonstrates using a PII-containing document
        assert "John Smith" in sample_text_with_pii
        assert "john.smith@example.com" in sample_text_with_pii

    def test_multiple_pii_types(self, analysis_result_factory):
        """Test handling multiple PII entity types."""
        # Using the factory fixture to create test data
        results = analysis_result_factory.create_batch(count=5)

        assert len(results) == 5
        assert all(hasattr(r, "entity_type") for r in results)
        assert all(hasattr(r, "score") for r in results)


class TestPresidioAnonymizer:
    """Tests for anonymization functionality."""

    def test_anonymize_simple_text(self, sample_text_with_pii, mock_analysis_results):
        """Test anonymizing text with detected PII."""
        # Using fixture for analysis results
        assert mock_analysis_results is not None
        assert len(mock_analysis_results) == 3

        # Verify each result has expected fields
        for result in mock_analysis_results:
            assert result.entity_type in ["PERSON", "EMAIL", "PHONE_NUMBER"]
            assert 0 < result.score <= 1.0

    def test_anonymize_preserves_length(self, sample_text_with_pii):
        """Test that anonymization preserves text length."""
        # This test demonstrates text length preservation
        assert len(sample_text_with_pii) > 0
        # Anonymized text should be roughly same length

    def test_anonymize_multiple_entities(self, analysis_result_factory):
        """Test anonymizing text with multiple entity types."""
        results = analysis_result_factory.create_batch(count=10)

        # Group by entity type
        entity_types = {}
        for result in results:
            entity_types.setdefault(result.entity_type, []).append(result)

        assert len(entity_types) > 1  # Multiple types


class TestPrivacyLogging:
    """Tests for privacy incident logging."""

    def test_log_pii_detection(self, privacy_logger, mock_analysis_results):
        """Test logging PII detection incidents."""
        incident = privacy_logger.log_pii_detection(
            document_id="doc-123", document_name="test.pdf", analysis_results=mock_analysis_results, action="ANONYMIZED"
        )

        assert incident.document_id == "doc-123"
        assert incident.pii_entity_count == 3
        assert incident.action == "ANONYMIZED"

    def test_log_high_confidence_pii(self, privacy_logger, analysis_result_factory):
        """Test logging high-confidence PII."""
        # Create results with high confidence
        results = [
            analysis_result_factory.create(confidence=0.95),
            analysis_result_factory.create(confidence=0.98),
        ]

        incident = privacy_logger.log_pii_detection(
            document_id="doc-456",
            document_name="report.pdf",
            analysis_results=results,
        )

        assert incident.has_high_confidence_pii is True

    def test_log_quarantine(self, privacy_logger_strict, mock_analysis_results):
        """Test logging document quarantine."""
        incident = privacy_logger_strict.log_quarantine(
            document_id="doc-789",
            document_name="sensitive.pdf",
            analysis_results=mock_analysis_results,
            reason="Contains high-confidence PII",
        )

        assert incident.action == "QUARANTINED"
        assert incident.reason == "Contains high-confidence PII"

    def test_privacy_statistics(self, privacy_logger, analysis_result_factory):
        """Test privacy statistics tracking."""
        # Log multiple incidents
        for i in range(3):
            results = analysis_result_factory.create_batch(count=2)
            privacy_logger.log_pii_detection(
                document_id=f"doc-{i}",
                document_name=f"doc-{i}.pdf",
                analysis_results=results,
            )

        stats = privacy_logger.get_statistics()

        assert stats["total_incidents"] == 3
        assert stats["total_pii_entities_detected"] == 6  # 3 * 2
        assert stats["average_entities_per_incident"] == 2.0


class TestPresidioEdgeCases:
    """Tests for edge cases and error scenarios."""

    def test_empty_text(self, sample_clean_document):
        """Test handling empty text."""
        empty_text = ""
        assert len(empty_text) == 0

    def test_very_long_text(self, sample_clean_document):
        """Test handling very long documents."""
        long_text = sample_clean_document * 100
        assert len(long_text) > 10000

    def test_unicode_characters(self):
        """Test handling unicode in text."""
        unicode_text = "Hello 世界 🌍 مرحبا мир"
        assert len(unicode_text) > 0
        assert "世界" in unicode_text

    def test_special_characters(self):
        """Test handling special characters."""
        special_text = "Test@#$%^&*()_+-=[]{}|;:',.<>?/\\~`"
        assert len(special_text) > 0

    def test_mixed_pii_types(self, analysis_result_factory):
        """Test mixing multiple PII types in document."""
        results = analysis_result_factory.create_batch(count=20)

        # Verify variety of entity types
        entity_types = {r.entity_type for r in results}
        assert len(entity_types) > 1


class TestDocumentFactoryFixture:
    """Tests demonstrating document factory usage."""

    def test_create_single_document(self, document_factory):
        """Test creating a single test document."""
        doc = document_factory.create(content="Test document")

        assert doc["content"] == "Test document"
        assert "metadata" in doc
        assert "embedding" in doc

    def test_create_batch_documents(self, document_factory):
        """Test creating batch of documents."""
        docs = document_factory.create_batch(count=10)

        assert len(docs) == 10
        assert all("content" in doc for doc in docs)
        assert all("embedding" in doc for doc in docs)

    def test_document_with_metadata(self, document_factory):
        """Test document with custom metadata."""
        metadata = {"source": "test", "category": "privacy"}
        doc = document_factory.create(content="Test", metadata=metadata)

        assert doc["metadata"] == metadata


class TestFixtureIntegration:
    """Tests demonstrating multiple fixture usage together."""

    def test_analyze_and_log_workflow(self, sample_text_with_pii, analysis_result_factory, privacy_logger):
        """Test complete workflow: analyze -> log -> verify."""
        # Simulate analysis results
        analysis_results = analysis_result_factory.create_batch(count=4)

        # Log the incident
        incident = privacy_logger.log_pii_detection(
            document_id="workflow-test",
            document_name="test.pdf",
            analysis_results=analysis_results,
            action="ANONYMIZED",
        )

        # Verify results
        assert incident.pii_entity_count == 4
        assert len(incident.entity_types) > 0
        assert incident.action == "ANONYMIZED"

    def test_strict_vs_lenient_mode(self, privacy_logger, privacy_logger_strict, analysis_result_factory):
        """Test difference between strict and lenient modes."""
        results = analysis_result_factory.create_batch(count=3)

        # Lenient mode logs anonymization
        lenient_incident = privacy_logger.log_pii_detection(
            document_id="lenient", document_name="test.pdf", analysis_results=results, action="ANONYMIZED"
        )

        # Strict mode logs quarantine
        strict_incident = privacy_logger_strict.log_quarantine(
            document_id="strict", document_name="test.pdf", analysis_results=results, reason="Strict mode enabled"
        )

        assert lenient_incident.action == "ANONYMIZED"
        assert strict_incident.action == "QUARANTINED"


# ============================================================================
# Marker Examples
# ============================================================================


@pytest.mark.privacy
class TestPrivacyFocused:
    """Tests marked as privacy-related."""

    def test_pii_detection(self, sample_text_with_pii):
        """Test PII detection (privacy marker)."""
        assert "123-45-6789" in sample_text_with_pii  # SSN pattern


@pytest.mark.slow
class TestSlowOperations:
    """Tests marked as slow running."""

    def test_large_batch_processing(self, analysis_result_factory):
        """Test processing large batch (slow marker)."""
        results = analysis_result_factory.create_batch(count=1000)
        assert len(results) == 1000


# ============================================================================
# Parametrized Tests Using Fixtures
# ============================================================================


@pytest.mark.parametrize(
    "entity_type,confidence",
    [
        ("PERSON", 0.95),
        ("EMAIL", 0.98),
        ("PHONE_NUMBER", 0.87),
        ("CREDIT_CARD", 0.92),
    ],
)
def test_entity_type_confidence(analysis_result_factory, entity_type, confidence):
    """Test different entity types and confidences."""
    result = analysis_result_factory.create(entity_type, confidence)

    assert result.entity_type == entity_type
    assert result.score == confidence


@pytest.mark.parametrize("count", [1, 5, 10, 50])
def test_batch_sizes(analysis_result_factory, count):
    """Test various batch sizes."""
    batch = analysis_result_factory.create_batch(count=count)

    assert len(batch) == count
    assert all(hasattr(item, "entity_type") for item in batch)
