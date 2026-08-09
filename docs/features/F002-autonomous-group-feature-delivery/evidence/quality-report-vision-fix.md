# F002 Quality Report — Vision handoff correction

- Date: 2026-08-09
- Verdict: **pass**
- Scope: ordinary A2A suppression inside exact Feature dispatch predecessors,
  fresh successor authority, L0/D14 lifecycle-handoff instructions, and all
  F002 regressions
- Base: `main@6cd0541e1866e86745a64e2b52b5edb330998bae`
- Review boundary: independent Review must bind the committed correction SHA;
  this Quality verdict does not authorize merge by itself.

## Fresh verification

| Check | Result |
|---|---|
| Python `unittest discover -s tests -v` | PASS: 95 tests run, 1 explicit live-network persona smoke test skipped |
| `test_feature_dispatch_runtime` | PASS: 8/8, including exact Review owner-prep and lifecycle edge table |
| `test_prompt_governance` + `test_group_routing` | PASS: 13/13 |
| Python `compileall -q server tests` | PASS |
| `scripts/check-skills.py` | PASS: 13 Skills, 10 stages, 16 transitions |
| `scripts/sync-skills.py --check` | PASS: 26 provider Skill mounts |
| `scripts/check-features.py` | PASS: 2 Feature Docs |
| Fresh OpenAPI generation and comparison | PASS: `contracts.ts` matches generated schema |
| `npm test -- --run` | PASS: 9 files, 27 tests |
| `npm run typecheck` | PASS |
| `npm run build` | PASS: production Vite bundle |
| `git diff --check` | PASS |

The production build retains the repository's existing large-chunk warning; it
does not fail the build and is unrelated to this server routing correction.

## Lint baseline disposition

Repository-wide `npm run lint` remains red with 33 errors and 5 warnings in
pre-existing frontend files. This correction changes no `.ts` or `.tsx`
production or test file, so it introduces no frontend lint finding. The current
count is lower than the previously recorded F002 baseline of 35 errors and 5
warnings, but that unrelated movement is not claimed as part of this fix.

## AC-to-evidence mapping

| AC | Evidence | Result |
|---|---|---|
| AC-5, AC-6 | Existing Feature MCP/route tests plus exact authority assertions in the new Review journey | PASS: MCP remains the dispatch-bound mutation channel |
| AC-7 | `test_request_review_mention_waits_for_fresh_successor` | PASS: predecessor runs Owner only; Reviewer runs once in another depth-zero invocation with successor authority |
| AC-7 | `test_lifecycle_edge_mentions_never_route_in_predecessor` | PASS: review-to-owner, merge-to-guardian, and acceptance-to-owner cannot use predecessor A2A |
| AC-10 | Full delivery/runtime tests | PASS: terminal promotion, lease, restart, and generation invariants remain green |
| AC-12 | Full fresh matrix above | PASS |
| Operator journey | L0/D14 assertions | PASS: Agent instructions name Feature MCP as the exclusive lifecycle handoff and forbid duplicate `@handle` routing after commit |

All other F002 ACs retain their original full-suite evidence and were covered by
the fresh 95-test backend and 27-test frontend regression runs.

## Residual risks

- The new end-to-end GroupManager test uses deterministic mocked Agent replies
  while exercising real FeatureManager, DeliveryManager, invocation, dispatch,
  Session, and message-routing state. Independent Vision must still replay the
  merged behavior from the user-experience boundary.
- If a Feature actor never commits its required MCP mutation, the exact
  invocation can end without a successor. Status/resume remains the deliberate
  recovery path; the system does not route an unprivileged teammate as fallback.
- Distributed multi-process scheduling and repository-wide frontend lint debt
  remain outside F002 scope.

## Gate conclusion

The Vision finding is reproduced, corrected, and protected without weakening
ordinary group A2A behavior. Quality Gate passes. The next authorized action is
a SHA-bound independent Review of the committed correction.
