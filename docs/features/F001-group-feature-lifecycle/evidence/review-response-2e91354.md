# Review response for `2e91354`

## Review identity

- Feature: F001 Group Feature Lifecycle
- Base SHA: `13253f3`
- Reviewed HEAD: `2e913544faa2f931a6fc2c9f024d53325a08962e`
- Reviewer: `f001_reviewer` (same independent reviewer)
- Verdict: `request_changes`

## Finding dispositions

### P1: a later mutation could supersede an undelivered document image

The Reviewer reproduced a failed role-document delivery followed by a stage
transition. The later image was built from stale disk content and permanently
lost Reviewer/Guardian fields. Document preparation now starts from the newest
pending outbox image when present. The outbox retains the hash of the disk
baseline that image supersedes, so a later mutation preserves all prior fields.
A regression test covers failed role delivery followed by a successful stage
mutation.

### P2: delayed delivery could overwrite an operator's manual document edit

Preparation and delivery compare the current canonical document with both the
pending image and its baseline hash. A third state means an external edit
occurred: the next Feature mutation is rejected, delivery stays pending, and
the operator's content is preserved for explicit conflict resolution.

### P2: session identity remained selectable under the shared bearer

Every live Session now owns a random, ephemeral capability that is omitted from
all Session response models. The harness injects it only into that Session's MCP
subprocess environment as `OCTOPUS_SESSION_CAPABILITY`. The transition route
requires the matching `X-Octopus-Session-Capability` header in addition to the
application bearer and rejects a capability copied from another Session. The
control plane then resolves the Agent from the capability-bound Session.

### P2: protected revision verification failed open outside Git

Protected gates now resolve the supplied revision and current HEAD as Git
commits and reject the transition when either cannot be verified. Review Base
SHA must resolve to a commit and be an ancestor of the exact Reviewed HEAD.
Lifecycle tests now initialize real temporary Git repositories instead of
passing fictional revisions; an explicit non-Git probe must fail closed.

## Red-green evidence

- RED: failed role delivery followed by a stage mutation lost role fields and
  cleared the pending outbox.
- RED: `deadbee` crossed a protected gate in a non-Git workspace.
- RED: a bearer caller could select another listed Session ID.
- GREEN: pending-image chaining preserves roles and stage together.
- GREEN: manual edits block supersession and remain intact.
- GREEN: live-session capabilities are distinct, unlisted, environment-injected,
  and rejected when paired with another Session ID.
- GREEN: real Git revisions pass, while unverifiable revisions fail closed;
  legacy outbox schema migration adds the baseline-hash column.

The next corrected revision requires a fresh Quality Gate and another review by
the same independent reviewer. Approval of `2e91354` is not implied.
