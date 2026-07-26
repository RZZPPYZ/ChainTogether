# Group `@` Routing Remediation Plan

Status: proposed
Date: 2026-07-25
Primary reference: `reference/reference_a2a.md`
Related historical plan: `docs/plans/group-a2a-routing-guards.md`

## 1. Objective

Harden Group `@` routing so that a handle has one unambiguous meaning:

- user `@Agent` means "start this member's turn";
- agent `@Agent` means "handoff to this member" only from the final routing
  paragraph;
- aliases resolve to the same durable Agent identity;
- malformed, conflicting, or rejected routes are visible and cannot be
  mistaken for successful completion;
- a plain reply without `@` remains a valid natural completion.

This plan is based on the current code, not only on the conclusions in
`reference_a2a.md`. The reference correctly emphasizes mechanical guardrails,
but some of its ChainTogether observations are now stale.

## 2. Current Baseline

The following capabilities already exist and should be preserved:

| Capability | Current implementation |
|---|---|
| Unicode/CJK handles | `parse_mentions()` and `_HANDLE_RE` |
| Canonical name plus mutable alias | `agent_routing_handles()` and Agent validation |
| No-`@` responder selection | recent responder, recent explicit mention, configured fallback |
| Agent handoff syntax | final non-empty paragraph, line-start handles only |
| Separator handling | `_strip_markdown_rules()` accepts the historical `---` case |
| Inline handoff correction | `analyze_agent_routing()` plus one remedial turn |
| A2A execution | one invocation worklist with long-lived `(group, agent)` sessions |
| Runtime guards | self/unknown/busy/pending checks, depth cap, ping-pong warning/block |
| Custody | durable active/held/blocked/void/resolved/cancelled/dead states |
| Prompt contract | Group system protocol plus per-turn Q1/Q2/Q3 exit check |
| UI attribution | canonical/alias highlighting and persisted execution activity |

The old plan in `docs/plans/group-a2a-routing-guards.md` records earlier work,
but its test counts and some remaining-gap statements no longer describe the
trimmed current repository. This document supersedes its "Still Deferred"
assessment for current-group `@` routing.

## 3. Decisions Adapted From The Reference

### 3.1 Keep natural DONE

ChainTogether intentionally allows an Agent to finish naturally without an
`@handle`. The user sees every Group reply, and the system protocol explicitly
forbids `STOP`/`DONE` completion tokens.

Therefore this plan will **not** implement the reference proposal that treats
every A2A reply without a routing signal as a dropped ball. It will also not add
`[routing-done]`.

There are two additional reasons:

1. Current initial user-to-Agent work starts at `depth=1`; A2A starts at
   `depth>=2`. The reference's `depth=0`/`depth=1` distinction is stale.
2. A task is allowed to finish at any member in a chain. Requiring another
   backend turn merely to confirm completion adds latency and tokens without a
   mechanically observable error.

Automatic remediation will run only when there is observable routing intent
that is malformed: inline known-member mentions, invalid HOLD syntax, or a
HANDOFF/HOLD conflict.

### 3.2 Preserve current-group scope

`@` continues to address only members of the current Group. Cross-thread and
cross-group delegation requires a structured tool and is outside this plan.

### 3.3 Use code for syntax and state, Prompt for intent

- Code decides whether a handle is exact, executable, duplicated, conflicting,
  or rejected.
- Prompt teaches Q1/Q2/Q3 and when a teammate should be involved.
- Code must not infer broad task intent from an ordinary natural-language
  completion.

## 4. Confirmed Gaps

### P0.1 Independent parsers can produce conflicting exits

`_run_mentioned_agent()` currently checks `parse_group_hold()` before
`analyze_agent_routing()`. A final block containing both HOLD and HANDOFF is
silently treated as HOLD, even though the system contract forbids both.

`parse_group_hold()` also clamps out-of-range values instead of rejecting them.
For example, `9999` becomes `3600`, so an invalid model action appears valid.

### P0.2 Failed turns and failed remediation can resolve as `task_done`

The worklist's `finally` block transitions any still-active, empty invocation
to `task_done`. Several paths inject an error but leave custody active:

- backend timeout or backend exception;
- empty Agent reply;
- inline routing correction timeout/failure returning `None`.

Those paths can be persisted as successful resolution even though execution or
routing failed.

### P0.3 Name and alias can execute the same Agent twice

For a user message such as `@胖虎 @峰哥`, both handles resolve to the same Agent,
but initial `targets` are not deduplicated by Agent id. The same member can
therefore receive two turns for one user message.

A2A has pending/active guards, but it still emits avoidable duplicate warnings
when canonical and alias handles target the same identity.

### P0.4 Explicit routing failures are mostly invisible to the sender

