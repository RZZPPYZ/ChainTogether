# Session folders — group an agent's sessions under a shared working directory

## 1. What & why

A session is created under an agent and previously always asked for a working
directory. Session folders pull that path out into a reusable, agent-scoped
container:

- An agent can contain **top-level sessions** (created exactly as before) and
  **folders**.
- A folder owns one working directory and many sessions.
- A session created inside a folder does **not** ask for a path — it inherits
  the folder's directory from the server.

Folders are organizational only. They are not a second kind of conversation:
each session still has its own transcript, backend, credential and status.

## 2. Data model

`session_folders`

| column        | notes                                              |
|---------------|----------------------------------------------------|
| `id`          | 12-char hex, same scheme as sessions                |
| `agent_id`    | FK → `agents(id)` ON DELETE CASCADE                |
| `name`        | unique per agent, case-insensitive                 |
| `working_dir` | normalized absolute path (expand `~`, resolve cwd) |
| `created_at`  | ISO-8601 UTC                                       |
| `updated_at`  | ISO-8601 UTC                                       |

`sessions.folder_id` — nullable FK → `session_folders(id)` ON DELETE SET NULL.
`NULL` means a top-level session. The column is added by an additive migration,
so existing databases upgrade on boot without rebuilding the table.

### Frozen working directory

The folder's path is copied onto the session at creation time. Editing a
folder's path affects **future** sessions only; existing sessions keep the path
they started with. Rewriting a live session's cwd would invalidate its backend
resume state and any shell/MCP subprocesses already anchored to the old path.

### Delete semantics

Deleting a folder never deletes conversations. The FK sets `folder_id = NULL`
for its sessions (archived rows included), so they reappear at the agent's top
level with the working directory they inherited. Live `Session` objects are
detached in `SessionManager.delete_session_folder` too, otherwise a stale
`folder_id` would break fork/archive paths until the next restart.

### Fork / archive behavior

- **Rewind fork** (`/rewind`): inherits the parent's `folder_id`; its working
  dir is the parent's exact path.
- **Full-copy duplicate** (`/fork`): `folder_id = NULL` — it lives on an
  independent copied directory, not in the folder that points at the original.
- **Archive successor** (`/archive`): stays in the same folder and follows the
  folder's current path (folders own the directory for new sessions).
- **Schedules / bridges / delegations / groups**: unchanged, `folder_id = NULL`.

## 3. API

| method | path                              | purpose                          |
|--------|-----------------------------------|----------------------------------|
| GET    | `/api/agents/{agent_id}/folders`  | list an agent's folders          |
| POST   | `/api/agents/{agent_id}/folders`  | create `{name, working_dir}`     |
| PATCH  | `/api/folders/{folder_id}`        | rename and/or change path        |
| DELETE | `/api/folders/{folder_id}`        | delete; sessions are detached    |

`POST /api/agents/{agent_id}/sessions` (and `POST /api/sessions`) accept an
optional `folder_id`. When present the server validates that the folder belongs
to the same agent and uses the folder's working directory; a body `working_dir`
is ignored. Errors (unknown folder, cross-agent folder, duplicate folder name,
empty name/path) return `400`.

`SessionInfo`/`SessionDetail` expose `folder_id`; `SessionFolderInfo` exposes
`id, agent_id, name, working_dir, session_count, created_at, updated_at`
(`session_count` counts live, non-archived sessions).

## 4. Frontend

- Agent row: **New session** (`+`) and **New folder** (folder-plus).
- `SessionFolderList` renders folder rows under the agent when expanded:
  expand/collapse, live session count, new-session-in-folder, inline edit and
  delete (with confirmation).
- `SessionList` takes `folderId`; inside a folder it hides the working-dir
  input and shows the folder path instead, and `POST`s `folder_id`.
- `getAgentSidebarSessions` splits by folder: top-level lists filter
  `!folder_id`, folder lists filter by the folder id. Group-owned sessions stay
  hidden from both.
- Folder create/delete/edit update the Zustand store directly; deleting a folder
  also nulls `folder_id` on the store's sessions so they immediately move to
  the top level.
