# Review Workflow

**How to review agent output before integrating.**

## Review Checklist

### 1. Scope Verification

- [ ] Agent only changed files in scope
- [ ] No unexpected edits
- [ ] No scope creep

### 2. Code Quality

- [ ] Changes are understandable
- [ ] No obvious bugs
- [ ] Follows project conventions
- [ ] No unnecessary complexity

### 3. Testing

- [ ] Agent ran tests
- [ ] Tests pass
- [ ] New tests added if needed
- [ ] No regressions

### 4. Documentation

- [ ] Code comments where needed
- [ ] Docs updated if behavior changed
- [ ] ADR created if architectural

### 5. Security

- [ ] No hardcoded secrets
- [ ] No new vulnerabilities
- [ ] Input validation present
- [ ] Error handling safe

## Using Zed for Review

```bash
# See what changed
git status
git diff

# Review in Zed
# - Check diffs visually
# - Look for unexpected changes
# - Verify logic makes sense
```

## Common Issues to Watch For

**Agent went too far:**
- Refactored code outside task
- Added features not requested
- Changed things "while I was there"

**Agent misunderstood:**
- Implemented wrong thing
- Made incorrect assumptions
- Missed requirements

**Agent broke things:**
- Tests failing
- Removed necessary code
- Introduced bugs

## Decision Tree

```
Agent output ready?
├─ Yes → Run tests
│   ├─ Pass → Commit & integrate
│   └─ Fail → Ask agent to fix OR fix manually
└─ No → What's wrong?
    ├─ Out of scope → Revert extra changes, keep good parts
    ├─ Misunderstood → Clarify requirements, try again
    └─ Low quality → Fix manually OR give agent specific feedback
```

## Integration Steps

1. **Review** (this checklist)
2. **Test** (`just test` or specific test commands)
3. **Clean up** (revert out-of-scope changes if any)
4. **Commit** with clear message
5. **Update context** (`.context/CONTEXT.md` if needed)
6. **Release lock** (if using `.locks/`)

## When to Reject

Reject and ask for redo if:
- Major misunderstanding of requirements
- Significant scope violation
- Security issues introduced
- Tests fail and agent can't explain why

## When to Fix Manually

Fix yourself if:
- Minor style issues
- Small bugs easy to fix
- Agent is stuck in a loop
- Faster to just do it

## Remember

**You are the integrator.**
Agent proposes, you dispose.
Don't merge anything you don't understand or trust.
