# F003 Worktree Record

- Worktree: `F:\RZP_program\my_project\ChainTogether\.worktrees\F003-group-session-chain`
- Branch: `codex/F003-group-session-chain`
- Base: `1fb75b26370a2301c94f409d1d817c587d172cb3`
- Feature: `F003`
- Owner: `codex`
- Isolation: separate Git worktree; existing main-worktree untracked
  `reference/reference_a2a.md` was not touched.
- Python dependencies: reused read-mostly root environment; no manifest change.
- Python command without activation:
  `F:\RZP_program\my_project\ChainTogether\.venv\Scripts\python.exe -m unittest discover -s tests -q`
- Frontend dependencies: not installed during discovery; if frontend changes
  require them, install/reuse a worktree-local `web/node_modules` from Bun cache.
- Baseline: the backend regression suite started from the exact base and ran
  through the established mocked-failure paths without an early collection or
  import failure. A concise exit-code baseline is rerun before implementation.
