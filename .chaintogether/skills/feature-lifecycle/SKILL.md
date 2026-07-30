---
name: feature-lifecycle
description: Route an existing feature through ChainTogether's durable lifecycle by inspecting its canonical feature document, workflow stage, blockers, roles, and evidence. Use when a group asks what happens next for a feature, resumes feature work, reports a gate result, or needs lifecycle status; do not use to implement code or perform the stage work itself.
---

# Feature Lifecycle

Treat the Feature Doc and FeatureRun as durable truth. Treat chat as evidence, not state.

## Route the feature

1. Locate the canonical `docs/features/Fxxx-*/feature.md`.
2. Read `stage`, `state`, assigned roles, open value questions, and artifact references.
3. Read `.chaintogether/workflows/feature-lifecycle.yaml`.
4. Stop if the document is missing, contradictory, blocked without a resolution, or references another group/feature.
5. Select the skill registered for the current stage. Do not perform that skill's work inside this router.
6. Build a self-contained work packet containing:
   - feature ID and stage
   - assigned role and expected actor
   - objective and fixed decisions
   - canonical artifact paths
   - open questions and blockers
   - expected output and next gate
7. Route only to an agent permitted by the workflow role constraints.

Value questions require the operator. Reversible technical questions may be decided by the responsible agent and recorded.

## Return

Return a `Lifecycle Routing` block with `feature`, `stage`, `state`, `skill`, `actor`, `inputs`, `blockers`, and `next_gate`. Never claim a transition occurred until the control plane records it.
