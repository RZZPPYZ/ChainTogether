# F002 Autonomous Group Feature Delivery - Implementation Plan

**Approved Feature revision:** `ed9bda4072ebfdb633f9973545530a6c6aff6f8a`

**Design verdict:** `evidence/design-verdict-ed9bda4.md`

**Finish line:** one group `/feature <requirement>` creates exactly one
recoverable FeatureRun with three distinct roles, then Session-and-dispatch-
bound Agents move it through fresh successor invocations until gated delivery.

## Acceptance coverage

| AC | Tasks | Primary verification |
|---|---|---|
| AC-1 | 7 | group command parser/menu component tests |
| AC-2 | 2 | zero-side-effect insufficient-roster test |
| AC-3 | 2, 7 | stable resolver/default owner and returned-role tests |
| AC-4 | 1, 2 | atomic start and every checkpoint recovery test |
| AC-5 | 4, 5 | core MCP tool and routing packet tests |
| AC-6 | 3, 4, 5 | wrong Session/token/generation and replay tests |
| AC-7 | 3, 6 | multi-invocation Review/fix/Vision journey |
| AC-8 | 7 | active status, assignments, and draft preservation tests |
| AC-9 | 2 | same/different concurrent start tests |
| AC-10 | 3, 6 | resume/transition/lease/terminal/restart races |
| AC-11 | 4 | Claude/Codex argv/env and optional-selection tests |
| AC-12 | 8 | full backend/frontend/contracts/validator quality matrix |
| AC-13 | 2, 5, 7 | role command, role loss, no MCP self-reassignment |
| AC-14 | 2, 5, 8 | persisted authorization and fail-closed policy evidence |

## State-object implementation map

| Object | Create/modify paths | Tests |
|---|---|---|
| FeatureStart checkpoint | `server/database.py`, `server/feature_delivery.py`, `server/models.py` | `tests/test_feature_delivery.py` |
| FeatureRun/active/doc outbox | `server/database.py`, `server/feature_manager.py` | existing workflow tests plus delivery tests |
| FeatureDispatch/lease/capability | `server/database.py`, `server/feature_delivery.py`, `server/crypto.py` if a shared hash helper is appropriate | dispatch concurrency/replay tests |
| GroupInvocation link/terminal callback | `server/database.py`, `server/group_manager.py`, `server/main.py` | group successor/restart tests |
| Per-turn dispatch env | `server/group_manager.py`, `server/session_manager.py`, `server/harness/run.py`, `server/harness/assembly.py` | harness argv/env tests |
| Feature MCP | `server/mcp_servers/feature.py`, `server/harness/assembly.py` | `tests/test_feature_mcp.py` |
| Session-bound API/routing packet | `server/routers/features.py`, `server/feature_manager.py`, `server/feature_delivery.py`, `server/models.py` | route/manager identity tests |
| UI draft/command/status/roles | `web/src/components/SlashCommandMenu.tsx`, `web/src/components/GroupChatView.tsx`, `web/src/stores/sessionStore.ts`, `web/src/api/contracts.ts` | `GroupChatView.test.tsx` and command helper tests |

## Numbered invariants implemented by tests

The canonical invariants are I1-I15 in `evidence/orchestration-design.md`.
Implementation must give each invariant at least one named test. In particular:

- I1/I10/I11: no dispatch or MCP code writes Feature stage outside
  `FeatureManager.transition_for_session`.
- I2/I3: active pointer claim and request key are one start transaction.
- I6/I7/I8: one invocation-bearing predecessor plus at most one unlaunched
  successor; exact binding and fresh depth-zero invocation.
- I9/I10: Session capability plus one-time dispatch capability, consumed in the
  mutation/handoff transaction.
- I12/I13: actor matrix and role loss fail closed.
- I14/I15: terminal cleanup and policy-bounded authorization.

## Task 1 - Schema and durable primitives (AC-4, AC-9, AC-10)

**Red**

