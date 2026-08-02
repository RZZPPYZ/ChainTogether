# F001 review response for `522a4fa`

- Reviewed HEAD: `522a4faf8e40fa5076b5a5f1bbc758f4b160ea13`
- Reviewer: independent `f001_reviewer`
- Verdict: `request_changes`
- Disposition: all three findings reproduced or structurally isolated, fixed,
  and returned to the same reviewer on a new exact HEAD.

## Finding dispositions

### P1: Feature Doc gate changed at the database boundary

Accepted. The previous baseline check still ran before entering the database
write critical section. A caller could replace an approved Review verdict with
`pending` after validation but before FeatureRun CAS.

The FeatureManager now supplies a synchronous precondition to the database
mutation. The database invokes it while holding the Feature write lock and
immediately before the SQL compare-and-swap. The exact Feature Doc baseline is
therefore revalidated inside the same control-plane critical section as the
state transition. A regression mutates the verdict at the database method
boundary and verifies that the run remains in Review.

### P1: protected Git HEAD changed at the database boundary

Accepted. The same boundary existed for protected-revision revalidation.

The database-bound transition precondition now re-resolves the protected Git
HEAD under the Feature write lock immediately before CAS. A regression creates
an empty commit at the database method boundary and verifies rejection with no
FeatureRun advance.

### P2: a late v1 document worker can overwrite a superseding v2 image

Accepted. The old protocol selected a pending row, released the lock, wrote the
file, and then conditionally removed the row. A later mutation could supersede
v1 with v2 while the old worker still held the v1 content.

Pending-image selection, synchronous disk delivery, and version-matched row
completion are now one database-owned operation under the same Feature write
lock used by transitions and role mutations. No pending image escapes that
critical section, so a later v2 mutation cannot be enqueued until v1 delivery
has either completed or failed without deletion. The obsolete split completion
API was removed to prevent bypassing this protocol.

## Verification

- Python compile passed.
- Full Python suite: 59 passed; 1 environment-gated live GitHub smoke skipped.
- Skill validation: 13 Skills, 10 stages, 16 transitions passed.
- Provider sync: 26 mounts passed.
- Feature validation and `git diff --check` passed.
- Frontend Vitest, TypeScript typecheck, and production build remain green;
  this correction changes only server workflow code, tests, and evidence.
