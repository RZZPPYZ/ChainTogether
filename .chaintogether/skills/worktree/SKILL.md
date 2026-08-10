---
name: worktree
description: "Prepare a safe isolated Git worktree for a ChainTogether feature while preserving unrelated user changes and verifying branch identity, repository synchronization, environment bootstrap/reuse, dependency state, and baseline tests. Use when: starting any code, script, API, schema, runtime prompt or template, first-party execution-surface change, new feature, or bug fix. Not for: read-only discussion or research, or documentation-only changes of at most five lines that do not affect code, scripts, APIs, configuration, schemas, prompts, or execution behavior. Output: an isolated worktree with the correct branch, environment configuration, reused or installed dependencies, baseline evidence, and exact commands for running without manual venv activation."
---

# Worktree

1. Inspect `git status`, current branch, worktrees, and the feature plan.
2. Preserve unrelated changes. Never clean, reset, stash, move, or delete them without explicit authority.
3. Create a feature-ID-bearing branch and an isolated worktree outside the repository root.
4. Record the absolute worktree path, branch, base SHA, feature ID, and owner.
5. Configure project-specific ports, databases, credentials, and caches so concurrent agents cannot share mutable runtime state accidentally.
6. Bootstrap dependencies without unnecessary reinstall work:
   - Python: prefer the canonical repository `.venv` when dependency manifests have not changed. Do not require manual activation; run Python commands with the absolute interpreter path, e.g. `<repo-root>/.venv/Scripts/python.exe -m unittest ...` on Windows. Treat the shared `.venv` as read-mostly; only install/update Python packages when dependency files changed or the task explicitly needs new dependencies.
   - Frontend: if a worktree-local `web/node_modules` already exists and package manifests/lockfiles are unchanged, reuse it. If missing, run the documented install once, preferring offline/cache-backed install when appropriate. If package manifests changed, run the documented install and record the change.
   - Never copy broad virtualenvs or dependency directories by hand. Never share mutable runtime state such as databases, dev servers, output dirs, or credential files merely because dependency caches are reused.
7. Record the dependency decision: reused root `.venv`, installed worktree-local frontend deps, updated dependency manifests, or skipped because no executable baseline is needed.
8. Run the smallest trustworthy baseline test/build command before editing, using the recorded interpreter/package-manager commands.

Return a `Worktree Record` with path, branch, base SHA, isolation settings, dependency/bootstrap decision, exact no-activation commands, and baseline result. Stop on dirty-target ambiguity, unsafe paths, or a failing unexplained baseline.

## Next step

Load `$tdd` and implement the first planned AC or reproduced failure in that worktree.
