---
name: vision-gate
description: Independently validate a merged ChainTogether feature against the operator's original intent and real user journey, looking for technically correct delivery that still misses the desired experience. Use after merge and before closure, or when a feature is returned for vision drift; do not use if you authored or code-reviewed the feature.
---

# Vision Gate

The guardian must be different from both author and code reviewer.

1. Read the original operator quote and discovery record before the implementation summary.
2. Execute or inspect the primary journey from entry to terminal state using merged code.
3. Compare actual behavior with Why, non-goals, journeys, ACs, design decisions, and evidence.
4. Ask:
   - Does this move the product toward the intended vision?
   - Did it introduce behavior that moves away from it?
   - Would the operator recognize this as the requested experience?
5. Treat AC checkboxes as inputs, never as the verdict.
6. Record unintentional deviations, missing experience, and evidence.

Return `accepted`, `changes_required`, or `blocked`, bound to merged revision and guardian identity. Changes return to discovery or implementation according to the root cause.
