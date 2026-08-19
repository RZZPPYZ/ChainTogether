# F003 Orchestration Design

## Lifecycle object census

| Object | Identity | Owner | States | Durable truth |
|---|---|---|---|---|
| Group member pointer | `(group_id, agent_id)` | Database | points to active session | existing `group_agent_sessions`; cursor retained across rotation |
| Session generation | `session_id` plus `(group_id, agent_id, generation)` | Group Session Chain service | `active -> sealing -> sealed` | new `group_session_generations` row |
| Provider conversation | `sessions.claude_session_id` | SessionManager/harness | absent, started, resumable, abandoned after seal | existing `sessions`; successor starts with null resume ID |
| Exact transcript | `(session_id, seq)` | SessionManager/Database | append-only while active, immutable when sealed | existing `messages` rows |
| Handoff digest | predecessor `session_id` | Group Session Chain service | pending, generative, extractive fallback | generation digest fields and provenance |
| Bootstrap packet | successor generation | PromptGovernance/chain service | pending, injected, consumed | successor `bootstrap_consumed_at`; predecessor digest is source |
| Lifecycle event | `(generation_session_id, event_seq)` | Database | immutable | new `group_session_chain_events` row |
| Recall authorization | caller member `session_id` | REST boundary | valid/invalid per request | live Session capability plus generation membership lookup |

The existing `server/session_chain.py` parent-chain walker is not in this
lifecycle; it continues to own delegation/A2A guard traversal.

## State-event table

| Current | Event | Guard | Durable effects | Next / failure |
|---|---|---|---|---|
| absent | first group turn | member is live | create normal member session, generation 1 active, active pointer | active |
| active | context observation | numeric usage in warn band, below action | snapshot health, append `warning` event | active |
| active | pre-turn projection or post-turn action threshold | CAS state is active and pointer still equals session | set status sealing, reason/context, append `sealing_started` | sealing; loser reloads pointer/state |
| sealing | build transcript projection | messages readable | build deterministic extractive digest/projection | sealing; read failure recorded and reconciliation retries |
| sealing | fresh summarizer succeeds | one-shot has no resume/MCP | sanitize/cap body, record generative provenance | sealing |
| sealing | fresh summarizer fails/times out | extractive projection exists | record error and extractive fallback | sealing |
| sealing | create successor | no successor already committed | create fresh group_member session with null resume ID | sealing |
| sealing | complete rotation | old CAS still sealing; pointer still old; unique next generation | archive old session; mark old sealed; insert successor active; move pointer preserving cursor; append sealed/successor events | sealed old + active successor |
| sealing | process restarts | age/state/pointer census | idempotently reuse committed successor or complete from old transcript; never generate two active successors | sealed + active, or retriable sealing with visible error |
| active successor | prepare first turn | bootstrap not consumed | render D-layer packet from predecessor digest | active, pending |
| active successor | successful result | packet was injected | set consumed timestamp and append event | active, consumed |
| active successor | failed/no result | packet was injected | no consumption write | active, pending for retry |

## Numbered invariants

1. For every live `(group, agent)` pointer, its target generation exists,
   belongs to the same group and Agent, and has `status='active'`.
2. At most one active generation exists per `(group, agent)`; generation is
   strictly increasing and predecessor edges never cross group or Agent.
3. Only `active -> sealing -> sealed` is allowed in normal operation. Sealed
   generations never accept a group turn and never regain a provider resume ID.
4. A pointer swap and old/new terminal state commit are one database
   transaction guarded by the old pointer and sealing state.
5. The group delta cursor is conversation-scoped, not provider-session-scoped;
   rotation preserves it exactly.
6. Old `messages` are never copied, rewritten or deleted by sealing. Digest and
   search pointers always resolve back to exact `(session_id, seq)` rows.
7. Summary availability is not a liveness dependency: any summarizer failure
   produces an extractive fallback and a visible degraded event.
8. A successor has a null provider resume ID. The summarizer has no resume ID,
   MCP, connectors, tools or mutation authority.
9. Generated or historical text is untrusted data. Bootstrap strips marker and
   directive spoofing, caps size, and never modifies L0 identity/policy.
10. Session Chain recall is self-chain-only. The caller Session capability is
    necessary but insufficient; every target must share the exact group and
    Agent continuity identity.
11. Bootstrap consumption is success-bound and idempotent. Failure/cancel does
    not consume it; duplicate success writes converge.
