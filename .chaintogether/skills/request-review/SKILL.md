---
name: request-review
description: Assemble a self-contained, SHA-bound ChainTogether review packet and assign an independent reviewer with the required context, artifacts, evidence, risks, and output contract. Use after Quality Gate passes or after review fixes are ready for re-review; do not use to review one's own work or to replace quality verification.
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
