# F001 Quality Report — Merge Candidate

- **Status:** pass; repository ESLint baseline remains red outside this diff
- **Date:** 2026-08-02
- **Branch:** `codex/group-feature-lifecycle`
- **Base:** `13253f3`
- **Scope:** durable FeatureRun lifecycle, group-current Feature persistence,
  per-turn D14 workflow injection, role-aware Skill routing, lifecycle Skill
  contracts, validators, documentation, tests, and generated API contracts.
- **Independent review:** pending; this report permits `request-review` only.

## Acceptance evidence

| Acceptance area | Evidence |
|---|---|
| Feature dossier and validator | `scripts/check-features.py`; lifecycle asset tests |
| Canonical Skill registry and provider mounts | `scripts/check-skills.py`; `scripts/sync-skills.py --check` |
| FeatureRun persistence and hard gates | `tests/test_feature_workflow.py` |
| Group-current Feature inheritance and D14 | `tests/test_feature_workflow.py`; `tests/test_prompt_governance.py` |
| Role-aware Review and Vision routing | workflow validator and Feature workflow tests |
| Generated frontend API contract | TypeScript build and Vite production build |

## Fresh verification

| Command | Result |
|---|---|
| `.venv\\Scripts\\python.exe -m compileall -q server scripts tests` | passed |
| `.venv\\Scripts\\python.exe -m unittest discover -s tests -v` | 45 passed; 1 environment-gated live GitHub smoke skipped |
| `.venv\\Scripts\\python.exe scripts\\check-skills.py` | 13 Skills, 10 stages, 16 transitions passed |
| `.venv\\Scripts\\python.exe scripts\\sync-skills.py --check` | 26 provider mounts passed |
| `.venv\\Scripts\\python.exe scripts\\check-features.py` | 1 Feature passed |
| `node node_modules\\vitest\\vitest.mjs run` | 8 files, 19 tests passed |
| `node node_modules\\typescript\\bin\\tsc -b` | passed |
| `node node_modules\\vite\\bin\\vite.js build` | passed; existing chunk-size warning only |
| `node node_modules\\eslint\\bin\\eslint.js .` | unchanged baseline: 20 errors, 5 warnings in pre-existing frontend files |

## Journey and invariant checks

1. Creating a FeatureRun activates it for the group.
2. Later group messages inherit the persisted current Feature without requiring
   the client to resend `feature_run_id`.
3. Every routed group Agent turn reloads durable state and receives registered
   D14 stage, role, Skill, gate, canonical-doc, and next-step context.
4. Owner, Reviewer, and Vision Guardian assignments must be distinct.
5. Review and Vision verdict transitions are limited to their assigned roles
   and require evidence plus canonical Feature Doc verdicts.
6. Reaching `done` clears the group's current Feature.

## Residual risk disposition

- Repository-wide ESLint debt predates F001 and occurs in files outside this
  diff. F001 adds only a generated frontend API contract, which passes the
  TypeScript and production-build checks.
- The Feature Dashboard and autonomous lifecycle orchestration are explicitly
  outside F001 and will be addressed by a subsequent Feature.
