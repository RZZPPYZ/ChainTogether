# F003 Independent Correction Review — 7d81067

- Reviewer: independent `f003_independent_review`
- Author: `/root`
- Base: `7ba664890cad0d922bb1c34ce0668d9a43f77629`
- Reviewed HEAD: `7d81067dd17b2a58b5b67f5ac33db248569f48c0`
- Verdict: **request_changes**

## P1 findings

None.

## P2 findings

None.

## P3 findings

1. `web/src/components/ChatView.tsx:1431-1436` — after selecting View on a
   sealed predecessor in Archived Sessions, the shared archived banner still
   says “Unarchive from the sidebar to continue the conversation.” A sealed
   row has no Unarchive control and the REST endpoint returns 409
   `session_sealed`. The real browse journey therefore advertises an impossible
   next action. Render sealed-specific Session Chain/read-only guidance and add
   a browsing-state regression.

## Residual risks recorded by reviewer

- Fresh focused backend tests: 52 passed, covering rotation, sealed write
  protection, MCP recall, group routing, prompt governance and FeatureRun.
- Fresh frontend tests: 3 passed, but they did not cover the ChatView sealed
  browsing banner above.
- The reviewer confirmed the append and unarchive barriers are single-statement
  SQLite predicates and current SessionManager message paths converge on the
  write barrier. The remaining direct message INSERT copies into a new fork and
  does not mutate the sealed source.
- Diff check passed and the reviewed worktree was clean.
- Existing archive-list N+1, repository lint debt and bundle warning remain
  residual, not findings for this correction.

## Required next step

Use `$receive-review`: reproduce the sealed browsing message, fix it with a
regression while retaining ordinary archive guidance, run focused plus frontend
regression/build evidence, and return the new exact HEAD to the same reviewer.
