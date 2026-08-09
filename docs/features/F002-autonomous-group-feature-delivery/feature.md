---
schema_version: 1
id: F002
title: "Autonomous Group Feature Delivery"
stage: review
state: active
priority: P1
owner: "codex"
reviewer: ""
vision_guardian: ""
origin_kind: "codex_conversation"
origin_group_id: ""
origin_message_seq: null
created_at: 2026-08-02
updated_at: 2026-08-09
related_features: ["F001"]
blocked_by: []
research_refs: ["docs/features/F002-autonomous-group-feature-delivery/evidence/discovery.md", "docs/features/F002-autonomous-group-feature-delivery/evidence/orchestration-design.md", "docs/features/F001-group-feature-lifecycle/evidence/vision-verdict-0c5482d.md"]
decision_refs: ["docs/features/F002-autonomous-group-feature-delivery/evidence/discovery.md", "docs/features/F002-autonomous-group-feature-delivery/evidence/design-response-f662c20.md", "docs/features/F002-autonomous-group-feature-delivery/evidence/design-response-ab83a23.md", "docs/features/F002-autonomous-group-feature-delivery/evidence/design-verdict-ed9bda4.md"]
plan_refs: ["docs/features/F002-autonomous-group-feature-delivery/plan.md"]
pr_refs: ["https://github.com/RZZPPYZ/ChainTogether/pull/1"]
---

# F002: Autonomous Group Feature Delivery

## Why

> Operator: "群组页面包含一个 /slash 命令叫 feature 特性开发，/feature 之后接你的开发需求，然后自动检查群组是否包含了 3 个特定角色的 agent……每个 agent 可以通过 MCP 自主调用流转状态……这样才可以达到我只需要一句话，agent 群组就可以自动按照规则来迭代做开发。"

F001 supplies a durable lifecycle control plane, but the operator still has to
create the FeatureRun, assign roles, start the first Agent, and arrange each
handoff. The product outcome is a group-native entry point that turns one
requirement into a resumable, evidence-gated delivery chain without manual
transition API calls.

## Current State

- The group composer advertises `/feature`; start/status/resume/role commands
  use dedicated delivery APIs and preserve a failed draft.
- FeatureStart and FeatureDispatch rows durably record idempotency,
  policy-bounded authorization, roles, revision/generation custody, exact
  invocation links, blockers, and restart recovery.
- Three eligible Agents are assigned deterministic run-scoped owner, reviewer,
  and vision-guardian roles; unavailable/archived actors block safely.
- Claude Code and Codex receive the mandatory Feature MCP. Session identity and
  one-time exact-dispatch authority are child-env-only.
- D14 injects stage, role, suggested Skill, next step, gate, and canonical doc
  on every scheduled group Agent turn.
- Every accepted handoff creates a fresh depth-zero successor invocation;
  owner-prepared review packets, independent review/re-review, merge, vision,
  and closure retain their separate actors and gates.

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
  5. The current turn's one-time dispatch capability authorizes one transition
     or Review request. That transaction consumes it, marks the predecessor
     `handoff_committed`, and creates one revision-bound `waiting` successor.
     After the exact predecessor invocation ends, the successor becomes
     dispatchable and starts a fresh depth-zero GroupInvocation for the required
     actor. Fix/Review cycles can repeat without exhausting A2A depth.
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

- [x] AC-1: The group composer advertises and accepts `/feature <requirement>`,
  `/feature status`, and `/feature resume`; empty new requirements are rejected
  without sending an ordinary group message.
- [x] AC-2: A group with fewer than three live members receives an actionable
  error before any FeatureRun, Feature Doc, role update, or invocation is
  created.
- [x] AC-3: With at least three members and no preassigned roles, start chooses
  three distinct live, non-archived Agents deterministically using
  `(joined_at, agent_id)`, prefers a valid default responder as owner, persists
  complete assignments, and returns names/IDs to the UI.
- [x] AC-4: Start commits request-key idempotency, complete roles, FeatureRun,
  created event, active pointer, create-only Feature Doc outbox image, and
  initial dispatch in one DB transaction; every later filesystem/launch crash
  point resumes the same run without an orphan or duplicate.
- [x] AC-5: Every group Agent receives the mandatory core Feature MCP with
  `status`, `transition`, and `request_review` tools; tool results identify the
  run, stage, role, suggested Skill, next step, dispatch state, and required
  successor actor. Each dispatched turn additionally receives an unlisted,
  one-time dispatch capability through process env, absent from argv/config.
- [x] AC-6: MCP derives identity from `OCTOPUS_SESSION_ID` plus the Session
  capability and binds mutation to the exact active invocation generation with
  its dispatch capability. The first transition/request consumes that token in
  the same transaction as lifecycle change and successor insert; replay, wrong
  Session/token/role, missing evidence, stale Git, or invalid edge fails closed.
