# Core Principles

Certus TAP is built on a set of core principles that guide every design decision. These principles emerged from hard-won lessons about security, trust, transparency, and the responsible use of AI.

These principles are not set in stone. As we learn more about AI assurance, security, and trust, they will evolve. But they provide a **north star** for the journey.

If a proposed feature doesn't align with these principles, we don't add it. If a design decision violates these principles, we refactor.

The principles that form the foundation of Certus are TAP:

| Principle                                 | Core Question                               | Implementation                                                           |
| ----------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------------ |
| **Trust Through Evidence**                | Can we verify this?                         | Cryptographic provenance, signed artifacts, audit logs                   |
| **Immutability from Storage to Workflow** | Is there an audit trail we can reproduce?   | Immutable evidence stores, digest references, signed sync batches        |
| **Framework Over Product**                | Does this adapt?                            | Tool-agnostic design, composable architecture, open standards            |
| **Learning Through Understanding**        | Do users understand how this works?         | Semi-Hard Way tutorials, explainable architecture, no magic              |
| **Research-First Mindset**                | Are we learning or shipping?                | Prioritize experimentation, reproducibility, and validation              |
| **Ethical AI**                            | Does this serve humanity?                   | Security-first, privacy-aware, open, accessible                          |
| **Design for Verifiability**              | Can anyone independently check the outcome? | Signed attestations, policy/scanner versioning, replayable evidence      |
| **Make AI Optional**                      | Can humans override or disable AI?          | Copilot posture, traceable prompts/responses, AI components as removable |

These aren't aspirational values we hope to achieve someday. They are **architectural constraints** that shape every decision.
