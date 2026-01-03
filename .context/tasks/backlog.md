# Task Backlog

**Future work. Lower priority.** Use the same template as `now.md`, but set `Status: queued` and include project/proposal references so future implementers know the source.

```markdown
### [Future Task]

**Owner:** [unassigned or TBD]
**Project/Proposal:** [docs/reference/... or epic link]
**Phase/Milestone:** [phase or target sprint]
**Files:** [expected files]
**Don't Touch:** [restricted files]
**Status:** queued
**Description:** [summary + acceptance notes]
```

Example:

```markdown
### Certus Insight – Analytics Endpoint

**Owner:** TBD
**Project/Proposal:** docs/reference/roadmap/proposals/core/certus-insight-proposal.md
**Phase/Milestone:** Phase 1 – Analytics & Dashboards
**Files:** certus_insight/routers/analytics.py, certus_insight/services/analytics/\*
**Don't Touch:** certus_assurance/\*\*
**Status:** queued
**Description:** Build `/v1/analytics/summary` returning trend metrics from sample SARIF data.
```

## Documentation

- Expand testing documentation
- Add more architecture diagrams
- Create quickstart guides for each component
- Document development workflows

## Infrastructure

- Set up automated link checking
- Add spell checking to CI
- Improve search functionality
- Optimize build performance

## Content

- Complete all component reference docs
- Expand troubleshooting guides
- Add more examples and tutorials
- Create video walkthroughs

## Technical Debt

- Review and clean up old proposals
- Consolidate duplicated content
- Update outdated screenshots
- Fix broken links

---

**Note:** Move items to `now.md` when ready to work on them.
