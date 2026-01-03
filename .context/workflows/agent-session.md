# Agent Session Workflow

**How to run a multi-agent development session.**

## Quick Start

```bash
./scripts/dev.zellij.sh
```

This launches a zellij session with 4 panes:

- **Planner** (top-left)
- **Reviewer** (top-right)
- **Implementer** (bottom-left)
- **Tester** (bottom-right)

Each pane shows the bootstrap instructions automatically.

## Session Flow

### 1. Start Session

```bash
./scripts/dev.zellij.sh certus
```

You'll see 4 panes, each with bootstrap instructions displayed.

### 2. Activate Agents

In each pane, start your AI agent (Claude, GPT, etc.) and paste/reference:

- The bootstrap text (already shown)
- Role-specific bootstrap from `.context/bootstraps/`
- The specific task from `.context/tasks/now.md`

### 3. Coordinate Work

**Planner** (if using):

- Analyzes requirements
- Breaks down tasks
- Updates `.context/tasks/now.md`

**Implementer**:

- Writes code
- Follows scope from task
- Reports what files changed

**Tester**:

- Runs tests
- Verifies changes
- Reports failures

**Reviewer**:

- Checks diffs
- Verifies scope compliance
- Flags issues

### 4. Integration

You (the human) integrate:

1. Review all changes in Zed
2. Run final tests
3. Commit approved changes
4. Update `.context/CONTEXT.md` if needed

### 5. End Session

```bash
# Detach (keeps session running)
Ctrl+o, d

# Kill session
zellij kill-session certus
```

## Pane Navigation

```
Ctrl+o, h/j/k/l  - Move between panes (vim keys)
Ctrl+o, n        - Next pane
Ctrl+o, p        - Previous pane
Ctrl+o, d        - Detach
Ctrl+o, q        - Quit pane
```

## Common Patterns

### Solo Work (1 agent)

Just use one pane. Ignore the others.

### Pair (2 agents)

- Implementer + Tester
- Planner + Implementer
- Implementer + Reviewer

### Full Team (4 agents)

Only use when working on complex, multi-file features.

## Lock Coordination

If multiple agents active:

```bash
# Before agent starts work
touch .locks/auth-in-progress

# When done
rm .locks/auth-in-progress
```

## Tips

**Start small:**

- Use 1 pane for first few sessions
- Add complexity only when needed

**Keep bootstrap visible:**

- Each pane shows it on startup
- Scroll up if you need to see it again

**Reattach anytime:**

- Session persists even if you close terminal
- `./scripts/dev.zellij.sh` to reattach

**Custom layouts:**

- Edit `.context/zellij.kdl` for different pane arrangements
- Restart session to see changes

## Troubleshooting

**Panes not showing bootstrap:**

- Check `.context/bootstrap.txt` exists
- Restart session

**Can't attach:**

- `zellij list-sessions` to see active sessions
- `zellij kill-session certus` to force cleanup

**Wrong directory:**

- Script always cd's to repo root
- If fails, check `REPO_ROOT` in script
