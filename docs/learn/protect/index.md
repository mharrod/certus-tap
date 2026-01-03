# Protect: Guardrails for Certus Services

> **Status:** Coming Soon

> **Target Audience:** Developers, Security Engineers, Security Analysts, SOC Teams

## Overview

**Certus Protect** provides multi-layered guardrails that defend against abuse, data leakage, prompt injection, and AI-specific security threats across all Certus services. Guardrails operate in **shadow mode** (log-only) or **enforce mode** (block/degrade), emit signed evidence to Certus Integrity, and enforce policies defined in evaluation manifests.

**Key Capabilities:**

- **Infrastructure Protection**: Rate limiting, burst detection, DoS prevention (Certus Integrity)
- **Data Protection**: PII detection/redaction, sensitive content filtering (Presidio integration)
- **AI Safety**: Prompt injection, jailbreak detection, hallucination mitigation (LLM Guard, NeMo Guardrails)
- **Code Security**: Unsafe code detection, credential scanning (Bandit, Semgrep integration)
- **Response Validation**: Citation enforcement, grounding verification, context budget limits
- **Observability**: All decisions logged, signed, and queryable through Integrity evidence chains

---

## Planned Tutorial Series

These tutorials will guide you through configuring and deploying guardrails:

### Infrastructure Guardrails

- **Configuring Rate Limits** - Prevent DoS attacks with request throttling
- **Burst Protection** - Detect rapid-fire attacks within short windows
- **IP Whitelisting** - Exempt trusted networks from guardrails
- **Shadow vs Enforce Mode** - Safely test guardrails before blocking traffic
- **Monitoring Guardrail Decisions** - Grafana dashboards and alerting

### Data Protection Guardrails

- **Deploying PII Detection** - Integrate Presidio for sensitive data scanning
- **PII Redaction Policies** - Configure masking vs quarantine vs blocking
- **Privacy Incident Response** - Handle detected PII in production systems
- **Data Exfiltration Prevention** - Detect attempts to extract sensitive information
- **Multi-Language PII Support** - Extend PII detection beyond English

### AI Safety Guardrails

- **Prompt Injection Defense** - Block jailbreak attempts and malicious prompts
- **Citation Enforcement** - Require LLM responses to cite retrieved context
- **Grounding Validation** - Ensure responses are grounded in source documents
- **Context Budget Management** - Limit LLM context window usage for cost control
- **Hallucination Detection** - Identify when LLMs generate false information
- **Code Safety Validation** - Scan generated code for security vulnerabilities

---

**Next Steps**: As tutorials become available, this page will be updated with hands-on guides.
