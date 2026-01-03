"""
Neo4j Spike Test Data Fixtures

Provides test data for all spike scenarios:
- Simple findings (CWE-79 XSS)
- Critical findings (CVE-2024-12345 Log4Shell)
- Control frameworks (NIST AC-3)
- Threat models (STRIDE categories)
- Service dependencies (multi-hop)
"""

from datetime import datetime
from typing import Any

import pytest

# ============================================================================
# SCENARIO A: Simple Finding → Control Mitigation
# ============================================================================


@pytest.fixture
def test_finding_cwe79_xss() -> dict[str, Any]:
    """
    CWE-79 (XSS) finding in login form

    Relationships:
    - Finding -[FINDING_HAS_CWE]-> CWE-79
    - CWE-79 -[CWE_VIOLATES_CONTROL]-> AC-3
    - AC-3 -[CONTROL_MITIGATES_THREAT]-> Tampering threat
    """
    return {
        "finding_id": "finding-cwe79-001",
        "evidence_id": "evidence-001",
        "source_type": "sarif",
        "timestamp": datetime(2024, 1, 15, 10, 30, 0),
        "structured_data": {
            "ruleId": "cwe-79-xss-login",
            "cwe_id": "CWE-79",
            "severity": "high",
            "cvss_score": 7.5,
            "epss_score": 0.42,
            "title": "Reflected Cross-Site Scripting in login form",
            "description": "User input from 'email' parameter is reflected without sanitization in error message",
            "location": {
                "uri": "src/routes/auth.py",
                "startLine": 45,
                "endLine": 48,
            },
            "tool": "semgrep",
            "timestamp": "2024-01-15T10:30:00Z",
        },
    }


@pytest.fixture
def test_finding_cwe352_csrf() -> dict[str, Any]:
    """
    CWE-352 (CSRF) finding in form submission

    Relationships:
    - Finding -[FINDING_HAS_CWE]-> CWE-352
    - CWE-352 -[CWE_VIOLATES_CONTROL]-> AC-7
    """
    return {
        "finding_id": "finding-cwe352-001",
        "evidence_id": "evidence-002",
        "source_type": "sarif",
        "timestamp": datetime(2024, 1, 16, 14, 0, 0),
        "structured_data": {
            "ruleId": "cwe-352-csrf-password-change",
            "cwe_id": "CWE-352",
            "severity": "medium",
            "cvss_score": 6.5,
            "epss_score": 0.35,
            "title": "Cross-Site Request Forgery in password change",
            "description": "Password change endpoint does not validate CSRF token",
            "location": {
                "uri": "src/routes/user.py",
                "startLine": 120,
                "endLine": 135,
            },
            "tool": "semgrep",
            "timestamp": "2024-01-16T14:00:00Z",
        },
    }


# ============================================================================
# SCENARIO B: Critical Finding → Blast Radius
# ============================================================================


@pytest.fixture
def test_finding_cve2024_log4shell() -> dict[str, Any]:
    """
    CVE-2024-12345 (Log4Shell variant) in logging library

    Relationships:
    - Finding -[FINDING_LINKS_CVE]-> CVE-2024-12345
    - CVE -[CVE_HAS_CWE]-> CWE-94
    - Finding -[FINDING_AFFECTS_SERVICE]-> logging-service
    - logging-service -[SERVICE_DEPENDS_ON_SERVICE]-> api-gateway, payment-service
    """
    return {
        "finding_id": "finding-log4j-001",
        "evidence_id": "evidence-003",
        "source_type": "sarif",
        "timestamp": datetime(2024, 2, 1, 8, 0, 0),
        "structured_data": {
            "ruleId": "cve-2024-12345-log4j-rce",
            "cwe_id": "CWE-94",
            "cve_id": "CVE-2024-12345",
            "severity": "critical",
            "cvss_score": 10.0,
            "epss_score": 0.97,
            "title": "Log4j Remote Code Execution (Log4Shell variant)",
            "description": "Unsupported version of log4j library contains RCE vulnerability via JNDI injection",
            "affected_services": ["logging-service", "api-gateway", "payment-service"],
            "dependency": {
                "library": "org.apache.logging.log4j:log4j-core",
                "version": "2.13.0",
                "vulnerable_versions": ["< 2.17.1"],
            },
            "tool": "snyk",
            "timestamp": "2024-02-01T08:00:00Z",
        },
    }