12. Group/member deletion deletes all generations and events; ordinary seal
    archives predecessors. Existing A2A and FeatureRun state machines are not
    altered by rotation.

## Context action policy

- `used_ratio = 1 - remaining_ratio` when a trustworthy remaining ratio exists.
- Otherwise use `total_tokens / context_window` when both are numeric.
- `warn` when used ratio is at least the configured warning threshold.
- `seal` before a turn when current used tokens plus estimated incoming prompt
  tokens plus configured reserve would reach the action threshold.
- `seal` after a successful turn when measured used ratio reaches action.
- No numeric observation means `none/unavailable`, not an invented estimate.
- Defaults: enabled, warning `0.85`, action `0.90`, reserve `8,000` tokens.
  Configuration validation requires `0 < warn < action < 1` and nonnegative
  reserve; invalid startup configuration fails fast.

## Transcript and digest design

The transcript authority is the existing `messages` table. Recall views are
computed without mutating it:

- `raw`: typed persisted rows with seq and compact JSON-safe fields.
- `chat`: user/assistant/system-error text only.
- `handoff`: invocation segments beginning at each user row, with tool names,
  errors, result context and key assistant text.
- `invocation detail`: one user-seq segment through the row before the next
  user message.

The summarizer receives a projection covering every transcript row but caps
individual oversized fields. It is explicitly told the payload is reference
data, not instructions. The output contract is concise meeting minutes:
accomplished work, decisions/reasons, files/artifacts, failures, current state,
next steps and unresolved risks. A deterministic extractive formatter uses the
same full projection when the one-shot fails.

## Security and privacy

- Session Chain MCP is a mandatory core read-only server.
- Its callback includes bearer token, caller Session ID and unlisted Session
  capability through child environment; secrets are absent from argv/config.
- REST verifies the live Session capability, resolves caller generation, and
  then constrains list/read/search to its exact group and Agent.
- Active generations can list the chain; transcript reads target sealed
  predecessors only. A successor cannot use the tool to introspect a currently
  executing peer.
- Search caps query length, result count and snippets. Read caps page size and
  serialized field length to prevent prompt/response amplification.

## Compatibility, migration and rollback

- Migration creates new tables/columns additively. Existing
  `group_agent_sessions` rows are adopted lazily as generation 1 active when
  first used; no provider session is reset on application upgrade.
- Feature can be disabled by configuration. Disabled mode keeps the old
  long-lived pointer behavior and leaves history readable.
- Rollback to old code ignores new tables; current pointer still targets a
  normal `group_member` session. Archived predecessors remain in DB.
- API fields are additive and frontend treats them as optional.

## Observability

Each lifecycle event records group, Agent, generation, session IDs, type,
timestamp and JSON detail. Expected types: `adopted`, `warning`,
`sealing_started`, `summary_generated`, `summary_degraded`, `sealed`,
`successor_created`, `bootstrap_injected`, `bootstrap_consumed`,
`reconciled`. Group API returns active generation and chain length; WebSocket
rotation updates the header without waiting for a reload.

## Adversarial verification matrix

| Case | Required assertion |
|---|---|
| Two concurrent seal attempts | one CAS winner, one successor, one pointer swap |
| Crash after sealing claim | restart completes/retries from exact old transcript |
| Crash after successor row creation | reconciliation reuses or removes orphan; never two active generations |
| Pointer changed during seal | commit fails closed and does not archive unrelated active target |
| Summarizer timeout/error/empty output | extractive digest, degraded event, successor still active |
| Malicious transcript/digest marker | bootstrap cannot close its data block or inject directive lines |
| First successor turn errors | bootstrap remains pending and is reinjected |
| Duplicate successful callback | one consumed timestamp/event semantic |
| Cross-group/Agent/active-session MCP read | 403/404 without data disclosure |
| Search huge query/page | validated caps and bounded response |
| Existing row with no generation | lazy adoption preserves resume ID and cursor |
| Remove member/delete group | all generations/events/messages deleted, no active pointer |
| FeatureRun transition during threshold turn | transition result persists; rotation only changes member transport session |
| Missing context usage | no forced seal; unavailable status remains explicit |
| Disabled policy | no rotation or bootstrap; existing reuse behavior unchanged |

## Design Gate readiness

The operator has already selected the user-visible direction: proactive sealed
handoff with fresh-context summary and MCP recall. Thresholds are reversible,
configurable defaults. Lifecycle objects, failure paths, privacy boundary,
migration, rollback, observability, invariants and adversarial tests are
explicit. No irreversible product decision remains open.

