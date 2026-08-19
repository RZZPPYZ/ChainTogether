---
schema_version: 1
id: F003
title: "Group Session Chain Handoff"
stage: discovery
state: active
priority: P1
owner: "codex"
reviewer: ""
vision_guardian: ""
origin_kind: "codex_conversation"
origin_group_id: ""
origin_message_seq: null
created_at: 2026-08-19
updated_at: 2026-08-19
related_features: []
blocked_by: []
research_refs: ["docs/features/F003-group-session-chain/evidence/discovery.md", "https://github.com/zts212653/cat-cafe-tutorials/blob/main/docs/lessons/08-session-management.md"]
decision_refs: ["docs/features/F003-group-session-chain/evidence/discovery.md"]
plan_refs: []
pr_refs: []
---

# F003: Group Session Chain Handoff

## Why

> Operator: "当前我们的group中不存在session封顶交接的动作……提前预测当要满的时候，进行sealed封装，以及提供MCP工具，供新的session去查，而且新的session也会附带旧的session的总结信息，这个总结是通过调用另外一个agent来做的，它的上下文是100%全新的。"

Group members currently reuse one provider session indefinitely. When its
context approaches the provider limit, continuity depends on opaque CLI
compaction. The product outcome is a durable multi-generation session chain:
seal before unsafe exhaustion, preserve the complete old transcript, start a
fresh provider session, inject a safe handoff digest, and let the new Agent
retrieve exact prior evidence instead of guessing.

## Current State

- One long-lived `group_agent_sessions` row points from `(group, agent)` to one
  reusable `origin='group_member'` session.
- Each completed harness result persists normalized context usage and the group
  UI shows remaining context per member.
- The session manager persists every member prompt, response, tool event and
  result in `messages`, but it has no sealed lifecycle or generation metadata.
- `server/session_chain.py` walks delegation/A2A parent pointers for safety; it
  is not a continuity chain and must retain that responsibility.
- No core MCP exposes prior group-member transcripts to a successor session.
- No fresh-context summarizer or continuity bootstrap exists.

## Scope

- In scope: group-member sessions only; per `(group, agent)` ordered
  generations; configurable warning/action thresholds; pre-turn projection and
  post-turn sealing; durable `active -> sealing -> sealed` state; immutable old
  DB transcript; fresh tool-free summarizer with deterministic fallback; safe
  D-layer bootstrap; Session-bound read-only MCP recall tools; restart
  reconciliation; API/UI generation visibility; cleanup and regression tests.
- Out of scope: direct-chat, bridge, schedule, delegation or research session
  rotation; provider-native compaction hooks/counting; `compress`/`hybrid`
  strategies; organization-wide summarizer Agents; deleting original
  transcripts after digest generation; cross-group or cross-Agent recall.

## User Journey

- **Scope unit**: one group member's session chain inside one group
- **Actor**: a group member Agent performing repeated turns
- **Entry**: a member has prior context usage and is selected for another group
  turn, or a completed turn crosses the configured action threshold
- **Flow**:
  1. The control plane reads the active generation's latest context health and
     predicts whether the next prompt plus safety reserve would enter the
     unsafe band.
  2. At the warning band it records and surfaces a warning; at the action band
     it atomically claims the active generation for sealing.
  3. The old session stops accepting new group work. Its complete persisted
     transcript remains readable and the transition is durably recorded.
  4. A separate tool-free, non-resumed one-shot summarizer reads a bounded
     handoff projection of the complete transcript and writes a meeting-minutes
     digest. Failure degrades to an extractive digest without blocking rebirth.
  5. A fresh provider session becomes the next generation and the existing
     `(group, agent)` pointer moves to it without losing the group-message
     cursor.
  6. Its first turn receives a D-layer bootstrap containing identity,
     predecessor digest and recall-tool instructions. The digest is marked as
     untrusted reference data, sanitized and capped.
  7. When details are uncertain, the Agent uses Session Chain MCP to list its
     own chain, read paged events or an invocation, and search all sealed
     generations. It cannot inspect another group member's private chain.
