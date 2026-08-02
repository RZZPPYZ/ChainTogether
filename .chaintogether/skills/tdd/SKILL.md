---
name: tdd
description: "Implement a ChainTogether feature or bug fix with observable red-green-refactor cycles tied to the approved plan and acceptance criteria. Use when: production code, scripts, APIs, schemas, runtime prompts, or executable behavior must change after worktree preparation, including review fixes. Not for: discovery, pure research, planning, independent review, or documentation-only work with no executable effect. Output: red-green-refactor evidence, minimal implementation, focused and regression test results, changed paths, and remaining plan tasks."
---

# TDD

For each behavior:

1. Select the AC, invariant, or reproduced failure being implemented.
2. Write the smallest test that fails for the intended reason.
3. Run it and preserve the red evidence.
4. Write the minimum implementation that makes it pass.
5. Run the focused test and relevant surrounding suite.
6. Refactor only while tests remain green.
7. Commit a coherent change referencing the feature ID.

For bugs, reproduce the bug before fixing it. For stateful behavior, test transitions and invariants, not only final values. Never weaken or delete a valid test merely to obtain green.

Return changed files, tests added, commands run, remaining plan tasks, and evidence paths. Route completed implementation to `quality-gate`.

## Next step

Load `$quality-gate` when every planned behavior and AC has passing evidence. Otherwise continue the next red-green-refactor cycle with `$tdd`.
