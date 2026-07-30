---
name: close-feature
description: Close a ChainTogether feature only after merge and independent vision acceptance by synchronizing the canonical Feature Doc, evidence, decisions, timeline, indexes, and lessons. Use at the final closure stage or to audit a claimed-done feature; do not use to waive unmet acceptance criteria.
---

# Close Feature

1. Verify the merge result and independent Vision Gate acceptance.
2. Re-read all ACs and confirm their evidence references still resolve.
3. Reconcile roles, decisions, plans, review provenance, PRs, deviations, and timeline.
4. Resolve every unmet AC by implementing it, deleting it with explicit scope approval, or recording an authorized scope change. Never use vague deferral.
5. Record lessons, rejected alternatives worth preserving, and any new operating rule in the proper durable artifact.
6. Set frontmatter `stage: done`, `state: done`, and update the completion timestamp.
7. Run feature and skill validators and regenerate derived indexes.

Return the closed Feature Doc path, merge and vision evidence, validator results, and remaining explicitly separate features. Closure is a truth synchronization operation, not a celebratory summary.
