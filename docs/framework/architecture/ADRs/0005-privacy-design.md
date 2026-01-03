# ADR-0005: Privacy-First Design with PII Detection

## Status
**Accepted**

## Date
2025-11-14

## Context

### Problem
Certus-TAP processes documents that may contain Personally Identifiable Information (PII) like:
- Email addresses
- Phone numbers
- Credit card numbers
- Social security numbers
- Names and addresses

The system needed to:

1. **Detect PII automatically** - Don't rely on manual review
2. **Prevent exposure** - Never store unmasked PII in indexes/logs unnecessarily
3. **Support compliance** - Audit trail for regulatory requirements (GDPR, CCPA, etc.)
4. **Be flexible** - Support both quarantine (reject) and anonymize (mask) modes
5. **Provide visibility** - Track what PII was detected and actions taken

### Current State (Before)
- No PII detection
- Documents with sensitive data could be indexed unmasked
- No audit trail for privacy incidents
- No compliance documentation

### Constraints
- Must work with existing document processing pipeline
- Should not significantly slow ingestion
- Must integrate with structured logging for audit trail
- Should support both strict (quarantine) and lenient (anonymize) modes
- Must handle fallback when Presidio unavailable (regex patterns)

## Decision

We chose **privacy-first design with Presidio-based detection, dual modes, and structured audit logging** because:

### 1. Automatic PII Detection with Presidio

```python
from presidio_analyzer import AnalyzerEngine

analyzer = AnalyzerEngine()
results = analyzer.analyze(text="Email: john@example.com")
# Returns: [RecognizerResult(entity_type="EMAIL_ADDRESS", start=7, end=25, score=0.95)]
```

Benefits:
- **Accurate** - ML-based detection (not just regex)
- **Contextual** - Understands context (not just patterns)
- **Comprehensive** - Detects 15+ PII types
- **Configurable** - Can enable/disable specific entity types
- **Industry standard** - Used by Microsoft, widely trusted

### 2. Dual Processing Modes

```python
# Mode 1: Quarantine (Strict)
if high_confidence_pii_detected:
    document.status = "quarantined"
    document.not_indexed = True
    log_incident("PII_DETECTED", action="QUARANTINE")

# Mode 2: Anonymize (Lenient)
if pii_detected:
    anonymized_text = anonymizer.anonymize(text, pii_results)
    document.content = anonymized_text  # Masked version
    log_incident("PII_DETECTED", action="ANONYMIZED")
```

Benefits:
- **Flexible** - Support different organizational policies
- **Configurable** - Switch modes via settings
- **Explicit** - Clear action taken for each document
- **Audit-friendly** - Both actions are logged

### 3. Structured Privacy Audit Logging

```python
privacy_logger.log_pii_detection(
    pii_type="CREDIT_CARD",
    confidence=0.98,
    position=(100, 116),
    document_id="doc-123",
    action="ANONYMIZED"
)

# Creates searchable event in OpenSearch:
# {
#   "event": "privacy.pii_detected",
#   "pii_type": "CREDIT_CARD",
#   "confidence": 0.98,
#   "position": [100, 116],
#   "document_id": "doc-123",
#   "action": "ANONYMIZED",
#   "request_id": "550e8400-e29b-41d4-a716-446655440000",
#   "timestamp": "2025-11-14T10:30:45.123Z"
# }
```

Benefits:
- **Queryable** - Search incidents by type, confidence, action
- **Traceable** - Request ID correlates all operations
- **Compliant** - Creates audit trail for regulations
- **Incident detection** - Can alert on suspicious patterns

### 4. Graceful Fallback to Regex

```python
def get_analyzer() -> AnalyzerProtocol:
    if _PRESIDIO_AVAILABLE:
        # Use ML-based detection
        return AnalyzerEngine()
    else:
        # Fallback: regex patterns for common PII
        return RegexAnalyzer()
```

Benefits:
- **Resilient** - Works even if Presidio unavailable
- **Lightweight** - Regex doesn't require ML models
- **Reasonable** - Catches most obvious PII patterns
- **Documented** - Clear fallback behavior

### 5. Per-Entity Detailed Logging

Each detected PII instance creates separate log entry:

```
Document contains 3 PII entities:
1. EMAIL_ADDRESS at position 50-70, confidence 0.95
2. PHONE_NUMBER at position 100-115, confidence 0.92
3. CREDIT_CARD at position 200-220, confidence 0.98

Creates 3 separate searchable events (plus document summary event)
```

Benefits:
- **Granular tracking** - Know exactly what was detected
- **Compliance** - Document-level and entity-level records
- **Analysis** - Can compute statistics per entity type
- **Incident response** - Specific details for investigation

## Architecture

