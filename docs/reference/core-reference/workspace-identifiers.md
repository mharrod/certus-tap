# Assurance Identifier Model

Certus Assurance now treats four identifiers as first-class metadata so you can
organize every scan (test) across teams, products, and audit campaigns:

| Field          | Purpose                                              | Example                  |
| -------------- | ---------------------------------------------------- | ------------------------ |
| `workspace_id` | Organizational or tenant boundary                    | `org-acme-security`      |
| `component_id` | Asset or service under test                          | `payment-api`            |
| `assessment_id`| Campaign / audit / release tracking multiple tests   | `fy25-q1-hardening`      |
| `test_id`      | Individual execution of the Dagger pipeline (unique) | `test_ab12cd34ef56`      |

The API, CLI, and Dagger module all expect these identifiers. They propagate to:

- `scan.json` and `manifest-info.json` inside each artifact bundle.
- S3 metadata keys when the raw→golden uploader stages artifacts.
- Registry mirrors / scratch images (manifest + attestation) so attestation
  consumers can correlate tests with the proper assessment.
- OpenSearch / downstream ingestion records if you choose to index the bundles.

## When to Create a New Assessment

Use a new `assessment_id` whenever you want to group multiple tests together
for reporting. Common triggers:

- A quarterly audit that runs SAST, DAST, and SBOM pipelines against the same
  component.
- A release readiness gate (e.g., `release-v2.0.1`) requiring multiple scans.
- A customer-specific onboarding where the same component is tested for
  different tenant requirements.

Each test remains independent (unique `test_id`) but inherits the assessment
context. Downstream, you can ask “show every test for workspace X, component Y,
assessment Z” and produce consolidated reports.

## Naming Tips

Keep identifiers short, URL-safe, and immutable:

- Stick to lowercase letters, numbers, and hyphens (`[a-z0-9-]`).
- Use organization-approved nomenclature (e.g., CMDB asset IDs) so auditors
  recognize the values without translation.
- Avoid revving identifiers mid-assessment. When scope changes, create a new
  assessment.

## Request Examples

### Managed API

```bash
curl -X POST http://localhost:8000/v1/security-scans \
  -H 'Content-Type: application/json' \
  -d '{
        "workspace_id": "org-acme-security",
        "component_id": "payment-api",
        "assessment_id": "fy25-q1-hardening",
        "git_url": "https://github.com/acme/payment-api.git",
        "requested_by": "auditor@example.com",
        "profile": "heavy",
        "manifest_uri": "s3://acme-manifests/payment-api/heavy.json",
        "manifest_signature_uri": "s3://acme-manifests/payment-api/heavy.json.sig"
      }'
```

### CLI (direct Dagger run)

```bash
uv run security-scan \
  --workspace-id org-acme-security \
  --component-id payment-api \
  --assessment-id fy25-q1-hardening \
  --test-id test_manual_cli_001 \
  --runtime dagger \
  --workspace . \
  --export-dir ./security-results \
  --manifest ./manifests/payment-api-heavy.json
```

Providing `--test-id` is optional for the CLI; if omitted it mirrors the
API’s UUID style so artifacts remain unique.

## Surfacing Identifiers Downstream

Because the four fields live in every metadata file, you can make them first-
class facets in other systems:

- **S3 Inventory:** `aws s3api head-object` returns `Metadata` containing all
  four fields, so inventories or lifecycle policies can filter by workspace or
  assessment.
- **OpenSearch / Trust:** ingestion pipelines should parse `scan.json` and
  store the identifiers in their documents, enabling dashboards and audit
  reports grouped by assessment.
- **CLI tooling:** scripts can use the `stream_url` to subscribe to logs for a
  particular test while labeling outputs with workspace / component context.

Start every workflow by deciding the workspace, component, and assessment scope
so you can trace every test end-to-end. Once these identifiers are embedded,
you can build dashboards, alerts, and compliance evidence without reverse-
engineering which scan belonged to which product.***
