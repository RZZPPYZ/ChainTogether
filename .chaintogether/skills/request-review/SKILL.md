---
name: request-review
description: "Assemble a self-contained, SHA-bound ChainTogether review packet and assign an independent reviewer through autonomous Feature MCP or an explicit manual handoff. Use when: Quality Gate passed for the current HEAD, or fixes are ready for the same reviewer to re-review. Not for: reviewing one's own work, replacing quality verification, handing off an uncommitted or unidentified revision, or duplicating a committed Feature MCP handoff with ordinary group A2A. Output: a durable review packet containing intent, scope, ACs, diff, evidence, risks, known gaps, base SHA, head SHA, and requested verdict format."
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
7. Inspect D14 to choose exactly one handoff mechanism:
   - For an autonomous FeatureRun, call Feature MCP `request_review` with the
     packet evidence and exact HEAD. A successful mutation creates the durable,
     fresh Reviewer successor. Then end naturally without an `@handle`.
   - For a manual or non-Feature group task, keep the final `@Reviewer` handoff
     short and point to the packet.

Never fall back to ordinary A2A after an autonomous `request_review` failure or
success. On failure, preserve the packet and report the blocker so status/resume
can recover the exact Feature dispatch.

## Next step

Autonomous FeatureRun: commit the handoff through Feature MCP and let the fresh
Reviewer successor load `$review-feature`. Manual task: hand the packet to an
independent Reviewer explicitly against the exact HEAD.
