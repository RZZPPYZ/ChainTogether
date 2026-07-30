---
name: writing-plans
description: Convert an approved ChainTogether Feature Doc into a straight-line, testable implementation plan with exact files, AC coverage, state-object census, invariants, adversarial cases, and red-green-refactor steps. Use after Design Gate approval and before creating a worktree; do not use for discovery, unapproved designs, or trivial documentation-only edits.
---

# Writing Plans

1. Verify the Design Gate is approved and identify the exact Feature Doc revision.
2. Pin the finish line: one-sentence outcome, complete AC list, and non-goals.
3. Prefer steps whose outputs remain in the final system. Mark exploration as a time-boxed spike with a decision artifact.
4. Census lifecycle-bearing objects. For each, include:
   - lifecycle owner
   - state-event transition table
   - numbered invariants
   - crash, restore, concurrency, and bypass tests
5. Map every task to ACs and exact create/modify/test paths.
6. Write implementation steps in red-green-refactor order with exact commands and expected outcomes.
7. Include migration, compatibility, observability, rollback, documentation, and evidence collection where applicable.

Save the plan in the feature dossier and return its path, AC coverage, unresolved technical questions, and the proposed worktree name. Do not start implementation.
