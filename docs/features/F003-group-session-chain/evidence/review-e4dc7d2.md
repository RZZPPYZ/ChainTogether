# F003 Independent Re-review — e4dc7d2

- Reviewer: same independent `f003_independent_review` Agent
- Base: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- Reviewed HEAD: `e4dc7d2c218071273bb051746fc392cc1bc22c45`
- Verdict: **request_changes**

## Findings

### P1

No findings. The prior transaction-isolation, MCP path-escape and summarizer
write/execute-authority findings were confirmed closed.

### P2

1. Invocation pages returned `next_seq`, but the next request rejected that
   cursor because only a user-role starting sequence was accepted. Invocations
   over 100 events therefore could not be completely recalled.

### P3

1. Frontend `summaryDegraded` used permanent OR accumulation. Once a fallback
   occurred, later generations with successful summaries still displayed
   fallback; after reload, the non-persisted field instead disappeared.

## Residual risks recorded by reviewer

- Focused backend and frontend checks passed except for the two independently
  reproduced gaps above.
- Codex one-shot remains argv-contract tested because this environment could
  not launch a live Codex CLI summarizer.
- Claude safe flags exist, but `--bare` compatibility across all OAuth
  credential forms has not been live-tested; failure uses deterministic
  fallback.

The same reviewer must verify the next exact remediation HEAD.