Unknown handles are logged but not returned as structured send results. A
message with only unknown handles produces no invocation and no clear UI
feedback. More than `MAX_MENTION_TARGETS` handles are silently truncated.

The frontend also clears the composer before sending and ignores non-success
HTTP bodies, so a send failure can discard the user's text.

### P0.5 Exact-handle policy is inconsistent

Agent A2A dispatch requires exact handles, but user routing and default-history
lookup call `_resolve_agent_by_name()` with prefix matching enabled. The Prompt
says handles must be exact. A short prefix can therefore wake an Agent even
though the same output from an Agent would not route.

### P1.1 Quoted and inline-code handles can be treated as commands

Fenced code is removed, but blockquotes are deliberately stripped to their
content, so `> @Agent` executes. Inline code can also be parsed as a mention.
This is dangerous when users or Agents quote an earlier message or show an
example.

Markdown list prefixes should remain supported because a list of handoffs can
be intentional. Standalone `---` before a handoff must continue to work.

### P1.2 Unicode comparison is casefolded but not normalized

Handle comparison uses `casefold()`, but there is no shared Unicode
normalization step. Canonically equivalent composed/decomposed forms can fail
to match, while future validation changes could allow visually equivalent
identities to coexist.

### P1.3 No-`@` responder availability is not fully deterministic

The intended order is:

1. the most recent replying Agent, if available;
2. otherwise the most recently explicitly mentioned Agent, if available;
3. otherwise the configured fallback Agent.

The current implementation scans older replies until it finds any idle Agent,
which can skip from a busy latest responder to an unrelated older responder.
Its availability check only examines active worklist entries and does not count
pending entries across invocations.

### P1.4 Textual waiting can close as successful completion

An Agent can end with "waiting for CI" but omit `[group-hold:SECONDS]`. The
current invocation then drains and becomes `task_done`, although no timer was
created. This is the useful part of the reference's void-hold proposal.

### P2.1 Routing decisions are not first-class observable events

The transcript contains warning text, but there is no durable structured event
describing:

- explicit vs inferred route source;
- raw handles and resolved Agent ids;
- ignored unknown/duplicate/overflow handles;
- exit type (`done`, `handoff`, `hold`, `invalid`);
- guard/remediation outcome.

This makes the UI and post-mortem debugging dependent on log text.

### P2.2 Coverage is too narrow for the routing surface

Current focused tests cover the Q1/Q2/Q3 Prompt, separator handling, final-slot
handoffs, aliases, and a few inline cases. They do not lock down lifecycle
failure states, duplicate aliases, malformed HOLD, quote/code suppression,
unknown handles, target overflow, or no-`@` precedence.

## 5. Proposed Design

### 5.1 Normalize identity once

Add a shared helper used by Agent validation, user routing, A2A routing, and
history inference:

```python
def normalize_handle(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()
```

Execution matching will be exact after normalization. Prefix matching may
remain a frontend autocomplete concern but will no longer execute a route.

Before enforcing this on existing rows, add a startup/database validation that
reports normalization collisions instead of silently choosing one Agent.

### 5.2 Separate user mention parsing from Agent exit analysis

Introduce two structured results rather than passing bare `list[str]` values:

```python
@dataclass(frozen=True)
class UserMentionAnalysis:
    raw_handles: tuple[str, ...]
    resolved_agent_ids: tuple[str, ...]
    unknown_handles: tuple[str, ...]
    duplicate_handles: tuple[str, ...]
    overflow_handles: tuple[str, ...]

@dataclass(frozen=True)
class AgentExitDecision:
    kind: Literal["done", "handoff", "hold", "invalid"]
    final_slot: str
    target_agent_ids: tuple[str, ...] = ()
    hold_seconds: int | None = None
    hold_reason: str | None = None
    reason_codes: tuple[str, ...] = ()
```

`analyze_user_mentions()` may accept mentions anywhere in ordinary prose.
`analyze_agent_exit()` will enforce the final routing slot and exactly one exit
kind. Both will deduplicate by durable Agent id before work enters a queue.

Reason codes will include at least:

- `unknown_handle`;
- `duplicate_agent_identity`;
- `target_limit_exceeded`;
- `inline_handoff`;
- `handoff_not_first_line`;
- `self_handoff`;
- `hold_out_of_range`;
- `hold_handoff_conflict`;
- `void_hold_claim`.

### 5.3 Make HOLD strict

Replace clamp-based HOLD parsing with validation:

- HOLD must be in the final routing slot;
- its first content line must begin with `[group-hold:SECONDS]`;
- seconds outside `GROUP_HOLD_MIN_SECONDS..GROUP_HOLD_MAX_SECONDS` are invalid;
- HOLD and executable HANDOFF cannot coexist;
- malformed HOLD gets one syntax-only remedial turn;
- a second invalid result transitions to `routing_void`.

