---
schema_version: 1
id: F002
title: "Autonomous Group Feature Delivery"
stage: discovery
state: active
priority: P1
owner: "codex"
reviewer: ""
vision_guardian: ""
origin_kind: "codex_conversation"
origin_group_id: ""
origin_message_seq: null
created_at: 2026-08-02
updated_at: 2026-08-02
related_features: ["F001"]
blocked_by: []
research_refs: ["docs/features/F002-autonomous-group-feature-delivery/evidence/discovery.md", "docs/features/F001-group-feature-lifecycle/evidence/vision-verdict-0c5482d.md"]
decision_refs: ["docs/features/F002-autonomous-group-feature-delivery/evidence/discovery.md"]
plan_refs: []
pr_refs: []
---

# F002: Autonomous Group Feature Delivery

## Why

> Operator: "群组页面包含一个 /slash 命令叫 feature 特性开发，/feature 之后接开发需求，然后自动检查群组是否包含了 3 个特定角色的 agent……每个 agent 可以通过 MCP 自主调用流转状态……我只需要一句话，agent 群组就可以自动按照规则来迭代做开发。"

F001 supplies a durable lifecycle control plane, but the operator still has to
create the FeatureRun, assign roles, start the first Agent, and arrange each
handoff. The product outcome is a group-native entry point that turns one
requirement into a resumable, evidence-gated delivery chain without manual
transition API calls.

## Current State

- The group composer has @mention routing but no group slash-command menu.
- REST APIs can create FeatureRuns, update roles, activate a run, and perform
  Session-bound transitions.
- D14 injects stage, role, suggested Skill, next step, gate, and canonical doc
  on every group Agent turn.
- Built-in MCP servers do not expose Feature status or transition tools.
- A group may contain two members and has no permanent coding/review/guardian
  role metadata.
- Existing group invocations already provide durable, depth-bounded A2A
  handoff custody; this Feature should compose with that system.

## Scope

- In scope: a discoverable group `/feature <requirement>` command; preflight;
  deterministic per-run role assignment; FeatureRun creation and activation;
  launch/resume/status UX; an Agent-callable built-in Feature MCP; exact
  Session identity and existing Gate enforcement; role-aware handoff guidance;
  active-feature visibility; backend/frontend/MCP tests and documentation.
- Out of scope: permanent organization-wide job titles, model-quality ranking,
  inventing missing operator product decisions, weakening independent Review
  or Vision gates, distributed multi-process orchestration, bypassing repository
  merge policy, and silently force-merging red or unauthorized work.

## User Journey

- **Scope unit**: one group FeatureRun
- **Actor**: operator, then three distinct group Agents assigned as owner,
  reviewer, and vision guardian
- **Entry**: operator enters `/feature <development requirement>` in a group
- **Flow**:
  1. The UI recognizes the command and the backend validates a non-empty
     requirement, group working directory, and at least three live members.
  2. The control plane assigns three distinct roles. The configured default
     responder is owner when valid; remaining members are selected in stable
     group order for reviewer and guardian. The assignment is shown to the
     operator.
  3. One active FeatureRun and canonical Feature Doc are created, and a linked
     group invocation wakes the owner with the requirement and autonomous
     lifecycle contract.
  4. Each Agent reads D14, loads the suggested stage Skill, produces the
     required artifact/evidence, and calls the Feature MCP to inspect or
     transition the run. MCP calls use the live Session capability and cannot
     bypass the existing transition API or role gates.
  5. Owner, reviewer, and guardian hand off through the existing group custody
     chain. Protected stages route to the assigned independent Agent; fixes
     route back to owner; accepted work closes through the canonical workflow.
  6. If the invocation stops or the server restarts, `/feature status` exposes
     durable state and `/feature resume` wakes the actor required by the current
     stage without creating a duplicate FeatureRun.
- **Terminal state**: FeatureRun is `done`, active group Feature is cleared,
  and the UI shows the closed run and evidence-backed delivery result.
- **Success evidence**: command/component tests; fewer-than-three and
  deterministic-assignment tests; start/resume idempotency tests; MCP
  identity/gate tests; group handoff journey; full Quality/Review/Vision chain.

## Requirements

| ID | Requirement | Source | AC |
|---|---|---|---|
| R1 | Make autonomous Feature delivery a discoverable group UI capability. | operator | AC-1, AC-8 |
| R2 | Fail safely when a group cannot provide three independent roles. | operator | AC-2 |
| R3 | Auto-assign valid run roles when permanent relationships are absent. | operator | AC-3 |
| R4 | Create and start one durable, resumable Feature chain from one sentence. | operator | AC-4, AC-7, AC-9 |
| R5 | Let Agents inspect and transition FeatureRun through MCP, not manual operator API calls. | operator | AC-5, AC-6 |
| R6 | Preserve F001 evidence, role, Git, and gate guarantees. | F001 Vision Gate | AC-6, AC-10 |
| R7 | Keep provider configuration and generated contracts consistent. | repository architecture | AC-11, AC-12 |

## Acceptance Criteria

- [ ] AC-1: The group composer advertises and accepts `/feature <requirement>`,
  `/feature status`, and `/feature resume`; empty new requirements are rejected
  without sending an ordinary group message.