```
Document Ingestion
      ↓
Document Preprocessing Pipeline
      ├─ Extract text
      ├─ Detect encoding/format
      ├─ Privacy Scanner (NEW)
      │  ├─ Presidio Analyzer
      │  │  └─ Returns: entity_type, confidence, position
      │  ├─ If Presidio unavailable: RegexAnalyzer
      │  └─ Creates Privacy Logger events
      ├─ Decision Point
      │  ├─ STRICT MODE (Quarantine)
      │  │  └─ Document marked quarantined
      │  │     (Not indexed, logged for review)
      │  └─ LENIENT MODE (Anonymize)
      │     └─ Presidio Anonymizer masks detected entities
      │        Document indexed with masked content
      ├─ Index document (if not quarantined)
      └─ Log incident (structured event)
      ↓
Structured Privacy Events in OpenSearch
└─ Queryable audit trail
```

## Consequences

### Positive
✅ **Automatic detection** - Finds PII without manual review
✅ **Audit compliance** - Complete trail for regulatory requirements
✅ **Flexible policies** - Support quarantine or anonymize modes
✅ **Graceful fallback** - Works without Presidio (regex)
✅ **Searchable incidents** - Query by PII type, confidence, action
✅ **Per-entity tracking** - Know exactly what was detected
✅ **Request correlation** - Link to complete ingestion context
✅ **Transparency** - Clear logging of actions taken

### Negative
❌ **Additional dependency** - Presidio adds to requirements
❌ **Performance impact** - Detection adds latency to ingestion
❌ **False positives** - May detect non-PII as PII (remedied by confidence threshold)
❌ **False negatives** - May miss some PII patterns (acceptable, better than exposed)
❌ **Storage overhead** - Privacy events increase log volume

### Neutral
◯ **Model size** - Presidio models require ~500MB storage
◯ **Maintenance** - Must keep Presidio updated for new patterns

## Alternatives Considered

### 1. No PII Detection
```python
# Process documents as-is, no screening
document.index()  # May contain unmasked PII
```
**Rejected** - Privacy risk, non-compliant, no audit trail

### 2. Manual Review Only
```python
# Require human to review before indexing
document.status = "pending_review"
# Human: "looks safe, index it"
```
**Rejected** - Doesn't scale, expensive, error-prone

### 3. Regex Only (No ML)
```python
# Use simple regex patterns
if re.search(r"\d{3}-\d{2}-\d{4}", text):  # SSN pattern
    quarantine_document()
```
**Rejected** - High false negatives, misses contextual PII, not accurate

### 4. Always Quarantine (Never Anonymize)
```python
if any_pii_detected:
    quarantine_document()  # Always reject
```
**Rejected** - Too restrictive, prevents legitimate use cases

### 5. Always Anonymize (Never Quarantine)
```python
anonymized = anonymizer.anonymize(text)  # Always mask
document.index(anonymized)
```
**Rejected** - May mask important context, loses precision

### 6. External PII Detection Service
```python
# Call third-party API for detection
response = external_service.detect_pii(text)
```
**Rejected** - Adds latency, cost, privacy risk, network dependency

## Implementation Details

### Presidio Analyzer Setup

```python
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_analyzer.nlp_engine import NlpEngineProvider

# Load NLP model (English language)
configuration = {
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
}
provider = NlpEngineProvider(nlp_configuration=configuration)
nlp_engine = provider.create_engine()

# Create analyzer with standard recognizers
registry = RecognizerRegistry()
registry.load_predefined_recognizers()
analyzer = AnalyzerEngine(nlp_engine=nlp_engine, registry=registry)

# Analyze text
results = analyzer.analyze(text="Email: john@example.com")
```

### Privacy Logger Integration

```python
class PrivacyLogger:
    """Structured logging for privacy incidents"""

    def log_pii_detection(
        self,
        pii_type: str,
        confidence: float,
        position: tuple[int, int],
        document_id: str
    ) -> None:
        """Log detected PII entity"""
        logger.info(
            "privacy.pii_detected",
            pii_type=pii_type,
            confidence=confidence,
            position=position,
            document_id=document_id
        )

    def log_quarantine(self, document_id: str, pii_types: list[str]) -> None:
        """Log quarantined document"""
        logger.warning(
            "privacy.document_quarantined",
            document_id=document_id,
            pii_types=pii_types,
            action="QUARANTINE"
        )

    def log_anonymization(self, document_id: str) -> None:
        """Log anonymized document"""
        logger.info(
            "privacy.document_anonymized",
            document_id=document_id,
            action="ANONYMIZED"
        )
```

### Configuration

```python
class Settings(BaseSettings):
    # Privacy mode: "strict" (quarantine) or "lenient" (anonymize)
    privacy_mode: str = Field(default="lenient", env="PRIVACY_MODE")

    # Confidence threshold (0.0-1.0) for triggering actions
    privacy_confidence_threshold: float = Field(
        default=0.9,
        env="PRIVACY_CONFIDENCE_THRESHOLD"
    )
```

