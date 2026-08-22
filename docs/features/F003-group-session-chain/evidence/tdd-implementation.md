# F003 TDD Implementation Evidence

Date: 2026-08-19
Base: `1fb75b26370a2301c94f409d1d817c587d172cb3`
Implementation checkpoint: `a66dfda7cd1ba437435734fa1f7397f34314edc7`

## Red-green-refactor record

1. Durable generations started with failing DB tests for adoption, seal CAS,
   cursor preservation and atomic successor activation. Commit `caa1dd9` added
   the two SQLite state tables, uniqueness constraints and narrow transaction
   methods.
2. Fresh handoff tests first failed because no isolated one-shot entry point or
   bootstrap template existed. Commit `763af52` added the tool-free
   `OneShotContext` path, extractive fallback, provenance and D15 rendering.
3. Recall tests first failed with no routes, capability checks or mandatory MCP.
   Commit `ba88aef` added sealed-only reads, paging/search/invocation views and
   fail-closed caller-chain authorization.
4. Group runtime tests first failed because dispatch still reused one session
   indefinitely. Commit `6c8e824` added pre/post-turn policy checks, one-time
   bootstrap consumption, restart reconciliation, cleanup and ordinary
   FeatureRun/A2A preservation.
5. Frontend tests first failed because group member projections had no
   generation fields or live successor update. Commit `1860706` added API/store,
   WebSocket and `S<generation>/<length>` UI support.
6. Quality inspection deliberately returned to red with three adversarial
   tests: a capped bootstrap lost its closing data marker, a long projection
   lost the latest next step, and lifecycle states were not all broadcast. The
   tests failed before the fix; commit `a66dfda` preserves the closing marker,
   retains head and true tail, broadcasts every durable phase, and makes the UI
   mutate only on `successor_created`.

## Focused green evidence

```powershell
F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe -m unittest tests.test_group_session_chain tests.test_group_working_dir tests.test_session_chain_mcp -q
```

Result: `Ran 18 tests ... OK`.

```powershell
bunx vitest run src/hooks/useWebSocket.test.ts src/stores/sessionStore.test.ts src/components/GroupChatView.test.tsx
```

Result: 3 files, 15 tests passed.

## Refactor constraints retained

- `messages` stays the canonical transcript; projections never mutate source
  rows or depend on provider JSONL.
- The summary runner receives backend/model/credential/working directory only;
  it has no predecessor resume identity, MCP or connector authority.
- `group_agent_sessions` remains the active routing pointer, so existing group,
  A2A and FeatureRun paths do not need a competing source of truth.
- Bootstrap content is dynamic, capped, control-character sanitized and marked
  as untrusted data. Exact evidence is retrieved on demand.
