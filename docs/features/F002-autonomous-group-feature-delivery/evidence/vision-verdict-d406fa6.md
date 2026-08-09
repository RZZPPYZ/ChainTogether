# F002 Corrective Vision Gate — merged revision `d406fa6`

- Guardian: independent `/root/f002_vision_guardian`
- Author: `codex`
- Code reviewer: independent `/root/f002_independent_review`
- Bound merged runtime revision: `d406fa6f0bc19d986b7c323ba32303b130b5889c`
- Current main during validation: `50b4229` (merge/review documentation only;
  runtime identical to the bound merge revision)
- Date: 2026-08-09
- Verdict: **accepted**

## Original failed journey replay

The guardian repeated the exact Review owner-preparation path that rejected the
first merge:

- predecessor collected Owner exactly once;
- Owner's visible final `@Reviewer` text did not enter ordinary A2A;
- formal Reviewer collected exactly once;
- Reviewer used a different invocation at depth zero;
- Reviewer received the exact successor dispatch ID and new one-time dispatch
  capability;
- there was no duplicate Reviewer message or unprivileged Reviewer turn.

Observed message probe:

```text
Owner    × 1  "@Reviewer..."
Reviewer × 1  "Review started with exact authority."
```

Review-to-owner, merge-to-guardian, and acceptance-to-owner also prevented
predecessor mention routing and delegated only through Feature MCP successors.

## Instruction and product evidence

- Canonical `.chaintogether`, Codex `.codex`, and Claude `.claude`
  `$request-review` content had identical SHA-256 hashes.
- Autonomous FeatureRun instructions use Feature MCP `request_review`, end
  without `@handle`, and never fall back to A2A on success or failure. Manual or
  non-Feature tasks retain short `@Reviewer` routing.
- Feature dispatch runtime: 8/8 passed.
- Lifecycle, D14/L0, ordinary A2A, and Skill contract: 20/20 passed.
- Group `/feature` command/UI: 14/14 passed.
- Start/status/resume/roles, mandatory MCP, and fail-closed checks: 24/24 passed.
- Insufficient roles, unavailable backend, invalid capability, undelivered doc,
  replay, and recovery paths remained fail closed.
- The full Discovery through Closure test retained fresh depth-zero generations.

## Deviations and residual risks

No product deviation requires rework. Deterministic mocked Agent replies remain
the automated provider boundary rather than a manual browser plus real
Claude/Codex CLI session. If an Agent omits its MCP mutation, the product exposes
a blocker and requires `/feature status` or `/feature resume`; it does not claim
false progress. This is the approved recovery behavior.

F002 is accepted for closure.
