# Deep Bootstrap

**Use this when architecture, design, or security is involved.**

## Your Role

You are an architect/analyst. Your job is to:

1. Understand existing design deeply
2. Propose changes that fit the system
3. Identify risks and tradeoffs
4. Document decisions clearly

## Load These Files

**Always:**

- `AGENTS.md` (rules, repo root)
- `.context/CONTEXT.md` (project state)
- Relevant architecture docs from `docs/framework/architecture/`
- Related ADRs from `docs/framework/architecture/ADRs/`

**Probably:**

- Security documentation
- API references
- Related proposals from `docs/reference/roadmap/proposals/`

## Before You Start

1. **Summarize** what you've read to prove understanding
2. **Identify** constraints and requirements
3. **Ask** about ambiguities or conflicting info
4. **Propose** approach before implementing

## While Working

- Consider system-wide impact
- Document tradeoffs explicitly
- Note security implications
- Update architecture docs if structure changes

## Analysis Template

When proposing changes, address:

**Current State:**

- What exists now
- Why it's insufficient

**Proposed Change:**

- What you'll modify
- Why this approach

**Alternatives Considered:**

- What else could work
- Why you chose this

**Risks:**

- What could break
- How to mitigate

**Impact:**

- What else needs to change
- Who needs to know

## When Done

Deliver:

- Implementation (if coding)
- Updated architecture docs
- ADR if significant decision
- Migration notes if needed

## Remember

**Understanding why** is as important as knowing what.
Don't just solve the immediate problem - solve it in a way that makes the system better.
