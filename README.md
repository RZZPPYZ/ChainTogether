# ChainTogether

ChainTogether is a personal project that started as a copy/extraction from
Octopus. The first goal is to keep the useful local agent runtime intact while
making it easier to explore richer multi-agent interaction patterns on top of
it.

The long-term vision is a lightweight workspace where multiple local agents can
work together in the same group context: mentioning each other, handing off
work, resuming their own private context, following shared rules, and giving the
user one place to coordinate the whole conversation.

This project is intentionally experimental and personal. It keeps several
Octopus-compatible names and environment variables for now so the copied
runtime stays stable while the multi-agent layer evolves.

## Project Direction

Current focus areas:

- Group chat routing with explicit `@AgentName` handoffs.
- Default responder selection when the user sends a group message without an
  `@mention`.
- Per-agent resumed sessions, so agents can keep their own private working
  context instead of repeatedly receiving the full group transcript.
- Two-layer group prompt governance: a versioned L0 system contract for
  identity/routing, plus a D-layer turn envelope containing only new group
  messages and the current trigger.
- Optional project-specific prompt additions loaded from
  `.chaintogether/agents.toml`; core routing rules live in packaged assets and
  are not duplicated in project files.
- A shared persona library imported from complete GitHub skill repositories,
  with several personas assignable to an agent and at most one active at once.
- Live group execution blocks showing agent phase, elapsed time, tool calls,
  bounded inputs/results, and streamed response text while a turn is running.
- Better guardrails around agent-to-agent routing, completion tokens, holds,
  and noisy model output.

## Personas

Open **Settings > Personas** to install a persona from an HTTPS GitHub
repository. ChainTogether pins the repository to its current commit, keeps the
complete package under `OCTOPUS_PERSONAS_DIR`, and uses its `SKILL.md` as the
persona's core prompt. Text references and examples remain available to the
agent through a read-only persona MCP server when needed.

When GitHub API access is unavailable or rate-limited, the same screen accepts
a locally downloaded ZIP package. Both import paths use the same archive safety
limits, package layout normalization, and `SKILL.md` validation.

In **Agent Settings**, assign any number of installed personas to an agent and
choose zero or one as active. The active persona is loaded fresh on every turn,
so switching it affects existing sessions without changing the selected Claude
Code or Codex backend.

## Octopus Roots

The initial codebase was copied from Octopus and trimmed toward the backend
runtime for multi-agent work:

- Agent CLI backend detection and spawning through `server/harness/` for Claude Code and Codex CLI.
- Agent definitions, per-agent memory roots, credentials, and backend selection.
- Group chat/session routing through `server/group_manager.py`,
  `server/prompt_governance.py`, packaged `server/assets/` policy/templates,
  and `server/routers/groups.py`.
- Built-in MCP servers for background tasks, user questions, agent-to-agent delegation, connectors, and research under `server/mcp_servers/`.
- Agent delegation lifecycle through `server/delegations.py` and `server/routers/delegations.py`.
- Slash-command workflows implemented in the session/group/bridge paths, including `/schedule`, `/research`, `/archive`, `/rewind`, bridge commands, and related frontend command menu source.
- Scheduled tasks via `server/scheduler.py`, `server/schedule_ai.py`, and `server/routers/schedules.py`.

The frontend source is included so the extracted runtime can still serve and
evolve a UI. Dependency folders, local databases, virtual environments, and
build artifacts should remain untracked.

## Group Prompt Governance

Group turns use two deliberately separate prompt layers:

- **L0** is a packaged, versioned system-prompt template. On every member turn
  ChainTogether renders the agent's canonical identity, current group roster,
  and the shared `@`/handoff/HOLD contract, then appends it last in the system
  prompt so it takes precedence over persona and project additions.
- **D** is a user-message envelope. It contains controller directives, only
  the group messages newer than that member's persistent cursor, and the
  current triggering message in its own JSON block. The agent's resumed CLI
  session remains responsible for its private earlier context.

Static templates and machine-readable thresholds live under
`server/assets/`. Derived roster snapshots are regenerated from the database
at startup and whenever group membership changes; by default they are written
to `~/.chaintogether/groups/<group-id>/group-members.json`. The snapshot is
diagnostic runtime state, not a second source of truth, and intentionally omits
user-only aliases.

## Backend Start

```powershell
cd F:\RZP_program\my_project\ChainTogether
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
python -m pip install -e .
Copy-Item .env.example .env
python -m server.main
```

Backend health check: `http://127.0.0.1:8000/health`. The default API token is `changeme` unless you edit `OCTOPUS_AUTH_TOKEN` in `.env`.

## Frontend

For live UI development:

```powershell
cd F:\RZP_program\my_project\ChainTogether\web
bun install
bun dev
```

Open `http://127.0.0.1:5173` for Vite HMR.

To let the backend serve the SPA at `http://127.0.0.1:8000`, build the frontend first:

```powershell
cd F:\RZP_program\my_project\ChainTogether\web
bun install
bun run build
cd ..
.\.venv\Scripts\Activate.ps1
python -m server.main
```

## CLI Backends

Put the desired agent CLIs on `PATH` before starting the server:

- `claude` for Claude Code style sessions.
- `codex` for Codex sessions.

On Windows, install the standalone Codex CLI (for example with
`npm install --global @openai/codex`). The executable bundled inside the
Microsoft Store Codex desktop app is under a protected `WindowsApps` package:
PowerShell can broker-launch it, but a Python service cannot start it with
`CreateProcess`. ChainTogether automatically prefers the native executable
inside the official npm package and ignores the inaccessible desktop binary.

On the original machine, the JS toolchain and `codex` may live under `~/.nvm/versions/node/*/bin`; prepend that directory to `PATH` when needed.

## Notes

The code intentionally keeps the Python package name `server` and the environment prefix `OCTOPUS_`. That makes this extraction low-risk and keeps the copied harness, MCP, group, schedule, and delegation paths internally consistent. Rename those later only as a deliberate refactor.
