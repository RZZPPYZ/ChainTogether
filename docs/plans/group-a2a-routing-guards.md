# Group A2A Routing Guards

## 1. Context

Group chat `@` routing now uses long-lived `(group, agent)` member sessions
and a single group worklist. This solved the first structural bug: agent
handoffs no longer create a fresh child session for every mention.

The remaining problem is routing governance. Once agents can hand off to each
other, the system needs enough guardrails to distinguish useful collaboration
from accidental infinite passing, syntax mistakes, and stale worklists.

This plan compares the current Octopus group design with the Clowder A2A
routing notes in `F:\RZP_program\reference\tutorials\clowder-ai补充.md`.

## 2. Already Implemented

- Long-lived group-member reuse sessions keyed by `(group_id, agent_id)`.
- One serial group worklist for both user mentions and A2A mentions.
- Agent replies route only line-start `@handle` mentions; inline mentions are
  ignored.
- Fenced code blocks are stripped before mention parsing.
- Basic A2A guards:
  - unknown member skip;
  - self-mention skip;
  - already-active target skip;
  - already-pending target skip;
  - generous A2A depth cap;
  - same-pair short ping-pong hard block.
- A user group message resets the in-memory ping-pong streak.
- Deleting a group refuses active turns and hard-deletes the backing session
  plus group-member reuse sessions.

## 3. Important Gaps

### 3.1 Ping-Pong Has A Hard Block But No Soft Warning

Current behavior only blocks at the threshold. It does not warn agents before
the block, so agents have no chance to adjust their routing decision.

Clowder uses a graded policy:

- first handoff: normal;
- warning range: inject routing feedback;
- block range: reject the worklist push.

### 3.2 Substantive Work Detection Is Too Thin

Current ping-pong detection mostly treats `reply_text.length > 200` as
substantive work. That is useful but incomplete.

The routing policy should reset or de-escalate the streak when the caller did
real work, for example:

- non-routing tool calls;
- long analytical output;
- multi-target fan-out;
- switching to a different pair.

Without this, two agents doing legitimate back-and-forth review can be
mistaken for a loop.

### 3.3 Recovery Semantics Are Too Implicit

The current block injects an `[agent-error]`, but the routing state does not
explicitly capture:

- which pair was blocked;
- why it was blocked;
- which action recovers it;
- whether a different target is allowed immediately.

Recovery should be explicit and predictable:

- user message resets the streak;
- different target resets the streak;
- substantive work resets the streak;
- the same blocked pair doing another short handoff remains blocked.

### 3.4 Inline Mention Feedback Is Missing

Agent replies such as `please ask @Alice` do not route, which is correct.
However, the agent receives no feedback that the inline mention was ignored.

Clowder detects inline mentions in the final routing slot and feeds back a
syntax reminder. Octopus should add a lightweight version so agents learn to
use line-start mentions.

### 3.5 No Valid-Exit Remediation

An A2A agent can finish with no line-start mention, no hold action, and no
handoff back to the user. For ordinary chat this is acceptable; for automatic
agent collaboration it means the ball silently drops.

A one-shot remedial turn should be considered for A2A chains: ask the agent to
provide only a routing exit, without redoing its work. The remedial attempt
must be capped at one try.

### 3.6 No Hold / Void-Hold State

There is currently no `hold_ball` equivalent. Agents can say they are waiting,
but the system cannot distinguish a real held state from a textual claim.

This is useful but larger than the first routing cleanup. It should come after
the ping-pong and feedback guards are stable.

### 3.7 Worklist Isolation Is Group-Level, Not Invocation-Level

The current active state is keyed by `group_id`. If a user sends a new message
while an old A2A chain is still draining, the old and new routing chains can
share one queue.

Clowder isolates worklists by parent invocation. Octopus should eventually do
the same so stale A2A pushes cannot contaminate a newer user request.

## 4. Priority 1: Implement Now

### 4.1 Add Graded Ping-Pong Policy

