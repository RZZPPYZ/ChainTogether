# F001 independent Vision Gate packet

- Feature: F001 Group Feature Lifecycle
- Merged revision: `0c5482d95fc56ec6ab3b63382134c3e55d370905`
- Approved implementation HEAD: `2982c8fdd64ea36ac5ff89c6fb93b339bb59d803`
- Guardian requirement: independent from author `codex` and reviewer
  `f001_reviewer`
- Requested verdict: `accepted`, `changes_required`, or `blocked`, bound to the
  merged revision

## Original intent

Give a group—not a single delegating Agent—a durable Feature journey from
signal through discovery, design, implementation, quality, independent review,
merge, independent vision acceptance, and closure. Every Agent turn must know
the current FeatureRun, stage, assigned role, suggested Skill, next step, gate,
and canonical Feature Doc. Role separation and evidence must prevent an author
from self-approving Review or Vision.

## Journeys to validate

1. Create or activate a FeatureRun for a group; send a later group message
   without resupplying the feature ID and confirm the persisted current Feature
   is inherited.
2. Render turns for owner, reviewer, and vision guardian; confirm D14 changes
   role-aware Skill guidance while retaining feature, stage, next step, gate,
   and canonical document.
3. Attempt role collisions and unauthorized protected transitions; confirm
   fail-closed behavior with no state advance.
4. Confirm the canonical Feature Doc, FeatureRun/event state, provider Skills,
   and generated contract form one coherent operator-visible lifecycle.
5. Judge whether this satisfies the operator's group-first intent, while
   recognizing that `/feature` one-sentence autonomous orchestration is the
   explicitly separate next Feature, not hidden unfinished F001 scope.

Do not edit the merged tree. Report concrete journey evidence, deviations,
residual risks, and an exact merged-revision-bound verdict.
