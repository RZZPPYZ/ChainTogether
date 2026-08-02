# Review response for `89b070f`

## Review identity

- Feature: F001 Group Feature Lifecycle
- Base SHA: `13253f3`
- Reviewed HEAD: `89b070fe5b3dcc587fd62d1a16949034d8f658f2`
- Reviewer: `f001_reviewer` (independent from author)
- Verdict: `request_changes`

## Finding dispositions

### P1: competing transitions were not linearized

Reproduced with two concurrent Quality transitions. Before the fix both calls
succeeded. The transition path now compares the observed stage and
`updated_at` inside a single write lock and database transaction; one caller
wins and the stale caller receives HTTP 409. The same compare-and-swap contract
also protects role updates.

### P1: database state could advance before the Feature Doc write

Reproduced by removing a required Feature Doc field and by forcing document
delivery to fail. Document preflight now rejects invalid dossiers before the
transaction. An accepted mutation commits the FeatureRun row, immutable event,
and a durable `feature_doc_syncs` outbox item together. Document replacement is
atomic, successful delivery completes the outbox item, and startup reconciliation
retries pending delivery without replaying the transition.

### P1: evidence, actor identity, and protected-gate provenance were forgeable

Reproduced with a missing evidence path and incomplete review provenance. The
public endpoint now derives the actor from the group-agent session binding and
forbids an `actor_agent_id` request field. Repository evidence must resolve
inside the workspace and exist. Review and Vision transitions require the
assigned independent role, structured Feature Doc fields, and the exact Git
revision supplied to the transition; review requires Reviewer/Base SHA/Reviewed
HEAD/Verdict, while acceptance requires Guardian/Merged revision/Journey
evidence/Verdict.

## Red-green evidence

- RED: concurrent transitions produced zero stale writers instead of one.
- RED: a document preflight failure still advanced persisted stage.
- RED: a missing evidence reference was accepted.
- RED: the transition request lacked revision and session-bound actor behavior.
- GREEN: the focused feature workflow suite passes all seven cases, including
  outbox recovery after a simulated filesystem delivery failure.

The corrected revision must receive a fresh Quality Gate and be returned to the
same reviewer. Approval of `89b070f` is not implied by these dispositions.
