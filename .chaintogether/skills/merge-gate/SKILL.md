---
name: merge-gate
description: Decide whether a reviewed ChainTogether branch can be merged by verifying current HEAD, independent review continuity, CI and local evidence, merge safety, feature-document truth, and post-merge synchronization. Use after an approving review; do not use while review is stale, blocked, or incomplete.
---

# Merge Gate

1. Resolve the PR's current HEAD and compare it with the approved reviewed HEAD.
2. Require an independent reviewer, non-blocking verdict, passing Quality Gate, and fresh CI/local checks.
3. Verify every required evidence reference exists and describes the current code.
4. Reconcile the Feature Doc with code reality before merge. Do not mark unmerged work as delivered.
5. Check branch cleanliness, conflicts, migration and rollback risks, and repository merge policy.
6. Merge through the repository's authorized PR mechanism. Never disguise a closed PR as merged.
7. After merge, record merge commit/PR, update AC and timeline truth, and regenerate the feature index.
8. Preserve unrelated worktrees and user changes during cleanup.

Return a Merge Evidence Manifest containing feature, PR, base, head, reviewed head, reviewer, verdict, CI, quality evidence, merge result, and document-sync result. A merge moves the feature to vision acceptance, not directly to done.
