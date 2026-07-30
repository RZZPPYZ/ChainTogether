---
name: feature-discovery
description: Turn a vague group signal into an evidence-backed ChainTogether Feature Doc through CVO interviewing, local and external research, independent discussion, convergence, and specification crystallization. Use for new feature ideas, unclear requirements, hidden user needs, unresolved value questions, or a feature sent back from Design or Vision Gate; do not use once an approved design is ready for planning.
---

# Feature Discovery

Discovery ends with a reviewable Feature Doc, not code.

## Discover

1. Preserve the operator's original quote and group-message reference.
2. Inspect the repository, existing features, plans, decisions, and tests before asking questions.
3. Interview one decision at a time. Separate:
   - user outcome and pain
   - primary journey and scope unit
   - constraints and non-goals
   - value questions requiring the operator
   - reversible technical questions
4. Research material unknowns. Prefer local evidence first; record claim provenance and rejected sources. Use independent perspectives when a decision is high-impact or difficult to reverse.
5. Converge without erasing disagreement. Record alternatives, trade-offs, rejected options, decisions, and remaining questions.
6. Externalize architecture, state flow, or UX only when a visual makes ambiguity testable.
7. Update the canonical Feature Doc:
   - Why and Current State
   - Scope and Non-goals
   - User Journey
   - Requirements and traceable Acceptance Criteria
   - research and decision references
   - risks, open questions, and evidence expectations

## Readiness

Declare `ready_for_design` only when every requirement maps to at least one independently verifiable AC, value questions are answered or explicitly awaiting the operator, and the user journey has a clear entry, flow, terminal state, and success evidence.

Return changed artifact paths, unresolved questions, and the proposed Design Gate packet. Do not advance the workflow yourself.
