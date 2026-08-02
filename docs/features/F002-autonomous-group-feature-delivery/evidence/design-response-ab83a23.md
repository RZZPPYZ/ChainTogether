# F002 Design Gate response for `ab83a23`

- Reviewed Feature Doc revision: `ab83a23244f56ce7ca302ea7e942e9e15faec05a`
- Independent reviewer: `f001_vision_guardian`
- Verdict: `changes_required`
- Next step taken: returned to `feature-discovery`

## Dispositions

The accepted start, recovery, role, MCP, and authorization designs remain.
Dispatch handoff is revised as follows:

1. A state-changing Agent action atomically changes its predecessor dispatch
   from `active` to `handoff_committed` and inserts one revision-bound successor
   in `waiting`. The two may coexist intentionally. Terminal predecessor
   callback completes only that predecessor, then promotes its successor from
   `waiting` to `pending`.
2. Constraints are split: at most one invocation-bearing dispatch
   (`leased|active|handoff_committed`) and at most one unlaunched successor
   (`waiting|pending`) may exist for a run. Exact revision/purpose/generation is
   unique independently.
3. Every dispatch has a random one-time capability whose hash is stored. The
   raw value is injected by the server into only that GroupInvocation's harness
   turn and inherited by Feature MCP. Mutating MCP calls require Session
   capability plus dispatch capability. They consume the dispatch capability
   in the same transaction as transition/request-review and successor insert.
4. A reused Agent Session therefore proves Agent identity while the dispatch
   capability proves the exact current invocation generation. Old turns,
   replayed requests, and a second transition after handoff receive 409/403.

State tables, invariants, and adversarial cases are updated in
`orchestration-design.md`.
