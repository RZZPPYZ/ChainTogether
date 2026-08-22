# F003 Independent Re-review Packet

- Feature: F003 — Group Session Chain Handoff
- Author: codex
- Requested reviewer: the same independent `f003_independent_review` Agent
- Branch: `codex/F003-group-session-chain`
- Worktree: `F:\RZP_program\my_project\ChainTogether\.worktrees\F003-group-session-chain`
- Base SHA: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- Previous reviewed HEAD: `4db1084683db7afc93ef373abac97fb903d5cd2c`
- Re-review HEAD / Feature Doc revision:
  `e4dc7d2c218071273bb051746fc392cc1bc22c45`
- Full diff:
  `git diff 1fb75b26370a2301c94f409d1d817c587d172cb3..e4dc7d2c218071273bb051746fc392cc1bc22c45`
- Focused remediation diff:
  `git diff 4db1084683db7afc93ef373abac97fb903d5cd2c..e4dc7d2c218071273bb051746fc392cc1bc22c45`

This packet is committed after the immutable review target. Review the exact
base/head range, not the moving branch, and do not edit the reviewed branch.

## Operator intent

> 当前我们的group中不存在session封顶交接的动作……提前预测当要满的时候，进行sealed封装，以及提供MCP工具，供新的session去查，而且新的session也会附带旧的session的总结信息，这个总结是通过调用另外一个agent来做的，它的上下文是100%全新的。

Source: current Codex conversation and Cat Cafe tutorial Lesson 08.

## Review inputs

- Canonical spec: `docs/features/F003-group-session-chain/feature.md`
- Design/state invariants:
  `docs/features/F003-group-session-chain/evidence/orchestration-design.md`
- Approved plan: `docs/features/F003-group-session-chain/plan.md`
- Original findings: `docs/features/F003-group-session-chain/evidence/review-4db1084.md`
- Finding dispositions:
  `docs/features/F003-group-session-chain/evidence/review-fixes-9fb82fb.md`
- Fresh Quality Gate:
  `docs/features/F003-group-session-chain/evidence/quality-report-9fb82fb.md`

## Delivered scope and AC evidence

| AC area | Delivery and fresh evidence |
|---|---|
| AC-1/2 durable lifecycle | Dedicated transaction, CAS, cancellation isolation, one-active pointer and restart reconciliation tests. |
| AC-3 proactive policy | Warning/action/projection/missing-telemetry policy tests and visible lifecycle events. |
| AC-4/7 exact recall | Immutable DB transcript, caller-bound MCP, opaque path IDs, invocation grouping/continuation and bounded pages/search tests. |
| AC-5 fresh summary | Non-resuming one-shot argv with execution/write/tool surfaces disabled; deterministic fallback tests. |
| AC-6 safe bootstrap | HTML-escaped, quote-prefixed, capped D15 data and one-time consumption tests. |
| AC-8/9 routing/cleanup | Cursor and ownership preservation, stale turn rejection and all-generation cleanup regressions. |
| AC-10 observability | Durable events plus WebSocket/store/badge tests for warning through ready/fallback. |
| AC-11 verification | 127 backend tests; 31 frontend tests; typecheck/build; validators; contract regeneration; clean base-to-HEAD diff check. |

## Previous finding closure to verify

1. P1: cancellation cannot expose half a rotation through a shared SQLite
   commit; path escape is rejected before HTTP; summary subprocesses cannot
   execute or write through Codex/Claude tools.
2. P2: turn and seal share the member lock with stale-object revalidation;
   transcript/D15 delimiters cannot be escaped; recall output/query/invocation
   sizes are bounded and complete enough to continue; all lifecycle events are
   projected and rendered.
3. P3: original false-positive Quality Report is marked historical and
   superseded; `git diff --check base..head` is actually clean.

## Intentional deviations and known risks

- SQLite normalized `messages` remain the canonical full transcript rather
  than duplicating provider-private JSONL.
- Phase 1 ships proactive `handoff` only, not provider-specific compression.
- No paid/live Claude or Codex one-shot was run. Unit tests bind the safety
  flags; provider failure must take the deterministic fallback path.
- `bun run lint` remains at the unmodified-main baseline of 19 errors and 5
  warnings in the same rules/files; none is introduced by F003.

## Required verdict format

Report findings first, ordered P1/P2/P3. Each finding must include evidence, a
tight file/line location and runtime/user impact. Then state residual risks,
the exact reviewed HEAD, and exactly one verdict:

- `approved`
- `request_changes`
- `blocked`

Do not approve any SHA other than
`e4dc7d2c218071273bb051746fc392cc1bc22c45`.
