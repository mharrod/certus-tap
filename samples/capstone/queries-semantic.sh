#!/bin/bash
# queries-semantic.sh - OpenSearch semantic search examples for capstone
# Shows how to discover security issues using natural language search

BASE_URL="${1:-localhost:9200}"

echo "🔍 Semantic Search Queries (OpenSearch)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Query 1: Find critical security issues
echo "1️⃣  Critical Security Issues"
echo "Query: Find all CRITICAL findings"
echo ""
curl -s -X POST "$BASE_URL/security-findings/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"term": {"severity": "critical"}},
    "_source": ["rule_id", "severity", "message", "file_path"],
    "size": 10
  }' | jq '.hits.hits[] | {rule_id: ._source.rule_id, severity: ._source.severity, message: ._source.message, file: ._source.file_path}'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Query 2: Search for SQL injection patterns
echo "2️⃣  SQL Injection Vulnerabilities"
echo "Query: Find findings mentioning SQL injection"
echo ""
curl -s -X POST "$BASE_URL/security-findings/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {"match": {"message": "SQL injection"}},
    "_source": ["rule_id", "severity", "message", "file_path"],
    "size": 10
  }' | jq '.hits | {total: .total.value, findings: .hits[] | {rule: ._source.rule_id, severity: ._source.severity, file: ._source.file_path}}'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Query 3: Authentication-related findings
echo "3️⃣  Authentication & Credential Issues"
echo "Query: Find findings related to authentication/credentials"
echo ""
curl -s -X POST "$BASE_URL/security-findings/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "multi_match": {
        "query": "authentication credentials password hardcoded",
        "fields": ["message^2", "rule_id"]
      }
    },
    "_source": ["rule_id", "severity", "message"],
    "size": 10
  }' | jq '.hits.hits[] | {rule_id: ._source.rule_id, severity: ._source.severity, message: ._source.message}'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Query 4: Findings by severity distribution
echo "4️⃣  Severity Distribution"
echo "Query: Count findings by severity"
echo ""
curl -s -X POST "$BASE_URL/security-findings/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "aggs": {
      "by_severity": {
        "terms": {"field": "severity", "size": 10}
      }
    },
    "size": 0
  }' | jq '.aggregations.by_severity.buckets[] | {severity: .key, count: .doc_count}'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Query 5: Find packages with security concerns
echo "5️⃣  Packages with Known Issues"
echo "Query: Find packages that might have security issues"
echo ""
curl -s -X POST "$BASE_URL/sbom-packages/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "bool": {
        "should": [
          {"match": {"dependencies": "requests"}},
          {"match": {"dependencies": "cryptography"}},
          {"match": {"dependencies": "urllib3"}}
        ]
      }
    },
    "_source": ["name", "version", "licenses"],
    "size": 20
  }' | jq '.hits.hits[] | {name: ._source.name, version: ._source.version, licenses: ._source.licenses}'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Query 6: License compliance issues
echo "6️⃣  License Compliance Check"
echo "Query: Find packages with GPL/restrictive licenses"
echo ""
curl -s -X POST "$BASE_URL/sbom-packages/_search" \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "bool": {
        "should": [
          {"match": {"licenses": "GPL"}},
          {"match": {"licenses": "AGPL"}},
          {"match": {"licenses": "SSPL"}}
        ]
      }
    },
    "_source": ["name", "version", "licenses"],
    "size": 50
  }' | jq '.hits.hits[] | {name: ._source.name, version: ._source.version, licenses: ._source.licenses}'

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "✅ Semantic search queries complete!"
echo ""
echo "💡 Tips:"
echo "   - Modify 'message' query terms to search for other patterns"
echo "   - Increase 'size' parameter for more results"
echo "   - Combine multiple 'should' clauses for OR logic"
