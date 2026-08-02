---
name: design-gate
description: "Decide whether a discovered ChainTogether feature is safe and clear enough to plan by checking journeys, scope, architecture ownership, state lifecycles, risks, decisions, and operator sign-off. Use when: Discovery claims the Feature Doc is ready for implementation design, or design-level feedback requires reevaluation. Not for: code review, quality verification, implementation, or bypassing an unresolved operator value decision. Output: a revision-bound approved, changes_required, or blocked design verdict with evidence and named gaps."
---

# Design Gate

Review the canonical Feature Doc and linked discovery evidence from a role independent of the proposed implementer when practical.

## Evaluate

1. Trace each AC to an operator need and a verification method.
2. Confirm the journey's scope unit, entry, transitions, failure paths, and terminal state.
3. Identify architecture owner, boundaries, extension points, and expected architecture-map delta.
4. Census every lifecycle-bearing object. Require a state-event table, numbered invariants, and adversarial tests for crash, restore, concurrency, and bypass paths.
5. Check security, privacy, migration, compatibility, observability, rollback, and explicit non-goals.
6. Separate value decisions from technical decisions. Obtain operator sign-off for user-visible direction or irreversible value choices.
7. Record deliberate deviations and rejected alternatives.

## Verdict

Return exactly one:

- `approved`: ready for `writing-plans`
- `changes_required`: return to `feature-discovery`
- `blocked`: name the missing decision or authority

Bind the verdict to the Feature Doc revision and list evidence. Do not write implementation code.

## Next step

On `approved`, load `$writing-plans`. On `changes_required`, load `$feature-discovery`. On `blocked`, request the missing decision or authority before loading another stage Skill.
