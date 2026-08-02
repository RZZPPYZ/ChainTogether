---
name: receive-review
description: "Verify and resolve ChainTogether review findings with tests and evidence, then return the updated HEAD to the same reviewer. Use when: the feature owner receives evidence-backed findings or a request_changes verdict for a known reviewed HEAD. Not for: self-approving fixes, agreeing performatively, silently reinterpreting unclear feedback, or changing the spec to avoid a valid defect. Output: finding-by-finding dispositions, reproduced failures, fix commits, tests, updated evidence, and the new HEAD."
---

# Receive Review

1. Parse every finding, severity, evidence, and reviewed HEAD.
2. Verify each finding against the code, Feature Doc, and runtime behavior before changing anything.
3. Classify it as code defect, test gap, documentation gap, design/spec gap, or unsupported claim.
4. For valid code findings, reproduce red before fixing, then run focused and regression tests.
5. For design/spec findings, stop implementation and return to the owning gate.
6. Push back with concrete evidence when a finding is incorrect.
7. Record disposition, fix commit, tests, and any generalized sweep for related failure modes.
8. Return the new HEAD to the same reviewer. Any code change makes the previous approval stale.

Do not mark the review stage complete until the reviewer issues a verdict covering the current HEAD.

## Next step

Load `$request-review` and return the new HEAD to the same reviewer. Any code change invalidates prior approval.
