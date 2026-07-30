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
