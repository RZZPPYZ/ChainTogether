# F002 Quality Report

- Date: 2026-08-09
- Verdict: **pass**
- Scope: autonomous group `/feature` start, routing, MCP handoffs, recovery,
  role enforcement, UI status/controls, generated contracts, and docs
- Implementation base: `3ea65be7a99ef19e3271ab235ef3921d0666e454`
- Review boundary: the exact implementation HEAD must be recorded after this
  report is committed; Quality Gate does not authorize merge.

## Fresh verification

| Check | Result |
|---|---|
| `F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe -m unittest discover -s tests -q` | PASS: 93 tests, 1 skipped |
| `F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe -m compileall -q server tests` | PASS |
| `F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe scripts\check-skills.py` | PASS: 13 Skills, 10 stages, 16 transitions |
| `F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe scripts\sync-skills.py --check` | PASS: 26 provider mounts |
| `F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe scripts\check-features.py` | PASS: 2 Features |
| `npm test -- --run` | PASS: 9 files, 27 tests |
| `npm run typecheck` | PASS |
| `npm run build` | PASS: production Vite bundle built |
| `git diff --check` | PASS |

The OpenAPI contract was freshly generated from the application schema using
`scripts/dump-openapi.py` and `openapi-typescript`; the generated
`web/src/api/contracts.ts` includes the new group and Session Feature routes.

## Lint baseline disposition

`npm run lint` remains red on the repository baseline (35 errors and 5
warnings across unrelated and pre-existing files). A changed-surface run found
no new errors:

- baseline `GroupChatView.tsx`: 4 errors, 1 warning;
- current `GroupChatView.tsx`: 4 errors, 1 warning, with the same rules;
- baseline `SlashCommandMenu.tsx`: 4 errors;
- current `SlashCommandMenu.tsx`: 4 errors;
- new `featureCommand.ts`, its tests, and the new GroupChatView tests: PASS.

The errors are existing Fast Refresh export layout and `Date.now()` render
purity debt. This Feature neither expands the error count nor waives a new
failure. Repository-wide lint cleanup remains separate scope.

## Acceptance criteria to evidence

| AC | Evidence | Result |
|---|---|---|
| AC-1, AC-8 | `featureCommand.test.ts`, `GroupChatView.test.tsx`, production build | PASS: dedicated command path, status UI, and exact draft preservation |
| AC-2, AC-3 | `test_feature_delivery_start.py` | PASS: zero-side-effect roster rejection and deterministic distinct roles |
| AC-4, AC-9 | `test_feature_delivery.py`, `test_feature_delivery_start.py` | PASS: atomic checkpoint, idempotency, active-pointer race, and doc recovery |
| AC-5, AC-11 | `test_feature_mcp.py`, harness tests | PASS: mandatory MCP and child-env-only authority for Claude Code/Codex |
| AC-6 | `test_feature_routes.py`, `test_feature_delivery.py`, `test_feature_mcp.py` | PASS: Session/dispatch binding, actor gates, replay/stale/missing evidence failure |
| AC-7 | `test_feature_dispatch_runtime.py` | PASS: atomic waiting successor, exact terminal promotion, fresh depth-zero launches |
| AC-10 | delivery and runtime restart tests | PASS: lease rotation, generation binding, startup reclaim, idempotent resume |
| AC-12 | fresh verification matrix above | PASS with documented no-new-error lint baseline disposition |
| AC-13 | start, route, and runtime tests | PASS: distinct eligible actors, operator-only role patch, unavailable backend block |
| AC-14 | start authorization assertions and lifecycle gate enforcement | PASS: scoped commit/push/PR/merge authority; bypass and unrelated effects remain denied |

## Real journey evidence

`test_multi_round_review_journey_uses_fresh_role_bound_generations` exercises
Discovery through Closure, including owner Review preparation, independent
request-changes, owner fix, renewed Quality, same reviewer re-review, Merge,
independent Vision, and Closure. Each dispatch creates a fresh depth-zero group
invocation, uses the stage actor matrix, and ends with the active pointer
cleared and the start checkpoint marked done.

Frontend integration tests exercise the operator-facing entry: one sentence
uses the dedicated Feature API rather than ordinary group `/send`, displays the
Feature status, and retains the exact sentence after a preflight failure.

## Independent Review repair verification

The first independent Review of exact HEAD `848d2a7d4cad91aaff764bf49e8d8a277ae596fa`
returned `request_changes` with seven reproducible findings. Each finding was
first encoded as a failing regression test, then fixed. Fresh evidence covers:

- rejection of Session-only transition for autonomous runs;
- canonical Feature Doc delivery before any launch, including resume/startup;
- startup exclusion of historical manual runs without FeatureStart authority;
- durable owner/reviewer Review subphase recovery;
- role-update rebinding of unlaunched dispatch revision and a successful
  transition by the new owner;
- stable exact-draft request key after a lost response;
- explicit rejection of malformed `roles` control syntax.

See `evidence/review-findings-848d2a7.md` and
`evidence/tdd-review-fixes.md`. A new exact HEAD still requires approval from
the same reviewer before Merge Gate.

## Gaps and residual risks

- No manual browser session was used; UI journey evidence is component-level
  plus a production build. Independent Vision Gate must still judge whether
  the merged experience matches the operator's one-sentence intent.
- Multi-process distributed scheduling remains explicitly out of scope; the
  implementation provides restart-safe single-control-plane reconciliation.
- Repository-wide lint debt is unchanged and should be tracked separately.
- A live Agent can still fail to call the MCP. That exact dispatch becomes a
  visible blocker and `/feature resume` creates a recovery generation; the
  system does not silently claim progress.

## Gate conclusion

All F002 acceptance criteria have fresh automated evidence, generated artifacts
are synchronized, and no new lint error was introduced. Quality Gate passes.
The next authorized action is a SHA-bound independent Review request.
