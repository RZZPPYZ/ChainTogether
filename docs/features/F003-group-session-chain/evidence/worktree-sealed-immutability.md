# Worktree Record — sealed predecessor immutability correction

- Feature: `F003-group-session-chain`
- Trigger: Vision Gate `changes_required` on merged revision `e3d05178d768e01728e98bc6b9aa4c713bc7afb7`
- Worktree: `F:/RZP_program/my_project/ChainTogether/.worktrees/F003-sealed-immutability`
- Branch: `codex/F003-sealed-immutability`
- Base: `7ba664890cad0d922bb1c34ce0668d9a43f77629`
- Python environment: reused `F:/RZP_program/my_project/ChainTogether/.venv`; commands use its absolute interpreter path, so manual activation is unnecessary.
- Frontend environment: worktree-local `web/node_modules`, installed from the existing lockfile with `bun install --frozen-lockfile --offline`.

## Baseline

- `F:/RZP_program/my_project/ChainTogether/.venv/Scripts/python.exe -m unittest tests.test_group_session_chain -q`
  - PASS — 17 tests.
- `bunx vitest run`
  - PASS — 10 files, 32 tests.

## Correction scope

The sealed predecessor must remain immutable after rotation: ordinary archive management must not revive it, and the message execution path must reject a sealed generation even if a stale/corrupt live object is reintroduced. The Session Chain read APIs remain the supported access path for prior evidence.

## Next Step

Load `$tdd`; add failing database/runtime/UI tests before implementing the atomic unarchive guard, turn-time sealed guard, and read-only archive presentation.
