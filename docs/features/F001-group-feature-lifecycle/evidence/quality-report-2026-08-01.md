# F001 Quality Report — D14 Refinement

- **Status:** changed scope passed; repository lint baseline remains red
- **Branch:** `codex/group-feature-lifecycle`
- **Base HEAD:** `a019e8b`
- **Scope:** persistent group current Feature, registered D14 dynamic template,
  role-aware Skill recommendation, stage next steps, discovery-visible Skill
  contracts, standalone next-Skill sections, validators, docs, tests, and
  generated API contracts.
- **Independent review:** pending; this is quality evidence, not approval.

## TDD evidence

The focused red run failed for the intended reasons:

- `dynamic.update_workflow_sop` was unknown to prompt governance.
- A later group invocation without explicit `feature_run_id` stored no link.
- All 13 skills lacked the enforced Contract block and catalog next skills.
- All 10 workflow stages lacked `next_step`.

A follow-up red run then rejected the old body-level Contract layout because
the 13 descriptions did not yet expose explicit `Use when:`, `Not for:`, and
`Output:` fields or standalone `## Next step` sections.

After implementation, the focused suite passed all D14, persistence,
role-routing, terminal-clear, discovery-metadata, and next-Skill routing tests.

## Fresh verification

| Check | Result |
|---|---|
| `python -m unittest discover -s tests -v` | 45 passed, 1 environment-gated live GitHub test skipped |
| direct Vitest CLI | 8 files, 19 tests passed |
| direct TypeScript `tsc -b` | passed |
| direct Vite production build | passed; existing bundle-size warning only |
| repository ESLint | baseline failed: 20 errors and 5 warnings in untouched frontend source files |
| official skill `quick_validate.py` | all 13 canonical skills passed |
| `python scripts/check-skills.py` | 13 skills, 10 stages, 16 transitions passed |
| `python scripts/sync-skills.py --check` | 26 Claude/Codex mounts passed |
| `python scripts/check-features.py` | passed |
| `git diff --check` | passed |

## Journey and invariants

1. Creating a FeatureRun makes it the group's current Feature.
2. A later group message without `feature_run_id` inherits and persists the
   FeatureRun link.
3. Every routed Agent receives the registered D14 block using current durable
   stage and role.
4. In review, owner receives `request-review`/`receive-review`; reviewer receives
   only `review-feature`.
5. Completing the FeatureRun clears group current-feature state.
6. GroupInvocation custody remains independent from FeatureRun stage.

## Residual notes

- The existing repository-wide ESLint debt is unchanged and outside this diff.
- The frontend now has generated types for current-feature GET/PUT endpoints;
  a dedicated Feature Dashboard remains outside F001 scope.
