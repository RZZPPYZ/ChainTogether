---
name: feature-lifecycle
description: "Route an existing feature through ChainTogether's durable lifecycle by inspecting its canonical Feature Doc, stage, blockers, roles, and evidence. Use when: a FeatureRun needs status, routing, resumption, or a decision about which stage Skill should act next. Not for: performing discovery, implementation, review, merge, or acceptance work inside the router. Output: a lifecycle-routing packet naming feature, stage, role, inputs, blockers, D14-suggested Skill, expected output, and next gate."
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

## Next step

Load the Skill named in D14's `Suggested skill(s)` field for the current stage and role. Return that Skill's evidence to the control plane before requesting a transition.