1. Add migration/schema tests in `tests/test_feature_delivery.py` for:
   - `feature_start_requests` request-key uniqueness and checkpoint fields;
   - `feature_dispatches` revision/purpose/generation, predecessor link,
     capability hash, lease, invocation ID, and state constraints;
   - invocation-to-dispatch linkage and indexes for one invocation-bearing and
     one unlaunched dispatch per run;
   - create-only document outbox migration compatibility.
2. Run `.venv\Scripts\python.exe -m unittest tests.test_feature_delivery -v`
   and preserve the expected missing-schema failures.

**Green/refactor**

3. Extend `_SCHEMA` and idempotent migrations in `server/database.py`.
4. Add row decoders and narrow DB methods; no manager may issue ad-hoc SQL.
5. Keep F001 migrations and 59-test baseline green.

## Task 2 - Atomic FeatureStart and role policy (AC-2, AC-3, AC-4, AC-9, AC-13, AC-14)

**Red**

1. Test fewer than three live/non-archived members causes no doc, run, event,
   pointer, start row, dispatch, or group message.
2. Test stable `(joined_at, agent_id)` ordering, valid default-owner priority,
   complete distinct role persistence, and returned names.
3. Race same and different request keys; assert one active-pointer winner and
   one recoverable run/doc/initial dispatch.
4. Inject failures after transaction, before/after document delivery, and
   before dispatch; repeat the same key and assert the same run/checkpoint.
5. Test an existing active run returns status/resume guidance.

**Green/refactor**

6. Add start/role/request/authorization response models in `server/models.py`.
7. Add `FeatureDeliveryManager` in `server/feature_delivery.py`.
8. Refactor Feature Doc template rendering in `server/feature_manager.py` so
   start can enqueue a create-only image before touching disk.
9. Add one database start transaction: FeatureRun with all roles, created
   event, active pointer claim, request row, doc outbox, initial dispatch.
10. Add role-patch service that invalidates/recomputes only safe unlaunched
    dispatches and blocks role loss; MCP receives no role-write API.

## Task 3 - Dispatch state machine and handoff pair (AC-6, AC-7, AC-10)

**Red**

1. Add table-driven transition tests for pending/leased/active/
   handoff_committed/waiting/completed/failed/superseded.
2. Reproduce double transition from one old turn, transition-vs-resume,
   predecessor-terminal-vs-successor-lease, replayed old token before/after new
   generation, expired lease rotation, and late callback.
3. Assert `closure -> done` consumes authority and creates no successor.

**Green/refactor**

4. Implement lease CAS and raw-token rotation after lease acquisition; persist
   only a cryptographic hash.
5. Extend the F001 transition DB transaction to validate/consume the exact
   active dispatch, mark predecessor handoff, and insert a waiting successor.
6. Implement Review-request dispatch as the only same-stage handoff mutation.
7. Implement exact predecessor terminal CAS and waiting-to-pending promotion.
8. Implement status/resume reconciliation from FeatureRun stage/roles, never
   from stale invocation current-agent state.

## Task 4 - Mandatory core Feature MCP (AC-5, AC-6, AC-11)

**Red**

1. Add `tests/test_feature_mcp.py` for missing env, status, transition,
   request-review, API errors, and dispatch-token headers.
2. Extend harness tests: `feature` is present even when optional MCP selection
   is empty; raw Session/dispatch capabilities are absent from Claude/Codex
   argv and MCP/connector configuration and present only in child env.

**Green/refactor**

3. Add `server/mcp_servers/feature.py` as an HTTP-only FastMCP shim.
4. Register it as mandatory core assembly in `server/harness/assembly.py`.
5. Add per-turn dispatch ID/token to neutral RunConfig/context and child env;
   do not persist the raw token in Session/DB/logs.
6. MCP mutation returns “handoff committed; end this turn” plus successor
   actor/Skill; status remains read-only and does not consume authority.

## Task 5 - Session-bound routes and actor matrix (AC-5, AC-6, AC-13, AC-14)

**Red**

1. Route tests for wrong/missing Session capability, dispatch capability,
   group membership, active run, assigned actor, edge actor, evidence, Git,
   consumed generation, and role patch authority.
