# Miscellaneous Notes

## Security & Environment

- Local services (`opensearch`, `localstack`, `mlflow`, `ask-certus-backend`) are launched via `just up` and are intended for **development only**.
- LocalStack uses dummy AWS credentials (`test/test`). Never point these credentials at a real AWS account.
- `.env` values are loaded through Pydantic settings; keep secrets out of source control and rotate anything shared externally.

## Dependency Management

- Runtime and tooling dependencies are defined in `pyproject.toml` and locked with `uv.lock`. After modifying dependencies, run `uv lock` and rebuild Docker images (`docker compose build ask-certus-backend`).
- To generate conventional requirement files:

```bash
uv export -f requirements.txt --output requirements.txt
uv export -f requirements.txt --dev --output requirements-dev.txt
```

## Guardrails & Testing

- `./scripts/preflight.sh` is the canonical health check. Run it before publishing changes that touch ingestion, LLM configs, or dependencies.
- Guardrail regressions (e.g., hallucination tests, robots.txt violations) should fail fast in `preflight` or CI. Reference `docs/architecture/roadmap.md` for the current guardrail roadmap.

## Contribution Tips

- `just install` keeps local tooling consistent with CI (pre-commit, mypy, etc.).
- `just docs-serve` spins up MkDocs with live reload for doc edits.
- Use feature branches + pull requests, and include doc updates when changing behavior (ingestion, guardrails, or deployment).

## License

This project is licensed under the MIT License. See `LICENSE` for full text.