- [ ] AC-2: A group with fewer than three live members receives an actionable
  error before any FeatureRun, Feature Doc, role update, or invocation is
  created.
- [ ] AC-3: With at least three members and no preassigned roles, start chooses
  three distinct Agents deterministically, prefers a valid default responder as
  owner, persists the assignments, and returns their names/IDs to the UI.
- [ ] AC-4: Start creates and activates one FeatureRun, writes its canonical
  Feature Doc, and launches one linked group invocation addressed to the owner
  with the original requirement and autonomous lifecycle contract.
- [ ] AC-5: Every existing and newly created Agent receives the built-in
  Feature MCP with `status` and `transition` tools; tool results identify the
  run, stage, role, suggested Skill, next step, and required handoff actor.
- [ ] AC-6: MCP derives identity from `OCTOPUS_SESSION_ID` plus the unlisted
  Session capability and calls the existing control-plane transition path;
  wrong Session/capability, wrong assigned role, missing evidence, stale Git,
  or invalid edge remains fail-closed.
- [ ] AC-7: The start prompt and transition/status outputs route ordinary work
  to owner, independent Review to reviewer, Vision acceptance to guardian, and
  fixes/closure back to owner through the existing group handoff contract.
- [ ] AC-8: The group header/composer shows active Feature ID, stage, state, and
  role assignments, and reflects start/status/resume failures without losing
  the operator's requirement.
- [ ] AC-9: Starting while an unfinished Feature is already active returns that
  run and an explicit status/resume path rather than creating a duplicate.
- [ ] AC-10: State is durable across server restart; status can reconstruct the
  required actor and resume launches at most one new invocation for a run that
  has no active invocation.
- [ ] AC-11: Claude Code and Codex provider assembly exposes the Feature MCP
  without leaking the Session capability in argv or connector configuration;
  migration backfills it into existing Agent MCP selections.
- [ ] AC-12: Focused backend, MCP, group journey, and frontend tests pass;
  generated API contracts, Skill/Feature validators, typecheck, and production
  build remain synchronized.

## Research and Decisions

- Research: local inspection of F001 FeatureRun/transition APIs, GroupManager
  custody and A2A handoff, D14 routing, group composer, and built-in MCP
  assembly. See `evidence/discovery.md`.
- Decisions: roles are per-FeatureRun rather than permanent Agent types;
  deterministic fallback assignment is valid because every group Agent can
  load the role's canonical Skill; existing GroupInvocation custody remains the
  orchestration transport; MCP is a secure client of the transition API, not a
  second state machine; active-run conflict resolves to status/resume.
- Rejected alternatives: require the operator to configure three permanent
  roles before every command; let one Agent self-review and self-accept when the
  group is small; let MCP update the database directly; implement orchestration
  only in frontend callbacks; create a duplicate run on retry; automatically
  merge despite a red or unauthorized Merge Gate.

## Architecture Ownership

- **Owner**: Feature delivery orchestration at the boundary of GroupManager and
  FeatureManager
- **Boundary**: FeatureRun owns long-lived delivery state and gates;
  GroupInvocation owns one live A2A custody chain; MCP is a Session-bound API
  adapter; the UI owns command discovery and status presentation.
- **Extension points**: group feature start/resume routes, role resolver,
  Feature MCP server and harness registry, D14 routing packet, group slash menu,
  generated OpenAPI contracts.
- **Map delta**: update `docs/architecture.md` and `docs/feature-lifecycle.md`

## Design Gate

- **Verdict**: pending
- **Feature Doc revision**: discovery draft 2026-08-02
- **Evidence**: `evidence/discovery.md`

## Delivery

- **Plan**: pending Design Gate
- **Worktree**: pending plan
- **Branch**: `codex/f002-autonomous-group-feature`

## Review Provenance

- **Author**: codex
- **Reviewer**:
- **Base SHA**: `3ea65be7a99ef19e3271ab235ef3921d0666e454`
- **Reviewed HEAD**:
- **Verdict**: pending

## Vision Gate

- **Guardian**:
- **Merged revision**:
- **Verdict**: pending
- **Journey evidence**:

## Risks and Open Questions

| ID | Type | Item | Owner | Status |
|---|---|---|---|---|
| RISK-1 | correctness | A start request can create a run before group invocation launch fails; active-run conflict must make retry resume rather than duplicate. | implementer | design mitigation defined |
| RISK-2 | security | Feature MCP must not turn the shared bearer into cross-Session impersonation. | implementer | reuse Session capability gate |
| RISK-3 | product | Deterministic role assignment does not measure model suitability. | operator | accepted fallback; assignment is visible and patchable |
| RISK-4 | operations | A group chain can stop on process crash or Agent failure. | implementer | durable status plus idempotent resume |
| RISK-5 | policy | One-sentence autonomy cannot authorize bypassing repo merge policy or unresolved operator value decisions. | operator | fail closed and surface blocker |

## Timeline

| Date | Event | Evidence |
|---|---|---|
| 2026-08-02 | Created from operator request after F001 closure | current Codex conversation |
| 2026-08-02 | Discovery converged role fallback, MCP boundary, and resume semantics | `evidence/discovery.md` |
