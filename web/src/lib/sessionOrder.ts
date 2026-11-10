import type { SessionInfo } from "../stores/sessionStore";

/** Group-owned sessions are controller implementation details and never
 * appear in an Agent's sidebar lists. */
const GROUP_SESSION_ORIGINS = new Set(["group", "group_member"]);

export type SessionDropPosition = "before" | "after";

/** Sidebar order: the user's manual drag position first, creation time as a
 * stable tie-breaker (legacy rows migrated with sort_order = 0). */
export function sortSessionsByOrder(sessions: SessionInfo[]): SessionInfo[] {
  return [...sessions].sort((a, b) => {
    const aOrder = a.sort_order ?? 0;
    const bOrder = b.sort_order ?? 0;
    if (aOrder !== bOrder) return aOrder - bOrder;
    return (a.created_at ?? "").localeCompare(b.created_at ?? "");
  });
}

/** Pure drag-and-drop move used by the sidebar and its unit tests. Returns
 * null for a no-op or when either id isn't in the list. */
export function reorderSessionIds(
  ids: string[],
  draggedId: string,
  targetId: string,
  position: SessionDropPosition,
): string[] | null {
  if (draggedId === targetId) return null;
  if (!ids.includes(draggedId) || !ids.includes(targetId)) return null;
  const next = ids.filter((id) => id !== draggedId);
  let index = next.indexOf(targetId);
  if (index < 0) return null;
  if (position === "after") index += 1;
  next.splice(index, 0, draggedId);
  return next;
}

export function getAgentSidebarSessions(
  sessions: SessionInfo[],
  agentId: string,
  // null = only top-level sessions (not inside a folder); a folder id =
  // only that folder's sessions. Group-owned sessions are always excluded.
  folderId: string | null = null,
): SessionInfo[] {
  return sortSessionsByOrder(
    sessions.filter(
      (session) =>
        session.agent_id === agentId &&
        !GROUP_SESSION_ORIGINS.has(session.origin) &&
        (folderId === null
          ? !session.folder_id
          : session.folder_id === folderId),
    ),
  );
}
