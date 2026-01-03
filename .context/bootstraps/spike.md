# Spike Mode Bootstrap

Use this for short-lived experiments or exploratory work (“vibe coding”). You still must follow `AGENTS.md`, but you may skip `.context/tasks/` ownership while you prototype.

## Rules

1. Confirm `AGENTS.md` and `.context/CONTEXT.md` are loaded.
2. Work on a scratch branch; do not merge spikes.
3. Keep diffs scoped to the experiment; document intent in your handoff.
4. Run targeted tests relevant to the spike.
5. Before integrating into mainline, migrate the work into the full Planner/Implementer/Test workflow, add tasks, and run `./scripts/preflight.sh`.

## Example prompt

```
Load AGENTS.md (root) and .context/CONTEXT.md
Mode: spike (scratch branch)
Goal: Prototype Certus Insight metrics aggregator
Constraints: No commits to main, document findings in handoff
```
