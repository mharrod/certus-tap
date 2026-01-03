# Privacy Scanning with Presidio

This guide demonstrates comprehensive privacy scanning using Microsoft Presidio to detect and redact personally identifiable information (PII) and sensitive data in documents and code repositories.

## Overview

Privacy scanning is critical for:
- **GDPR Compliance** - Identify and protect personal data
- **CCPA Compliance** - Know what personal information exists
- **Data Governance** - Classify and control sensitive information
- **Supply Chain Security** - Ensure vendors don't leak customer data
- **Code Security** - Prevent credentials and PII in repositories

## Sample Data: `presidio-privacy.sarif.json`

The sample contains 8 realistic privacy violations across different document types:

| Finding | Type | Confidence | Source |
|---------|------|------------|--------|
| Sarah Johnson | PERSON | 95% | Client contract |
| sarah.johnson@company.com | EMAIL | 100% | Client contract |
| +1-555-0147 | PHONE | 98% | Client contract |
| 4532-1234-5678-9010 | CREDIT_CARD | 99% | Payment records |
| 123-45-6789 | SSN | 100% | HR records |
| 1987-03-15 | DATE_OF_BIRTH | 92% | HR records |
| 192.168.1.105 | IP_ADDRESS | 100% | Audit logs |
| MySecurePass123! | PASSWORD | 85% | .env file |

## Presidio Architecture

```
Input Document
      ↓
┌─────────────────────────────────┐
│  Presidio Analyzer Engine       │
├─────────────────────────────────┤
│  Pattern Recognition:           │
│  - Regex patterns (SSN, CC)     │
│  - NER models (Names, Orgs)     │
│  - Context detection            │
│  - Custom patterns              │
│                                 │
│  Confidence Scoring:            │
│  - Pattern match strength       │
│  - Context validation           │
│  - NLP model confidence         │
└─────────────────────────────────┘
      ↓
PII Entities with Confidence Scores
      ↓
┌─────────────────────────────────┐
│  Presidio Anonymizer            │
├─────────────────────────────────┤
│  Redaction Strategies:          │
│  - Replace with mask            │
│  - Hash with salt               │
│  - Encrypt for reversible       │
│  - Custom transformation        │
└─────────────────────────────────┘
      ↓
Anonymized Document
```

## Supported Entity Types

### High-Risk (CRITICAL)
| Entity | Pattern | Confidence | Example |
|--------|---------|-----------|---------|
| CREDIT_CARD | 16-digit with validation | Very High | 4532-1234-5678-9010 |
| SOCIAL_SECURITY_NUMBER | XXX-XX-XXXX format | Very High | 123-45-6789 |
| BANK_ACCOUNT | Account number format | High | 987654321 |
| PASSWORD | Common patterns | Medium | MyPassword123! |

### Medium-Risk (HIGH)
| Entity | Pattern | Confidence | Example |
|--------|---------|-----------|---------|
| PERSON | NER + name lists | High | Sarah Johnson |
| EMAIL_ADDRESS | RFC 5322 pattern | Very High | sarah.johnson@company.com |
| PHONE_NUMBER | International format | High | +1-555-0147 |
| DRIVERS_LICENSE | State DL format | High | D1234567 |

### Low-Risk (MEDIUM/LOW)
| Entity | Pattern | Confidence | Example |
|--------|---------|-----------|---------|
| DATE_OF_BIRTH | YYYY-MM-DD format | Medium | 1987-03-15 |
| IP_ADDRESS | IPv4/IPv6 format | High | 192.168.1.105 |
| LOCATION | Place names | Medium | San Francisco |

## Using Presidio in Pipelines

### 1. Docker Installation
```bash
# Pull official Presidio image
docker pull mcr.microsoft.com/presidio:latest

# Run with API
docker run -d -p 8000:8000 mcr.microsoft.com/presidio:latest
```

### 2. Python Installation
```bash
# Install Presidio
pip install presidio-analyzer presidio-anonymizer

# Download NLP model
python -m spacy download en_core_web_lg
```

### 3. Basic Usage
```python
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

# Initialize
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Analyze
text = "My name is Sarah Johnson, email: sarah.johnson@company.com"
results = analyzer.analyze(text=text, language="en")

# Anonymize
anonymized = anonymizer.anonymize(
    text=text,
    analyzer_results=results,
    operators={"PERSON": OperatorConfig("replace", {"new_value": "[PERSON]"})}
)
```

### 4. File-Based Scanning
```python
from pathlib import Path
import json

def scan_directory(path: Path):
    """Scan all files in directory for PII."""
    findings = []

    for file in path.rglob("*"):
        if file.is_file():
            try:
                content = file.read_text()
                results = analyzer.analyze(content, language="en")

                if results:
                    findings.append({
                        "file": str(file),
                        "pii_count": len(results),
                        "entities": [
                            {
                                "type": r.entity_type,
                                "confidence": r.score,
                                "text": content[r.start:r.end]
                            }
                            for r in results
                        ]
                    })
            except Exception as e:
                print(f"Error scanning {file}: {e}")

    return findings
```

