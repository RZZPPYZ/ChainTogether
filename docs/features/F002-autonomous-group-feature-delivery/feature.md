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
research_refs: ["docs/features/F002-autonomous-group-feature-delivery/evidence/discovery.md", "docs/features/F002-autonomous-group-feature-delivery/evidence/orchestration-design.md", "docs/features/F001-group-feature-lifecycle/evidence/vision-verdict-0c5482d.md"]
decision_refs: ["docs/features/F002-autonomous-group-feature-delivery/evidence/discovery.md", "docs/features/F002-autonomous-group-feature-delivery/evidence/design-response-f662c20.md"]
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
  deterministic per-run role assignment and correction; atomic start
  checkpoint; FeatureRun creation and activation; revision-bound durable
  successor dispatch across fresh GroupInvocations; launch/resume/status UX;
  an Agent-callable mandatory core Feature MCP; exact Session identity and
  existing Gate enforcement; active-feature visibility;
  backend/frontend/MCP/recovery tests and documentation.
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
  3. One atomic start checkpoint creates the complete FeatureRun roles, event,
     active pointer, create-only Feature Doc outbox image, and initial durable
     dispatch. Recovery finishes the document and launches a linked owner
     GroupInvocation with the requirement and autonomous lifecycle contract.
  4. Each Agent reads D14, loads the suggested stage Skill, produces the
     required artifact/evidence, and calls the Feature MCP to inspect or
     transition the run. MCP calls use the live Session capability and cannot
     bypass the existing transition API or role gates.
  5. A transition transaction records one revision-bound successor dispatch.
     Each dispatch waits for the current invocation to end, then starts a fresh
     depth-zero GroupInvocation for the required actor. Review preparation uses
     an explicit MCP `request_review` dispatch; fixes route to owner and can
     repeat without exhausting the A2A depth cap.
  6. If an invocation stops or the server restarts, `/feature status` exposes
     durable start/dispatch state and `/feature resume` recomputes the actor
     from current FeatureRun truth, leases one dispatch generation, and cannot
     duplicate a FeatureRun, message, or live invocation.
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
| R4 | Create and start one durable, resumable Feature chain from one sentence. | operator | AC-4, AC-7, AC-9, AC-10 |
| R5 | Let Agents inspect, request Review, and transition FeatureRun through MCP, not manual operator API calls. | operator | AC-5, AC-6 |
| R6 | Preserve F001 evidence, role, Git, and gate guarantees. | F001 Vision Gate | AC-6, AC-10 |
| R7 | Keep provider configuration and generated contracts consistent. | repository architecture | AC-11, AC-12 |
| R8 | Make role loss and autonomous merge authority explicit and auditable. | Design Gate + operator delivery request | AC-13, AC-14 |

## Acceptance Criteria

- [ ] AC-1: The group composer advertises and accepts `/feature <requirement>`,
  `/feature status`, and `/feature resume`; empty new requirements are rejected
  without sending an ordinary group message.
- [ ] AC-2: A group with fewer than three live members receives an actionable
  error before any FeatureRun, Feature Doc, role update, or invocation is
  created.
- [ ] AC-3: With at least three members and no preassigned roles, start chooses
  three distinct live, non-archived Agents deterministically using
  `(joined_at, agent_id)`, prefers a valid default responder as owner, persists
  complete assignments, and returns names/IDs to the UI.
- [ ] AC-4: Start commits request-key idempotency, complete roles, FeatureRun,
  created event, active pointer, create-only Feature Doc outbox image, and
  initial dispatch in one DB transaction; every later filesystem/launch crash
  point resumes the same run without an orphan or duplicate.
- [ ] AC-5: Every group Agent receives the mandatory core Feature MCP with
  `status`, `transition`, and `request_review` tools; tool results identify the
  run, stage, role, suggested Skill, next step, dispatch state, and required
  successor actor.
- [ ] AC-6: MCP derives identity from `OCTOPUS_SESSION_ID` plus the unlisted
  Session capability and calls the existing control-plane transition path;
  wrong Session/capability, wrong assigned role, missing evidence, stale Git,
  or invalid edge remains fail-closed.
- [ ] AC-7: Start, each accepted transition, and `request_review` create an
  idempotent revision-bound successor dispatch. After the current invocation
  ends, it launches one fresh depth-zero invocation for owner, reviewer, or
  guardian according to the actor matrix; multi-round Review/fix chains reach
  Vision without the single-invocation A2A depth cap.
- [ ] AC-8: The group header/composer shows active Feature ID, stage, state, and
  role assignments, and reflects start/status/resume failures without losing
  the operator's requirement.
