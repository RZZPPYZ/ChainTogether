# F002 Vision Gate Verdict — merged revision `918e04a`

- Feature: F002 Autonomous Group Feature Delivery
- Guardian: independent `/root/f002_vision_guardian`
- Author: `codex`
- Code reviewer: independent `/root/f002_independent_review`
- Bound merged revision: `918e04a0dfc3b46b1b3e66f9a77fec4256965790`
- Validation date: 2026-08-09
- Verdict: **changes_required**

## Passing evidence

- Backend lifecycle journey: 1/1 passed.
- Mandatory Feature MCP, Session/dispatch authority, and routing checks: 11/11
  passed.
- Group `/feature` parser, entry, status, and error recovery checks: 14/14
  passed.
- The UI uses dedicated Feature APIs, exposes three roles and blockers, keeps a
  failed requirement draft, and does not require the operator to call lifecycle
  transition APIs manually.

## Blocking journey deviation

The exact merged runtime was replayed at Review owner-preparation. Owner called
the dispatch-bound `request_review` MCP successfully, which consumed the current
dispatch and created the durable waiting Reviewer successor. Owner then emitted
the Skill-required final `@Reviewer` paragraph.

The ordinary group mention router added Reviewer to the same predecessor
GroupInvocation before it became terminal:

- Owner invocation: `947ff4a82221`, with exact dispatch authority.
- Premature Reviewer invocation: also `947ff4a82221`, with
  `feature_run_id=None`, `feature_dispatch_id=None`, and no capability.
- Only after that unprivileged turn ended did the predecessor complete and the
  formal `review_request` successor become pending with `invocation_id=None`.
- The fresh successor would therefore invoke Reviewer a second time.

This violates the single, auditable, fresh depth-zero handoff promised by AC-7.
The same routing conflict applies generically to reviewer-to-owner,
merge-to-guardian, and acceptance-to-owner lifecycle edges.

## Required correction

1. Feature dispatch invocations must not execute ordinary A2A reply mentions;
   Feature MCP plus the durable successor is their only role-handoff channel.
2. L0 and D14 must explicitly tell an Agent to end naturally after a successful
   Feature MCP mutation, without an ordinary `@handle` handoff.
3. Regression coverage must execute the real Review owner-prep path and prove
   the predecessor only runs Owner, while Reviewer runs once in a different
   depth-zero invocation with the exact successor authority.
4. Review-to-owner, merge-to-guardian, and acceptance-to-owner must receive
   table-driven routing-policy coverage.
5. The canonical operator quote must remain valid UTF-8 and preserve the
   original one-sentence autonomy request.

The Feature cannot close until a new merged revision passes Quality, independent
Review, Merge, and an independent replay of this Vision journey.
