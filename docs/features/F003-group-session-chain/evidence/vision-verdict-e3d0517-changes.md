# F003 Vision Gate — Changes Required at e3d0517

- Guardian: independent `/root/f003_vision_guardian`
- Author: `/root`
- Code reviewer: `f003_independent_review`
- Merged revision: `e3d05178d768e01728e98bc6b9aa4c713bc7afb7`
- Verdict: **changes_required**

## Journey evidence

The guardian independently verified the intended primary journey: context
warning/action projection, `active -> sealing -> sealed`, fresh tool-free
summary and successor, deterministic fallback, one-time D15 bootstrap,
capability-bound Session Chain recall, and generation/lifecycle UI including
reload. Focused backend 27 tests and frontend 17 tests passed.

## Blocking deviation

A sealed predecessor remains in the ordinary Archived Sessions surface and can
be unarchived. The unarchive endpoint does not reject
`group_session_generations.status='sealed'`; once restored to the live session
manager, a normal message can append to its transcript. The guardian reproduced
`messages_before: 2`, `messages_after: 3`, and `live_again: true` on a sealed
generation.

This violates the operator's sealed-handoff expectation and AC-4 transcript
immutability. It is an implementation gap, not a Discovery decision.

## Required delivery fix

- Reject ordinary unarchive for sealed group predecessors.
- Hide sealed predecessors from the ordinary Archived Sessions recovery entry.
- Add a sealed-state guard at message-write/turn entry as defense in depth.
- Add backend and frontend regressions proving the predecessor cannot be
  revived or modified.

Route to `$worktree` then `$tdd`; after Quality Gate, repeat independent review,
merge and Vision Gate against the corrected merged revision.