- [x] AC-7: Start creates an initial dispatch. Each accepted transition or
  `request_review` atomically marks its active predecessor
  `handoff_committed` and creates one `waiting` revision-bound successor. Only
  the exact predecessor terminal callback promotes it; one fresh depth-zero
  invocation then launches for the actor matrix, supporting multi-round Review.
- [x] AC-8: The group header/composer shows active Feature ID, stage, state, and
  role assignments, and reflects start/status/resume failures without losing
  the operator's requirement.
- [x] AC-9: Two concurrent starts (same or different request keys) produce one
  active-pointer winner; retries return the same checkpoint/run and explicit
  status/resume path rather than creating another doc, run, or invocation.
- [x] AC-10: Dispatch state, revision, lease, target, purpose, generation, and
  invocation/predecessor link and capability hash survive restart. Two resumes,
  transition-vs-resume, double transition from an old turn, terminal-vs-lease,
  token replay, and a late callback converge to one current actor invocation;
  dead/blocked runs recompute from FeatureRun truth.
- [x] AC-11: Claude Code and Codex always expose Feature MCP as an unremovable
  core control-plane server without leaking Session capability in argv or
  connector configuration, regardless of an Agent's optional MCP selection.
- [x] AC-12: Focused backend, MCP, group journey, and frontend tests pass;
  generated API contracts, Skill/Feature validators, typecheck, and production
  build remain synchronized.
- [x] AC-13: `/feature roles owner=@... reviewer=@... guardian=@...` visibly
  patches three distinct live members through the operator API; removal,
  archival, or unavailable backend blocks affected dispatch/edge until roles
  are corrected and resumed. Agents cannot self-reassign through MCP.
- [x] AC-14: `/feature <requirement>` records run-scoped authorization for
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
- **Design Gate responses**: `evidence/design-response-f662c20.md`,
  `evidence/design-response-ab83a23.md`
- **Merge authorization**: the operator's explicit one-sentence-to-delivery
  request is interpreted as the policy-bounded decision in AC-14.

## Design Gate

- **Verdict**: approved
- **Feature Doc revision**: `ed9bda4072ebfdb633f9973545530a6c6aff6f8a`
- **Evidence**: `evidence/design-verdict-ed9bda4.md`

## Delivery

- **Plan**: `docs/features/F002-autonomous-group-feature-delivery/plan.md`
- **Worktree**: `F:\\RZP_program\\my_project\\ChainTogether\\.worktrees\\F002-autonomous-group-feature`
- **Branch**: `codex/f002-autonomous-group-feature`
- **Vision-fix worktree**: `F:\\RZP_program\\my_project\\ChainTogether\\.worktrees\\F002-vision-handoff-fix`
- **Vision-fix branch**: `codex/f002-vision-handoff-fix`
- **Control plane**: mandatory Feature MCP, Session/dispatch-bound routes,
  atomic handoff pairs, restart reconciliation
- **Group UX**: `/feature` autocomplete, start/status/resume/roles, live stage
  and role panel, blocker and draft recovery
- **Journey test**: owner stages -> owner review preparation -> independent
  review -> owner fixes -> re-review -> merge -> guardian -> closure, with a
  fresh generation at every handoff

## Review Provenance

- **Author**: codex
- **Reviewer**: independent `/root/f002_independent_review`
- **Base SHA**: `6cd0541e1866e86745a64e2b52b5edb330998bae`
- **Reviewed HEAD**: `f43b80e612e51ed4045f63e0dbafe892f1037452`
- **Verdict**: approved after Vision handoff correction and canonical Skill
  continuity re-review

## Quality Gate

- **Verdict**: pass
- **Evidence**: `evidence/quality-report-vision-fix.md`
- **Fresh matrix**: backend 96 tests (1 skipped), frontend 27 tests,
  typecheck/build/validators/contracts/diff check green; the unchanged
  frontend lint baseline remains 33 errors and 5 warnings

## Merge Gate

