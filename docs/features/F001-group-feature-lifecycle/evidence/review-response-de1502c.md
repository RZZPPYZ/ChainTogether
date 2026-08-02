# Review response for `de1502c`

## Review identity

- Feature: F001 Group Feature Lifecycle
- Base SHA: `13253f3`
- Reviewed HEAD: `de1502c6d83e7cf2616424ea0d809d50453012dd`
- Reviewer: `f001_reviewer` (same independent reviewer)
- Verdict: `request_changes`

## Finding dispositions

### P1: gate verification and document mutation used different snapshots

The Reviewer changed Review Verdict from `approved` to `pending` between the
gate read and the later document-preparation read and reproduced DB stage
`merge` with a pending canonical verdict. Transition preparation now reads one
document snapshot, applies the target frontmatter to that image, and passes the
same image to gate validation. Immediately before the database CAS it rereads
the canonical file and compares the exact baseline hash; protected edges also
recheck Git HEAD. A regression probe mutates the verdict after snapshot capture
and verifies the transition remains at Review.

### P2: legacy pending outbox rows migrated into permanent conflict

When adding `base_hash`, migration now reads each legacy row's existing disk
document and records its SHA-256 baseline. The migration regression test starts
from the previous schema with a real pending image, initializes the new
database, delivers the pending content, and verifies both the file and outbox
completion rather than only checking column presence.

### P2: Session capability appeared in provider CLI arguments

Built-in MCP entries no longer carry callback values in their rendered MCP
configuration. The parent Harness process receives callback values in its OS
environment, and built-in MCP subprocesses inherit them. Connector entries do
not receive the Session capability. Regression checks render both Claude Code
and Codex argv, assert the capability is absent, and verify it remains present
in the spawn environment for the correct Session.

## Red-green evidence

- RED: an approved Review snapshot followed by a second pending read advanced
  the DB to Merge.
- RED: a migrated pending row had `base_hash=''` and could not deliver.
- RED: Claude and Codex MCP configuration argv contained the raw capability.
- GREEN: the same queued snapshot drives gate validation and document output;
  a changed baseline fails before FeatureRun mutation.
- GREEN: real legacy pending content migrates and reconciles successfully.
- GREEN: neither provider argv contains the capability; the per-Session Harness
  spawn environment still does.

The next corrected exact HEAD requires the same independent reviewer. Approval
of `de1502c` is not implied.