- **Terminal state**: one fresh active generation exists, every predecessor is
  sealed and queryable, and the group UI identifies the active generation.
- **Success evidence**: state-machine/concurrency tests, threshold and fallback
  tests, MCP authorization/query tests, dynamic bootstrap tests, restart tests,
  group journey test, frontend tests and production build.

## Requirements

| ID | Requirement | Source | AC |
|---|---|---|---|
| R1 | Replace indefinite group-member reuse with an ordered durable session chain. | operator | AC-1, AC-2 |
| R2 | Predict unsafe context exhaustion early enough to avoid relying on CLI compaction. | operator + tutorial | AC-3 |
| R3 | Seal without losing the old session's complete, exact transcript. | operator + tutorial | AC-2, AC-4 |
| R4 | Generate the handoff summary from a completely fresh model invocation. | operator | AC-5 |
| R5 | Bootstrap the successor with safe summary and retrieval guidance. | operator + tutorial | AC-6 |
| R6 | Give the successor MCP tools to retrieve exact prior evidence on demand. | operator + tutorial | AC-7 |
| R7 | Keep group routing, FeatureRun custody and member cursor semantics intact. | repository architecture | AC-8, AC-9 |
| R8 | Make rotation observable, recoverable and configurable. | operator outcome | AC-3, AC-10, AC-11 |

## Acceptance Criteria

- [ ] AC-1: Each `(group_id, agent_id)` has an ordered generation chain with
  exactly one active pointer; each record carries session ID, generation,
  predecessor, lifecycle state, context snapshot, seal reason/timestamps,
  digest metadata and bootstrap-consumption state.
- [ ] AC-2: The only normal lifecycle is `active -> sealing -> sealed`; a CAS
  prevents two concurrent turns from creating two successors, and startup
  reconciliation repairs an interrupted seal without losing or overwriting a
  transcript.
- [ ] AC-3: Defaults are enabled for group members with warning at 85% used and
  action at 90% used. Environment configuration can change/disable them.
  Action is decided both from current usage and a conservative projection of
  the incoming prompt plus turn reserve; missing health fails open and remains
  visible as unavailable rather than fabricating certainty.
- [ ] AC-4: Every user/assistant/thinking/tool/result message already persisted
  for a sealed member session remains immutable and pageable after rotation;
  the implementation does not depend on a provider's private JSONL layout.
- [ ] AC-5: Generative digest creation uses a new tool-free one-shot invocation
  with no resume ID, MCP servers or old Agent context. It reads a handoff
  projection derived from the complete stored transcript, records generator
  provenance/failure, and falls back to a deterministic extractive digest so
  session rebirth never depends on model availability.
- [ ] AC-6: The successor's first successful turn receives a D-layer bootstrap
  with generation identity, sanitized/capped predecessor digest and exact MCP
  recall instructions. The packet is data-marked, never inserted into L0,
  remains pending after a failed turn, and is consumed once after success.
- [ ] AC-7: Mandatory read-only Session Chain MCP tools let a member list only
  its current `(group, agent)` chain, read paged `chat|handoff|raw` events, read
  one invocation, and search exact transcript text with location pointers.
  Session capability plus chain membership fails closed on cross-member,
  cross-group, unknown or unsealed targets.
- [ ] AC-8: Rotation preserves `group_agent_sessions.last_seen_group_seq`, group
  working directory, Agent/backend/credential ownership and group backing
  session. It starts a provider conversation with no reused resume ID and does
  not alter ordinary A2A/FeatureRun routing rules.
- [ ] AC-9: Group deletion and member removal hard-delete every generation;
  normal sealing archives rather than deletes predecessor sessions, which stay
  hidden from the ordinary session list but available through chain APIs.
