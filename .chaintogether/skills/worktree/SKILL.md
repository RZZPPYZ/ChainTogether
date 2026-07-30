---
name: worktree
description: Prepare a safe isolated Git worktree for a ChainTogether feature, preserving unrelated user changes and verifying branch identity, repository synchronization, environment isolation, and baseline tests. Use immediately before implementation or takeover work; do not use for read-only analysis or tiny documentation-only changes.
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
