---
name: receive-review
description: Verify and resolve ChainTogether review findings without performative agreement, using tests and evidence, then return the updated HEAD to the same reviewer. Use when an author receives review findings or a request-changes verdict; do not use to self-approve fixes or silently reinterpret unclear feedback.
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
