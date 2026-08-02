---
name: feature-discovery
description: "Turn a vague group signal into an evidence-backed ChainTogether Feature Doc through CVO interviewing, research, independent discussion, convergence, and specification crystallization. Use when: a new or returned feature has unclear needs, journeys, scope, value decisions, research gaps, or acceptance criteria. Not for: planning or coding after Design Gate approval, or inventing product choices that require the operator. Output: a canonical Feature Doc with research, decisions, rejected alternatives, open questions, acceptance criteria, and a Design Gate packet."
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

## Next step

Load `$design-gate` after every requirement maps to a verifiable AC and the primary journey is explicit.
