# F001 Merge Evidence Manifest

- Merge authorization: operator explicitly requested direct merge to `main`
- Source branch: `codex/group-feature-lifecycle`
- Base branch: `main`
- Approved source HEAD: `2982c8fdd64ea36ac5ff89c6fb93b339bb59d803`
- Independent reviewer verdict: `approved`
- Merge commit: `0c5482d95fc56ec6ab3b63382134c3e55d370905`
- Merge mode: `--no-ff`
- Remote result: `origin/main` equals local `main`
- Tree continuity: merge tree `ec682d2c` equals approved source tree
  `ec682d2c`

## Post-merge checks

- Python: 59 passed, 1 environment-gated live GitHub smoke skipped.
- Skill validation: 13 Skills, 10 stages, 16 transitions passed.
- Feature validation: passed.
- Provider mounts were regenerated after branch switch; 26 mounts passed.
- `git diff --check`: passed.
- Frontend evidence from the exact approved tree remains applicable: 19 tests,
  typecheck, and production build passed; repository lint baseline remains the
  pre-existing 20 errors and 5 warnings outside the F001 diff.
