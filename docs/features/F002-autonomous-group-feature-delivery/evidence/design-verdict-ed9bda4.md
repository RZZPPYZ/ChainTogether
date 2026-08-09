# F002 independent Design Gate verdict

- Reviewer: `f001_vision_guardian`
- Feature Doc revision: `ed9bda4072ebfdb633f9973545530a6c6aff6f8a`
- Verdict: `approved`
- Next step: `writing-plans`

## Approval evidence

- FeatureDispatch delivers exact-revision successors but never advances the
  F001 lifecycle state machine.
- One invocation-bearing predecessor and one waiting/pending successor form a
  valid handoff pair with separate uniqueness constraints.
- Exact predecessor terminal CAS promotes the successor; late callbacks cannot
  mutate the new generation.
- Session capability establishes Agent/group identity and a per-dispatch,
  single-use capability establishes exact invocation-generation mutation
  authority. Consumption and handoff commit are atomic.
- Atomic start, create-only doc outbox, request-key idempotency, role matrix,
  deterministic membership order, role correction, restart recovery, mandatory
  core MCP, adversarial cases, and policy-bounded merge authorization remain
  complete.

## Planning clarifications

- `closure -> done` consumes the active dispatch authority and commits terminal
  FeatureRun truth but creates no successor.
- Read-only status requires Session capability and group/run ownership;
  mutation additionally requires dispatch capability.
- A recovered lease rotates the dispatch capability after CAS so a lost or old
  raw token cannot regain authority.
