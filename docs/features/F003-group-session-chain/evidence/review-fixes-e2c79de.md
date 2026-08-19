# F003 Second Review-Fix Dispositions — e2c79de

- Review: `review-e4dc7d2.md`
- Reviewed HEAD: `e4dc7d2c218071273bb051746fc392cc1bc22c45`
- Fix checkpoint: `e2c79de74da1daee3afa4070de4413c9d89bbd87`
- Author disposition: both findings accepted and fixed; same-reviewer approval
  remains required.

## P2 — unusable invocation continuation

`read_invocation` now accepts either the invocation's user sequence or the
exact `next_seq` returned by a prior page. It walks backward to retain
`invocation_start_seq`, bounds the page to 100 events, and returns another
usable cursor until the next user turn. The regression creates a 108-event
invocation, reads events 2–101, continues at 102, reads through 109, and proves
the terminal cursor is null.

## P3 — stale/non-durable degraded state

- `sealing_started` and `summary_generated` reset the current rotation's
  degraded bit; `summary_degraded` sets it. It is no longer permanent OR state.
- `successor_created` carries an explicit `summary_degraded` value so a client
  that missed an intermediate event still receives the correct generation.
- Group reload projection derives the active generation's state from its
  predecessor's durable `digest_provenance`; `GroupMemberSessionInfo`, generated
  OpenAPI contracts and `toGroup` preserve the value.
- Badge rendering falls back to durable `chain_status`/`summary_degraded` when
  no ephemeral event type exists after reload.
- Tests cover fallback generation 2, successful generation 3 reset, API model
  round-trip and reload rendering.

See `quality-report-e2c79de.md` for fresh full-gate evidence. This author does
not convert the review verdict into approval.
