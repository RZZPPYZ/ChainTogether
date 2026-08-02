# F001 fourth independent review packet

- Feature: F001 Group Feature Lifecycle
- Branch: `codex/group-feature-lifecycle`
- Base SHA: `13253f3`
- Previous reviewed HEAD: `de1502c6d83e7cf2616424ea0d809d50453012dd`
- Corrected HEAD: `522a4faf8e40fa5076b5a5f1bbc758f4b160ea13`
- Reviewer: the same independent `f001_reviewer`
- Requested verdict: `approved`, `request_changes`, or `blocked`, bound to the
  corrected exact HEAD

This packet is uncommitted so it cannot invalidate the reviewed HEAD.

## Dispositions since `de1502c`

1. Gate validation no longer rereads the Feature Doc. The exact image prepared
   for the document outbox supplies Review/Vision fields and verdict.
2. Immediately before FeatureRun CAS, the controller rereads the canonical
   document and compares the captured baseline hash. Protected edges also
   re-resolve current Git HEAD. A verdict mutation after snapshot capture is
   rejected while the DB remains at Review.
3. Legacy outbox migration hashes the existing disk document. A regression
   starts with the old schema plus a real pending row and proves the new server
   can deliver it and clear the outbox.
4. Built-in MCP configuration contains no callback env. Sensitive callback
   values are placed in the spawned Harness process environment and inherited
   by its built-in MCP children. Connector configuration excludes the Session
   capability. Rendered Claude Code and Codex argv are both tested not to
   contain the raw value.

Full dispositions: `evidence/review-response-de1502c.md`.

## Active review probes

- Repeat the exact approved-to-pending mutation between snapshot and commit;
  also attempt a Git HEAD change before CAS.
- Upgrade an old schema containing a pending row and verify actual delivery,
  not only column shape.
- Render both provider invocations and search all argv/MCP config fields for
  the Session capability; verify mismatched capability/Session remains 403.
- Recheck chained outbox, manual edit conflict, concurrent transition CAS, and
  the complete tree `13253f3..522a4fa`.

Do not edit the reviewed branch. Findings must include severity and tight
file/line evidence. Approval must name the exact corrected HEAD.

## Fresh Quality Gate

- Python compile: passed.
- Python unit tests: 56 passed; 1 environment-gated live GitHub smoke skipped.
- Frontend Vitest: 8 files, 19 tests passed.
- TypeScript typecheck: passed.
- Vite production build: passed; existing chunk-size warning only.
- Skill validation: 13 Skills, 10 stages, 16 transitions passed.
- Provider sync: 26 mounts passed.
- Feature validation and `git diff --check`: passed.
- ESLint remains the unchanged repository baseline of 20 errors and 5 warnings
  in existing frontend files outside the F001 implementation diff.
