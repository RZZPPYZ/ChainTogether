---
name: merge-gate
description: "Decide whether a reviewed ChainTogether branch can be merged by verifying current HEAD, independent review continuity, CI and local evidence, merge safety, Feature Doc truth, and post-merge synchronization. Use when: independent review approved the current HEAD and merge readiness must be checked. Not for: stale or incomplete review, red quality or CI, unauthorized direct merges, or treating a closed PR as merged. Output: a Merge Evidence Manifest recording PR, base, current and reviewed HEAD, reviewer verdict, checks, merge result, and Feature Doc synchronization."
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

## Next step

After a real merge, load `$vision-gate` and assign an independent guardian to the merged revision.
