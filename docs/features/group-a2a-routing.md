# Group A2A Routing

## Overview

Group chat supports `@Agent` routing inside a shared group transcript. A group
has one backing transcript session, while each `(group, agent)` pair has one
long-lived member session that is reused across mentions.

This feature covers all three routing hardening stages and the follow-up
fixes for user handoff noise and Markdown rendering.

## Implemented Behavior

### Reused Member Sessions

- The group transcript lives in one backing session with `origin="group"`.
- Each member agent gets one reuse session per group with
  `origin="group_member"`.
- Repeated `@Agent` calls reuse the same member session, preserving the
  agent's private resume transcript.

### Serial Worklist

- Each user message that wakes an agent owns an isolated invocation worklist.
- User mentions and subsequent agent-to-agent mentions share that invocation's
  worklist, depth, custody state, and ping-pong streak.
- Each worklist drains serially while separate invocations remain independently
  cancellable.
- Already-active and already-pending A2A targets are skipped to avoid duplicate
  fan-out.

### Agent Mention Syntax

- User messages can mention agents anywhere in the message.
- Agent replies are stricter: only line-start `@Agent` mentions in the final
  non-empty paragraph route.
- Markdown quote/list prefixes are accepted before the line-start mention.
- Mentions inside fenced code blocks are ignored.
- `@User` in agent replies is ignored as a routing target because the user
  already sees every group message.
- An earlier line-start handoff followed by more prose is malformed rather
  than executable and enters the one-shot correction path.

### Inline Handoff Correction

- A known member mentioned inline in the final routing paragraph is treated as
  a malformed handoff only when the reply has no valid line-start route.
- The original reply remains visible in the transcript.
- The same member session receives one syntax-only correction prompt asking
  for line-start `@Agent` lines without repeating completed work.
- A corrected reply is appended and routed normally.
- If the single correction attempt still has no valid route, automatic
  correction stops and the group receives an
  `[agent-routing-warning:<Agent>]` notice.
- Plain replies with no mention are valid completions and never trigger this
  correction path.

### Visible Routing Diagnostics

Agent routes skipped because the target is unknown, is the sender itself, is
already active, or is already pending now produce a visible
`[agent-routing-warning:<Agent>]` message in addition to server logs. Depth
overflow and ping-pong termination remain `[agent-error:<Agent>]` events.

### Prompt Contract

- Every `origin="group_member"` session receives a mandatory routing contract
  in its system prompt on every backend invocation. Ordinary user sessions do
  not receive this contract.
- The member roster lists only agent handles, not `User`.
- Every turn also lists the exact valid handles for the current group.
- Agents must end each reply with exactly one outcome:
  - STOP: complete normally and use no `@handle` anywhere;
  - HANDOFF: use a final routing paragraph whose lines start with exact member
    handles and assign concrete next work;
  - HOLD: use the final `[group-hold:SECONDS] reason` action.
- `@` is reserved for routing. Agents must use plain teammate names in prose,
  must never `@User` or themselves, and must not hand back merely to thank,
  agree, acknowledge, or repeat prior content.
- Mechanical parsing matches the prompt contract: an `@` outside the final
  routing paragraph cannot silently dispatch another agent.

### Ping-Pong Guard

The first routing hardening pass added a graded same-pair ping-pong policy:

- count 1: normal handoff;
- count 2 and 3: inject `[agent-routing-warning:<Agent>]`;
- count 4: reject the handoff with `[agent-error:<Agent>]`.

The streak resets when:

- the user sends a new group message;
- the A2A reply mentions multiple targets;
- the handoff switches to a different pair;
- the caller produced substantive activity.

Substantive activity currently means:

- assistant output longer than the configured threshold;
- a non-routing tool call observed during the member turn.

### Invocation Lifecycle And Cancellation

- A routed user message creates a durable `group_invocations` record.
- The lifecycle records its current agent, routing depth, status, custody
  state, hold details, errors, and timestamps.
- REST endpoints list, cancel, and resume individual invocations.
- WebSocket `group_invocation` events keep the frontend synchronized.
- The group header shows each actionable chain with state, current agent, and
  depth. Stop cancels only that chain; Play resumes held/blocked/void chains.
- Cancellation marks the invocation terminal before interrupting its active
  member turn, so late output cannot enqueue another handoff.

### Ball Custody And Hold

The validated custody states are `new`, `active`, `held`, `blocked`, `void`,
`dead`, `resolved`, and `cancelled`.

An agent pauses a chain by ending its reply with:

```text
[group-hold:300] Waiting for CI results
```

Hold duration is clamped to 5-3600 seconds. The deadline and reason survive a
server restart. The user may resume or cancel the chain; an expired hold moves
to `dead` and emits a visible transcript notice.

### Crash Reconciliation

- Unexpired held invocations restore their expiry timers at startup.
- Expired holds become `dead`.
- Invocations that were running during shutdown become `dead` instead of being
  replayed, preventing duplicate side effects from an uncertain final turn.
- `@Agent` remains current-group only; no text mention can cross sessions.

### Markdown Rendering

Group chat message bubbles render Markdown for normal and agent reply bodies,
including `**bold**`, GFM tables/lists, and math plugins already used by the
main chat surface.

The group renderer also normalizes the common model output form
`** bold text **` into valid Markdown emphasis before rendering, so the
literal `**` markers do not leak into the UI.

## Still Deferred

- Structured cross-thread handoff tools and their authorization model.
