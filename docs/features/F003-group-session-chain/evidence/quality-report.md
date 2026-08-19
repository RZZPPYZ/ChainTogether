# F003 Quality Report

- Date: 2026-08-19
- Verdict: **pass**
- Base: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- Verified implementation checkpoint:
  `a66dfda7cd1ba437435734fa1f7397f34314edc7`
- Scope: group-member session generations, proactive sealing, fresh handoff,
  D15 bootstrap, Session Chain REST/MCP, restart/cleanup and group UI projection

## Acceptance evidence

| AC | Result | Evidence |
|---|---|---|
| AC-1 | pass | DB adoption/rotation tests prove ordered generations and one active pointer; API/store fields expose generation and length. |
| AC-2 | pass | Concurrent seal-claim test has one CAS winner; restart test completes a stranded `sealing` generation. |
| AC-3 | pass | Policy tests cover 85/90 defaults, projection/reserve, disabled mode and missing-health fail-open; `.env.example` documents every setting. |
| AC-4 | pass | Sealing archives the predecessor without editing `messages`; MCP tests page normalized DB events and reject active/foreign targets. |
| AC-5 | pass | Fresh-one-shot test proves no session/resume/MCP identity; failure test produces bounded deterministic fallback with error provenance. |
| AC-6 | pass | Bootstrap tests prove data marking, sanitization, cap and closing marker; runtime test proves one-time consumption after success. |
| AC-7 | pass | REST/MCP tests cover list, raw/chat/handoff paging, invocation read, search and cross-chain fail-closed capability checks. |
| AC-8 | pass | Rotation test preserves cursor, working directory, backend and ownership while successor resume ID is null; existing routing/FeatureRun regressions pass. |
| AC-9 | pass | Cleanup enumeration contains sealed and active generations; normal rotation archives the predecessor. |
| AC-10 | pass | Runtime test verifies ordered sealing/summary/sealed/successor/bootstrap broadcasts; DB events and reload UI projection are covered. |
| AC-11 | pass | Full backend/frontend suites, typecheck, build, feature/skill validators, generated contracts and diff checks pass. |

## Fresh verification

| Command | Result |
|---|---|
| `...\.venv\Scripts\python.exe -m unittest discover -s tests -q` | 119 passed, 1 existing conditional skip |
| `bun run test` | 10 files, 30 tests passed |
| `bun run typecheck` | pass (`tsc --noEmit`) |
| `bun run build` | pass; 6,987 modules transformed; existing chunk-size advisory only |
| `scripts/check-features.py` | pass, 3 features |
| `scripts/check-skills.py` | pass, 13 skills / 10 stages / 16 transitions |
| `scripts/sync-skills.py --check` | pass after generating the worktree-local ignored provider mirrors |
| `git diff --check` | pass |

## Lint baseline disposition

`bun run lint` reports 24 existing issues (19 errors, 5 warnings). Running the
same command on unmodified `main` reports the same count, rules and files. F003
only shifts line numbers in `GroupChatView.tsx` and `useWebSocket.ts`; none of
the reported expressions were introduced or changed by F003. This is recorded
as pre-existing repository debt, not waived feature-specific failure.

## Journey and residual risk

The automated runtime journey crosses the action threshold, archives generation
1, creates a no-resume generation 2, injects its digest, consumes it once and
exposes the exact predecessor through capability-bound MCP. The frontend journey
then replaces the member session and clears stale context usage.

No paid/live Claude or Codex provider smoke turn was executed. Provider context
telemetry can still be absent or estimated in production; the designed behavior
is visible fail-open (continue the current session) rather than a fabricated
threshold decision. Operators can tune the documented ratios and reserve after
observing real workloads.
