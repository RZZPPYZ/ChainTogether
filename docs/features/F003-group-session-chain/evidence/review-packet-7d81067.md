# F003 Correction Review Packet — 7d81067

## Assignment

- Author: `/root` (`codex` in Feature Doc)
- Independent reviewer: `f003_independent_review`
- Mechanism: explicit manual handoff; this Codex task is not a D14-bound autonomous FeatureRun
- Requested verdict: findings first with P1/P2/P3 severity, evidence and tight file locations, then exactly one of `approved`, `request_changes`, or `blocked`

Review only the exact target below. The later packet commit is evidence-only and
must not silently change the reviewed revision.

## Revision identity

- Base SHA: `7ba664890cad0d922bb1c34ce0668d9a43f77629`
- Head SHA: `7d81067dd17b2a58b5b67f5ac33db248569f48c0`
- Implementation HEAD within that revision: `0849d174027b85f3dff56a46a81f75d4cc191449`
- Branch: `codex/F003-sealed-immutability`
- Worktree: `F:/RZP_program/my_project/ChainTogether/.worktrees/F003-sealed-immutability`
- Feature Doc blob: `6a78f980ae8075d50482ffc6e15c312c25572c20`
- Diff: `git diff 7ba664890cad0d922bb1c34ce0668d9a43f77629..7d81067dd17b2a58b5b67f5ac33db248569f48c0`

## Original intent and correction trigger

> Operator: "当前我们的group中不存在session封顶交接的动作……提前预测当要满的时候，进行sealed封装，以及提供MCP工具，供新的session去查，而且新的session也会附带旧的session的总结信息，这个总结是通过调用另外一个agent来做的，它的上下文是100%全新的。"

The first merged feature implemented the threshold → seal → fresh summary →
fresh successor → D-layer bootstrap → MCP recall journey. Independent Vision
Gate then reproduced a blocking deviation at merged revision `e3d0517`: a
sealed predecessor could be unarchived through ordinary session management and
receive another message (`messages_before: 2`, `messages_after: 3`).

Required correction from
`evidence/vision-verdict-e3d0517-changes.md`:

1. reject ordinary unarchive for sealed group predecessors;
2. remove the ordinary recovery action or make the sealed row read-only;
3. guard message write/turn entry;
4. add backend and frontend regressions proving no revival or mutation.

## Canonical inputs

- Feature Doc: `docs/features/F003-group-session-chain/feature.md`
- Approved design: `evidence/design-verdict-2371014.md`, `evidence/orchestration-design.md`
- Plan: `docs/features/F003-group-session-chain/plan.md`
- Vision deviation: `evidence/vision-verdict-e3d0517-changes.md`
- Worktree record: `evidence/worktree-sealed-immutability.md`
- TDD evidence: `evidence/tdd-sealed-immutability.md`
- Quality Report: `evidence/quality-report-0849d17.md` — **pass**

Architecture ownership remains unchanged: Database owns generation truth and
the transcript; SessionManager owns write execution; REST exposes session
management; frontend archive management is projection only. The only intentional
UX choice is read-only visibility (`Session Chain · sealed`) instead of hiding
the row completely; the recovery action is absent and the server remains the
enforcement boundary.

## Change summary

- `Database.append_message` uses an atomic INSERT predicate that rejects
  `status='sealed'`; every SessionManager persistence path inherits it.
- `Database.unarchive_session_if_recoverable` uses an atomic conditional UPDATE
  so no check/write race can revive a sealed predecessor.
- SessionManager maps database rejection to `SealedSessionError`, advances
  message counters only after successful persistence, and checks durable state
  after the turn lock before harness execution.
- REST returns HTTP 409 with stable reason `session_sealed`.
- `SessionInfo` and generated contracts expose additive `sealed: boolean`.
- Archived Sessions shows sealed history read-only with no Unarchive; ordinary
  archives remain recoverable.
- WebSocket-created ordinary replacements initialize `sealed: false`.
- Regression fixtures now finish writing the exact transcript before sealing.

## AC and evidence focus

| AC | Review question | Evidence |
|---|---|---|
| AC-2 | Can concurrency or restart reintroduce a writable sealed generation? | conditional DB write/update predicates; rotation/runtime suite |
| AC-4 | Can any normal/internal message path mutate sealed transcript or counters? | `test_sealed_predecessor_cannot_be_unarchived_or_written` |
| AC-7 | Does exact MCP recall still work without post-seal writes? | `tests/test_session_chain_mcp.py` builds full transcript before seal, then pages/searches it |
| AC-9 | Is sealed history archived but unavailable to ordinary recovery while ordinary archives still work? | manager/route assertions and `ArchivedSessionsDialog.test.tsx` |
| AC-10 | Do API/UI projections distinguish sealed history after reload? | `sealed` contract field and archive UI test |
| AC-11 | Is the complete feature still green? | Quality Report command matrix |

Fresh Quality Gate at the reviewed tree: 130 backend tests passed (1 skipped),
52 focused backend tests passed, 34 frontend tests passed, typecheck and
production build passed, all changed hand-written frontend files pass lint,
contracts regenerate cleanly, feature/skill/mirror validators pass, and diff
check passes.

## Adversarial review requests

Please specifically inspect:

1. SQLite `cursor.rowcount` and transaction behavior for INSERT/UPDATE guards;
2. races among rotation, unarchive, stale live objects, normal turns and
   internal injection;
3. whether any message persistence path bypasses `Database.append_message`;
4. counter consistency when a write is rejected;
5. API compatibility of the required additive `sealed` field and all synthetic
   SessionInfo constructors;
6. UI behavior for sealed versus ordinary archives and reload;
7. whether the adjusted recall fixture hides a real production regression;
8. exact scope preservation for direct chat, A2A and FeatureRun.

## Known gaps and residual risks

- Repository-wide frontend lint has unrelated legacy debt (15 errors, 5
  warnings); none of its files changed, while the changed-file lint is green.
- Production bundles retain the existing >500 kB warning.
- Archived listing performs one generation lookup per archived row; this is a
  low-volume administrative surface but may merit batching later.
- No new database migration is required; the correction depends on the
  existing generation table shipped by F003.

## Reviewer output contract

Bind the report to base `7ba6648` and reviewed HEAD `7d81067`. For each finding,
provide severity, proof, and narrow file/line references. State residual risks
even if there are no findings. End with `approved`, `request_changes`, or
`blocked`. Do not edit the reviewed branch.
