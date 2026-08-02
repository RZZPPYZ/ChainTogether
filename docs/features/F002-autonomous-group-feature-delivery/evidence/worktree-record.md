# F002 Worktree Record

- Path: `F:\RZP_program\my_project\ChainTogether\.worktrees\F002-autonomous-group-feature`
- Branch: `codex/f002-autonomous-group-feature`
- Base: `0b2f4de0c85c284cbf214e8535557170637ca596`
- Preparation commit: `3fa7798b4c9e2a8298766e5a5eb69e4b19aaa11a`
- Owner: `codex`
- Isolation: separate Git worktree under the writable repository boundary;
  `.worktrees/` is ignored. Python uses the repository virtual environment;
  frontend dependencies and npm cache are worktree-local. Runtime tests use
  temporary databases. A manual app launch, if required, must use a non-default
  database and port.

## Baseline

- Python: `59 passed`, `1 skipped` (environment-gated).
- Frontend: `8` files and `19` tests passed.
- TypeScript: `npm run typecheck` passed.
- Production bundle: `npm run build` passed; only the pre-existing Vite chunk
  size warning was reported.

The worktree lives inside the repository solely because the active filesystem
sandbox cannot write to an external sibling directory. It remains a true,
separate Git worktree and the primary checkout is not used for implementation.
