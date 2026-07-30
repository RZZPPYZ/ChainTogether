---
name: quality-gate
description: Verify a completed ChainTogether implementation against original operator intent, Feature Doc requirements, acceptance criteria, fresh test and build evidence, real user journeys, and delivery completeness. Use before requesting independent review or when completion is claimed; do not use as the independent review or merge authority.
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
