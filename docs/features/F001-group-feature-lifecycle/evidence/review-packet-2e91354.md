# F001 independent re-review packet

- Feature: F001 Group Feature Lifecycle
- Branch: `codex/group-feature-lifecycle`
- Base SHA: `13253f3`
- Previous reviewed HEAD: `89b070fe5b3dcc587fd62d1a16949034d8f658f2`
- Corrected HEAD: `2e913544faa2f931a6fc2c9f024d53325a08962e`
- Reviewer: the same independent `f001_reviewer`
- Requested verdict: `approved`, `request_changes`, or `blocked`, bound to the
  corrected exact HEAD

This packet is intentionally uncommitted so creating it cannot invalidate the
corrected HEAD it identifies.

## Previous findings and dispositions

1. Competing stage transitions both succeeded. The database now performs a
   stage and `updated_at` compare-and-swap under a feature write lock, and
   commits exactly one transition event.
2. Database state could advance before the canonical Feature Doc write. A
   preflighted document image now commits in the same transaction through a
   durable outbox; atomic file replacement and startup reconciliation recover
   failed delivery without replay.
3. Protected gates accepted caller-supplied actor identity, missing evidence,
   and incomplete provenance. The public request no longer accepts an Agent ID;
   the control plane resolves the bound group-agent session. Local evidence
   must exist inside the workspace, and Review/Vision gates require structured
   independent-role fields plus an exact Git revision.

Durable finding-by-finding evidence is in `evidence/review-response-89b070f.md`.

## Re-review scope

Review the complete corrected tree `13253f3..2e91354`, with particular focus on
`89b070f..2e91354`:

- SQLite migration and transaction behavior in `server/database.py`.
- CAS conflict semantics and outbox delivery/reconciliation in
  `server/feature_manager.py`.
- Session-derived public transition route and request-model contract.
- Evidence path containment, exact-revision checks, and structured Reviewer and
  Guardian provenance.
- Regression tests, documentation truth, and generated OpenAPI types.

Do not edit the reviewed branch. Findings must include severity and tight
file/line evidence. Approval must name the corrected exact HEAD.

## Fresh Quality Gate

- Python compile: passed.
- Python unit tests: 50 passed; 1 environment-gated live GitHub smoke skipped.
- Frontend Vitest: 8 files, 19 tests passed.
- TypeScript typecheck: passed.
- Vite production build: passed; existing chunk-size warning only.
- Skill validation: 13 Skills, 10 stages, 16 transitions passed.
- Provider sync: 26 mounts passed.
- Feature validation: passed.
- ESLint: unchanged repository baseline, 20 errors and 5 warnings in existing
  frontend files outside the F001 implementation diff.

## Residual questions to decide explicitly

- Is the session-bound control-plane identity adequate for the repository's
  documented shared-token trust boundary and MCP model, where the harness—not
  the model—injects `OCTOPUS_SESSION_ID`?
- Can a failed or delayed Feature Doc delivery overwrite a newer mutation? The
  outbox is one row per FeatureRun and completion is revision-bound.
- Can a short, stale, dirty, or mismatched Git revision cross Review, Merge, or
  Vision gates?