@pytest.fixture
def test_finding_cve2023_sql_injection() -> dict[str, Any]:
    """
    CVE-2023-45678 (SQL Injection) in user search

    Relationships:
    - Finding -[FINDING_LINKS_CVE]-> CVE-2023-45678
    - CVE -[CVE_HAS_CWE]-> CWE-89
    - Finding -[FINDING_AFFECTS_SERVICE]-> user-service
    """
    return {
        "finding_id": "finding-sqli-001",
        "evidence_id": "evidence-004",
        "source_type": "sarif",
        "timestamp": datetime(2024, 1, 20, 9, 15, 0),
        "structured_data": {
            "ruleId": "cve-2023-45678-sqli-user-search",
            "cwe_id": "CWE-89",
            "cve_id": "CVE-2023-45678",
            "severity": "critical",
            "cvss_score": 9.1,
            "epss_score": 0.85,
            "title": "SQL Injection in User Search API",
            "description": "User search endpoint concatenates user input directly into SQL query",
            "affected_services": ["user-service"],
            "location": {
                "uri": "src/services/user_search.py",
                "startLine": 87,
                "endLine": 92,
            },
            "tool": "codeql",
            "timestamp": "2024-01-20T09:15:00Z",
        },
    }


# ============================================================================
# SCENARIO C: Control Framework & Evidence Mapping
# ============================================================================


@pytest.fixture
def test_control_framework_nist() -> dict[str, Any]:
    """
    NIST 800-53 control framework

    Controls:
    - AC-3 (Access Enforcement) - partial
    - AC-7 (Unsuccessful Logon Attempts) - implemented
    - SC-7 (Boundary Protection) - partial
    - SI-10 (Security Testing) - missing
    """
    return {
        "framework_id": "nist-800-53-v5",
        "evidence_id": "evidence-control-001",
        "source_type": "control",
        "timestamp": datetime(2024, 1, 1, 0, 0, 0),
        "structured_data": {
            "framework": "nist-800-53",
            "version": "5.1",
            "controls": [
                {
                    "id": "AC-3",
                    "family": "AC",
                    "title": "Access Enforcement",
                    "description": "The information system enforces approved authorizations for logical access to information and system resources in accordance with applicable access control policies.",
                    "status": "partial",
                    "evidence_count": 5,
                    "supporting_evidence": [
                        "finding-cwe79-001",
                        "finding-cwe89-001",
                        "finding-cwe352-001",
                    ],
                },
                {
                    "id": "AC-7",
                    "family": "AC",
                    "title": "Unsuccessful Logon Attempts",
                    "description": "The information system enforces a limit of consecutive invalid logon attempts by a user during a [assignment: organization-defined time period] and automatically [assignment: locks/delays logon] the account/node for [assignment: organization-defined time period].",
                    "status": "implemented",
                    "evidence_count": 3,
                    "supporting_evidence": [
                        "finding-cwe352-001",
                    ],
                },
                {
                    "id": "SC-7",
                    "family": "SC",
                    "title": "Boundary Protection",
                    "description": "The information system manages information flow to and from external networks (including wireless) by employing boundary protection mechanisms.",
                    "status": "partial",
                    "evidence_count": 2,
                    "supporting_evidence": [],
                },
                {
                    "id": "SI-10",
                    "family": "SI",
                    "title": "Information and Communication Technology (ICT) Security Testing",
                    "description": "The organization includes security testing as part of system development life cycle activities.",
                    "status": "missing",
                    "evidence_count": 0,
                    "supporting_evidence": [],
                },
            ],
        },
    }


# ============================================================================
# SCENARIO D: Threat Models (STRIDE)
# ============================================================================


@pytest.fixture
def test_threat_stride_tampering() -> dict[str, Any]:
    """
    STRIDE Threat: Tampering

    Threat:
    - Attacker modifies data in transit (HTTP requests/responses)
    - Mitigated by AC-3 (Access Enforcement)
    - Affects api-gateway service
    """
    return {
        "threat_id": "threat-tampering-001",
        "evidence_id": "evidence-threat-001",
        "source_type": "threat_model",
        "timestamp": datetime(2024, 1, 10, 11, 0, 0),
        "structured_data": {
            "threat_id": "threat-tampering-001",
            "stride_category": "T",
            "stride_name": "Tampering",
            "title": "Attacker modifies user input in transit",
            "description": "An attacker intercepts and modifies HTTP requests/responses between client and server",
            "attack_surface": [
                "HTTP requests from browsers",
                "API responses",
                "WebSocket messages",
            ],
            "likelihood": "medium",
            "impact": "high",
            "mitigating_controls": ["AC-3", "SC-7"],
            "affected_services": ["api-gateway", "auth-service"],
            "examples": [
                "Man-in-the-middle attack on login",
                "Session hijacking",
                "Request modification (e.g., changing user ID)",
            ],
        },
    }


