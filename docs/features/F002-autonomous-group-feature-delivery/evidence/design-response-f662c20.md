# F002 Design Gate response for `f662c20`

- Reviewed Feature Doc revision: `f662c20c703f186410386fd96b5a905cdfeb3b32`
- Independent reviewer: `f001_vision_guardian`
- Verdict: `changes_required`
- Next step taken: returned to `feature-discovery`

## Dispositions

1. The existing single GroupInvocation custody chain is no longer treated as
   the whole delivery orchestrator. A durable FeatureDispatch creates a fresh,
   depth-zero successor invocation for each stage entry or explicit Review
   request. F001 FeatureRun remains the only lifecycle state machine.
2. Start is specified as a database checkpoint transaction containing request
   idempotency, complete roles, FeatureRun/event, active pointer, create-only
   document outbox image, and initial dispatch. Filesystem delivery and launch
   are recoverable post-commit steps.
3. Concurrent start/resume/transition are serialized with database claims,
   revision-bound dispatch keys, leases, and one active dispatch per run.
4. Restart recovery recomputes actor from current FeatureRun stage and roles,
   supersedes stale dispatches, treats dead invocations as retryable, and never
   reuses old `current_agent_id` as authority.
5. Live membership, stable ordering, actor matrix, role loss, and an operator
   `/feature roles` correction path are specified.
6. MCP status is Session/capability/group bound. Feature MCP is an unremovable
   core control-plane tool, and transition still calls the F001 API path.
7. The operator's explicit request for one-sentence delivery is recorded as
   run-scoped authorization to commit, push, open a PR, and merge only after a
   green Merge Gate and subject to repository policy. It does not authorize
   force push, policy bypass, deployment, or unrelated external effects.

Detailed state/event tables, invariants, and adversarial cases are in
`orchestration-design.md`.
