---
name: worktree
description: "Prepare a safe isolated Git worktree for a ChainTogether feature while preserving unrelated user changes and verifying branch identity, repository synchronization, environment isolation, and baseline tests. Use when: starting any code, script, API, schema, runtime prompt or template, first-party execution-surface change, new feature, or bug fix. Not for: read-only discussion or research, or documentation-only changes of at most five lines that do not affect code, scripts, APIs, configuration, schemas, prompts, or execution behavior. Output: an isolated worktree with the correct branch, environment configuration, dependency state, and baseline evidence."
---

# Worktree

1. Inspect `git status`, current branch, worktrees, and the feature plan.
2. Preserve unrelated changes. Never clean, reset, stash, move, or delete them without explicit authority.
3. Create a feature-ID-bearing branch and an isolated worktree outside the repository root.
4. Record the absolute worktree path, branch, base SHA, feature ID, and owner.
5. Configure project-specific ports, databases, credentials, and caches so concurrent agents cannot share mutable runtime state accidentally.
6. Install dependencies using the repository's documented command.
7. Run the smallest trustworthy baseline test/build command before editing.

Return a `Worktree Record` with path, branch, base SHA, isolation settings, and baseline result. Stop on dirty-target ambiguity, unsafe paths, or a failing unexplained baseline.

## Next step

Load `$tdd` and implement the first planned AC or reproduced failure in that worktree.
