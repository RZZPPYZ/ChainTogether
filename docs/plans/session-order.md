# Session ordering — drag sessions to reorder the sidebar

## 1. What & why

The sidebar used to follow creation order. Sessions are now manually
reorderable by dragging them up or down inside their group. The order is
persisted per session, so it survives a reload, another browser tab, and a
server restart.

A **group** is one list in the sidebar:

- an agent's top-level sessions (`folder_id = NULL`), or
- the sessions inside one agent-scoped folder (`folder_id = <folder>`).

Reordering never moves a session between groups; it only changes its vertical
position. The folders feature is documented in
[session-folders](session-folders.md).

## 2. Data model

`sessions.sort_order REAL NOT NULL DEFAULT 0` (additive migration).

- **Sort key**: `(sort_order ASC, created_at ASC)`. Existing rows migrate to
  `0`, so their creation order is preserved until the user drags.
- **New sessions**: `MAX(sort_order) + 1` over all rows (archived included), so
  they append to the bottom of their group and can never collide with a
  restored row.
- **Drag**: the endpoint rewrites the listed group to sequential positions
  `0..N-1` in one transaction. Positions are only compared inside a group, so
  different folders may reuse the same numbers.
- **Rewrite of a replaced session**:
  - `/rewind` fork inherits the parent's `sort_order` (it takes the parent's
    slot; the parent is archived).
  - `/archive` successor also inherits the old session's slot.
  - `/fork` full-copy duplicate appends (it is an unrelated new session).
- **Hidden delegation sessions** participate in the same order. The frontend
  reorders the full group (including the ones hidden by the deployment
  toggle), so revealing them later doesn't scramble the list.

## 3. API

`PUT /api/agents/{agent_id}/sessions/order`

```json
{
  "folder_id": null,
  "session_ids": ["session-c", "session-a", "session-b"]
}
```

- `folder_id: null` targets top-level sessions; a folder id targets that
  folder.
- `session_ids` is the complete desired sequence for that group and must
  contain unique, live session ids owned by `agent_id` with the matching
  `folder_id`.
- `204 No Content` on success; `400` for cross-agent, cross-folder, duplicate
  or non-live ids.
- `SessionInfo` exposes `sort_order`; `GET /api/sessions` and
  `GET /api/agents/{agent_id}/sessions` return sessions sorted by it.

## 4. Frontend

- `SessionList` uses Pointer Events (`pointerdown`/`pointermove`/`pointerup`)
  rather than native HTML5 drag, so it also works in environments that disable
  HTML5 drag. A row becomes draggable after a 5 px movement threshold; a plain
  click still selects the session, and the click that follows a drag is
  swallowed.
- Each row shows a grip handle as the drag affordance (the whole row is
  draggable, not just the handle). Dropping in the top half of a row inserts
  before it, the bottom half inserts after it; a thin primary-color line shows
  the target.
- `sortSessionsByOrder` applies the same `(sort_order, created_at)` ordering
  the server uses.
- The reorder is optimistic: the Zustand store is updated first, then
  `PUT /api/agents/{agent_id}/sessions/order` runs. A failed request restores
  the pre-drag array and shows an inline error (usually a stale/not-restarted
  backend), while the reason is also logged to the console.
- Cross-group drops (top level ↔ folder, folder ↔ folder) are ignored; moving
  a session between groups is intentionally not supported because folders own
  their working directory.
- Pointer dragging is desktop-oriented (mouse/pen); touch scrolling is left to
  the browser, and there is no keyboard reordering yet.
