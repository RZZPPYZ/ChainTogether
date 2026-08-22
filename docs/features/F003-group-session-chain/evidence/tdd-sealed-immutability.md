# TDD Evidence — sealed predecessor immutability correction

- Feature: `F003-group-session-chain`
- Vision correction: `vision-verdict-e3d0517-changes.md`
- Branch: `codex/F003-sealed-immutability`
- Base: `7ba664890cad0d922bb1c34ce0668d9a43f77629`

## Cycle 1 — recovery and ordinary turn execution

Red:

- Backend test failed because archived SessionInfo had no `sealed` marker (`KeyError: 'sealed'`).
- Frontend test failed because a sealed predecessor still rendered an `Unarchive` button.

Green:

- Archived session/detail responses expose `sealed` from durable generation state.
- `unarchive_session_if_recoverable` uses one conditional SQL update, so a sealed predecessor cannot pass a read/check/write race.
- The unarchive route returns HTTP 409 with stable reason `session_sealed`.
- `send_message` checks durable generation state after acquiring the session lock and before persisting or spawning a harness.
- Archived Sessions renders sealed generations as read-only `Session Chain · sealed` evidence; ordinary archives retain `Unarchive`.

## Cycle 2 — all transcript writes

Red:

- An internal `inject_message` call could still append to a sealed predecessor and did not raise the expected error.

Green:

- `Database.append_message` atomically inserts only when the target is not a sealed generation.
- `SessionManager._persist_message` translates the database rejection to `SealedSessionError` and increments its in-memory message count only after a successful insert.
- The regression test verifies user-turn, internal-injection, harness, database message-count, in-memory count, and active-generation pointer invariants.

## Verification

- `python -m unittest tests.test_group_session_chain tests.test_session_chain_mcp -q`
  - PASS — 25 tests.
- `bunx vitest run`
  - PASS — 11 files, 33 tests.
- `bun run typecheck`
  - PASS.
- `bunx eslint src/components/ArchivedSessionsDialog.tsx src/components/ArchivedSessionsDialog.test.tsx`
  - PASS.
- `git diff --check`
  - PASS; only repository line-ending notices.
- Repository-wide `bun run lint`
  - Existing baseline remains red with 19 errors and 5 warnings in unrelated files; neither changed frontend file appears in the findings.

The Session Chain recall fixture was corrected to build its complete transcript before sealing. This is a test-data ordering change required by the new invariant, not a production bypass.

## Next Step

Load `$quality-gate` and verify the exact committed correction HEAD against AC-4, the Vision Gate deviation, full backend/frontend tests, contracts, build, and the real archive-management journey.
