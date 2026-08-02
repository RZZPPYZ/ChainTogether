# F001 Independent Review Packet

- **Feature:** F001 — Group Feature Lifecycle
- **Branch:** `codex/group-feature-lifecycle`
- **Base SHA:** `13253f3`
- **Head SHA:** `89b070fe5b3dcc587fd62d1a16949034d8f658f2`
- **Author:** root Codex agent
- **Reviewer requirement:** independent; do not edit the reviewed branch
- **Requested verdict:** `approved`, `request_changes`, or `blocked`, bound to
  the exact Head SHA above

## Operator intent

Provide a durable group-first Feature lifecycle from discovery through delivery,
with canonical Feature Docs and Skills shared by Claude Code and Codex. Every
routed Agent turn must receive current Feature, stage, role, suggested Skill,
gate, canonical document, and concrete next step through the registered D14
`update-workflow-sop` template. Skill discovery metadata must expose `Use when`,
`Not for`, and `Output`; each Skill body must name its next Skill.

## Canonical artifacts

- `docs/features/F001-group-feature-lifecycle/feature.md`
- `docs/features/F001-group-feature-lifecycle/plan.md`
- `docs/features/F001-group-feature-lifecycle/evidence/quality-report-2026-08-02.md`
- `docs/features/F001-group-feature-lifecycle/evidence/d14-skill-contract-audit.md`
- `.chaintogether/workflows/feature-lifecycle.yaml`
- `.chaintogether/skills.yaml`
- `docs/feature-lifecycle.md`

## Review scope

Review the complete diff `13253f3..89b070f`, including:

1. FeatureRun persistence, stage transitions, distinct roles, evidence and
   Feature Doc gates.
2. One current FeatureRun per group and inheritance across later invocations.
3. Per-Agent, per-turn D14 rendering with role-aware Skill selection.
4. Canonical Skill registry, provider synchronization, discovery-visible Skill
   metadata, next-Skill routing, and validators.
5. API models/routes and generated frontend contract.
6. Tests, error paths, migration compatibility, and documentation truth.

## Acceptance and quality evidence

All F001 ACs are checked in the Feature Doc. Fresh 2026-08-02 verification:

- Python: 45 passed; 1 environment-gated live GitHub smoke skipped.
- Frontend Vitest: 8 files, 19 tests passed.
- TypeScript: passed.
- Vite production build: passed; existing chunk warning only.
- Skill validation: 13 Skills, 10 stages, 16 transitions passed.
- Provider sync: 26 mounts passed.
- Feature validation: passed.
- ESLint: unchanged repository baseline of 20 errors / 5 warnings in existing
  frontend files outside this diff.

## Known risks and questions

- YAML workflow/catalog assets intentionally use a constrained JSON-compatible
  subset to avoid a new runtime dependency.
- A dedicated Feature Dashboard and autonomous `/feature` orchestration are
  explicitly outside F001 and planned as a subsequent Feature.
- Confirm that actor-role enforcement, group ownership checks, terminal clearing,
  and database migration behavior cannot be bypassed or desynchronized.

## Reviewer output contract

1. List findings first as P1/P2/P3 with evidence and tight file/line locations.
2. Distinguish code defects from specification or design gaps.
3. Record commands run and residual risks.
4. End with exact reviewed Head SHA and one verdict:
   `approved`, `request_changes`, or `blocked`.
