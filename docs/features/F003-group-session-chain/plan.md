# F003 Implementation Plan: Group Session Chain Handoff

## Finish line

Repeated group work automatically rotates a near-full member into a fresh
provider session, preserves and exposes exact predecessors, injects a safe
fresh-context handoff digest, and shows the active generation without changing
ordinary group or FeatureRun routing.

All AC-1 through AC-11 in `feature.md` must be green. Direct-chat session
rotation, provider compaction hooks, `compress`/`hybrid` and a full transcript
browser remain non-goals.

## State objects and invariants

Implementation must preserve the lifecycle census, transition table and twelve
numbered invariants in `evidence/orchestration-design.md`. Every task below names
the state it owns and includes failure-path tests before production changes.

## AC coverage

| AC | Tasks |
|---|---|
| AC-1 | 1, 2, 5, 6 |
| AC-2 | 2, 5 |
| AC-3 | 1, 5 |
| AC-4 | 3, 4 |
| AC-5 | 3 |
| AC-6 | 3, 5 |
| AC-7 | 4 |
| AC-8 | 2, 5 |
| AC-9 | 2, 5 |
| AC-10 | 2, 5, 6 |
| AC-11 | 7 |

## Task 1 — Context action policy and configuration

**AC:** AC-3, AC-11
**State owner:** context observation/action decision (pure value, no mutation)

**Modify**

- `server/config.py`
- `.env.example`
- `server/group_session_chain.py` (create)
- `tests/test_group_session_chain.py` (create)

**Red**

Add pure tests for:

- remaining-ratio and token/window observations;
- warning at 0.85 used, action at 0.90 used;
- pre-turn prompt estimate plus 8k reserve crossing action;
- `reported` and `estimated` health retaining provenance;
- absent/malformed health producing `unavailable/none`;
- disabled policy producing no action;
- invalid `warn >= action`, out-of-range ratios or negative reserve rejected.

Run:

```powershell
F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe -m unittest tests.test_group_session_chain.GroupSessionChainPolicyTests -v
```

Expected red: module/types/settings do not exist.

**Green/refactor**

Create immutable policy/action DTOs and pure calculation helpers. Add settings:

- `group_session_chain_enabled=True`
- `group_session_chain_warn_ratio=0.85`
- `group_session_chain_action_ratio=0.90`
- `group_session_chain_turn_reserve_tokens=8000`
- `group_session_chain_summary_timeout_seconds=60`
- `group_session_chain_bootstrap_max_chars=12000`

Validate once on service construction; keep policy independent from DB and
harness code.

## Task 2 — Durable generations, events and atomic rotation commit

**AC:** AC-1, AC-2, AC-8, AC-9, AC-10
**State owner:** Database generation/event truth and active pointer

**Modify**

- `server/database.py`
- `server/models.py`
- `server/group_session_chain.py`
- `tests/test_group_session_chain.py`

**Red**

Add async DB/service tests for:

- lazy adoption of an existing active pointer as generation 1;
- ordered generation uniqueness and predecessor identity;
- active-to-sealing CAS with one winner under two concurrent calls;
- atomic old sealed/new active/pointer swap preserving
  `last_seen_group_seq`;
- pointer mismatch and wrong lifecycle fail closed;
- all lifecycle events ordered and JSON-safe;
- cleanup enumerating all generations;
- startup reconciliation for sealing-without-successor and already-committed
  successor; no duplicate active generation.

Expected red: tables and DB methods absent.

**Green/refactor**

Add `_SCHEMA` tables:

- `group_session_generations` keyed by session ID with group, Agent,
  generation, predecessor, state, context snapshot, seal fields, digest
  provenance/error, bootstrap consumption and timestamps;
- `group_session_chain_events` append-only by generation and sequence;
- indexes/unique constraints for `(group, agent, generation)` and at most one
  active generation.

Add narrow DB methods for adopt/get/list/CAS/event/transactional-rotation and
cleanup. `GroupSessionChainService` owns per-chain asyncio locks and idempotent
reconciliation; it never edits `messages`.

## Task 3 — Complete transcript views, fresh summarizer and safe bootstrap

**AC:** AC-4, AC-5, AC-6
**State owner:** immutable transcript projection, digest and bootstrap packet

**Modify/create**

- `server/group_session_chain.py`
- `server/session_manager.py`
- `server/assets/prompts/dynamic/session-chain-bootstrap.md` (create)
- `server/assets/prompt-manifest.json`
- `tests/test_group_session_chain.py`
- `tests/test_prompt_governance.py`

**Red**

Add tests that:

- transform every persisted message type into bounded `raw`, `chat` and
  invocation-based `handoff` views without changing source rows;
- construct a summarizer projection from the full ordered transcript;
- call an injected fake one-shot runner exactly once with no resume/MCP
  authority and record model/backend provenance;
- timeouts/errors/empty results yield extractive meeting minutes and a
  `summary_degraded` event;
- sanitizer removes control characters, close-marker spoofing and directive
  lines while retaining useful facts;
- bootstrap is capped, data-marked, identifies generation/predecessor, and
  gives exact recall-tool order;
- failed successor result leaves bootstrap pending; successful result consumes
  it once.

**Green/refactor**

Expose a SessionManager fresh one-shot summary helper using the member's
backend/model/credential and `OneShotContext` only. It must not construct a
`HarnessRun`, resume ID, MCP set or connectors. Implement deterministic fallback
from the same projection. Register/render the bootstrap through
`GroupPromptGovernance.render_dynamic`; do not concatenate ad hoc system text.

## Task 4 — Capability-bound Session Chain REST and mandatory MCP

