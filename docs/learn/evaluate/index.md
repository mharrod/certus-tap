# Evaluate: RAG Quality Assessment with RAGAS

> **Status:** Coming Soon

> **Target Audience:** Developers, Security Engineers, Security Analysts, SOC Teams

## Overview

**Certus Evaluate** provides automated quality assessment for RAG (Retrieval-Augmented Generation) systems using RAGAS metrics. It enforces quality thresholds, blocks low-quality responses, and integrates with Certus Integrity to create signed evidence of every evaluation decision.

**Key Capabilities:**

- **RAGAS Metrics**: Faithfulness, answer relevancy, context precision, context recall
- **Quality Enforcement**: Shadow mode (log-only) and enforce mode (block low-quality responses)
- **Guardrails Integration**: PII detection, prompt injection prevention, hallucination mitigation
- **Evidence Chains**: All evaluations signed and stored in Certus Trust for audit trails
- **MLflow Integration**: Track evaluation metrics across experiments

---

## Planned Tutorials

These tutorials will guide you through RAG evaluation and quality enforcement:

### RAGAS Fundamentals

- **Understanding RAGAS Metrics** - Faithfulness, relevancy, precision, recall
- **Configuring Evaluation Manifests** - Define quality thresholds per workspace
- **Running Evaluations** - Evaluate queries via REST API or Python SDK
- **Interpreting Results** - Understand metric scores and pass/fail decisions

### Quality Enforcement

- **Shadow Mode Testing** - Log evaluations without blocking responses
- **Enforce Mode Deployment** - Block low-quality responses in production
- **Threshold Tuning** - Calibrate thresholds for optimal quality vs. availability
- **Graceful Degradation** - Handle timeouts and evaluation failures

### Guardrails Integration

- **PII Detection in RAG** - Scan queries and responses for sensitive data
- **Prompt Injection Prevention** - Detect malicious prompts before LLM processing
- **Hallucination Detection** - Cross-reference LLM responses with retrieved context
- **Citation Enforcement** - Require responses to cite source documents

### Advanced Evaluation

- **Custom Metrics** - Define workspace-specific quality metrics
- **Multi-Model Evaluation** - Compare quality across different LLMs
- **A/B Testing** - Evaluate retrieval strategies (keyword vs. semantic vs. hybrid)
- **MLflow Integration** - Track evaluation experiments and model performance

**Next Steps**: As tutorials become available, this page will be updated with hands-on guides.