@pytest.fixture
def test_threat_stride_spoofing() -> dict[str, Any]:
    """
    STRIDE Threat: Spoofing

    Threat:
    - Attacker forges authentication credentials
    - Mitigated by AC-3 (Access Enforcement)
    - Affects auth-service
    """
    return {
        "threat_id": "threat-spoofing-001",
        "evidence_id": "evidence-threat-002",
        "source_type": "threat_model",
        "timestamp": datetime(2024, 1, 10, 11, 15, 0),
        "structured_data": {
            "threat_id": "threat-spoofing-001",
            "stride_category": "S",
            "stride_name": "Spoofing",
            "title": "Attacker forges authentication credentials",
            "description": "An attacker creates fake credentials to impersonate legitimate users",
            "attack_surface": [
                "Login endpoint",
                "API key storage",
                "Session tokens",
            ],
            "likelihood": "high",
            "impact": "critical",
            "mitigating_controls": ["AC-3", "AC-7"],
            "affected_services": ["auth-service"],
            "examples": [
                "Brute force attack on password",
                "Weak password policy",
                "Compromised API keys",
            ],
        },
    }


@pytest.fixture
def test_threat_stride_disclosure() -> dict[str, Any]:
    """
    STRIDE Threat: Information Disclosure

    Threat:
    - Sensitive info exposed in error messages
    - Mitigated by AU-12 (Audit Generation)
    - Affects user-service
    """
    return {
        "threat_id": "threat-disclosure-001",
        "evidence_id": "evidence-threat-003",
        "source_type": "threat_model",
        "timestamp": datetime(2024, 1, 10, 11, 30, 0),
        "structured_data": {
            "threat_id": "threat-disclosure-001",
            "stride_category": "I",
            "stride_name": "Information Disclosure",
            "title": "Information disclosure via error messages",
            "description": "Application exposes sensitive info (stack traces, SQL errors) to users",
            "attack_surface": [
                "Error pages",
                "Log files",
                "Debug endpoints",
            ],
            "likelihood": "medium",
            "impact": "medium",
            "mitigating_controls": ["AU-12"],
            "affected_services": ["user-service"],
            "examples": [
                "Verbose error messages revealing database structure",
                "Stack traces exposed in production",
                "Unmasked API responses",
            ],
        },
    }


# ============================================================================
# SCENARIO E: Service Dependencies (Multi-hop)
# ============================================================================


@pytest.fixture
def test_service_dependency_graph() -> dict[str, Any]:
    """
    Service dependency graph:

    api-gateway
    ├─ auth-service (critical)
    ├─ user-service (high)
    └─ logging-service (high)

    payment-service
    ├─ api-gateway (critical)
    └─ user-service (high)

    Blast radius: log4j RCE in logging-service affects api-gateway → payment-service
    """
    return {
        "services": [
            {
                "service_id": "auth-service",
                "name": "Authentication Service",
                "criticality": "critical",
                "owner": "security-team",
                "status": "active",
            },
            {
                "service_id": "api-gateway",
                "name": "API Gateway",
                "criticality": "critical",
                "owner": "platform-team",
                "status": "active",
            },
            {
                "service_id": "logging-service",
                "name": "Logging Service",
                "criticality": "high",
                "owner": "platform-team",
                "status": "active",
            },
            {
                "service_id": "payment-service",
                "name": "Payment Service",
                "criticality": "critical",
                "owner": "finance-team",
                "status": "active",
            },
            {
                "service_id": "user-service",
                "name": "User Service",
                "criticality": "high",
                "owner": "product-team",
                "status": "active",
            },
        ],
        "dependencies": [
            {
                "from": "api-gateway",
                "to": "auth-service",
                "criticality": "critical",
                "reason": "Auth required for all requests",
            },
            {
                "from": "api-gateway",
                "to": "logging-service",
                "criticality": "high",
                "reason": "Logs all API requests",
            },
            {
                "from": "api-gateway",
                "to": "user-service",
                "criticality": "high",
                "reason": "Routes user service requests",
            },
            {
                "from": "payment-service",
                "to": "api-gateway",
                "criticality": "critical",
                "reason": "Routes payment requests",
            },
            {
                "from": "payment-service",
                "to": "user-service",
                "criticality": "high",
                "reason": "Validates user account",
            },
        ],
    }