Introduce:

- warning threshold: repeated same-pair short handoffs at count 2 and 3;
- block threshold: count 4;
- visible warning injection before the target turn runs;
- visible block injection when the target is rejected.

The warning should be inserted into the group transcript and included in the
next target prompt through normal group context, so the target can adjust.

### 4.2 Improve Substantive Activity Detection

Track caller activity while collecting a member reply:

- output length;
- whether the turn used tool calls;
- whether any tool call looks substantive rather than routing-only.

The ping-pong streak should reset when the caller produced substantive output.
At minimum, long output and substantive tool calls should be treated as
substantive.

### 4.3 Make Recovery Rules Explicit

Keep the recovery lightweight and in-memory for now:

- user message resets routing streak;
- multi-target A2A resets routing streak;
- different pair resets routing streak;
- substantive caller activity resets routing streak;
- same-pair short handoff increments;
- same-pair short handoff at block threshold rejects the push and records the
  blocked pair.

## 5. Priority 2: Routing Feedback And Syntax Remediation

- Detect known-member inline mentions only in the final routing paragraph.
- When no valid line-start route exists, preserve the original reply and run
  one syntax-only correction turn in the same member session.
- Stop after that single correction attempt and notify the group if it still
  has no valid line-start route.
- Show transcript diagnostics for skipped unknown/self/active/pending routes.

Octopus does not treat every reply without an `@` as a dropped route. Unlike
Clowder's strict ball-custody model, a plain group reply is a valid completion:
the user already sees it, and `@User` is intentionally unnecessary. Automatic
remediation therefore only
triggers when a known member appears as an inline mention in the final routing
paragraph, which is a mechanically observable malformed handoff.

## 6. Priority 3: Durable Invocation And Ball Custody

- Every user message that resolves at least one group member creates a durable
  `group_invocations` row and an isolated in-memory queue.
- Custody transitions are explicit and validated:
  `new -> active -> held/blocked/void/resolved/cancelled/dead`.
- Agents may hold a chain with a final
  `[group-hold:SECONDS] reason` action. Holds are bounded to 5-3600 seconds,
  persisted, resumable, cancellable, and fail visibly when they expire.
- Running and held chains are listed through REST and mirrored through
  `group_invocation` WebSocket events.
- The UI can cancel one running/held invocation without cancelling another
  chain in the same group, and can resume held/blocked/void chains.
- Startup reconciliation restores unexpired hold timers. A chain that was
  running when the server stopped is marked `dead` rather than replayed, since
  replay could duplicate an agent turn that completed just before the crash.
- Plain `@Agent` routing remains current-group only. Cross-thread handoff is
  explicitly unsupported until a structured cross-thread tool exists.

## 7. Implementation Status

Priority 1, Priority 2, and Priority 3 have been implemented.

### 7.1 Completed In This Pass

- Added a graded ping-pong policy:
  - warning starts at same-pair short handoff count 2;
  - warning continues at count 3;
  - block happens at count 4.
- Added visible transcript warnings using
  `[agent-routing-warning:<Agent>]` before the target turn runs.
- Kept visible transcript blocks using `[agent-error:<Agent>]`, with a message
  that explains the recovery conditions.
- Added lightweight activity tracking to group-member turns:
  - assistant output length;
  - observed tool names;
  - substantive tool detection.
- Added ping-pong recovery/reset rules:
  - user message resets the streak;
  - multi-target A2A resets the streak;
  - different same-pair handoff resets by starting a new pair count;
  - substantive caller activity resets the streak;
  - same-pair short handoff increments the streak;
  - same-pair short handoff at the block threshold records a blocked streak.
- Added tests for:
  - warnings before ping-pong block;
  - hard block after repeated short same-pair handoffs;
  - substantive tool activity resetting the streak.

### 7.2 Verified

- `.\.venv\Scripts\python.exe -m pytest tests\test_group_manager_mention.py::TestRunMentionedAgentA2A -v`
  passed: 9 tests.
