# F001 third independent review packet

- Feature: F001 Group Feature Lifecycle
- Branch: `codex/group-feature-lifecycle`
- Base SHA: `13253f3`
- Previous reviewed HEAD: `2e913544faa2f931a6fc2c9f024d53325a08962e`
- Corrected HEAD: `de1502c6d83e7cf2616424ea0d809d50453012dd`
- Reviewer: the same independent `f001_reviewer`
- Requested verdict: `approved`, `request_changes`, or `blocked`, bound to the
  corrected exact HEAD

This packet remains uncommitted so it does not move the reviewed HEAD.

## Dispositions since `2e91354`

1. Pending-document supersession now builds from the newest outbox image and
   preserves its original disk baseline hash. A failed role delivery followed
   by a stage mutation delivers Reviewer, Guardian, and stage together.
2. A manual edit that matches neither the outbox baseline nor desired image
   blocks later mutation and delivery; the edit and pending recovery record are
   preserved.
3. Every live Session has a random, ephemeral, unlisted capability. The harness
   injects it only into that Session's MCP environment. The transition route
   requires the matching capability header plus the shared bearer, so a caller
   cannot reuse another listed Session ID with its own capability.
4. Protected revisions resolve through Git and fail closed when revision or
   current HEAD cannot be verified. Review Base SHA must resolve and be an
   ancestor of the exact Reviewed HEAD.
5. Tests use real temporary Git repositories. Added outbox supersession,
   operator-conflict, cross-session capability, non-Git fail-closed, and legacy
   outbox-migration regression cases.

Full dispositions: `evidence/review-response-2e91354.md`.

## Review focus

- Probe failed delivery followed by later mutations and manual Feature Doc
  changes. Confirm no pending image is silently lost or overwritten.
- Verify Session capability generation, non-disclosure, harness injection,
  route enforcement, and binding to the URL Session.
- Probe invalid, short, stale, non-commit, non-Git, and non-ancestor revisions.
- Check SQLite migration compatibility, generated OpenAPI header contract, and
  documentation truth.
- Recheck the complete tree `13253f3..de1502c`, not only the latest commit.

Do not edit the reviewed branch. Findings must include severity and tight
file/line evidence. Approval must name the exact corrected HEAD.

## Fresh Quality Gate

- Python compile: passed.
- Python unit tests: 55 passed; 1 environment-gated live GitHub smoke skipped.
- Frontend Vitest: 8 files, 19 tests passed.
- TypeScript typecheck: passed.
- Vite production build: passed; existing chunk-size warning only.
- Skill validation: 13 Skills, 10 stages, 16 transitions passed.
- Provider sync: 26 mounts passed.
- Feature validation: passed.
- ESLint: unchanged repository baseline, 20 errors and 5 warnings in existing
  frontend files outside the F001 implementation diff.
