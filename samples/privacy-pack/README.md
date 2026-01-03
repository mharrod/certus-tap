# Privacy Pack Sample Corpus

This bundle backs the `docs/Learn/privacy-screening.md` tutorial. It contains intentionally sensitive artifacts so you can practice running the Presidio dry-run, quarantining risky files, and ingesting only sanitized content.

Structure:

```
raw/
  customer-onboarding.md   # contains email, phone, address
  legacy-contact.rtf       # includes SSN, phone
  intake-form.pdf          # minimal PDF with PII
clean/
quarantine/
```

Recommended workflow:
1. Copy the `samples/privacy-pack` folder to your home directory.
2. Run the Presidio dry-run script from the tutorial to flag PII.
3. Move offending files into `quarantine/`, vetted files into `clean/`.
4. Upload `clean/` to LocalStack (`aws s3 sync clean/ s3://raw/privacy-pack/`).
5. Ingest via `/v1/index_folder` or `/datalake/ingest/batch`.

Feel free to edit the files or add new ones—this directory is only for local testing and contains no real customer data.
