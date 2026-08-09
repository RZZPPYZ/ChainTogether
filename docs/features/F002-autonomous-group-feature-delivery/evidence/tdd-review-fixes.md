# F002 TDD Evidence — Independent Review Fixes

## Reviewed boundary

- Reviewed HEAD: `848d2a7d4cad91aaff764bf49e8d8a277ae596fa`
- Verdict: `request_changes`
- Findings: three P1, three P2, one P3

## Red

Backend regression tests reproduced five failures:

- autonomous Session-only transition advanced the run;
- `doc_pending` had no blocker and launched the runtime;
- startup launched a manual run with no autonomous checkpoint;
- Review owner-preparation recovered to reviewer;
- role updates left pending dispatch revision stale.

Frontend regressions reproduced two failures:

- exact retry generated a different request key;
- incomplete `roles` syntax became a start request.

## Green

- `python -m unittest tests.test_feature_delivery_start tests.test_feature_dispatch_runtime tests.test_feature_routes tests.test_feature_mcp -q`
  — PASS, 30 tests.
- `npm test -- --run src/lib/featureCommand.test.ts src/components/GroupChatView.test.tsx`
  — PASS, 14 tests.
- Full backend — PASS, 93 tests with one pre-existing skip.
- Full frontend — PASS, 27 tests.
- Frontend typecheck and production build — PASS.
- Feature validation and `git diff --check` — PASS.

## Disposition

All findings were accepted as code defects/test gaps. Autonomous runs now
require dispatch-bound mutation; doc delivery gates launch and is retried on
resume/startup; reconciliation ignores manual runs; Review recovery derives
its durable owner/reviewer subphase from lifecycle events; role updates rebind
unlaunched dispatch revision atomically; the UI retains one request key for an
unaccepted exact draft; malformed role controls fail explicitly.
