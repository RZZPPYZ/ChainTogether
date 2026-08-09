# F002 TDD Evidence — Vision handoff correction

## RED

Added a real Review owner-preparation journey in
`tests/test_feature_dispatch_runtime.py`. Owner used dispatch-bound
`request_review`, returned a final `@Reviewer` paragraph, and the test required
exactly one Owner turn before a fresh Reviewer successor.

Command:

```text
F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe -m unittest tests.test_feature_dispatch_runtime.FeatureDispatchRuntimeTests.test_request_review_mention_waits_for_fresh_successor -v
```

Observed failure: `AssertionError: 1 != 2` for `len(owner_turns)`. The second
turn was the premature Reviewer routed inside the predecessor without Feature
authority.

## GREEN

- Feature dispatch replies now bypass ordinary A2A analysis, remedial routing,
  and mention dispatch. Ordinary group invocations retain existing behavior.
- D14 declares successful Feature MCP mutation the exclusive lifecycle handoff
  and instructs the Agent to end without an `@handle`.
- L0 documents the matching Active Feature Workflow exception.
- The journey proves Reviewer starts only through the formal fresh successor,
  in another depth-zero invocation, with its exact dispatch ID and capability.
- Table-driven GroupManager coverage verifies predecessor mention suppression
  for review-to-owner, merge-to-guardian, and acceptance-to-owner.

Focused results:

```text
tests.test_feature_dispatch_runtime: 8 passed
tests.test_prompt_governance + tests.test_group_routing: 13 passed
```

The full Quality Gate remains required before independent Review.

## Instruction-contract follow-up

After the runtime correction received its first independent approval, a
canonical instruction mismatch was identified: `$request-review` still told
every group owner to emit a final `@Reviewer`, even for an autonomous FeatureRun.

RED added
`test_autonomous_review_uses_feature_control_plane_handoff`; it failed because
the canonical Skill did not name Feature MCP `request_review`, the fresh
successor, the no-`@handle` completion rule, or the no-A2A fallback rule.

GREEN updates the canonical Skill description, procedure, and Next step to
choose exactly one handoff mechanism. Autonomous runs use Feature MCP and end
naturally; manual/non-Feature group tasks retain the short `@Reviewer` route.
All 26 provider mounts were regenerated from the canonical source and checked.
