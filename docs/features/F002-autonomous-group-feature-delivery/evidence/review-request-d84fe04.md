# F002 Independent Review Request — Vision handoff correction

- Feature: F002 Autonomous Group Feature Delivery
- Author: `codex`
- Requested reviewer: independent `/root/f002_independent_review`
- Base SHA: `6cd0541e1866e86745a64e2b52b5edb330998bae`
- Head SHA: `d84fe046c9ea8695f0821d29a692d0bd83dfe259`
- Branch: `codex/f002-vision-handoff-fix`
- Worktree: `F:\\RZP_program\\my_project\\ChainTogether\\.worktrees\\F002-vision-handoff-fix`
- Prior rejected merge revision: `918e04a0dfc3b46b1b3e66f9a77fec4256965790`

## Intent

Close the independent Vision finding where a Feature actor could commit an MCP
handoff and then wake the successor a first time without authority inside the
old GroupInvocation through an ordinary final `@Agent` paragraph. The durable
Feature successor must be the only lifecycle handoff and must launch the target
once, in a fresh depth-zero invocation, with exact dispatch authority.

## Review scope

- Runtime boundary: `server/group_manager.py`
- Agent contracts: L0 and D14 prompt templates
- Regression tests: exact Review owner-prep, fresh Reviewer successor, and
  table-driven review-to-owner, merge-to-guardian, acceptance-to-owner edges
- Canonical Feature Doc plus Vision/TDD/Quality evidence

No frontend TypeScript, API schema, database schema, or ordinary group A2A
policy is intentionally changed.

## Acceptance focus

1. A Feature dispatch never runs reply mention analysis, remedial routing, or
   `_dispatch_a2a_mentions` in its predecessor invocation.
2. An ordinary group invocation still routes valid final mentions exactly as
   before.
3. Review Owner may commit `request_review` and visibly return `@Reviewer`, but
   only the formal waiting successor invokes Reviewer.
4. The formal Reviewer invocation has another invocation ID, depth zero, exact
   successor dispatch ID, and its one-time capability.
5. L0 and D14 do not conflict: after a successful Feature MCP mutation, the
   Agent ends naturally without ordinary `@handle` routing.
6. Failure to mutate does not silently delegate authority to a teammate.

## Changed paths

```text
docs/features/F002-autonomous-group-feature-delivery/feature.md
docs/features/F002-autonomous-group-feature-delivery/evidence/quality-report-vision-fix.md
docs/features/F002-autonomous-group-feature-delivery/evidence/tdd-vision-handoff-fix.md
docs/features/F002-autonomous-group-feature-delivery/evidence/vision-fix-worktree.md
docs/features/F002-autonomous-group-feature-delivery/evidence/vision-verdict-918e04a.md
server/assets/prompts/dynamic/update-workflow-sop.md
server/assets/prompts/l0/system-prompt-l0.md
server/group_manager.py
tests/test_feature_dispatch_runtime.py
tests/test_group_routing.py
tests/test_prompt_governance.py
```

## Fresh evidence

- Backend: 95 tests run, all green; 1 configured live-network smoke test skipped.
- Exact Feature dispatch suite: 8/8.
- Prompt and ordinary routing suites: 13/13.
- Frontend: 27/27; typecheck and production build pass.
- Python compile, Skill/Feature validators, 26 provider mounts, fresh OpenAPI
  generation comparison, and `git diff --check`: pass.
- Repository frontend lint remains a pre-existing 33 errors/5 warnings; this
  change contains no `.ts` or `.tsx` path.

Primary evidence:

- `evidence/vision-verdict-918e04a.md`
- `evidence/tdd-vision-handoff-fix.md`
- `evidence/quality-report-vision-fix.md`

## Risks and adversarial questions

- Does blanket suppression for all Feature dispatch replies break HOLD,
  terminal callback promotion, status/resume recovery, or visible replies?
- Can routing still occur through the invalid-inline remedial path?
- Could a non-target actor inherit the predecessor authority through the reused
  group member Session?
- Does the new real journey accidentally pass by mocking the manager transition
  instead of traversing reply injection and routing?
- Is a Feature actor that fails to mutate left auditable and recoverable rather
  than falsely completed?

Known residual risks are merged UX replay, distributed multi-process scheduling,
and repository-wide frontend lint debt. They are explicitly deferred to Vision
or outside F002 scope, not waived by this Review.

## Requested verdict contract

Review exact `6cd0541..d84fe04`. Report evidence-backed P1/P2/P3 findings with
tight file/line references and residual risks, then return exactly one verdict:
`approved`, `request_changes`, or `blocked`. Do not edit the reviewed branch.
