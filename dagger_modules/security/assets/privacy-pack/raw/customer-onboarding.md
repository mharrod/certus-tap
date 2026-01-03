# Customer Onboarding Workflow

## Intake Data
- Full name: Jane Example
- Personal email: jane.example@contoso.com
- Mobile: +1-202-555-0148
- Mailing address: 1800 Mission St, San Francisco, CA 94103

## Controls
1. Encrypt uploaded IDs at rest (S3 SSE-KMS key `tap-priv`).
2. Redact contact details in support transcripts before sharing with vendors.
3. Retain onboarding packets for 90 days, then purge.

## Reviewer Notes
The pilot program in **RegionWest** allows temporary storage in the "quarantine" folder until Presidio approves release.
