# F003 Design Gate Verdict

- Verdict: `approved`
- Feature Doc revision: `23710147e14a095c26b012708b3febe6952e20c4`
- Reviewer role: design-gate review performed separately from implementation
  activity; no implementation code existed at the reviewed revision.
- Evidence: `feature.md`, `evidence/discovery.md`,
  `evidence/orchestration-design.md`, Cat Cafe Lesson 08 and the inspected
  clowder-ai session-continuity implementation.

## Evaluation

1. Every AC traces to the operator's sealed-handoff, fresh-summary or MCP
   recall need and names a testable verification surface.
2. The scope unit, entry, warning/action paths, degraded summarizer path,
   restart recovery, successor bootstrap and terminal state are explicit.
3. Architecture ownership separates durable DB truth, transition policy,
   harness invocation, D-layer rendering, REST/MCP authorization and frontend
   visibility. The existing A2A parent-chain module is deliberately excluded.
4. Eight lifecycle-bearing objects are censused. The state-event table,
   twelve invariants and fifteen adversarial cases cover concurrency, crash,
   restore, privacy bypass and migration.
5. Security is fail-closed at both Session capability and exact chain
   membership. Transcript and generated summary are untrusted data, bounded
   before injection. MCP remains read-only.
6. Migration is additive and lazy; disabling or rolling back preserves the
   existing active pointer. Summary failure cannot block session rebirth.
7. The user-visible direction is already operator-approved. Thresholds and
   reserve are reversible configuration, not unresolved value decisions.

## Deliberate deviations from the reference

- ChainTogether keeps exact provider-neutral transcript rows in SQLite, so it
  does not duplicate them into clowder-ai's filesystem JSONL layout.
- Phase 1 implements only `handoff`; it does not claim `hybrid` without a
  reliable compaction signal.
- The summarizer uses ChainTogether's existing tool-free one-shot harness and
  deterministic fallback rather than a provider-specific direct HTTP model.

## Named gaps

No Design Gate blocker remains. A rich transcript browser and provider-native
compression-count strategies are explicitly separate future features.

## Next gate

Load `$writing-plans` and produce an AC-complete implementation plan with exact
files, state invariants, red-green steps and verification commands.
