# F002 TDD Evidence - Task 3 Dispatch Generations

## Red

The two focused AC-10 tests errored because `FeatureDeliveryManager` had no
lease API. The tests require cryptographic raw-token rotation, hash-only
persistence, exact invocation linkage, fail-closed activation, terminal
failure recording, and idempotent one-generation resume.

After those primitives were made green, the handoff-pair test failed because
`FeatureManager.transition_for_dispatch` did not exist. This second red binds
the exact lifecycle mutation, capability consumption, waiting successor, and
predecessor terminal promotion into one contract.

## Green

Implemented:

- pending/expired-lease CAS with fresh lease and dispatch secrets;
- hash-only persistence and old-token invalidation;
- exact dispatch-to-GroupInvocation activation/linkage;
- terminal failure recording plus idempotent recovery generation creation;
- Session-and-dispatch-bound lifecycle transition;
- atomic predecessor `handoff_committed` plus one `waiting` successor;
- exact predecessor terminal promotion and late-callback idempotency.

Focused verification: `8` start/dispatch tests passed. The handoff test also
proves a wrong capability leaves FeatureRun at its original stage, a valid
capability advances it, replay fails closed, and only one successor is promoted.

Full Python regression: `71` tests passed, `1` environment-gated test skipped.