## Integration with CI/CD

### GitHub Actions Example
```yaml
name: Privacy Scan

on: [push, pull_request]

jobs:
  privacy-scan:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Run Presidio scan
        run: |
          pip install presidio-analyzer presidio-anonymizer
          python -m spacy download en_core_web_lg

          python -c "
          from presidio_analyzer import AnalyzerEngine
          import json

          analyzer = AnalyzerEngine()
          # Scan and report
          "

      - name: Upload results
        uses: actions/upload-artifact@v3
        if: always()
        with:
          name: privacy-scan-results
          path: privacy-results.sarif
```

### Pre-commit Hook
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: presidio-scan
        name: Presidio Privacy Scan
        entry: python scripts/privacy-scan.py
        language: system
        stages: [commit]
        files: \.(py|txt|md|json)$
```

## Redaction Strategies

### Strategy 1: Masking
```python
operators = {
    "PERSON": OperatorConfig("mask", {"chars_to_mask": 4, "masking_char": "*"}),
    # Result: "Sarah Johnson" → "**** Johnson"

    "EMAIL_ADDRESS": OperatorConfig("mask", {"chars_to_mask": 10, "masking_char": "*"}),
    # Result: "sarah.johnson@company.com" → "******.****@company.com"
}
```

### Strategy 2: Replacement
```python
operators = {
    "CREDIT_CARD": OperatorConfig("replace", {"new_value": "[CREDIT_CARD]"}),
    # Result: "4532-1234-5678-9010" → "[CREDIT_CARD]"

    "PHONE_NUMBER": OperatorConfig("replace", {"new_value": "[REDACTED_PHONE]"}),
}
```

### Strategy 3: Encryption (Reversible)
```python
from cryptography.fernet import Fernet

key = Fernet.generate_key()
cipher = Fernet(key)

operators = {
    "PERSON": OperatorConfig("encrypt", {
        "key": key.decode(),
        "type": "fernet"
    }),
    # Result: Encrypted but can be decrypted with key
}
```

### Strategy 4: Hashing (Irreversible)
```python
operators = {
    "EMAIL_ADDRESS": OperatorConfig("hash", {"hash_type": "sha256"}),
    # Result: "sarah@company.com" → "abc123def456..."
}
```

## Custom Entity Recognition

### Add Domain-Specific Patterns
```python
from presidio_analyzer import PatternRecognizer

# Custom pattern for internal employee IDs
employee_id_recognizer = PatternRecognizer(
    supported_entity="EMPLOYEE_ID",
    patterns=[
        {"name": "employee_id", "regex": r"EMP-\d{6}"}
    ],
    context=["employee", "staff", "id"],
    score=0.9
)

analyzer.add_recognizer(employee_id_recognizer)
```

### Add Custom NER Model
```python
from presidio_analyzer import EntityRecognizer

class CustomNER(EntityRecognizer):
    def load(self):
        # Load your custom model
        pass

    def predict(self, text):
        # Return predictions
        pass

analyzer.add_recognizer(CustomNER())
```

## Threshold Management

```python
# High sensitivity: Flag everything possible
results = analyzer.analyze(
    text=text,
    language="en",
    threshold=0.3,  # Lower threshold = more findings
    ad_hoc_recognizers=recognizers
)

# Production: Only high-confidence findings
results = analyzer.analyze(
    text=text,
    language="en",
    threshold=0.8,  # Higher threshold = fewer false positives
)
```

## Context-Aware Detection

Presidio uses context to improve accuracy:

```python
# "Sarah" alone = Low confidence
# "My name is Sarah Johnson" = High confidence
# "Dr. Sarah Johnson" = Very high confidence

results = analyzer.analyze(
    text=text,
    language="en",
    context=["client", "contract"]  # Additional context
)
```

## Handling False Positives

### Whitelisting
```python
whitelist = {
    "PERSON": ["John", "Johnson", "Smith"],  # Common names
    "EMAIL_ADDRESS": ["no-reply@company.com"],  # Bot emails
}

# Filter results
for result in results:
    if result.entity_type in whitelist:
        if result.text in whitelist[result.entity_type]:
            results.remove(result)  # Skip whitelisted
```

### Confidence Thresholds per Entity Type
```python
# Different thresholds for different entities
entity_thresholds = {
    "CREDIT_CARD": 0.95,      # Very strict
    "PERSON": 0.75,           # Moderate
    "DATE_OF_BIRTH": 0.60,    # Lenient
}