The original substantive reply remains visible. The correction response should
only contain the corrected exit and should be merged into routing evaluation,
as the existing inline-remedial flow already does.

### 5.4 Centralize terminal outcomes

Refactor `_run_mentioned_agent()` to return a structured turn outcome instead
of relying on the worklist's empty queue to imply success:

```python
TurnOutcome = Literal[
    "completed", "handed_off", "held", "routing_void",
    "execution_failed", "cancelled"
]
```

The worklist may transition to `task_done` only when the final processed turn
returned `completed` and there is no pending work.

- backend timeout/error/empty reply -> `invocation_died` (failed);
- malformed or rejected routing exit -> `routing_void`;
- depth/ping-pong hard stop -> `routing_blocked`;
- valid no-`@` reply -> `task_done`;
- valid HOLD -> `ball_held`;
- cancellation -> `task_cancelled`.

Change remedial methods to return a discriminated result (`corrected`,
`invalid`, `timeout`, `backend_error`) rather than `AgentTurnResult | None`.
This prevents a failed correction from falling through to natural completion.

### 5.5 Harden Markdown routing boundaries

Use a conservative sanitizer shared by user and Agent parsing:

- remove fenced code blocks;
- remove inline-code spans;
- ignore blockquote lines;
- ignore URL/link destinations;
- preserve ordinary prose and Markdown list prefixes;
- preserve current standalone separator handling.

Agent handoffs still require the final non-empty paragraph's first content line
to start with a handle. Quoted `> @Agent` and code examples never execute.

No new Markdown dependency is required for the first pass; the sanitizer will
be a small stateful scanner with focused tests. If nested Markdown behavior
becomes broader than routing needs, evaluate a CommonMark parser separately.

### 5.6 Make no-`@` inference match the product policy

Return the inference source together with the Agent:

```python
InferredResponder(agent, source="recent_reply" | "recent_mention" | "fallback")
```

Rules:

1. Inspect only the latest Agent reply. Use it if available; do not fall back
   to an older responder.
2. Then inspect explicit user mentions newest-first.
3. Then use the configured fallback, even if it must queue.
4. Availability must include active and pending work across all Group
   invocations and the member reuse session's current status.

The selected source is returned and persisted for UI/debugging.

### 5.7 Add targeted void-hold remediation

Scan only the sanitized final routing slot for a small reviewed set of explicit
waiting phrases such as `等待`, `暂停`, `waiting`, `pending`, and `hold ball`.

This detector is not a general intent classifier. It activates only when:

- the final slot explicitly claims waiting;
- there is no valid HOLD or HANDOFF;
- the invocation is otherwise about to resolve.

Run one correction asking for either a valid bounded HOLD, a valid HANDOFF, or
a natural completion that no longer claims waiting. If correction fails, mark
the route void rather than silently resolving it. Record the matched pattern id
for diagnostics.

### 5.8 Return and persist routing feedback

Extend Group send results with a routing summary:

```json
{
  "invocation": {},
  "routing": {
    "source": "explicit",
    "resolved_agent_ids": ["..."],
    "unknown_handles": ["Ghost"],
    "duplicate_handles": ["峰哥"],
    "overflow_handles": []
  }
}
```

Also persist a compact `group_routing_activity` system message with stable
reason codes. Like execution activity, it must be excluded from Agent context
and survive refresh.

Frontend behavior:

- restore the composer text when the request fails;
- show rejected/unknown handles beside the sent message or invocation strip;
- show whether a no-`@` message selected recent reply, recent mention, or
  fallback;
- render guard/remedial status inside the same collapsible Agent run;
- never rely on frontend parsing to decide execution; backend results remain
  authoritative.

### 5.9 Align documentation and contracts

Update stale comments and generated/API contracts. In particular,
`GroupSendRequest` still says a no-`@` message invokes nobody, which conflicts
with the implemented inference policy.

## 6. Implementation Phases

### Phase 1: Correctness and lifecycle (P0)

1. Add normalized exact-handle resolution.
2. Add structured user and Agent routing analyses.
3. Deduplicate name/alias targets by Agent id.
4. Enforce mutually exclusive DONE/HANDOFF/HOLD decisions.
5. Reject invalid HOLD ranges instead of clamping.
6. Return structured remedial outcomes.
7. Prevent backend/remedial failures from transitioning to `task_done`.
8. Return visible unknown/duplicate/overflow routing feedback.

Exit criteria:

- one user message can invoke a given Agent at most once;
- every invocation terminal state matches its actual outcome;
- malformed routing never silently becomes DONE;
- valid natural completion remains zero-remedial.

