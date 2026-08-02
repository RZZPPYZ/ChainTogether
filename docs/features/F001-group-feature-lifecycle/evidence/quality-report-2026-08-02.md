# F001 Quality Report — Merge Candidate

- **Status:** pass; repository ESLint baseline remains red outside this diff
- **Date:** 2026-08-02
- **Branch:** `codex/group-feature-lifecycle`
- **Base:** `13253f3`
- **Scope:** durable FeatureRun lifecycle, group-current Feature persistence,
  per-turn D14 workflow injection, role-aware Skill routing, lifecycle Skill
  contracts, validators, document-sync recovery, session-bound transitions,
  revision provenance, documentation, tests, and generated API contracts.
- **Independent review:** `89b070f` received `request_changes`; the corrected
  exact HEAD requires re-review by the same reviewer. This report permits
  `request-review` only.

## Acceptance evidence

| Acceptance area | Evidence |
|---|---|
| Feature dossier and validator | `scripts/check-features.py`; lifecycle asset tests |
| Canonical Skill registry and provider mounts | `scripts/check-skills.py`; `scripts/sync-skills.py --check` |
| FeatureRun persistence, CAS, outbox recovery, and hard gates | `tests/test_feature_workflow.py` |
| Group-current Feature inheritance and D14 | `tests/test_feature_workflow.py`; `tests/test_prompt_governance.py` |
| Role-aware Review and Vision routing | workflow validator and Feature workflow tests |
| Generated frontend API contract | TypeScript build and Vite production build |

## Fresh verification

| Command | Result |
|---|---|
| `.venv\\Scripts\\python.exe -m compileall -q server tests` | passed |
| `.venv\\Scripts\\python.exe -m unittest discover -s tests -v` | 50 passed; 1 environment-gated live GitHub smoke skipped |
| `.venv\\Scripts\\python.exe scripts\\check-skills.py` | 13 Skills, 10 stages, 16 transitions passed |
| `.venv\\Scripts\\python.exe scripts\\sync-skills.py --check` | 26 provider mounts passed |
| `.venv\\Scripts\\python.exe scripts\\check-features.py` | 1 Feature passed |
| `npm test -- --run` | 8 files, 19 tests passed |
| `npm run typecheck` | passed |
| `npm run build` | passed; existing chunk-size warning only |
| `npm run lint` | unchanged baseline: 20 errors, 5 warnings in pre-existing frontend files |

## Journey and invariant checks

1. Creating a FeatureRun activates it for the group.
2. Later group messages inherit the persisted current Feature without requiring
   the client to resend `feature_run_id`.
3. Every routed group Agent turn reloads durable state and receives registered
   D14 stage, role, Skill, gate, canonical-doc, and next-step context.
4. Owner, Reviewer, and Vision Guardian assignments must be distinct.
5. Competing transitions are compare-and-swap linearized; exactly one writer
   may advance an observed FeatureRun revision.
6. An accepted mutation atomically persists the run, event, and document
   outbox item; failed filesystem delivery is recoverable without replay.
7. The public transition route derives actor identity from the bound group
   session. Review and Vision transitions additionally require existing
   evidence, the exact Git revision, and structured independent-role provenance.
8. Reaching `done` clears the group's current Feature.

## Residual risk disposition

- Repository-wide ESLint debt predates F001 and occurs in files outside this
  diff. F001 adds only a generated frontend API contract, which passes the
  TypeScript and production-build checks.
- The Feature Dashboard and autonomous lifecycle orchestration are explicitly
  outside F001 and will be addressed by a subsequent Feature.
