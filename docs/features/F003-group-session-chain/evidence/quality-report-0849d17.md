# F003 Quality Report — sealed predecessor correction

- Verdict: **pass**
- Implementation HEAD: `0849d174027b85f3dff56a46a81f75d4cc191449`
- Base: `7ba664890cad0d922bb1c34ce0668d9a43f77629`
- Trigger: Vision Gate `changes_required` on merged revision `e3d05178d768e01728e98bc6b9aa4c713bc7afb7`
- Scope: sealed predecessor immutability, recovery UX, additive API contract, and regressions

## Operator intent and coverage

The original operator requested proactive sealing, a fresh successor, durable
old-session evidence, fresh-context handoff summarization, and MCP recall. The
first merged delivery implemented that journey, but the independent guardian
proved the predecessor could be revived and modified through ordinary archive
management. This correction closes that deviation without changing discovery
scope or weakening exact Session Chain recall.

No requirement is missing from the Feature Doc ACs. R3 maps to AC-2/AC-4 and
R7 maps to AC-8/AC-9; those are the directly corrected requirements. The full
AC-1 through AC-11 suite was rerun because database write semantics and the
public SessionInfo contract are shared surfaces.

## Requirements / AC / evidence matrix

| Requirement | AC | Fresh evidence at 0849d17 | Result |
|---|---|---|---|
| Ordered durable chain and one active pointer | AC-1, AC-2 | 52-test focused backend suite; runtime rotation regression; 130-test full suite | pass |
| Early warning/action prediction | AC-3 | focused policy/group tests and full suite | pass |
| Exact immutable predecessor transcript | AC-4 | `test_sealed_predecessor_cannot_be_unarchived_or_written`: unarchive, normal turn, internal injection and database insert all fail before mutation; counts and active pointer remain unchanged | pass |
| Fresh tool-free summary and fallback | AC-5 | focused group/prompt suite and full regression | pass |
| Safe one-time D-layer bootstrap | AC-6 | focused group/prompt suite and full regression | pass |
| Capability-bound exact MCP recall | AC-7 | Session Chain MCP tests page/search the complete pre-seal transcript; invalid fixture ordering was removed rather than bypassing the invariant | pass |
| Group cursor, ownership and routing continuity | AC-8 | focused group/FeatureRun tests and full regression | pass |
| Archive rather than delete; no ordinary recovery | AC-9 | atomic conditional unarchive rejects sealed rows; REST maps it to 409 `session_sealed`; archive UI gives sealed rows View plus `Session Chain · sealed`, but no Unarchive; ordinary archives remain recoverable | pass |
| Observable generation/lifecycle state | AC-10 | additive `sealed` API field, generated contracts, UI label, and existing lifecycle event/reload tests | pass |
| Tests, contracts, build and validators | AC-11 | command matrix below | pass |

## Primary correction journey

The automated backend journey creates a group member, persists its transcript,
crosses the action threshold, seals generation 1 and creates generation 2. It
then verifies all of the following against durable state:

1. generation 1 appears archived with `sealed: true` and generation 2 remains
   the group member pointer;
2. manager unarchive is rejected and the REST surface reports HTTP 409 with
   stable reason `session_sealed`;
3. a deliberately reintroduced stale live object cannot execute a normal turn
   or reach the harness;
4. internal message injection is also rejected by the database-level atomic
   insert predicate;
5. persisted and in-memory message counts do not change;
6. Session Chain recall remains pageable and searchable because the complete
   transcript is constructed before sealing.

The frontend journey loads one sealed predecessor and one ordinary archive.
The sealed row remains viewable and is labeled Session Chain evidence with no
Unarchive control; the ordinary row retains Unarchive. A WebSocket-created
ordinary replacement explicitly initializes `sealed: false`.

## Fresh command evidence

All commands below ran in
`F:/RZP_program/my_project/ChainTogether/.worktrees/F003-sealed-immutability`
against the implementation tree at `0849d17`.

| Command | Exit | Result |
|---|---:|---|
| `F:/RZP_program/my_project/ChainTogether/.venv/Scripts/python.exe -m unittest discover -s tests -q` | 0 | 130 tests passed; 1 skipped |
| `...python.exe -m unittest tests.test_group_session_chain tests.test_session_chain_mcp tests.test_group_routing tests.test_prompt_governance tests.test_feature_dispatch_runtime -q` | 0 | 52 focused tests passed |
| `bun run test` | 0 | 11 files, 34 tests passed |
| `bun run typecheck` | 0 | TypeScript passed |
| `bun run build` | 0 | production build passed; 6,987 modules; existing chunk-size warning only |
| `bunx eslint src/components/ArchivedSessionsDialog.tsx src/components/ArchivedSessionsDialog.test.tsx src/hooks/useWebSocket.ts src/hooks/useWebSocket.test.ts` | 0 | all changed hand-written frontend files clean |
| `...python.exe scripts/check-features.py` | 0 | 3 features valid |
| `...python.exe scripts/check-skills.py` | 0 | 13 skills, 10 stages, 16 transitions valid |
| `...python.exe scripts/sync-skills.py --check` | 0 | 26 provider skill mounts synchronized |
| OpenAPI dump plus `bunx openapi-typescript .openapi.json -o src/api/contracts.ts` | 0 | regeneration produced a clean worktree |
| `git diff --check 7ba6648..HEAD` | 0 | clean |

## Lint scope disposition

Repository-wide `bun run lint` remains red with 15 errors and 5 warnings in
legacy files outside this correction. `git diff --name-only 7ba6648..0849d17`
has zero overlap with every file named by that lint result. The one previously
reported changed-file issue in `useWebSocket.ts` was fixed and the scoped lint
above is green. The Feature implementation plan explicitly calls for recording
the existing lint disposition; expanding this Vision correction into a
repository-wide React lint migration would be a separate feature.

## Invariants, compatibility and artifact hygiene

- The database owns the final write barrier: an INSERT cannot target a
  generation whose durable status is `sealed`.
- Unarchive uses one conditional UPDATE, closing check/write races with seal.
- Message counters advance only after successful persistence.
- No schema migration is needed; the correction uses existing generation
  status. `SessionInfo.sealed` is additive and defaults to false.
- Direct chat, schedules, bridges, A2A and FeatureRun routing remain outside
  rotation scope and passed the full regression.
- Generated contracts are synchronized; build artifacts and provider skill
  mirrors are ignored environment outputs; `git status --porcelain` is empty.

## Residual risks

- Repository-wide frontend lint debt remains explicitly separate from F003.
- Production bundles retain the existing >500 kB chunk warning.
- Archived-session rendering performs a generation lookup per archived row;
  this is acceptable for the administrative surface but could be batched if
  archive populations become large.

## Next Step

Quality `pass` permits `$request-review`. It does not authorize merge. The
reviewer must inspect the exact correction revision independently before a new
Merge Gate.
