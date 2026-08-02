# F002 Discovery Evidence

## Operator signal

The operator wants a group-page `/feature <requirement>` capability that checks
whether the group can provide coding, review, and vision roles, loads the
correct lifecycle Skills, lets Agents transition state themselves through MCP,
and continues from one sentence through delivery.

## Local research

| Area | Finding | Consequence |
|---|---|---|
| Feature control plane | F001 already provides FeatureRun creation, activation, role CAS, Session-bound transitions, gate evidence, Git provenance, and D14. | F002 composes with F001; it must not add a second lifecycle state machine. |
| Group routing | One GroupInvocation owns a persistent, depth-bounded worklist and recursively routes final Agent @mentions. | Use existing custody for cross-role handoff rather than a parallel orchestration queue. |
| Roles | Group membership has no permanent coding/reviewer/guardian metadata; FeatureRun already stores three role IDs. | Assign roles per run; deterministic fallback removes setup burden. |
| Frontend | Direct chat has a reusable SlashCommand menu; GroupChatView currently only supports mentions and ordinary send. | Add a group-specific command catalog and command handling without routing `/feature` as ordinary text. |
| MCP | Built-ins are selected per Agent, backfilled by migration, launched as stdio children, and receive Session ID/capability only through process env. | Add `feature` as a built-in and call Session-scoped REST endpoints with the capability header. |
| Recovery | FeatureRun and GroupInvocation are durable, but the in-memory worklist can stop after failure/restart. | Expose status and idempotent resume; do not duplicate an active run or active invocation. |

## Convergence decisions

1. A Feature needs three distinct Agents, not three globally configured Agent
   classes. Skills supply the temporary role behavior.
2. Fewer than three members is a hard preflight failure. Independence cannot be
   waived or emulated by one Agent.
3. For an unconfigured group, owner is the valid default responder or first
   stable member; reviewer and guardian are the next distinct stable members.
   The UI displays the result so the operator can audit it.
4. The built-in Feature MCP exposes status and transition. It calls the exact
   F001 transition route, so the API remains the sole control plane while the
   operator no longer calls it manually.
5. The live group custody chain performs cross-Agent transport. D14 and MCP
   outputs provide exact next actor/Skill/handoff guidance.
6. `/feature status` is read-only. `/feature resume` starts one invocation only
   when the active Feature has no running/held invocation; retries return the
   existing invocation.
7. Full autonomy means advancing while gates and repository policy are green.
   A missing product decision, authorization, evidence, or independent actor is
   surfaced as a durable blocker, not guessed around.

## Discovery readiness

Every requirement maps to independently verifiable ACs. The entry, stateful
flow, recovery path, terminal state, non-goals, security boundary, and user
visible role fallback are explicit. No unresolved value decision blocks Design
Gate; proposed status is `ready_for_design`.
