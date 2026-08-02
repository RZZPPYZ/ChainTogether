# F001 Group Feature Lifecycle — Implementation Plan

**Feature:** F001 — `docs/features/F001-group-feature-lifecycle/feature.md`
**Goal:** Give group agents one durable, validated path from feature signal to accepted delivery.
**Acceptance Criteria:** AC-1 through AC-8 in the Feature Doc.
**Architecture:** Keep FeatureRun separate from GroupInvocation and inject only the active feature context into group turns.

## Task 1: Durable artifacts

- Add the Feature Doc template and F001 dossier.
- Add workflow and skill catalogs.
- Add feature and skill validators.

## Task 2: Unified skills

- Create concise lifecycle skills with generated Codex metadata.
- Add cross-platform provider sync with provenance checking.

## Task 3: FeatureRun control plane

- Add FeatureRun, event, and invocation-link tables.
- Add manager, API models, and routes.
- Enforce transitions and role separation.

## Task 4: Group integration

- Accept an optional `feature_run_id` on group messages.
- Persist the relation and inject a stage/role/skill directive into every routed Agent turn.

## Task 5: Verification

- Add validator tests, FeatureManager tests, and group context tests.
- Run Python tests, skill validation, feature validation, and frontend checks affected by regenerated API contracts.

## Task 6: D14 workflow SOP refinement

- Register a first-class D14 `update-workflow-sop` dynamic prompt asset.
- Persist one active FeatureRun per group so later messages inherit it without
  resending `feature_run_id`; explicit linkage switches the active feature.
- Add stage-level `next_step` and role-aware skill recommendations.
- Standardize all lifecycle skills with `Use when`, `Not for`, `Output`, and
  `Next step` contracts and enforce them in validation.
- Add red/green regression tests, refresh evidence, and return F001 to Quality.

## Task 7: Independent-review hardening

- Linearize competing role and stage writes with compare-and-swap semantics.
- Commit the FeatureRun update, immutable event, and Feature Doc outbox item in
  one transaction; atomically deliver and reconcile pending document updates.
- Bind public transitions to the caller's group-agent session instead of a
  caller-supplied actor ID, and require an unlisted live-session capability in
  addition to the shared application bearer.
- Require real repository evidence, exact Git revisions, and structured
  Reviewer or Guardian provenance at protected gates.
- Chain later document mutations from the pending outbox image, retain a disk
  baseline hash, and fail closed on conflicting operator edits or unverifiable
  Git repositories.
- Reproduce every review finding with a failing test, rerun the full Quality
  Gate, and return the new exact HEAD to the same independent reviewer.