### Phase 2: Parser and inference hardening (P1)

1. Ignore blockquotes, inline code, fenced code, and links for routing.
2. Preserve list handoffs and the `---` compatibility case.
3. Normalize Unicode handles and detect existing collisions.
4. Make no-`@` precedence and availability exact.
5. Add narrowly scoped void-hold detection and one-shot correction.

Exit criteria:

- quoted/example handles never wake Agents;
- composed/decomposed equivalent handles resolve consistently;
- no-`@` routing follows the documented three-step order under busy/pending
  conditions.

### Phase 3: Observability and frontend feedback (P2)

1. Persist structured routing activity with reason codes.
2. Extend REST/WebSocket contracts.
3. Integrate routing state into Group rich execution messages.
4. Restore failed composer input and render explicit routing diagnostics.
5. Update API docs and historical routing documentation.

Exit criteria:

- a user can tell which Agent was selected and why;
- rejected `@` commands have a visible reason;
- refresh preserves routing diagnostics;
- logs, database state, REST responses, and UI use the same reason codes.

## 7. Files Expected To Change

| File | Planned responsibility |
|---|---|
| `server/group_manager.py` | structured analysis, exact resolution, lifecycle outcomes, remediation |
| `server/group_protocol.py` | HOLD/conflict/void-hold correction prompts |
| `server/agent_manager.py` | normalized identity validation |
| `server/models.py` | structured Group send/routing response models and corrected docs |
| `server/database.py` | optional invocation/routing activity fields and migration |
| `server/routers/groups.py` | return structured routing summary |
| `web/src/components/GroupChatView.tsx` | send failure recovery and routing diagnostics |
| `web/src/hooks/useWebSocket.ts` | persisted routing activity events |
| `web/src/stores/sessionStore.ts` | routing event types/state |
| `tests/test_group_routing.py` | parser and exit-decision unit matrix |
| new integration test module | invocation lifecycle, remediation, inference, duplicate identity |
| frontend tests | composer recovery and diagnostics rendering |

## 8. Required Test Matrix

### User routing

- exact canonical name and exact alias;
- canonical plus alias in one message invokes once;
- unknown-only and mixed known/unknown handles;
- more than four targets returns overflow feedback;
- ambiguous/prefix handles do not execute;
- CJK, accented, composed, and decomposed handles;
- mentions in fenced code, inline code, blockquotes, links, and email-like text;
- Markdown lists remain executable.

### Agent exit decisions

- natural DONE with no `@`;
- valid final HANDOFF, including multiple targets;
- valid bounded HOLD;
- HOLD below/above bounds;
- HOLD plus HANDOFF conflict;
- inline known-member handoff corrected once;
- correction success, invalid response, timeout, backend error, cancellation;
- self, unknown, active, pending, depth-blocked, and ping-pong-blocked targets;
- separator before final handoff remains valid.

### Invocation lifecycle

- successful natural completion -> resolved;
- successful handoff chain -> resolved after final member completes;
- held -> resumed/expired/cancelled;
- backend error/timeout/empty output -> failed/dead, never resolved;
- malformed route -> void;
- guard block -> blocked;
- concurrent invocations do not misreport Agent availability.

### No-`@` inference

- latest responder available;
- latest responder busy, then latest explicit mention;
- no recent candidate, then fallback;
- fallback busy queues by policy;
- pending Agent is not considered idle;
- routing source survives persistence and refresh.

### Frontend

- failed send restores input;
- unknown/duplicate/overflow handles are visible;
- inferred responder source is visible without duplicating the Agent reply;
- routing guard activity folds into the same run block;
- reload reconstructs the same routing status.

## 9. Rollout And Compatibility

1. Add pure analyzers and tests before changing dispatch behavior.
2. Run existing Group routing tests to establish a baseline.
3. Introduce structured outcomes behind the existing REST shape, then extend
   the response additively.
4. Keep existing transcript prefixes readable for old history.
5. Add database fields/messages through additive migration only.
6. Validate existing Agent handles for normalization collisions before exact
   normalized matching becomes mandatory.
7. Do not rewrite historical Group messages or retroactively execute old `@`.

## 10. Definition Of Done

The remediation is complete when:

- each visible executable `@` resolves to one current Group member identity;
- the same identity cannot be queued twice through name plus alias;
- code/quotes/examples cannot execute routes;
- DONE, HANDOFF, HOLD, and INVALID are mutually exclusive mechanical outcomes;
- only genuine completion reaches `task_done`;
- all rejected or inferred routing decisions are visible after refresh;
- no valid natural DONE requires an extra model turn;
- backend and frontend routing suites pass on Windows without starting a
  persistent development server.