- [ ] AC-10: Warning, sealing, sealed, successor-created, bootstrap-consumed and
  degraded-summary events are durably recorded and broadcast. Group APIs/UI
  show active generation, chain length and lifecycle health after reload.
- [ ] AC-11: Focused backend/MCP/group/frontend tests, full backend regression,
  typecheck/build and project validators pass; generated contracts remain in
  sync.

## Research and Decisions

- Research: Cat Cafe tutorial Lesson 08; local clowder-ai `F033`, `F065`,
  `SessionSealer`, `HandoffDigestGenerator`, `SessionBootstrap`, transcript
  reader/writer and Session Chain MCP; current ChainTogether group reuse,
  context usage, persistence, prompt-governance and MCP assembly. See
  `evidence/discovery.md`.
- Decisions: reuse current DB messages as the complete transcript; add a
  separate continuity table while retaining `group_agent_sessions` as the
  active pointer; use a fresh one-shot summarizer with extractive fallback;
  make recall MCP mandatory and read-only; inject bootstrap through D-layer;
  ship `handoff` only, with configurable thresholds.
- Rejected alternatives: wait for the CLI to compact; ask the nearly-full Agent
  to write its own handoff; copy provider-private transcript files; inject the
  entire old transcript into every successor turn; reuse the old resume ID;
  permit cross-Agent chain search; block rebirth when summary generation fails.

## Architecture Ownership

- **Owner**: group-member continuity at the boundary of `GroupManager`,
  `SessionManager` and `Database`
- **Boundary**: DB owns chain truth/transcript/events; a new group session-chain
  service owns policy and state transitions; SessionManager owns fresh harness
  invocations and session persistence; PromptGovernance owns bootstrap
  rendering; REST/MCP expose capability-bound read-only recall; frontend owns
  visibility only.
- **Extension points**: group-member session lookup/rotation, context policy,
  core MCP registry, group response models/store, dynamic prompt manifest.
- **Map delta**: update group/session architecture documentation.

## Design Gate

- **Verdict**: pending
- **Feature Doc revision**: pending
- **Evidence**: pending

## Delivery

- **Plan**: pending
- **Worktree**: `F:\\RZP_program\\my_project\\ChainTogether\\.worktrees\\F003-group-session-chain`
- **Branch**: `codex/F003-group-session-chain`

## Review Provenance

- **Author**: codex
- **Reviewer**: pending independent reviewer
- **Base SHA**: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- **Reviewed HEAD**: pending
- **Verdict**: pending

## Vision Gate

- **Guardian**: pending independent guardian
- **Merged revision**: pending
- **Verdict**: pending
- **Journey evidence**: pending

## Risks and Open Questions

| ID | Type | Item | Owner | Status |
|---|---|---|---|---|
| RISK-1 | telemetry | Provider usage may be estimated or unavailable. | implementation | mitigate with source labels, projection only when numeric, fail-open visibility |
| RISK-2 | concurrency | Two turns can observe the action threshold together. | implementation | CAS seal claim plus unique generation |
| RISK-3 | continuity | A model-generated digest can omit facts or contain prompt injection. | implementation | exact transcript remains queryable; sanitize, data-mark and cap digest |
| RISK-4 | availability | Summarizer CLI can fail, timeout or lack credentials. | implementation | deterministic fallback; rebirth does not block |
| RISK-5 | privacy | Recall tools could expose another Agent's private session. | implementation | derive caller from Session capability and enforce chain membership |
| RISK-6 | recovery | Crash between seal claim, successor creation and pointer swap can strand state. | implementation | idempotent reconciliation and transaction/CAS tests |
| RISK-7 | UX | Old 5% seal margin may be too narrow for long tool turns. | operator | pre-turn projection and configurable thresholds; tune from observed usage |

## Timeline

| Date | Event | Evidence |
|---|---|---|
| 2026-08-19 | Created from operator request | current Codex conversation |
| 2026-08-19 | Discovery compared Lesson 08, clowder-ai and current group/session architecture | `evidence/discovery.md` |
