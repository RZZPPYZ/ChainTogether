# F002 Independent Review Findings

- Reviewer: independent `review-feature` agent `/root/f002_independent_review`
- Base SHA: `3ea65be7a99ef19e3271ab235ef3921d0666e454`
- Reviewed HEAD: `848d2a7d4cad91aaff764bf49e8d8a277ae596fa`
- Verdict: **request_changes**
- Review mode: read-only; the reviewer did not edit, stage, or commit files

## Findings

1. **P1 — Session-only transition bypass.** The legacy Session transition API
   advanced an autonomous run without exact dispatch authority, leaving the
   original dispatch pending and creating no atomic successor.
2. **P1 — doc_pending launch.** Start called the runtime even when create-only
   Feature Doc delivery failed, allowing Discovery without its canonical doc.
3. **P1 — unauthorized startup adoption.** Startup reconciliation iterated all
   unfinished FeatureRuns and could create/launch recovery work for historical
   manually-created runs that had no `/feature` checkpoint or AC-14 authority.
4. **P2 — wrong Review recovery actor.** A failed owner review-packet turn was
   recovered to reviewer based only on `stage=review`, skipping
   `request_review`.
5. **P2 — stale role-update revision.** Pending/waiting dispatch targets were
   patched after a role update, but `observed_revision` remained stale and the
   new actor's mutation was guaranteed to fail.
6. **P2 — unstable frontend request key.** A lost response followed by exact
   draft retry generated a new key and hit active-run conflict instead of the
   server's idempotent checkpoint.
7. **P3 — malformed roles fallback.** An incomplete `/feature roles ...`
   control fell through to autonomous start.

The reviewer independently reproduced the first five backend failures with
temporary databases and the frontend retry/parser failures from source and
tests. It also inspected secret handling, fresh depth-zero invocation custody,
terminal callbacks, actor boundaries, and mandatory MCP child-env injection;
no raw dispatch secret persistence was found.

## Required disposition

All seven findings are valid code defects plus test gaps. Fix through
Red-Green regression tests, refresh Quality evidence, and return a new exact
HEAD to the same reviewer. The old verdict cannot authorize merge.
