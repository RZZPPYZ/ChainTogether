---
name: vision-gate
description: "Independently validate a merged ChainTogether feature against the operator's original intent and real user journey, including technically correct delivery that may miss the desired experience. Use when: code is merged and an independent guardian must validate intent and experience before closure. Not for: author or code-reviewer self-acceptance, pre-merge testing, or equating checked ACs with product acceptance. Output: a merged-revision-bound accepted, changes_required, or blocked vision verdict with journey evidence and deviations."
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

## Next step

On `accepted`, load `$close-feature`. For a vision gap, load `$feature-discovery`. For an approved delivery fix, load `$worktree` and then `$tdd`.
