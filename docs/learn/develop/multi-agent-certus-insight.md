# Multi-Agent Development Walkthrough: Certus Insight

Learn how to stand up a new feature (the Certus-Insight service) using the multi-agent workflow defined in `.context/`. This tutorial mirrors the Phase 0 scope from `docs/reference/roadmap/proposals/core/certus-insight-proposal.md` and shows how Goose-powered agents collaborate while a human integrates the final result.

## Prerequisites

- Repo cloned locally with dependencies installed (`uv`, `docker`, `just`, `zellij`, Goose CLI, provider API keys).
- LocalStack/OpenSearch stack is healthy (`just up`).
- Read `AGENTS.md`, `.context/CONTEXT.md`, and the Certus-Insight proposal so you understand goals and guardrails.

## 1. Launch the Agent Workspace

```bash
./scripts/dev.zellij.sh
```

This loads the 4-pane layout (Planner, Reviewer, Implementer, Tester). Inside each pane:

1. Start Goose with your preferred model, e.g. `goose --model claude-3-opus`.
2. Paste `.context/bootstrap.txt`.
3. Confirm the agent replies with `AGENTS.md loaded: yes`, `CONTEXT.md loaded: yes`, and declare the role.

> Tip: rename panes (Ctrl+p, r) if you pivot roles later (Reviewer → Security).

## 2. Planner Goose Creates the Work Plan

1. Load `.context/session-charter.md`, `.context/tasks/now.md`, and the Certus-Insight proposal.
2. Break Phase 0 into concrete tasks, e.g.:
   - Scaffold `certus_insight/` FastAPI skeleton.
   - Add `/v1/reports` endpoint returning sample data.
   - Implement Jinja2/WeasyPrint template generation.
   - Wire LocalStack S3 uploads + mock signing metadata.
   - Update docs + add smoke tests.
3. For each task, add an entry to `.context/tasks/now.md` using the provided template. Declare `Owner`, `Files`, `Don't Touch`, and set `Status: in-progress`.
4. Create locks for shared regions, e.g. `echo "certus_insight bootstrap" > .locks/certus_insight.lock`.
5. Handoff using the charter format so other agents know the plan.

## 3. Implementer Goose Builds the Service

For each assigned task:

1. Load only the scoped files (e.g., `certus_insight/main.py`, `pyproject.toml`) plus relevant documentation.
2. Follow `AGENTS.md`: keep diffs small, explain why, and update docs/tests as part of the change.
3. Example commands:
   ```bash
   uv run fastapi dev certus_insight/main.py
   uv run pytest tests/certus_insight/test_reports.py -k sample_report
   ```
4. Update `.context/tasks/now.md` with progress notes and release locks when done.

## 4. Tester Goose Validates the Stack

- Runs targeted tests suggested by Implementer Goose.
- Executes the acceptance gate:
  ```bash
  ./scripts/preflight.sh
  ```
- Records pass/fail output in the handoff template. If anything fails, bounce the task back to Implementer with logs.

## 5. Reviewer (and Security) Goose Checks the Diff

1. Load `AGENTS.md`, `.context/session-charter.md`, and the changed files.
2. Inspect diffs in Zed (`git diff certus_insight`). Look for guardrail regressions (e.g., S3 upload safety, signing metadata, secrets).
3. If code touches authentication, attestation, or data handling, switch to the security bootstrap and produce findings before merging.
4. Mark the task `Status: completed` in `.context/tasks/now.md` once satisfied.

## 6. Human Integrator Commits the Work

1. Review every change in Zed.
2. Ensure locks in `.locks/` are cleared.
3. Verify `./scripts/preflight.sh` results and any extra tests run by the agents.
4. Commit and push:
   ```bash
   git add certus_insight .context/tasks/now.md docs/learn/develop/multi-agent-certus-insight.md
   git commit -m "feat: scaffold Certus Insight service"
   ```
5. Update `CONTEXT.md` or docs/roadmap entries if architecture shifted.

## Recap & Next Steps

- Planner, Implementer, Tester, and Reviewer roles operate via Goose CLIs in zellij panes, all governed by the `.context` bootstraps and charter.
- Tasks live in `.context/tasks/now.md`, not the public docs.
- Humans remain the final gate: only you commit, merge, and update project state.

Future tutorials will build on this flow: analytics endpoints (Phase 1), supply-chain verification (Phase 2), and MCP/ACP connectors once Certus Insight matures.