- `.\.venv\Scripts\python.exe -m pytest tests\test_group_manager.py tests\test_group_manager_mention.py tests\test_group_e2e.py -v`
  passed: 69 tests.

### 7.3 Priority 2 Completed

- Added `AgentRoutingAnalysis` with separate valid line-start and invalid
  inline mention signals.
- Limited invalid-inline detection to known current group members in the final
  non-empty paragraph; earlier prose, unknown handles, code fences, and plain
  completions do not trigger automatic correction.
- Added a one-shot routing correction on the same `(group, agent)` reuse
  session. The prompt requests only corrected line-start handoff lines and
  explicitly forbids repeating completed work.
- Preserved the original reply in the group transcript. A successful corrected
  reply is appended and routed; a failed correction emits a visible warning
  and stops without retrying.
- Added visible `[agent-routing-warning:<Agent>]` diagnostics for unknown,
  self, already-active, and already-pending targets.
- Added focused tests for routing analysis, successful correction, one-shot
  failure, and visible skip diagnostics.
- `\.venv\Scripts\python.exe -m pytest tests\test_group_manager.py tests\test_group_manager_mention.py -q`
  passed: 74 tests.

### 7.4 Priority 3 Completed

- Added durable `group_invocations` storage with status, custody, current
  agent, depth, hold deadline/reason, terminal error, and timestamps.
- Replaced the single group-owned routing lifecycle with one `GroupRunState`
  per invocation. `_runs[group_id]` remains only the latest-run compatibility
  pointer; all active lifecycle operations use the invocation registry.
- Added the validated custody transition table and persisted state events.
- Added bounded hold, expiry, resume, cancellation, and visible
  `[group-invocation:<id>:<state>]` transcript notices.
- Added list/cancel/resume REST endpoints and `group_invocation` WebSocket
  updates.
- Added a compact frontend chain strip with current state/agent/depth plus
  icon controls for resume and cancellation.
- Added startup zombie reconciliation and cancellation ownership checks so a
  late result cannot append more work to a terminal invocation.
- Added tests for state transitions, hold parsing/expiry, persistence,
  exact-chain cancellation, hold/resume, and both running/held restart
  recovery paths.
- `\.venv\Scripts\python.exe -m pytest tests\test_group_manager.py tests\test_group_manager_backend_error.py tests\test_group_manager_mention.py tests\test_group_e2e.py -q`
  passed: 90 tests.

### 7.5 Mandatory Group Routing Contract

- Added a shared system-level protocol to every `origin="group_member"`
  session while leaving ordinary one-to-one sessions unchanged.
- Defined one terminal decision per reply: STOP without any handle, HANDOFF in
  a final line-start routing paragraph with concrete work, or HOLD using the
  bounded hold action.
- Reserved `@` exclusively for executable routing; teammate references in
  prose use plain names, and acknowledgements are not valid reasons to hand
  work back.
- Added the current group's exact valid handles to every member turn.
- Aligned mechanical enforcement with the protocol: only the final non-empty
  paragraph can route. Earlier line-start handles and final inline handles are
  malformed handoffs eligible for the existing one-shot correction.
- Added tests for system-prompt scoping, final-slot enforcement, malformed
  earlier handoffs, and per-turn contract rendering.
- Verification after this contract change:
  - Group routing suites: `94 passed`;
  - focused group-member system protocol test: `1 passed`;
  - frontend unit tests: `84 passed`;
  - TypeScript check: passed;
  - full backend suite: `909 passed, 25 skipped, 53 failed`, with failures in
    the repository's existing Windows/POSIX environment assumptions (`/tmp`,
    `/bin/sh`, process groups, symlinks, and restricted home directories), not
    in Group routing.

### 7.6 Still Deferred

- Structured cross-thread handoff tools. Current group `@` syntax is
  deliberately scoped to current group members and cannot cross sessions.