filtered_results = [
    r for r in results
    if r.score >= entity_thresholds.get(r.entity_type, 0.7)
]
```

## Compliance Mapping

### GDPR
- **Personal Data:** PERSON, EMAIL_ADDRESS, PHONE_NUMBER, DATE_OF_BIRTH
- **Sensitive Data:** SOCIAL_SECURITY_NUMBER, CREDIT_CARD, DRIVER_LICENSE
- **Action:** Encrypt, restrict access, obtain consent

### CCPA
- **Consumer Identifiers:** All PII types
- **Commercial Information:** CREDIT_CARD, BANK_ACCOUNT
- **Biometric Information:** DRIVER_LICENSE, PASSPORT
- **Action:** Catalog, provide access rights, delete on request

### HIPAA
- **Protected Health Information:** Medical records, diagnosis codes
- **Identifiers:** PERSON, PHONE_NUMBER, EMAIL_ADDRESS
- **Action:** De-identify, encrypt transmission, audit access

## Privacy Scanning in Non-Repudiation Pipeline

### Integration with SARIF
The `presidio-privacy.sarif.json` sample shows how to:
1. **Detect PII** - Identify entities in documents
2. **Report in SARIF** - Standardized format for tooling
3. **Track Confidence** - Score each finding
4. **Audit Trail** - Who scanned, when, what was found

### Compliance Report Integration
```json
{
  "privacy_assessment": {
    "files_scanned": 12,
    "files_with_pii": 5,
    "pii_findings": 8,
    "remediation_required": true,
    "estimated_effort": "HIGH",
    "next_steps": [
      "Quarantine files with PII",
      "Redact customer data",
      "Implement access controls"
    ]
  }
}
```

## Common Challenges

### Challenge 1: False Positives
**Example:** "James" identified as PERSON in non-personal context

**Solution:**
```python
# Increase threshold
analyzer.analyze(text, language="en", threshold=0.8)

# Add context awareness
analyzer.analyze(text, language="en", context=["variable_name"])
```

### Challenge 2: Language Detection
**Example:** Spanish name not recognized by English NER

**Solution:**
```python
# Auto-detect language
from langdetect import detect

language = detect(text)  # 'es' for Spanish
results = analyzer.analyze(text, language=language)
```

### Challenge 3: Performance at Scale
**Example:** Scanning 10,000 documents takes hours

**Solution:**
```python
# Use batch processing
from concurrent.futures import ThreadPoolExecutor

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [
        executor.submit(scan_file, file)
        for file in files
    ]
    results = [f.result() for f in futures]
```

### Challenge 4: Custom Domain Entities
**Example:** Internal employee IDs not recognized

**Solution:**
```python
# Add custom recognizers (see above)
employee_recognizer = PatternRecognizer(
    supported_entity="EMPLOYEE_ID",
    patterns=[{"name": "emp_id", "regex": r"EMP-\d{6}"}]
)
analyzer.add_recognizer(employee_recognizer)
```

## Best Practices

1. **Layered Defense**
   - Multiple scanner passes (different threshold, language)
   - Combine automated detection with manual review
   - Use whitelisting for known non-sensitive uses

2. **Audit Trail**
   - Log all scans (who, when, what)
   - Track redaction decisions
   - Document exceptions/whitelist additions

3. **Remediation Workflow**
   - Quarantine files with sensitive PII
   - Redact or encrypt found entities
   - Provide remediation guidance to developers

4. **Continuous Improvement**
   - Track false positive rates
   - Add patterns for missed entities
   - Regularly update NLP models

5. **Privacy by Design**
   - Prevent PII from entering codebase (pre-commit hooks)
   - Use synthetic data in tests
   - Mask logs in production

## Redaction Examples

### Before Redaction
```
Name: Sarah Johnson
Email: sarah.johnson@company.com
Phone: +1-555-0147
SSN: 123-45-6789
Credit Card: 4532-1234-5678-9010
```

### After Redaction (Masking)
```
Name: **** Johnson
Email: ******.****@company.com
Phone: +1-555-****
SSN: ***-**-6789
Credit Card: ****-****-****-9010
```

### After Redaction (Replacement)
```
Name: [PERSON]
Email: [EMAIL]
Phone: [PHONE]
SSN: [SSN]
Credit Card: [CREDIT_CARD]
```

## References

- [Microsoft Presidio](https://microsoft.github.io/presidio/)
- [Spacy NER Models](https://spacy.io/models)
- [GDPR Compliance](https://gdpr-info.eu/)
- [CCPA Compliance](https://oag.ca.gov/privacy/ccpa)
- [SARIF Specification](https://docs.oasis-open.org/sarif/sarif/v2.1.0/sarif-v2.1.0.html)

## Summary

Presidio privacy scanning:
- **Detects** PII with high accuracy
- **Redacts** sensitive data with multiple strategies
- **Reports** in standard SARIF format
- **Integrates** into CI/CD pipelines
- **Supports** custom entities and patterns
- **Enables** compliance (GDPR, CCPA, HIPAA)
- **Scales** with batch processing
- **Audits** all scanning and remediation activities