- [ ] AC-9: Two concurrent starts (same or different request keys) produce one
  active-pointer winner; retries return the same checkpoint/run and explicit
  status/resume path rather than creating another doc, run, or invocation.
- [ ] AC-10: Dispatch state, revision, lease, target, purpose, generation, and
  invocation link survive restart. Two resumes, transition-vs-resume, and a
  late old worker converge to one current actor invocation; dead/blocked runs
  recompute from FeatureRun stage/roles instead of trusting stale custody.
- [ ] AC-11: Claude Code and Codex always expose Feature MCP as an unremovable
  core control-plane server without leaking Session capability in argv or
  connector configuration, regardless of an Agent's optional MCP selection.
- [ ] AC-12: Focused backend, MCP, group journey, and frontend tests pass;
  generated API contracts, Skill/Feature validators, typecheck, and production
  build remain synchronized.
- [ ] AC-13: `/feature roles owner=@... reviewer=@... guardian=@...` visibly
  patches three distinct live members through the operator API; removal,
  archival, or unavailable backend blocks affected dispatch/edge until roles
  are corrected and resumed. Agents cannot self-reassign through MCP.
- [ ] AC-14: `/feature <requirement>` records run-scoped authorization for
  commit, push, PR, and merge only after green gates and repository policy.
  Force push, protection/CI bypass, deployment, unrelated external effects, or
  unresolved value decisions remain blocked and visible.

## Research and Decisions

- Research: local inspection of F001 FeatureRun/transition APIs, GroupManager
  custody and A2A handoff, D14 routing, group composer, and built-in MCP
  assembly. See `evidence/discovery.md`.
- Decisions: roles are per-FeatureRun rather than permanent Agent types;
  deterministic fallback assignment is valid because every group Agent can
  load the role's canonical Skill; FeatureDispatch creates fresh successor
  invocations while FeatureRun stays the sole lifecycle state machine; MCP is a
  secure client of the transition API; active-run conflict resolves to
  status/resume; the command grants policy-bounded run merge authorization.
- Rejected alternatives: require the operator to configure three permanent
  roles before every command; let one Agent self-review and self-accept when the
  group is small; let MCP update the database directly; implement orchestration
  only in frontend callbacks; create a duplicate run on retry; automatically
  merge despite a red or unauthorized Merge Gate.

## Architecture Ownership

- **Owner**: Feature delivery orchestration at the boundary of GroupManager and
  FeatureManager
- **Boundary**: FeatureRun owns long-lived delivery state and gates;
  FeatureDispatch owns revision-bound successor delivery; GroupInvocation owns
  one live A2A custody segment; MCP is a Session-bound API adapter; the UI owns
  command discovery, role correction, and status presentation.
- **Extension points**: group feature start/resume routes, role resolver,
  Feature MCP server and harness registry, D14 routing packet, group slash menu,
  generated OpenAPI contracts.
- **Map delta**: update `docs/architecture.md` and `docs/feature-lifecycle.md`

## Lifecycle Design

- **State census, event tables, actor matrix, invariants, recovery and bypass
  tests**: `evidence/orchestration-design.md`
- **Design Gate response**: `evidence/design-response-f662c20.md`
- **Merge authorization**: the operator's explicit one-sentence-to-delivery
  request is interpreted as the policy-bounded decision in AC-14.

## Design Gate

- **Verdict**: pending
- **Feature Doc revision**: discovery revision after `f662c20` changes_required
- **Evidence**: `evidence/discovery.md`, `evidence/orchestration-design.md`, `evidence/design-response-f662c20.md`

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
| RISK-6 | concurrency | Start, resume, transition, and late workers can duplicate delivery without database claims. | implementer | revision dispatch/lease protocol defined |
| RISK-7 | routing | One GroupInvocation depth cap cannot sustain multi-round Review. | implementer | fresh successor invocation per dispatch |

## Timeline

| Date | Event | Evidence |
|---|---|---|
| 2026-08-02 | Created from operator request after F001 closure | current Codex conversation |
| 2026-08-02 | Discovery converged role fallback, MCP boundary, and resume semantics | `evidence/discovery.md` |
| 2026-08-02 | Independent Design Gate requested durable successor dispatch, atomic start, concurrency/restart semantics, actor matrix, Session-bound status, and merge authorization | `evidence/design-response-f662c20.md` |
| 2026-08-02 | Discovery revised state census, dispatch protocol, invariants, adversarial matrix, and policy-bounded authorization | `evidence/orchestration-design.md` |
