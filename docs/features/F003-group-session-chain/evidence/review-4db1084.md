# F003 Independent Review — 4db1084

- Reviewer: independent `f003_independent_review` Agent
- Base: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- Reviewed HEAD: `4db1084683db7afc93ef373abac97fb903d5cd2c`
- Verdict: **request_changes**

## Findings

### P1

1. The multi-statement SQLite rotation used the shared connection, so an
   unrelated coroutine could commit a partially completed seal and leave the
   active pointer on a predecessor already marked sealed.
2. Session Chain MCP interpolated an unchecked predecessor session ID into an
   HTTP path, permitting `..`, query or fragment syntax to escape the intended
   recall endpoint after URL normalization.
3. The Codex summarizer's claimed tool-free process used
   `--dangerously-bypass-approvals-and-sandbox`, allowing transcript prompt
   injection to reach local execution surfaces.

### P2

1. Model turns and session rotation did not share a mutex, so a turn waiting on
   a captured predecessor object could execute after that object was rotated
   out of the active chain.
2. D15/transcript sanitization allowed delimiter text such as
   `</handoff_digest>` to escape the untrusted-data boundary.
3. Recall responses were incomplete or unbounded: invocation read returned a
   single row, search accepted an unbounded query and returned full content,
   and large recall fields had no response cap.
4. The frontend applied only `successor_created`, hiding warning, seal,
   degraded-summary and bootstrap lifecycle state from the group UI.

### P3

1. The base-to-HEAD diff contained trailing whitespace and extra blank lines at
   EOF even though the Quality Report recorded the diff check as passing.

## Required return path

Reproduce each issue, fix it with tests, run a fresh Quality Gate, and return a
new exact HEAD to the same reviewer. This document preserves the original
verdict; later evidence must not rewrite it as approval.