- **Pull request**: [#1](https://github.com/RZZPPYZ/ChainTogether/pull/1)
- **PR head / reviewed head**: `e09e09040237bc69e6bf9a165976ef075165e051`
- **Merge commit**: `918e04a0dfc3b46b1b3e66f9a77fec4256965790`
- **Verdict**: merged; proceed to independent Vision Gate
- **Evidence**: `evidence/merge-evidence-918e04a.md`

## Vision Gate

- **Guardian**: independent `/root/f002_vision_guardian`
- **Merged revision**: `918e04a0dfc3b46b1b3e66f9a77fec4256965790`
- **Verdict**: changes_required
- **Journey evidence**: `evidence/vision-verdict-918e04a.md`

## Risks and Open Questions

| ID | Type | Item | Owner | Status |
|---|---|---|---|---|
| RISK-1 | correctness | A start request can create a run before group invocation launch fails; active-run conflict must make retry resume rather than duplicate. | implementer | mitigated by atomic checkpoint, exact lease failure, same-key recovery |
| RISK-2 | security | Feature MCP must not turn the shared bearer into cross-Session impersonation. | implementer | verified Session + one-time dispatch capability; raw tokens child-env-only |
| RISK-3 | product | Deterministic role assignment does not measure model suitability. | operator | accepted fallback; assignment is visible and patchable |
| RISK-4 | operations | A group chain can stop on process crash or Agent failure. | implementer | startup lease reclaim, zombie completion, status and idempotent resume implemented |
| RISK-5 | policy | One-sentence autonomy cannot authorize bypassing repo merge policy or unresolved operator value decisions. | operator | fail closed and surface blocker |
| RISK-6 | concurrency | Start, resume, transition, and late workers can duplicate delivery without database claims. | implementer | DB CAS, partial uniqueness, handoff pair, replay tests implemented |
| RISK-7 | routing | One GroupInvocation depth cap cannot sustain multi-round Review. | implementer | verified fresh depth-zero successor per dispatch |
| RISK-8 | routing | A lifecycle reply's ordinary `@Agent` handoff can enqueue an unprivileged actor in the predecessor before the durable successor launches. | implementer | fixed and covered at Review plus three lifecycle edges; merged Vision revalidation pending |

## Timeline

| Date | Event | Evidence |
|---|---|---|
| 2026-08-02 | Created from operator request after F001 closure | current Codex conversation |
| 2026-08-02 | Discovery converged role fallback, MCP boundary, and resume semantics | `evidence/discovery.md` |
| 2026-08-02 | Independent Design Gate requested durable successor dispatch, atomic start, concurrency/restart semantics, actor matrix, Session-bound status, and merge authorization | `evidence/design-response-f662c20.md` |
| 2026-08-02 | Discovery revised state census, dispatch protocol, invariants, adversarial matrix, and policy-bounded authorization | `evidence/orchestration-design.md` |
| 2026-08-02 | Second Design Gate requested an explicit handoff pair invariant and invocation-generation authorization | `evidence/design-response-ab83a23.md` |
| 2026-08-02 | Discovery added handoff-committed/waiting successor protocol and one-time dispatch capability | `evidence/orchestration-design.md` |
| 2026-08-02 | Independent Design Gate approved exact Feature Doc revision `ed9bda4` | `evidence/design-verdict-ed9bda4.md` |
| 2026-08-02 | Isolated implementation worktree prepared; Python and frontend baselines are green | `evidence/worktree-record.md` |
| 2026-08-09 | Mandatory Feature MCP and Session/dispatch-bound control APIs implemented | `evidence/tdd-task-4.md`, `evidence/tdd-task-5.md` |
| 2026-08-09 | Fresh successor runtime, restart recovery, and multi-round review-to-closure journey implemented | `evidence/tdd-task-6.md` |
| 2026-08-09 | Group `/feature` command, role grammar, status panel, errors, and exact draft restoration implemented | `evidence/tdd-task-7.md` |
| 2026-08-09 | Quality Gate passed with full tests/build/validators and an explicit no-new-error lint baseline disposition | `evidence/quality-report.md` |
| 2026-08-09 | Independent Review of `848d2a7` found 3 P1, 3 P2, and 1 P3; all were reproduced and fixed through new regression tests | `evidence/review-findings-848d2a7.md`, `evidence/tdd-review-fixes.md` |
| 2026-08-09 | Same independent Reviewer replayed all seven fixes and approved exact implementation HEAD `02e78e8` with no new findings | `evidence/review-verdict-02e78e8.md` |
| 2026-08-09 | GitHub PR #1 merged exact reviewed head `e09e090` into `main` as `918e04a`; Feature moved to Vision acceptance | `evidence/merge-evidence-918e04a.md` |
| 2026-08-09 | Independent Vision Gate reproduced a duplicate, unprivileged Reviewer turn in the predecessor invocation and returned `changes_required` | `evidence/vision-verdict-918e04a.md` |
| 2026-08-09 | A fresh isolated worktree started the lifecycle-handoff fix from `main@6cd0541`; the focused runtime baseline was green | `evidence/vision-fix-worktree.md` |
| 2026-08-09 | TDD prevented ordinary mention routing in Feature dispatch predecessors and aligned L0/D14 with MCP-owned fresh successors | `evidence/tdd-vision-handoff-fix.md` |
| 2026-08-09 | Fresh Quality Gate passed the corrected runtime, full backend/frontend suites, build, contracts, and lifecycle validators | `evidence/quality-report-vision-fix.md` |
| 2026-08-09 | Independent Review approved runtime correction `d84fe04`; a subsequent canonical `$request-review` instruction gap made that approval stale for the final HEAD | `evidence/review-verdict-d84fe04.md` |
| 2026-08-09 | Canonical `$request-review` now selects Feature MCP for autonomous runs and reserves `@Reviewer` for manual/non-Feature tasks; provider mounts and contract tests are synchronized | `evidence/tdd-vision-handoff-fix.md` |
| 2026-08-09 | Same independent Reviewer approved exact final correction HEAD `f43b80e` with no P1/P2/P3 and verified canonical/Claude/Codex Skill continuity | `evidence/review-verdict-f43b80e.md` |
