# Corporate Security Governance Policy

## Purpose
This policy defines the governance structure that keeps the organization's security program aligned with SOC 2, ISO/IEC 27001, and industry expectations. It documents the leadership model, accountability, and cadence for reviewing controls and newly ingested data sources.

## Scope
Applies to all business units, subsidiaries, and contractors who store, process, or transmit organizational data, including workloads deployed through TAP ingestion pipelines.

## Policy Statements
- **Security Leadership Council (SLC):** The SLC meets monthly to review control health, ingest metrics, and audit results. Council members include the CISO, Head of Engineering, Compliance, and Site Reliability Engineering (SRE).
- **Risk Register:** Product and infrastructure teams must log new risks within five business days of discovery. Risks are prioritized using ISO 27005 methodology and mapped to SOC 2 Trust Services Criteria (TSC) identifiers.
- **Control Ownership:** Every ISO 27001 Annex A control is assigned a single owner and deputy. Ownership changes require SLC approval recorded in the compliance tracker.
- **Policy Lifecycle:** Policies undergo annual review plus trigger-based reviews for mergers, platform changes, or material findings from preflight ingestion.
- **Exception Management:** Exceptions require documented compensating controls, expiration date, and VP-level approval. Exceptions older than 90 days trigger automatic escalation.

## Roles & Responsibilities
| Role | Responsibility |
| --- | --- |
| CISO | Sponsors the security program, approves budgets, and signs SOC 2 management assertions. |
| Compliance Lead | Maintains ISO 27001 Statement of Applicability and manages external audits. |
| Head of Engineering | Ensures engineering policies integrate secure SDLC checkpoints. |
| Data Owners | Approve access to datasets and confirm data classification accuracy. |
| TAP Team | Keeps ingestion pipelines aligned with guardrails, robots.txt, and rate limits. |

## Monitoring & Metrics
- Quarterly key risk indicators (KRIs) covering incident response MTTR, control test pass rate, and patch SLA adherence.
- `./scripts/preflight.sh` output archived for two years as audit evidence of ingestion and guardrail health.
- Aggregated OpenSearch dashboards show ingestion anomalies and correlate with SOC 2 CC7 monitoring requirements.

## Enforcement
Violations of this policy may result in disciplinary action up to termination and must be reported to HR, Legal, and the CISO per incident response procedures.