**AC:** AC-4, AC-7, AC-10
**State owner:** read-only recall authorization and query pagination

**Create/modify**

- `server/routers/session_chains.py` (create)
- `server/mcp_servers/session_chain.py` (create)
- `server/harness/assembly.py`
- `server/main.py`
- `server/database.py`
- `tests/test_session_chain_mcp.py` (create)
- `tests/test_group_session_chain.py`

**Red**

Test REST and MCP handlers for:

- list caller's chain with generation/state/health/digest metadata;
- paged `raw|chat|handoff` reads with next cursor;
- invocation detail by starting user seq;
- case-insensitive cross-sealed-generation search with `(session_id, seq)`
  pointers and bounded snippets;
- live bearer + exact Session capability + caller generation membership;
- cross-group, cross-Agent, active peer, unknown session and malformed
  page/query rejection without data leakage;
- Session Chain MCP present even when an Agent deselects all optional MCPs;
- child env contains caller identity/capability while argv/config does not.

**Green/refactor**

Implement additive routes under
`/api/sessions/{caller_session_id}/session-chain/...`. MCP tools derive caller
identity only from environment and pass the capability header. Register it in
`_CORE_MODULES`, keep tools read-only and return concise human-readable results.

## Task 5 — Group turn integration, sealing and recovery

**AC:** AC-1, AC-2, AC-3, AC-6, AC-8, AC-9, AC-10
**State owner:** group dispatch chooses current generation and commits rotation

**Modify**

- `server/group_manager.py`
- `server/main.py`
- `server/database.py`
- `server/models.py`
- `tests/test_group_session_chain.py`
- `tests/test_group_routing.py`
- `tests/test_feature_dispatch_runtime.py`

**Red**

Add group journey tests for:

- first mention creates/adopts generation 1;
- pre-turn projection seals before dispatch and rebuilds the D-layer for the
  successor;
- post-result action threshold injects the visible reply, then seals before
  any successor A2A work;
- warning-only observation records/broadcasts once per observation band;
- successor inherits working dir, Agent, backend and credential but has no
  resume ID;
- group cursor remains monotonic across generations;
- first successor failure/success bootstrap semantics;
- Feature MCP transition on a threshold turn remains committed and the next
  Feature dispatch resolves the new member pointer;
- remove member/group deletes every generation; ordinary seal only archives;
- restart calls reconciliation before new group work.

**Green/refactor**

Bind one `GroupSessionChainService` in GroupManager. Replace the documented
"one session forever" assumption with "one active generation". Before prompt
assembly, rotate when projection predicts action; load the pending bootstrap as
the first runtime directive. Capture successful result/context in
`AgentTurnResult`; after visible reply injection, rotate on measured action
before dispatching A2A mentions. Broadcast a dedicated
`group_member_session_chain` event after durable writes.

## Task 6 — Group UI generation and live rotation visibility

**AC:** AC-1, AC-10, AC-11
**State owner:** frontend projection only; backend remains truth

**Modify**

- `web/src/stores/sessionStore.ts`
- `web/src/hooks/useWebSocket.ts`
- `web/src/components/GroupChatView.tsx`
- `web/src/components/GroupChatView.test.tsx`
- `web/src/stores/sessionStore.test.ts`
- `web/src/api/contracts.ts` (generated)

**Red**

Add tests that API group members map optional `generation`, `chain_length` and
`chain_status`; a rotation WebSocket event replaces session ID, clears stale
context usage, and increments visible generation; header renders `S2/3` plus
context badge/title explaining sealed continuity; reload uses API truth.

**Green/refactor**

Extend additive types/store actions and render a compact generation label beside
each member. Do not add a full transcript viewer. Regenerate contracts with the
workspace Python interpreter on Windows rather than the package's POSIX-only
script literal if necessary.

## Task 7 — Documentation, validators and full evidence

**AC:** AC-11 and final coverage of all ACs
**Modify**

- `docs/architecture.md`
- `.env.example`
- `docs/features/F003-group-session-chain/feature.md`
- `docs/features/F003-group-session-chain/evidence/tdd-*.md`
- `docs/features/F003-group-session-chain/evidence/quality-report.md`

**Verify**

Focused backend:

```powershell
F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe -m unittest tests.test_group_session_chain tests.test_session_chain_mcp tests.test_group_routing tests.test_prompt_governance tests.test_feature_dispatch_runtime -v
```

Full backend:

```powershell
F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

Frontend from `web/`:

```powershell
bun run test
bun run typecheck
bun run build
```

Project gates:

```powershell
F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe scripts\check-features.py
F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe scripts\check-skills.py
F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe scripts\sync-skills.py --check
git diff --check
```

Record exact commands, counts, expected existing lint disposition, AC-to-
evidence mapping, remaining risks and a manual journey:

1. Repeatedly invoke one group member until warning/action can be simulated or
   observed.
2. Confirm its header changes from `S1/1` to `S2/2` and remaining context resets.
3. Ask the successor what happened; confirm it cites digest and can use MCP to
   find an exact old decision.
4. Restart during a forced sealing fixture and confirm one active successor.

## Unresolved technical questions

None blocks implementation. The implementation may choose exact internal DTO
names and SQL helper decomposition, but may not weaken the state machine,
authorization, transcript immutability, fallback or bootstrap invariants.

## Execution record

- Worktree: `F:\RZP_program\my_project\ChainTogether\.worktrees\F003-group-session-chain`
- Branch: `codex/F003-group-session-chain`
- Base: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- Dependency decision: reuse root `.venv`; install/reuse worktree-local Bun
  dependencies only when frontend execution begins.
