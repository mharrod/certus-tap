# Reference Doc Template

This template keeps the `docs/reference/` section consistent so readers can scan every component guide quickly. Use it (and prune sections that do not apply) whenever you add a new reference page.

## 1. Title
- `# Component Or Concept Name`
- Keep it short and noun-focused (e.g., “OpenSearch Explorer”, “Metadata Envelopes”).

## 2. Purpose
- Brief paragraph explaining what this thing is and why it exists.
- Mention the system(s) it belongs to (TAP API, Datalake, Logging, etc.).

## 3. Audience & Prerequisites
- Who should read it (operators, analysts, backend devs).
- Required context or prior tutorials/readings.
- Optional: quick links to relevant Learn guides or architecture diagrams.

## 4. Overview
- High-level bullets covering:
  - Where it sits in the stack.
  - Key responsibilities.
  - Dependencies or external services.
- Include a diagram only if it adds clarity; otherwise link to an existing diagram.

## 5. Key Concepts / Data Model
- Define important entities, schemas, or terminology.
- Tables work well for fields/attributes (name, type, description).
- For APIs, include sample request/response stubs.

## 6. Workflows / Operations
- Describe how the component is used day-to-day.
- Step-by-step bullets for common tasks (start/stop, ingest, refresh, rotate keys).
- Link to “Learn” tutorials for hands-on guides; do not duplicate full walkthroughs here.

## 7. Configuration / Interfaces
- Environment variables, CLI flags, API endpoints, file paths, config snippets.
- Include code blocks for common snippets (YAML, JSON, `curl`, `just`, etc.).
- Call out defaults and where values are defined (e.g., `.env`, `pyproject.toml`).

## 8. Troubleshooting / Gotchas
- Common failure modes with pointers to logs or metrics.
- FAQ-style bullets for known pitfalls or edge cases.
- Reference relevant `docs/reference/logging/` pages when helpful.

## 9. Related Documents
- Bullet list of links to:
  - Learn tutorials that exercise this component.
  - Architecture diagrams or ADRs.
  - Other reference docs (e.g., API schema, logging queries).

## Notes
- Remove any section that is truly N/A (e.g., no external config).
- Keep individual sections concise (1–4 short paragraphs or bullet lists).
- Prefer tables/bullets over long prose when listing fields or steps.
- Update the template itself if we add new cross-cutting requirements (e.g., security considerations).