2. Test status derives role and required actor server-side.

**Green/refactor**

3. Add Session-bound status/start/resume/request-review endpoints to
   `server/routers/features.py`; bind `FeatureDeliveryManager` in `server/main.py`.
4. Strengthen owner-stage actor enforcement in `FeatureManager` while retaining
   existing independent Review/Vision gates.
5. Return a structured routing packet: Feature/run/stage/state/role, canonical
   doc, Skill, next step, gate, dispatch/checkpoint, required actor, blocker,
   authorization boundary.

## Task 6 - Fresh successor GroupInvocations (AC-4, AC-7, AC-10)

**Red**

1. Test deterministic `[feature-dispatch:<id>]` message/invocation recovery at
   each launch checkpoint and no duplicate injected message.
2. Run an owner->review-prep->reviewer->owner-fix->quality->reviewer->owner-
   merge->guardian->owner-closure journey across fresh invocations; assert each
   starts at depth zero and D14 matches the new role/stage.
3. Test restart marks old invocation dead, dispatch failed, and resume chooses
   current FeatureRun actor once.

**Green/refactor**

4. Extend `GroupManager.send_message` with server-only deterministic dispatch
   identity/marker recovery; ordinary group sends remain unchanged.
5. Pass dispatch authority only into the target `_run_mentioned_agent` turn.
6. Notify `FeatureDeliveryManager` on exact invocation terminal state and run
   reconciler during startup/shutdown.
7. Ensure pending successor waits while predecessor invocation is live.

## Task 7 - Group `/feature` UX (AC-1, AC-3, AC-8, AC-13)

**Red**

1. Add pure parser tests for new/status/resume/roles grammar and malformed
   commands.
2. Add GroupChatView tests for autocomplete, start request key, response role
   display, active Feature status, role patch, status/resume, active conflict,
   fewer-than-three error, and exact draft restoration on failure.

**Green/refactor**

3. Add a group command catalog to `SlashCommandMenu.tsx` without exposing
   direct-chat-only commands.
4. Intercept feature commands before ordinary `/send`; clear draft only after
   accepted response and retain it on any error.
5. Render a compact active Feature chip/panel with ID, stage/state, three role
   names, dispatch/checkpoint status, blocker, and resume/role actions.
6. Update `sessionStore.ts` only if shared active-feature state is needed;
   otherwise keep request state local and abort fetches on group switch.

## Task 8 - Contracts, documentation, quality evidence (AC-12, AC-14)

1. Generate `web/src/api/contracts.ts` from the updated OpenAPI schema; do not
   hand-edit generated types.
2. Update `docs/architecture.md`, `docs/feature-lifecycle.md`, README/API notes,
   Feature Doc timeline, and `docs/features` indexes.
3. Run focused tests after each task, then:
   - `.venv\Scripts\python.exe -m compileall -q server tests`
   - `.venv\Scripts\python.exe -m unittest discover -s tests -v`
   - `.venv\Scripts\python.exe scripts\check-skills.py`
   - `.venv\Scripts\python.exe scripts\sync-skills.py --check`
   - `.venv\Scripts\python.exe scripts\check-features.py --write-index`
   - `npm test -- --run`, `npm run typecheck`, `npm run build`, and lint
     baseline comparison in `web/`
   - `git diff --check`
4. Write `evidence/quality-report.md` with AC-to-evidence mapping, commands,
   journey result, migration evidence, known gaps, and residual risks.
5. Route the exact implementation HEAD through `request-review`; do not merge
   or self-issue Vision acceptance.

## Worktree proposal

- Branch: `codex/f002-autonomous-group-feature`
- Worktree: `.worktrees/F002-autonomous-group-feature` (separate Git worktree
  under the writable workspace boundary; ignored by the primary checkout)
- Base SHA: the commit containing this approved plan
- Isolation: test DBs remain temporary; if the app is run manually use a
  non-default port and DB path; install `web` dependencies inside the worktree.

## Next step

Load `$worktree`, create the isolated checkout, record its base and baseline,
then load `$tdd` for Task 1's schema failures.
