# F003 Independent Review Packet

- Feature: F003 — Group Session Chain Handoff
- Author: codex
- Requested reviewer: independent reviewer (must not edit the reviewed branch)
- Branch: `codex/F003-group-session-chain`
- Worktree: `F:\RZP_program\my_project\ChainTogether\.worktrees\F003-group-session-chain`
- Base SHA: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- Head SHA: `4db1084683db7afc93ef373abac97fb903d5cd2c`
- Diff: `git diff 1fb75b26370a2301c94f409d1d817c587d172cb3..4db1084683db7afc93ef373abac97fb903d5cd2c`

The packet is committed after the immutable review target; review the exact
base/head range above, not a moving branch name.

## Operator intent

> 当前我们的group中不存在session封顶交接的动作……提前预测当要满的时候，进行sealed封装，以及提供MCP工具，供新的session去查，而且新的session也会附带旧的session的总结信息，这个总结是通过调用另外一个agent来做的，它的上下文是100%全新的。

Source: current Codex conversation and Cat Cafe tutorial Lesson 08.

## Review inputs

- Canonical spec: `docs/features/F003-group-session-chain/feature.md`
- Design decisions/state invariants:
  `docs/features/F003-group-session-chain/evidence/orchestration-design.md`
- Approved plan: `docs/features/F003-group-session-chain/plan.md`
- TDD record: `docs/features/F003-group-session-chain/evidence/tdd-implementation.md`
- Quality report and AC matrix:
  `docs/features/F003-group-session-chain/evidence/quality-report.md`

## Delivered scope

- ordered durable generation state, append-only lifecycle events and one-active
  uniqueness/CAS;
- current/projected context policy with warning/action/reserve configuration;
- fresh tool-free, non-resuming handoff summarizer plus deterministic fallback;
- capped, data-marked, one-time D15 bootstrap;
- capability- and chain-bound read-only Session Chain REST/MCP;
- pre/post group-turn rotation, restart recovery and all-generation cleanup;
- generation/chain length in group API, WebSocket/store and group member header.

## Intentional deviations from the reference

- Existing normalized SQLite `messages` remain the canonical full transcript;
  no duplicate provider JSONL is introduced.
- Phase 1 ships only proactive `handoff`, not a fake `compress`/`hybrid` mode
  without a real provider hook.
- Summary generation is an isolated `Harness.run_oneshot` using the same model
  configuration, not an administratively managed organization-wide agent.

## Evidence already run

- Backend: 119 passed, 1 conditional skip.
- Frontend: 30 passed; TypeScript typecheck passed.
- Production build: passed, 6,987 modules; existing large-chunk advisory.
- Feature validator: 3 features passed.
- Skill validator: 13 skills / 10 stages / 16 transitions passed.
- Skill mirror check: 26 mounts passed after worktree-local bootstrap.
- `git diff --check`: passed.
- Lint: same pre-existing main baseline, 19 errors / 5 warnings; no F003
  expression introduced among findings. See Quality Report.

## Review focus and known risks

1. Prove concurrent or restart paths cannot produce two active successors or
   strand the group pointer/cursor.
2. Look for a turn that can still enter the sealed predecessor after CAS.
3. Attack REST/MCP authorization across group, member, active-peer and unknown
   session boundaries.
4. Verify transcript/digest content cannot escape the untrusted bootstrap data
   boundary or leak resume/tool authority into the summary call.
5. Verify FeatureRun and A2A behavior remains ordered when rotation happens
   post-result.
6. Check cleanup covers every generation and UI events do not select an
   intermediate/sealed session.
7. Provider telemetry may be absent/estimated; intended behavior is visible
   fail-open. No paid live-provider smoke turn was run.

## Required verdict format

Report findings first, ordered P1/P2/P3. Every finding must include evidence,
a tight file/line location and user/runtime impact. Then state residual risks,
the exact reviewed HEAD, and exactly one verdict:

- `approved`
- `request_changes`
- `blocked`

Do not modify the reviewed branch and do not approve any SHA other than
`4db1084683db7afc93ef373abac97fb903d5cd2c`.