### Pipeline Integration

```python
@component.output_types(documents=list[Document], quarantined=list[Document])
def run(self, documents: list[Document]) -> dict:
    """Process documents with privacy screening"""
    indexed_documents = []
    quarantined_documents = []

    for doc in documents:
        # Detect PII
        results = self.analyzer.analyze(doc.content)

        # Log all detected entities
        for entity in results:
            privacy_logger.log_pii_detection(
                pii_type=entity.entity_type,
                confidence=entity.score,
                position=(entity.start, entity.end),
                document_id=doc.id
            )

        # Filter by confidence threshold
        high_confidence = [r for r in results if r.score >= self.confidence_threshold]

        if high_confidence and self.strict_mode:
            # Quarantine mode: reject document
            privacy_logger.log_quarantine(doc.id, [r.entity_type for r in high_confidence])
            quarantined_documents.append(doc)
        elif high_confidence:
            # Anonymize mode: mask detected entities
            anonymized = self.anonymizer.anonymize(doc.content, results)
            doc.content = anonymized.text
            privacy_logger.log_anonymization(doc.id)
            indexed_documents.append(doc)
        else:
            # No PII detected
            indexed_documents.append(doc)

    return {
        "documents": indexed_documents,
        "quarantined": quarantined_documents
    }
```

### OpenSearch Queries for Incident Investigation

Find all high-confidence PII detections:
```
GET logs-certus-tap-*/_search
{
  "query": {
    "bool": {
      "must": [
        {"term": {"event.keyword": "privacy.pii_detected"}},
        {"range": {"confidence": {"gte": 0.9}}}
      ]
    }
  },
  "size": 100
}
```

Find all quarantined documents:
```
GET logs-certus-tap-*/_search
{
  "query": {
    "term": {"action.keyword": "QUARANTINE"}
  }
}
```

Find all CREDIT_CARD detections:
```
GET logs-certus-tap-*/_search
{
  "query": {
    "term": {"pii_type.keyword": "CREDIT_CARD"}
  }
}
```

## Trade-offs Made

| Decision | Why | Trade-off |
|----------|-----|-----------|
| Dual modes | Flexibility | More complex configuration |
| Presidio ML | Accurate detection | Slower than regex, requires models |
| Regex fallback | Resilience | Lower detection accuracy without Presidio |
| Per-entity logging | Compliance | More log volume |
| Confidence threshold | Reduce false positives | May miss some PII |
| Structured logging | Queryable audit trail | Requires OpenSearch storage |

## Compliance Implications

### GDPR
- **Article 32** (Security) - Automatic PII detection + masking satisfies
- **Article 33** (Breach notification) - Audit trail enables incident response
- **Article 35** (DPIA) - Document processing risks mitigated

### CCPA
- **Consumer Rights** - Can query audit trail for data subject rights requests
- **Security** - Demonstrates reasonable security measures
- **Transparency** - Clear logging of what happened to data

### HIPAA
- **Safeguards** - Access controls + audit logging
- **Breach notification** - Audit trail supports incident response

## Related ADRs

- **ADR-0001** - Structured Logging (privacy events logged)
- **ADR-0003** - Error Handling (privacy violations raise exceptions)

## References

### Implementation
- [Privacy Logger Service](../../certus_ask/services/privacy_logger.py)
- [Preprocessing Pipeline](../../certus_ask/pipelines/preprocessing.py)
- [Presidio Analyzer](../../certus_ask/services/presidio.py)

### Documentation
- [Privacy Operations Guide](../Logging/privacy-operations.md)
- [Privacy Queries](../Logging/privacy-queries.md)
- [Privacy Logging Implementation](../Logging/PRIVACY_LOGGING_IMPLEMENTATION.md)

### Standards
- [Presidio Documentation](https://microsoft.github.io/presidio/)
- [GDPR Compliance Checklist](https://gdpr-info.eu/)
- [CCPA Compliance Guide](https://oag.ca.gov/privacy/ccpa)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)

## Questions & Answers

**Q: What if Presidio detects a false positive?**
A: Review in quarantine queue. Adjust confidence threshold if needed. Add custom recognizers.

**Q: What about PII in metadata (filenames, etc.)?**
A: Currently only screens content. Can extend to metadata if needed.

**Q: Can I use different detection rules for different document types?**
A: Yes, can customize analyzer per document type (emails vs. medical records).

**Q: What about non-English text?**
A: Presidio supports multiple languages. Configure NLP engine with appropriate model.

**Q: How do I audit what was anonymized?**
A: Query OpenSearch for privacy events with action="ANONYMIZED".

---

**Status**: Accepted and implemented
**Last Updated**: 2025-11-14
