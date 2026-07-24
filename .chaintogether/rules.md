# Group Pre-Send Exit Check

Immediately before sending every group reply, pause and perform this check
silently. Do not include the checklist or its answers in the visible reply.

First ask: **Does the workflow truly end with me?**

- If yes, and no teammate needs action or awareness, finish naturally
  without `@`.
- If no, identify who should receive the next route and apply Q1/Q2/Q3.

Q1: Does the other agent need to take action?
- Yes: directly `@AgentName` with a concrete next action. Stop the decision
  flow and skip Q2/Q3.
- No: continue to Q2.

Q2: Does the other agent need to know this information?
- Yes: `@AgentName` with a concise awareness note and why it matters. Stop the
  decision flow.
- No: continue to Q3.

Q3: Will this affect the other agent's work?
- Yes: `@AgentName` with the expected impact and concrete follow-up.
- No: do not use `@` for that agent.

If Q1, Q2, and Q3 are all No, do not use `@`. Refer to teammates by plain name
without `@` when mentioning them conversationally. Every visible `@` is an
executable route, not decoration.
