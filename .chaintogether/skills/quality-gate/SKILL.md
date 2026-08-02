---
name: quality-gate
description: "Verify a completed ChainTogether implementation against operator intent, Feature Doc requirements, acceptance criteria, fresh test and build evidence, real user journeys, and delivery completeness. Use when: implementation is claimed complete and needs fresh requirements, AC, test, lint, build, journey, and artifact verification. Not for: independent code approval, merge authorization, or accepting known failures without explicit scope disposition. Output: a Quality Report with pass, fail, or blocked, exact commands and results, AC-to-evidence mapping, gaps, and residual risks."
---

# Quality Gate

No completion claim is valid without fresh evidence.

1. Read the operator quote, journey, approved design, plan, and current diff.
2. Build a requirements-to-AC-to-evidence matrix. Flag requirements missing from the ACs.
3. Verify every AC with a fresh command, inspection, screenshot, or reproducible manual path.
4. Run the repository's relevant tests, lint, typecheck, and build commands. Record exact command, exit code, and summary.
5. Exercise the primary user journey end to end for user-visible behavior.
6. Check error paths, state invariants, migration, compatibility, observability, documentation, and artifact hygiene.
7. Compare the delivered slice with the complete feature. Partial delivery requires explicit scope approval.
8. Write a Quality Report in the feature evidence directory.

Return `pass`, `fail`, or `blocked`, plus evidence paths and uncovered gaps. `pass` permits `request-review`; it is not approval to merge.

## Next step

On `pass`, load `$request-review`. On `fail`, return to `$tdd`. On `blocked`, resolve the named dependency or decision before continuing.
