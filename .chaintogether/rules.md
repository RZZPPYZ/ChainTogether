# Group @ Routing Decision Rule

Before using an `@AgentName` handoff in a group reply, apply this decision flow:

Q1: Does the other agent need to take action?
- Yes: directly `@AgentName` with a concrete next action. Skip Q2 and Q3.
- No: continue to Q2.

Q2: Does the other agent need to know this information?
- Yes: `@AgentName` with a concise awareness note and why it matters.
- No: continue to Q3.

Q3: Will this affect the other agent's work?
- Yes: `@AgentName` with the expected impact and any concrete follow-up.

If Q1, Q2, and Q3 are all No, do not use `@`.
Refer to teammates by plain name without `@` when you are only mentioning them conversationally.
