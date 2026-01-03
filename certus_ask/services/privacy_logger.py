"""Privacy incident logging and tracking service."""

from dataclasses import dataclass
from typing import Optional

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class PIIEntity:
    """Represents a detected PII entity."""

    entity_type: str  # e.g., "PERSON", "EMAIL", "PHONE_NUMBER", "CREDIT_CARD"
    value: str  # The actual detected value (masked in logs)
    confidence: float  # Confidence score 0-1
    start: int  # Character position in text
    end: int  # Character position in text
    original_text: Optional[str] = None  # Original context (optional)


@dataclass
class PrivacyIncident:
    """Represents a privacy incident during ingestion."""

    document_id: str
    document_name: str
    pii_entity_count: int
    entity_types: list[str]  # Unique entity types found
    entities: list[PIIEntity]  # Full entity details
    has_high_confidence_pii: bool  # Any entity with confidence > 0.9
    action: str  # "ANONYMIZED", "QUARANTINED", "REJECTED"
    reason: Optional[str] = None  # Why it was quarantined/rejected


class PrivacyLogger:
    """Service for logging privacy incidents with detailed PII tracking."""

    def __init__(self, strict_mode: bool = False, high_confidence_threshold: float = 0.9):
        """
        Initialize privacy logger.

        Args:
            strict_mode: If True, reject documents with any PII. If False, anonymize.
            high_confidence_threshold: Confidence score threshold for "high confidence" PII
        """
        self.strict_mode = strict_mode
        self.high_confidence_threshold = high_confidence_threshold
        self.incident_count = 0
        self.pii_entity_total = 0

    def log_pii_detection(
        self,
        document_id: str,
        document_name: str,
        analysis_results: list,
        action: str = "ANONYMIZED",
        reason: Optional[str] = None,
    ) -> PrivacyIncident:
        """
        Log detection of PII in a document with detailed entity information.

        Args:
            document_id: Unique identifier for the document
            document_name: Human-readable document name/path
            analysis_results: List of Presidio AnalysisResult objects
            action: What action was taken (ANONYMIZED, QUARANTINED, REJECTED)
            reason: Optional reason for quarantine/rejection

        Returns:
            PrivacyIncident object with all details
        """
        # Extract entity information
        entities = []
        entity_types_set = set()

        for result in analysis_results:
            entity = PIIEntity(
                entity_type=result.entity_type,
                value=f"<{result.entity_type}>",  # Don't log actual PII value
                confidence=result.score,
                start=result.start,
                end=result.end,
            )
            entities.append(entity)
            entity_types_set.add(result.entity_type)

        # Detect high-confidence PII
        has_high_confidence = any(e.confidence >= self.high_confidence_threshold for e in entities)

        incident = PrivacyIncident(
            document_id=document_id,
            document_name=document_name,
            pii_entity_count=len(entities),
            entity_types=sorted(entity_types_set),
            entities=entities,
            has_high_confidence_pii=has_high_confidence,
            action=action,
            reason=reason,
        )

        # Update statistics
        self.incident_count += 1
        self.pii_entity_total += len(entities)

        # Log the incident with structured data
        logger.info(
            event="privacy.scan_complete",
            doc_id=document_id,
            pii_entities_found=len(entities),
            entity_types=incident.entity_types,
            has_high_confidence=has_high_confidence,
            action=action,
            reason=reason,
            # Entity distribution by type
            entity_distribution={et: sum(1 for e in entities if e.entity_type == et) for et in entity_types_set},
        )

        # Log PII detected event if action requires it
        if action in ("QUARANTINED", "REJECTED", "ANONYMIZED"):
            logger.info(
                event="privacy.pii_detected",
                doc_id=document_id,
                severity="HIGH" if has_high_confidence else "MEDIUM",
                pii_count=len(entities),
                action=action,
                message=f"Document contains {len(entities)} PII entities - {action.lower()}",
            )

        # Log each entity with detailed information
        for idx, entity in enumerate(entities):
            logger.info(
                event="privacy.entity_detected",
                doc_id=document_id,
                entity_index=idx,
                entity_type=entity.entity_type,
                confidence=round(entity.confidence, 3),
                position_start=entity.start,
                position_end=entity.end,
                text_length=entity.end - entity.start,
            )

        # Log anonymization or quarantine event
        if action == "ANONYMIZED":
            logger.info(
                event="privacy.anonymization_complete",
                doc_id=document_id,
                entities_masked=len(entities),
            )
        elif action == "QUARANTINED":
            logger.warning(
                event="privacy.pii_detected",
                doc_id=document_id,
                severity="HIGH" if has_high_confidence else "MEDIUM",
                pii_count=len(entities),
                action="QUARANTINE",
                message=f"Document contains {len(entities)} PII entities - moved to quarantine",
            )

        return incident

    def log_quarantine(
        self,
        document_id: str,
        document_name: str,
        analysis_results: list,
        reason: str,
    ) -> PrivacyIncident:
        """
        Log when a document is quarantined due to PII detection.

        Args:
            document_id: Document identifier
            document_name: Document name/path
            analysis_results: List of Presidio AnalysisResult objects
            reason: Reason for quarantine

        Returns:
            PrivacyIncident object
        """
        return self.log_pii_detection(
            document_id=document_id,
            document_name=document_name,
            analysis_results=analysis_results,
            action="QUARANTINED",
            reason=reason,
        )

    def log_rejection(
        self,
        document_id: str,
        document_name: str,
        analysis_results: list,
        reason: str,
    ) -> PrivacyIncident:
        """
        Log when a document is rejected due to PII detection.

        Args:
            document_id: Document identifier
            document_name: Document name/path
            analysis_results: List of Presidio AnalysisResult objects
            reason: Reason for rejection

        Returns:
            PrivacyIncident object
        """
        return self.log_pii_detection(
            document_id=document_id,
            document_name=document_name,
            analysis_results=analysis_results,
            action="REJECTED",
            reason=reason,
        )

    def log_anonymization(
        self,
        document_id: str,
        document_name: str,
        analysis_results: list,
    ) -> PrivacyIncident:
        """
        Log when a document is successfully anonymized.

        Args:
            document_id: Document identifier
            document_name: Document name/path
            analysis_results: List of Presidio AnalysisResult objects

        Returns:
            PrivacyIncident object
        """
        return self.log_pii_detection(
            document_id=document_id,
            document_name=document_name,
            analysis_results=analysis_results,
            action="ANONYMIZED",
        )

    def get_statistics(self) -> dict:
        """Get privacy incident statistics."""
        return {
            "total_incidents": self.incident_count,
            "total_pii_entities_detected": self.pii_entity_total,
            "average_entities_per_incident": (
                self.pii_entity_total / self.incident_count if self.incident_count > 0 else 0
            ),
        }


__all__ = [
    "PIIEntity",
    "PrivacyIncident",
    "PrivacyLogger",
]
