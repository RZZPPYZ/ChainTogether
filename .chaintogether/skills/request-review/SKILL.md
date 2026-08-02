---
name: request-review
description: "Assemble a self-contained, SHA-bound ChainTogether review packet and assign an independent reviewer with the required context, artifacts, evidence, risks, and verdict contract. Use when: Quality Gate passed for the current HEAD, or fixes are ready for the same reviewer to re-review. Not for: reviewing one's own work, replacing quality verification, or handing off an uncommitted or unidentified revision. Output: a durable review packet containing intent, scope, ACs, diff, evidence, risks, known gaps, base SHA, head SHA, and requested verdict format."
---

# Request Review

1. Verify the Quality Report is current and passing.
2. Select a reviewer different from the author. Prefer a different backend/model family when available.
3. Capture exact `base_sha`, `head_sha`, branch, worktree, and Feature Doc revision.
4. Include:
   - original operator quote and source
   - Feature Doc, decisions, and plan
   - AC-to-evidence matrix and Quality Report
   - diff target and commands already run
   - known risks and open technical questions
   - architecture ownership and intentional deviations
5. Require findings with severity, evidence, and tight file locations, followed by `approve`, `request_changes`, or `blocked`, all bound to `head_sha`.
6. Persist the packet under the feature dossier before handing off.

In a group, keep the final `@Reviewer` handoff short and point to the packet. Do not paste an improvised summary that omits durable references.

## Next step

Hand the packet to an independent agent and have that agent load `$review-feature` against the exact HEAD.
