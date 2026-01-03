## Trust Through Evidence

**If AI is to become our partner, it cannot be a black box.**

The cornerstone of Certus TAP is this: **trust must be earned through evidence, not assumed through complexity.**

### What This Means in Practice

- **Traceable Provenance**: Every artifact, every scan result, every AI output must have a cryptographically verifiable lineage
- **Auditable Decisions**: No decision should be opaque—log it, sign it, make it reviewable
- **Reproducible Results**: Research and analysis must be repeatable and verifiable by third parties
- **Transparent Reasoning**: AI systems should explain their conclusions, not just provide answers

### Why This Matters

In security, trust without evidence is faith—and faith has no place in risk management. When we delegate analysis to AI systems, we must be able to:

1. Verify what data it used
2. Understand how it reached conclusions
3. Reproduce its analysis independently
4. Hold it accountable when it's wrong

Certus TAP enforces this through **Assurance Manifests**, **cryptographic signing**, **ledger-based provenance**, and **evaluation frameworks** that treat AI outputs as hypotheses to be validated, not facts to be accepted.

### Start with the Evidence, Not the Ticket

Your Ticket Management System (TMS) is not your source of truth—it is the collaboration layer. The source of truth is the immutable evidence store:

- Each scanner (OpenGrep, ZAP, Trivy, Grype, etc.) outputs a signed SARIF or JSON file.
- Those files are stored in an OCI registry or a WORM-locked bucket, indexed by content digest.
- Tickets only reference that evidence, rather than owning it.

**Example:** `Evidence: ghcr.io/org/app@sha256:abcd.../trivy.sarif`

That single line in every ticket creates an unbreakable chain of custody between a human process and machine-verifiable proof.

---

## Immutability from Storage to Workflow

Evidence is immutable by design, and the workflows that manipulate it must respect the same constraint.

- Update findings only by re-running scans and re-synchronizing; manual edits break reproducibility.
- Never overwrite historical states—if a vulnerability returns, mark the event as a state change tied to new digests.
- Prefer content digests (`sha256:abcd...`) over filenames so references remain verifiable years later.
- Sign sync jobs (`cosign attest`, in-toto, etc.) so every batch of tickets or updates carries a proof of origin and timing.

This turns vulnerability management into a cryptographically provable audit trail, not a spreadsheet of opinions.

---

## Framework" Over Product

**The world doesn't need another rigid tool; it needs a blueprint.**

Certus TAP is not a product you buy and deploy. It's a **framework** you adopt and adapt.

### What This Means in Practice

- **Tool-Agnostic Design**: We don't lock you into specific scanners, models, or vendors
- **Composable Architecture**: Mix and match components based on your needs
- **Open Standards**: Built on MCP, AAIF, OPA, and other open protocols
- **Extensible by Design**: Add your own tools, models, and workflows

### Why This Matters

The AI landscape changes monthly. New models, new vulnerabilities, new regulatory requirements. A rigid product becomes obsolete. A flexible framework evolves with the ecosystem.

Organizations have unique contexts:

- Different compliance requirements (SOC 2, FedRAMP, GDPR)
- Different risk appetites
- Different security tools already in use
- Different AI maturity levels

Rather than force everyone into the same mold, Certus TAP provides the **patterns, practices, and infrastructure** for each organization to build their own assurance approach.

---

## Learning Through Understanding

> **We teach the "Semi-Hard Way"—no magic buttons, just transparent education.**

Inspired by Zed Shaw's _Learn Python the Hard Way_ and Kelsey Hightower's _Kubernetes the Hard Way_, Certus TAP refuses to hide complexity behind abstractions.

### What This Means in Practice

- **Hands-On Learning**: You'll build components yourself, not click "deploy"
- **Explainable Architecture**: Diagrams, workflows, and documentation reveal how things work
- **Progressive Complexity**: Start simple, add sophistication as understanding grows
- **No Vendor Magic**: If it seems magical, we explain how the magic works

### Why This Matters

Quick-start guides and one-click deploys create **users**. Deep understanding creates **practitioners**.

When (not if) something breaks, you need to understand:

- What failed and why
- How to diagnose the problem
- How to fix it
- How to prevent it

When you need to adapt the system to your context, you need to understand:

- What each component does
- How they interact
- What can be safely changed
- What are the architectural constraints

The "Semi-Hard Way" is harder upfront. But it creates competence, not dependency.

---

## Research-First Mindset

**This is a learning journey, not a product roadmap.**

Certus TAP prioritizes **research, experimentation, and exploration** over production readiness.

### What This Means in Practice

- **Research Capabilities First**: Enable experimentation before optimizing for scale
- **Reproducibility Over Performance**: Prove it works before making it fast
- **Documentation Over Features**: Understanding before expansion
- **Validation Over Velocity**: Ensure correctness before adding capabilities

### Why This Matters

The field of AI assurance is **uncharted territory**. We don't yet know:

- Which AI architectures are most trustworthy
- How to best evaluate AI security analysis
- What provenance granularity is sufficient
- How to balance automation with human oversight

Rushing to production means **encoding today's assumptions into tomorrow's technical debt**. Research-first means we:

1. **Explore** different approaches
2. **Measure** their effectiveness
3. **Publish** findings openly
4. **Iterate** based on evidence

The platform may never be "production-ready" in the enterprise sense—and that's okay. Its value is in **enabling research**, not replacing commercial products.

## Ethical AI for Human Good

**Guide people on how to use AI ethically and securely—not just to make money.**

Certus TAP exists to serve a higher purpose than profit: **responsible AI for societal benefit**.

### What This Means in Practice

- **Security-First Design**: Every AI capability is built with security guardrails
- **Privacy by Default**: Data handling follows privacy-first principles
- **Transparency**: Open source, open standards, open research
- **Accessibility**: Free for learning, research, and non-commercial use

### Why This Matters

AI is powerful—and power without responsibility is dangerous. As AI systems gain influence over:

- Security decisions
- Risk assessments
- Vulnerability prioritization
- Incident response

...we must ensure they are:

- **Secure** (not exploitable by attackers)
- **Private** (respecting data sensitivity)
- **Fair** (not biased or discriminatory)
- **Accountable** (traceable and auditable)

Certus TAP embeds these values into the **technical architecture**, not just the documentation. It's not enough to say "use AI responsibly"—we must build systems that **make irresponsible use difficult and responsible use natural**.

## Design for Verifiability, Not Just Visibility

Dashboards show what's happening; verifiability proves it. Every output must be independently checkable by an auditor, developer, or regulator.

- Prefer **signed attestations** to unsigned reports.
- Record **policy version**, **scanner/model version**, and **timestamp** for every result.
- Enable **re-verification** (replayability) from artifact digests without rerunning scans.

This ensures the assurance pipeline produces _proofs_, not just _reports_.

## Make AI Optional, Keep Humans in the Loop

AI can accelerate assurance but must never become a single point of failure or authority.

- Treat AI as a **copilot**, not a **controller**.
- Ensure every AI output is **traceable**, **explainable**, and **verifiable** via supporting evidence.
- Always allow human override; approvals, waivers, and sign-offs must remain attributable to a person or policy key.
- Build the pipeline so AI components can be disabled entirely without breaking the assurance flow.
- Log both **AI prompts** and **responses** in the immutable evidence store for accountability.

The goal isn't autonomous assurance; it's **assistive, auditable, and reversible** workflows.
