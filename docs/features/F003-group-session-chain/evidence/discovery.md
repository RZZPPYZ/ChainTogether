# F003 Discovery Evidence

## Operator signal

The operator wants group Agents to stop depending on opaque CLI compaction.
When a member session is predicted to approach its context ceiling, the system
must seal it, preserve the old session, start a fresh session, have a separate
fresh-context Agent summarize the old transcript, inject that digest into the
successor, and give the successor MCP tools to inspect exact prior records.

## External and reference research

| Source | Finding | ChainTogether consequence |
|---|---|---|
| Cat Cafe tutorial Lesson 08 | Session continuity is five layers: context detection, `active -> sealing -> sealed`, complete transcript archive, MCP recall, and successor bootstrap. Defaults discussed are 85% warning and 90% action. | Implement all five layers for group-member sessions; do not treat the context badge alone as completion. |
| Lesson 08 | A nearly-full Agent is a poor handoff author. A fresh, inexpensive summarizer should read preserved history; the successor reads a digest and drills into exact records only when needed. | Use a new non-resumed one-shot invocation and keep exact DB transcript searchable. |
| Lesson 08 / F033 | Provider capabilities differ and `hybrid` needs a real compaction hook; Codex/Gemini-style black boxes cannot reliably count compactions. | F003 ships only configurable `handoff`; it does not fake hybrid support. |
| clowder-ai `SessionSealer` | Seal request is a fast CAS; transcript/digest finalization is a bounded slow path; terminal sealing should complete even if digest work degrades. | Separate claim from best-effort summarization and guarantee a usable successor. |
| clowder-ai `HandoffDigestGenerator` | A fresh tool-free call creates meeting-minutes output; failures return null. | Use ChainTogether harness `run_oneshot`, record provenance, and fall back extractively. |
| clowder-ai `SessionBootstrap` / F065 | Bootstrap carries identity, prior digest and recall instructions, has a hard token cap, treats generated text as data, sanitizes marker/directive spoofing, and instructs the Agent not to guess. | Add a D-layer template with sanitization, one-shot consumption and exact MCP drill-down instructions. |
| clowder-ai Session Chain MCP | Useful recall primitives are list chain, paged event read with `raw|chat|handoff`, invocation detail, and full-text search returning pointers. | Provide equivalent mandatory read-only MCP tools scoped to the caller's own chain. |

Reference repository inspected at
`F:\RZP_program\reference\clowder-ai-main\clowder-ai-main`.

## Local research

| Area | Finding | Consequence |
|---|---|---|
| Group session reuse | `group_agent_sessions` stores one long-lived session ID and a durable `last_seen_group_seq` per `(group, agent)`. | Preserve this table as the active pointer and cursor; add separate generation history. |
| Context health | Harness results already normalize `context_usage` and persist it on `sessions`; group activity and UI receive it per member. | Reuse this telemetry and preserve `reported|estimated` provenance. |
| Transcript | `SessionManager.send_message` persists user, assistant, thinking, tool, error and result rows in `messages`. | The DB is already a provider-neutral complete transcript; no duplicate JSONL archive is required. |
| Prompt governance | Group turns combine L0 with D-layer runtime directives and message deltas. | Continuity bootstrap belongs in D-layer, not system identity L0. |
| MCP assembly | Core MCP servers are mandatory and receive Session ID/capability through child environment. | Add Session Chain as a core read-only MCP and enforce caller membership at REST. |
| Harness | `Harness.run_oneshot(OneShotContext)` is tool-free, has no MCP and accepts no resume ID. | It is the correct fresh-context summarizer primitive. |
| Existing `session_chain.py` | It walks parent pointers for delegation/A2A cycle/depth safety. | Do not rename or overload it; continuity gets a clearly named group service/module. |
| Cleanup | Group deletion/removal currently hard-deletes the single active member session. | Extend cleanup to all recorded generations while ordinary sealing archives predecessors. |

## Convergence decisions

1. Scope only group-member sessions. Other origins need separate lifecycle and
   UX decisions.
2. Store ordered continuity records in a new table; keep
   `group_agent_sessions` as the current pointer for backward compatibility.
3. Use current DB `messages` as exact transcript truth. A digest is an index,
   not a replacement.
4. Default warning/action thresholds are 0.85/0.90 used, configurable by env.
   Pre-turn projection uses prompt estimate plus a conservative reserve; absent
   numeric health does not trigger a fabricated seal.
5. Summary is made by a fresh, tool-free one-shot harness call with the same
   backend/credential compatibility as the member but no resume or MCP. Its
   input is a handoff projection built from the complete transcript. A
   deterministic fallback makes rotation available offline.
6. Bootstrap is sanitized, capped, data-marked, D-layer-only and consumed after
   the first successful successor turn.
7. Recall MCP is mandatory but read-only. The host derives the caller session
   and verifies the requested record belongs to that exact group+Agent chain.
8. The backend records each lifecycle event and the frontend exposes current
   generation/chain length; a full transcript viewer can remain a later UX.

## Discovery readiness

Every requirement maps to an independently verifiable AC. Entry, normal flow,
degraded summary path, restart path, privacy boundary, terminal state and
non-goals are explicit. Thresholds are configurable defaults, so no unresolved
operator value decision blocks Design Gate. Proposed status:
`ready_for_design`.

