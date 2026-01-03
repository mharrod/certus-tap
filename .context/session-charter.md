# Session Charter (Multi-Agent Workflow)

Use this file to bootstrap any multi-agent session (Zed Agent Panel, zellij, tmux, etc.). It keeps roles, scope boundaries, and handoffs explicit.

## Policy

1. **AGENTS.md is mandatory** – confirm it is loaded before doing anything.
2. **Context is optional** – load only the files needed for your task (start with `CONTEXT.md` and `.context/tasks/now.md`).
3. **One agent speaks per decision** – propose in threads, but the Coordinator records the decision.

## Roles

| Role                       | Responsibilities                                                                 | Default Context                                                           |
| -------------------------- | -------------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **Planner**                | Break goals into tasks, update `.context/tasks/`, define file ownership & locks. | `CONTEXT.md`, `.context/tasks/now.md`, relevant proposals.                |
| **Implementer**            | Apply scoped changes only, keep diffs tight, update docs/tests.                  | Files listed on the task, module docs, relevant ADRs.                     |
| **Tester**                 | Run `./scripts/preflight.sh` + targeted tests, report failures with logs.        | Test files, scripts, CI notes.                                            |
| **Reviewer**               | Inspect diffs, security posture, and documentation impact.                       | This charter, `AGENTS.md`, relevant code/docs touched by the implementer. |
| **Security (temporary)**   | Audit auth/guardrails/IaC; report findings, no direct fixes.                     | `bootstrap-security.txt`, code under review, threat models.               |
| **Doc Scribe (on demand)** | Update `CONTEXT.md`, decisions, and release notes after milestones.              | `docs/02-decisions.md`, `.context/tasks/now.md`, change summaries.        |
| **Integrator (human)**     | Rebase/merge branches, enforce locks, ensure clean handoff to production.        | git history, CI logs, reviewer notes.                                     |

Only keep 2–4 panes/threads active at once. Reassign a pane to a new role when needed (e.g., Reviewer → Security) instead of creating more panes.

## Coordination Rules

1. **Declare ownership before editing**

- Planner or Coordinator assigns `Owner`, `Files`, and `Don't Touch` in `.context/tasks/now.md`.
  - Acquire a lock (`.locks/<area>.lock`) before editing shared folders; remove it on completion.

2. **Announce actions**
   - At task start: state role, files, and planned commands.
   - At task end: report files changed, tests run, risks, and locks released.

3. **Avoid collisions**
   - If two tasks need the same file, serialize: one agent edits, the other reviews or proposes diffs only.
   - Infrastructure/auth/crypto areas are single-writer: request approval before touching them.

4. **Handoffs** (all roles)

   ```
   ## Handoff
   Changes: <summary>
   Files: <paths>
   Commands: <tests/run steps>
   Risks: <known gaps or TODOs>
   Next: <next action or reviewer needed>
   ```

5. **Review gate**
   - Reviewer (or Security) must ACK changes before Integrator merges.
   - No merge if locks still exist or `./scripts/preflight.sh` is failing.

## When to Invoke Security Mode

Trigger `bootstrap-security.txt` when touching:

- Authentication, authorization, PII handling, anonymizers.
- New ingestion sources or schema changes.
- Infrastructure, IAM, crypto, or rate limiting.

Security agent reports findings + severity; Implementer (or human) applies fixes.

## Session Startup Checklist

1. Run `./scripts/dev.zellij.sh` (or open equivalent panes).
2. In each pane/thread: load `AGENTS.md`, `CONTEXT.md`, and this charter.
3. Assign roles + tasks from `.context/tasks/now.md`.
4. Acquire locks if needed.
5. Proceed with Modify → Lock → Build → Test.
6. Record outcomes + release locks + update tasks.

This charter is the single source for coordination. If reality diverges, update this file so future sessions inherit the truth.
