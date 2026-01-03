# Agent Workspace

This directory contains coordination files for AI-assisted development.

## Structure

```
.context/
├── CONTEXT.md            # Current project state (updated frequently)
├── bootstrap.txt         # Default startup handshake
├── bootstraps/           # Role-specific initialization prompts
│   ├── lite.md           # Default: focused tasks
│   ├── deep.md           # Architecture & design work
│   ├── security.md       # Security reviews
│   └── spike.md          # Short-lived experiments (vibe mode)
├── session-charter.md    # Multi-agent roles, locks, and handoffs
├── tasks/                # Task board (`now.md`, `backlog.md`)
└── workflows/            # Process documentation
    └── review.md         # How to review agent output
```

## Quick Start

**Launch multi-agent session:**

```bash
./scripts/dev.zellij.sh
```

This creates a zellij workspace with 4 panes (planner, reviewer, implementer, tester), each showing bootstrap instructions.

**Starting a single agent:**

1. Choose bootstrap based on task type (lite/deep/security or spike for scratch experiments)
2. Tell agent to load `AGENTS.md` (root) and `.context/CONTEXT.md`
3. Provide bootstrap file: `.context/bootstraps/[lite|deep|security].md`
4. Confirm ownership/locks in `.context/session-charter.md` + `.locks/`
5. Give specific task from `.context/tasks/now.md`

**Example prompt:**

```
Load and follow rules from AGENTS.md (repo root)
Load current context from .context/CONTEXT.md
Use lite bootstrap from .context/bootstraps/lite.md

Task: Update the API versioning documentation in docs/reference/api/
Files you may edit: docs/reference/api/api-versioning.md
```

See `.context/workflows/agent-session.md` for full multi-agent workflow.

## Files Reference

**AGENTS.md (root)** - Always loaded. Core rules and constraints.

**CONTEXT.md** - Always loaded. Current project state.

**bootstraps/lite.md** - For routine tasks with clear scope.

**bootstraps/deep.md** - For architecture, design, or complex changes.

**bootstraps/security.md** - For security reviews only.

**bootstraps/spike.md** - For sanctioned spike/vibe work (scratch branches).

**session-charter.md** - Defines roles, locks, and multi-agent coordination.

**tasks/now.md** - Current work queue (authoritative task board).

**workflows/review.md** - For humans reviewing agent work.

**TL;DR:**

- Files are truth
- Agents are tools
- Humans integrate
- Explicit > Implicit
