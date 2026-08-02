# F001 D14 and Skill Contract Audit

## Finding

The first F001 implementation injected FeatureRun context on every Agent turn
inside one linked `GroupInvocation`, but it did not implement the full D14
pattern:

- Feature context was assembled as an ad hoc string, not a registered dynamic
  prompt asset.
- A new group message lost context unless the client repeated `feature_run_id`.
- Review-stage Agents saw all review skills regardless of owner/reviewer role.
- Workflow stages did not supply a concrete `next_step`.
- Skill descriptions generally contained trigger and exclusion language, while
  outputs and follow-on routing were only implicit prose. Discovery metadata
  was incomplete, and next-Skill routing had no dedicated section.

## D14 resolution

- `group_active_features` persists one current FeatureRun per group.
- Feature creation activates it; an explicit linked send switches it; later
  sends inherit it; terminal `done` clears it.
- Every routed Agent turn reloads durable FeatureRun/workflow state and renders
  `dynamic.update_workflow_sop` from the prompt manifest.
- D14 includes FeatureRun/Feature, stage/state, receiving role, canonical doc,
  gate, role-aware suggested skills, and a stage-specific next step.
- D14 is advisory. Agents return evidence; the control plane owns transitions.

## Skill discovery and routing contracts

Every Skill now exposes `Use when:`, `Not for:`, and `Output:` directly in its
frontmatter `description`, because that is the metadata visible before an Agent
decides whether to load the Skill body. The body contains a separate
`## Next step` section naming the next Skill for every relevant verdict or
outcome.

| Skill | Output | Next step |
|---|---|---|
| `feature-lifecycle` | Lifecycle routing packet | Load the D14-suggested stage skill |
| `feature-discovery` | Feature Doc + discovery evidence | `design-gate` |
| `design-gate` | Revision-bound design verdict | `writing-plans` or `feature-discovery` |
| `writing-plans` | AC-complete implementation plan | `worktree` |
| `worktree` | Isolated worktree + environment/baseline record | `tdd` |
| `tdd` | Red-green-refactor implementation evidence | `quality-gate` |
| `quality-gate` | Quality Report and verdict | `request-review` or `tdd` |
| `request-review` | SHA-bound review packet | Independent `review-feature` |
| `review-feature` | Findings + reviewed-HEAD verdict | `merge-gate` or `receive-review` |
| `receive-review` | Finding dispositions + new HEAD | `request-review` |
| `merge-gate` | Merge Evidence Manifest | `vision-gate` |
| `vision-gate` | Merged-revision vision verdict | `close-feature`, `feature-discovery`, or `worktree`/`tdd` |
| `close-feature` | Synchronized done Feature Doc | `feature-lifecycle` terminal check or new `feature-discovery` |

`check-skills.py` rejects a description missing any discovery field, the obsolete
body-level `## Contract`, a missing or empty `## Next step`, an unknown catalog
`next_skill`, a stage without `next_step`, or an unknown role-aware workflow
Skill.
