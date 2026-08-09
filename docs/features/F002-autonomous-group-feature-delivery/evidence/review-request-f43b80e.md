# F002 Independent Re-review Request — final handoff contract

- Reviewer: independent `/root/f002_independent_review`
- Base SHA: `6cd0541e1866e86745a64e2b52b5edb330998bae`
- Previously approved runtime HEAD: `d84fe046c9ea8695f0821d29a692d0bd83dfe259`
- Exact re-review HEAD: `f43b80e612e51ed4045f63e0dbafe892f1037452`
- Branch: `codex/f002-vision-handoff-fix`
- Worktree: `F:\\RZP_program\\my_project\\ChainTogether\\.worktrees\\F002-vision-handoff-fix`

## Why re-review is required

The reviewer approved `d84fe04` runtime, L0, D14, and journey changes. Before
Merge, the author found that canonical `$request-review` still told every group
owner to end with `@Reviewer`. That instruction was outside the reviewed diff
and contradicted the new autonomous Feature MCP rule.

`d84fe04..f43b80e` now:

- updates the canonical Skill description to distinguish autonomous Feature MCP
  from explicit manual handoff;
- tells autonomous owners to call Feature MCP `request_review`, then end without
  `@handle` because the control plane creates a fresh Reviewer successor;
- retains short `@Reviewer` only for manual/non-Feature group tasks;
- forbids ordinary A2A fallback on both Feature MCP success and failure;
- adds a canonical contract regression test;
- regenerates and verifies all 26 Claude/Codex provider mounts;
- records the prior approved verdict without misrepresenting it as final-HEAD
  approval.

## Evidence

- RED: the new contract test failed against the old Skill because none of the
  Feature MCP/fresh-successor/no-A2A instructions existed.
- GREEN: contract test passes; `tests.test_lifecycle_assets` 7/7; Skill
  validation reports 13 Skills/10 stages/16 transitions; provider mount check
  reports 26/26.
- Full backend after the Skill change: 96 tests run, all green; 1 configured
  live-network smoke test skipped.
- Prior frontend 27/27, typecheck/build, OpenAPI comparison, and runtime journey
  remain applicable because this follow-up changes only Skill/docs/Python
  contract test.
- `git diff --check` passes.

## Review contract

Verify the full `6cd0541..f43b80e` outcome and specifically inspect
`d84fe04..f43b80e` for instruction consistency, trigger metadata, provider sync,
manual-task behavior, and stale-review truthfulness. Report P1/P2/P3 findings,
residual risks, and exactly one `approved`, `request_changes`, or `blocked`
verdict bound to `f43b80e612e51ed4045f63e0dbafe892f1037452`.
