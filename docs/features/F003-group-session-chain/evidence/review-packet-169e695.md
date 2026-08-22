# F003 Second Independent Re-review Packet

- Feature: F003 — Group Session Chain Handoff
- Author: codex
- Reviewer: same independent `f003_independent_review` Agent
- Branch: `codex/F003-group-session-chain`
- Worktree: `F:\RZP_program\my_project\ChainTogether\.worktrees\F003-group-session-chain`
- Base SHA: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- Previous reviewed HEAD: `e4dc7d2c218071273bb051746fc392cc1bc22c45`
- Re-review HEAD / Feature Doc revision:
  `169e695fc184ceb8296a45a6e0efbd25976ff096`
- Full diff: `git diff 1fb75b26370a2301c94f409d1d817c587d172cb3..169e695fc184ceb8296a45a6e0efbd25976ff096`
- Focused diff: `git diff e4dc7d2c218071273bb051746fc392cc1bc22c45..169e695fc184ceb8296a45a6e0efbd25976ff096`

The packet commit follows the immutable review target. Review the exact SHA,
not the moving branch, and do not modify the branch.

## Operator intent and canonical inputs

> 当前我们的group中不存在session封顶交接的动作……提前预测当要满的时候，进行sealed封装，以及提供MCP工具，供新的session去查，而且新的session也会附带旧的session的总结信息，这个总结是通过调用另外一个agent来做的，它的上下文是100%全新的。

- Feature Doc: `docs/features/F003-group-session-chain/feature.md`
- Design: `docs/features/F003-group-session-chain/evidence/orchestration-design.md`
- Plan: `docs/features/F003-group-session-chain/plan.md`
- Second review: `docs/features/F003-group-session-chain/evidence/review-e4dc7d2.md`
- Dispositions: `docs/features/F003-group-session-chain/evidence/review-fixes-e2c79de.md`
- Fresh Quality Gate: `docs/features/F003-group-session-chain/evidence/quality-report-e2c79de.md`

## Required closure checks

1. Call `read_invocation` for an invocation longer than 100 events, consume its
   returned `next_seq`, and verify the second page continues within the same
   invocation to a null cursor without crossing the next user turn.
2. Verify one fallback generation displays fallback live and after API reload,
   then a later fresh-summary rotation resets it live and after reload.
3. Verify `summary_degraded` is derived from the active generation's durable
   predecessor provenance, crosses Pydantic/OpenAPI/toGroup, and is also present
   on `successor_created` for missed-intermediate-event recovery.
4. Reconfirm no regression in the previously closed P1/P2 security and
   transaction findings.

## AC and fresh evidence

- AC-7: continuation test reads the 108-event invocation in two bounded pages.
- AC-10: DB/model, generated contract, WebSocket/store and badge tests cover
  durable per-generation degraded health.
- Full gate: 128 backend tests with 1 conditional skip; 32 frontend tests;
  typecheck/build; feature/skill/mirror validators; generated contract; clean
  base-to-HEAD diff check.
- Lint remains the exact main baseline of 19 errors and 5 warnings.

## Known risks

No paid/live provider summarizer was run. Codex and Claude one-shot safety is
argv-contract tested and failures use deterministic fallback. The intended
reference deviations remain normalized SQLite transcript truth and handoff-only
phase 1 rather than provider-private transcript copies or fake compression.

## Required verdict

Report P1/P2/P3 findings first with evidence, tight locations and impact, then
residual risks, exact reviewed HEAD, and exactly one of `approved`,
`request_changes`, or `blocked`. Do not approve another SHA.
