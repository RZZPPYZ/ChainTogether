# F003 Review-Fix Dispositions — 9fb82fb

- Original review: `review-4db1084.md`
- Original reviewed HEAD: `4db1084683db7afc93ef373abac97fb903d5cd2c`
- Fix checkpoint: `9fb82fbaa2f251a25ff3f6cb7d6fc47d2bf18a2a`
- Author disposition: all findings accepted and fixed; independent re-review
  remains required.

## Finding-by-finding disposition

| Finding | Disposition | Fix and evidence |
|---|---|---|
| P1.1 shared SQLite transaction | fixed | Rotation now uses a dedicated `aiosqlite` connection with `BEGIN IMMEDIATE`, commit/rollback across the complete state change, and `BaseException` rollback for cancellation. `test_cancelled_rotation_cannot_be_partially_committed_by_another_writer` reproduces the old partial commit and proves the pointer, predecessor, successor and reconciliation state remain consistent. |
| P1.2 MCP path escape | fixed | MCP validates predecessor IDs as one opaque `[A-Za-z0-9_-]{1,64}` path segment before HTTP. `test_mcp_rejects_path_escape_before_making_http_request` proves an escape string never reaches HTTPX. |
| P1.3 unsafe summarizer process | fixed | Claude one-shot uses bare/safe/tool-empty/no-persistence flags; Codex uses a read-only sandbox and explicitly disables shell, unified exec, apply-patch, web, MCP, history and project-doc loading. `test_oneshot_harnesses_remove_agentic_tools_and_write_authority` binds the argv contract. |
| P2.1 turn/rotation race | fixed | Rotation shares the member `Session._lock` with turns; `send_message` rechecks active object identity after acquiring a possibly stale reference. Lock-order and stale-waiter tests prove a seal waits for an active turn and an old waiter cannot execute after rotation. |
| P2.2 delimiter injection | fixed | Transcript and D15 digest data are HTML-escaped and every line is quote-prefixed; inline identity fields are collapsed to one line. The transcript and bootstrap boundary tests include malicious closing tags and fake directives. |
| P2.3 incomplete/unbounded recall | fixed | Invocation read returns the full user-to-next-user slice, capped at 100 events with `truncated`/`next_seq`; raw/chat/handoff fields and digests are capped; search queries stop at 256 characters and return bounded snippets plus exact location metadata. MCP tests cover semantics, caps and continuations. |
| P2.4 hidden UI lifecycle | fixed | Every chain event updates the member projection. The badge renders warning, usage-unknown, sealing, summarizing, fallback, sealed, fresh and ready states while successor creation alone switches the session and clears stale usage. WebSocket/store/component tests cover the flow. |
| P3 diff hygiene / false evidence | fixed | Historical Quality Report is explicitly marked superseded. All reported trailing whitespace and blank EOF lines were removed; `git diff --check 1fb75b2..9fb82fb` is clean and the fresh report records the exact command. |

## Verification summary

See `quality-report-9fb82fb.md` for the fresh full regression, build,
validators, generated-contract check, lint-baseline comparison and residual
risk. Fixes must return to the same independent reviewer; this author does not
convert `request_changes` into approval.
