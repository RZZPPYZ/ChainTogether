# F002 Independent Review Request

## Exact review target

- Feature: F002 Autonomous Group Feature Delivery
- Author: Codex implementation agent
- Independent reviewer: unassigned at packet creation
- Branch: `codex/f002-autonomous-group-feature`
- Worktree: `F:\RZP_program\my_project\ChainTogether\.worktrees\F002-autonomous-group-feature`
- Base SHA: `3ea65be7a99ef19e3271ab235ef3921d0666e454`
- Head SHA: `848d2a7d4cad91aaff764bf49e8d8a277ae596fa`
- Feature Doc revision: `848d2a7d4cad91aaff764bf49e8d8a277ae596fa`
- Diff: `git diff --find-renames 3ea65be7a99ef19e3271ab235ef3921d0666e454 848d2a7d4cad91aaff764bf49e8d8a277ae596fa`

Review only this exact committed revision. Do not edit the reviewed branch. If
the branch moves, return `blocked` until a new SHA-bound packet is issued.

## Operator intent and source

Current operator request in the Codex conversation:

> “我希望的就是/feature一句要求，群组内的agent就可以帮我去实现这个feature，同时记录这个feature的整个流转过程！确保feature可以实现！”

The originating product decision is recorded in the Feature Doc: one group
`/feature <requirement>` should validate/assign three independent actors and
autonomously drive a durable, resumable, evidence-gated Discovery-to-Closure
chain. Agents call the transition control plane themselves through mandatory
MCP; the operator must not manually advance every stage.

## Canonical artifacts

- Feature Doc: `docs/features/F002-autonomous-group-feature-delivery/feature.md`
- Discovery: `docs/features/F002-autonomous-group-feature-delivery/evidence/discovery.md`
- Orchestration design, actor matrix, invariants, and races:
  `docs/features/F002-autonomous-group-feature-delivery/evidence/orchestration-design.md`
- Approved Design Gate:
  `docs/features/F002-autonomous-group-feature-delivery/evidence/design-verdict-ed9bda4.md`
- Implementation plan: `docs/features/F002-autonomous-group-feature-delivery/plan.md`
- Quality Report:
  `docs/features/F002-autonomous-group-feature-delivery/evidence/quality-report.md`
- TDD evidence: `evidence/tdd-task-4.md` through `evidence/tdd-task-7.md`

## Scope and architecture ownership

Review the complete main-to-head delta, with particular focus on:

1. `FeatureDeliveryManager` start/resume/role policy and durable dispatch
   reconciliation;
2. `FeatureManager` actor matrix, exact Git/evidence gates, capability
   consumption, same-stage Review request, and waiting successor insertion;
3. `GroupManager` fresh depth-zero invocation launch, exact terminal callback,
   and one-turn authority propagation;
4. mandatory HTTP-only Feature MCP and Session/dispatch-bound routes;
5. group `/feature` parser, dedicated API path, status/roles/resume UI, and
   exact draft restoration;
6. migration compatibility, startup recovery, replay resistance, and absence
   of raw secrets from argv/config/messages/database/log-facing results.

FeatureRun remains the lifecycle source of truth; FeatureDispatch owns one
revision-bound delivery generation; GroupInvocation owns one runtime custody
segment; MCP is only a constrained API client. The implementation intentionally
uses one fresh depth-zero GroupInvocation per successor instead of extending
ordinary nested A2A depth.

## Acceptance and verification

All AC-1 through AC-14 are checked in the Feature Doc and mapped to fresh
evidence in `evidence/quality-report.md`. The author ran:

- backend full suite: 88 tests passed, 1 skipped;
- frontend: 9 files / 25 tests passed;
- Python compileall;
- frontend typecheck and production build;
- Skill synchronization and validation;
- Feature validation and generated index refresh;
- generated OpenAPI contract refresh;
- `git diff --check`.

`test_multi_round_review_journey_uses_fresh_role_bound_generations` is the
primary full-chain evidence, including request-changes/fix/re-review and
Vision/Closure actors.

## Known gaps, risks, and questions

- Full-repository lint has an existing 35-error/5-warning baseline. The two
  changed legacy components have the same 8-error total as their base versions;
  new Feature command files/tests lint clean. Confirm this is a non-regression,
  not a hidden new lint waiver.
- UI evidence is component/integration plus production build; manual browser
  experience remains for independent Vision Gate after merge.
- Distributed multi-process orchestration is out of scope. Verify the
  single-control-plane restart and lease invariants do not imply otherwise.
- Check the transaction boundaries around database dispatch creation versus
  external GroupInvocation launch. A launch failure must become a visible,
  resumable blocker and must not duplicate messages/invocations.
- Verify Quality-to-Review correctly dispatches the owner to prepare a
  SHA-bound packet before `request_review` hands off to the independent
  reviewer; reviewer request-changes must return to owner implementation and
  re-enter Quality.
- Verify actor loss/unavailable backend always fails closed and role updates do
  not retarget a running or handoff-committed dispatch.

## Required reviewer output

Return findings first, ordered P1/P2/P3. Every finding must include evidence,
a tight file and line location, the violated intent/AC/invariant, and a concrete
failure scenario. Then list residual risks and finish with exactly one verdict:

- `approve`
- `request_changes`
- `blocked`

Bind the verdict explicitly to head
`848d2a7d4cad91aaff764bf49e8d8a277ae596fa`. Absence of findings is not enough;
state which high-risk boundaries were inspected and why the verdict follows.
