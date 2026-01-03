# Sample Datalake Payloads

This folder contains synthetic documents that exercise the ingestion pipeline end-to-end. They are short, anonymized, and safe to upload to LocalStack.

Contents:
- `policies/usage-policy.txt` – plain-text policy with redactable PII markers.
- `notes/team-sync.md` – Markdown meeting notes for splitting/cleaning checks.
- `reports/quarterly-summary.pdf` – miniature PDF exported from Markdown.
- `csv/customer-mapping.csv` – CSV lookup table for the CSV converter.
- `html/help-page.html` – static HTML fragment similar to scraped pages.

Use `./scripts/datalake-upload-sample.sh` (or `curl /datalake/upload`) to send this directory to the raw bucket.
