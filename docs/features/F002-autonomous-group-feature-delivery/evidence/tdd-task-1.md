# F002 TDD Evidence - Task 1 Durable Primitives

## Red

Command:

```text
..\..\.venv\Scripts\python.exe -m unittest tests.test_feature_delivery -v
```

Observed before implementation: `4` tests ran; `3` failed and `1` errored.
The failures were the intended missing contracts:

- `feature_start_requests` had none of the checkpoint fields;
- `feature_dispatches` and its partial uniqueness constraints did not exist;
- `feature_invocation_links.dispatch_id` did not exist;
- a legacy `feature_doc_syncs` table did not migrate `sync_mode`.

This establishes the red baseline for invariants I2, I3, I6 and I7.

## Green

Implemented:

- durable start-request and revision-bound dispatch tables;
- state and target-role checks;
- one invocation-bearing plus one unlaunched dispatch partial indexes;
- invocation-to-dispatch generation linkage;
- legacy-safe create-only/update document outbox mode;
- typed database row decoders and read methods.

Verification:

- focused Task 1 suite: `4` tests passed;
- F001 lifecycle regression suite: `16` tests passed;
- full Python suite: `63` tests passed, `1` environment-gated test skipped;
- `compileall` passed.
