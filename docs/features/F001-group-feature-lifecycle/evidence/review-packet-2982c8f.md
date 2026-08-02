# F001 fifth independent review packet

- Feature: F001 Group Feature Lifecycle
- Branch: `codex/group-feature-lifecycle`
- Base SHA: `13253f3`
- Previous reviewed HEAD: `522a4faf8e40fa5076b5a5f1bbc758f4b160ea13`
- Corrected HEAD: `2982c8fdd64ea36ac5ff89c6fb93b339bb59d803`
- Reviewer: the same independent `f001_reviewer`
- Requested verdict: `approved`, `request_changes`, or `blocked`, bound to the
  corrected exact HEAD

This packet is intentionally uncommitted so it cannot invalidate the reviewed
HEAD.

## Intent and scope

Review the complete F001 implementation from `13253f3..2982c8f`, with emphasis
on the three findings from the exact `522a4fa` review. F001 provides the durable
FeatureRun control plane, group-current Feature inheritance, D14 per-turn
stage/role/Skill/next-step injection, lifecycle Skill registry, independent
Review/Vision gates, evidence and Git provenance, and recoverable canonical
Feature Doc synchronization.

## Dispositions since `522a4fa`

1. Final Feature Doc and protected Git HEAD preconditions are passed into the
   database transition API. They execute under the Feature write lock
   immediately before SQL CAS. Database-boundary verdict mutation and Git
   commit regressions both leave the run in Review.
2. Feature role mutations use the same database-bound document precondition.
3. Pending outbox image selection, synchronous disk delivery, and
   version-matched deletion now execute as one database-owned operation under
   the same Feature write lock used by transitions and role changes. The old
   split completion API was removed. A regression asserts disk delivery occurs
   while that lock is held; existing tests cover failed recovery, chained later
   mutations, and external-edit conflict rejection.

Full dispositions: `evidence/review-response-522a4fa.md`.

## Active review probes

- Repeat approved-to-pending mutation and a Git HEAD advance at the database
  method boundary; confirm neither state nor event advances.
- Attempt the old v1-worker/v2-supersession schedule. Verify no pending image
  leaves the serialized selection/delivery/completion critical section and
  that transitions cannot enqueue v2 until v1 delivery returns.
- Recheck previous security and recovery findings: concurrent CAS, structured
  reviewer/guardian provenance, real evidence paths, fail-closed Git, legacy
  outbox delivery, session capability isolation, and capability-free provider
  argv.
- Review the entire diff `13253f3..2982c8f`, not only the latest correction.

Do not edit the reviewed branch. Findings must include severity and tight
file/line evidence. Approval must name the exact corrected HEAD.

## Fresh Quality Gate

- Python compile: passed.
- Python unit tests: 59 passed; 1 environment-gated live GitHub smoke skipped.
- Frontend Vitest: 8 files, 19 tests passed.
- TypeScript typecheck: passed.
- Vite production build: passed; existing chunk-size warning only.
- Skill validation: 13 Skills, 10 stages, 16 transitions passed.
- Provider sync: 26 mounts passed.
- Feature validation and `git diff --check`: passed.
- ESLint remains the unchanged repository baseline of 20 errors and 5 warnings
  in pre-existing frontend files outside the F001 implementation diff.

## Known residual boundary

The serialized filesystem/outbox protocol is scoped to one ChainTogether
control-plane process, matching the current application deployment model. F001
does not claim a distributed multi-process filesystem transaction.
