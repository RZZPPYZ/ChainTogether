import {
  useEffect,
  useRef,
  useState,
  type PointerEvent as ReactPointerEvent,
} from "react";
import {
  IconCheck,
  IconCopy,
  IconEye,
  IconEyeOff,
  IconFolder,
  IconGripVertical,
  IconSubtask,
  IconX,
} from "@tabler/icons-react";
import {
  getAgentSidebarSessions,
  reorderSessionIds,
  sortSessionsByOrder,
  type SessionDropPosition,
} from "../lib/sessionOrder";
import { useSessionStore, type SessionInfo } from "../stores/sessionStore";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

const API_URL = window.location.origin;

/** The session list for a single agent — rendered nested under its agent row
 * in AgentList (sessions belong to an agent). No "Sessions" header; the
 * new-session "+" lives on the agent row and drives `formOpen`.
 *
 * With `folderId`, the list is the contents of that agent-scoped folder:
 * the working directory comes from the folder, so the create form omits the
 * path input and the server inherits the folder's path. */
export function SessionList({
  agentId,
  folderId = null,
  folderWorkingDir = null,
  formOpen,
  onCloseForm,
}: {
  agentId: string;
  folderId?: string | null;
  folderWorkingDir?: string | null;
  formOpen: boolean;
  onCloseForm: () => void;
}) {
  const [newName, setNewName] = useState("");
  const [workingDir, setWorkingDir] = useState("");
  const [credentialId, setCredentialId] = useState<string>("");
  const [backend, setBackend] = useState<string>("claude-code");
  const [copiedId, setCopiedId] = useState<string | null>(null);
  // Drag-and-drop reorder state. `draggingId` dims the source row;
  // `dropTarget` renders the insertion line on the hovered row.
  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [dropTarget, setDropTarget] = useState<{
    id: string;
    position: SessionDropPosition;
  } | null>(null);
  const [reorderError, setReorderError] = useState<string | null>(null);
  // Pointer-event drag (works even where native HTML5 drag is unavailable).
  // The candidate is armed on pointerdown and only becomes a real drag after
  // a small movement threshold, so a plain click still selects the session.
  const listRef = useRef<HTMLDivElement>(null);
  const dragCandidateRef = useRef<{
    sessionId: string;
    startX: number;
    startY: number;
    active: boolean;
  } | null>(null);
  const dragCleanupRef = useRef<(() => void) | null>(null);
  const suppressClickRef = useRef(false);
  const reorderErrorTimerRef = useRef<number | null>(null);

  useEffect(
    () => () => {
      dragCleanupRef.current?.();
      if (reorderErrorTimerRef.current !== null) {
        window.clearTimeout(reorderErrorTimerRef.current);
      }
    },
    [],
  );

  const token = useSessionStore((s) => s.token);
  const sessions = useSessionStore((s) => s.sessions);
  const setSessions = useSessionStore((s) => s.setSessions);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const setActiveSessionId = useSessionStore((s) => s.setActiveSessionId);
  const setActiveGroupId = useSessionStore((s) => s.setActiveGroupId);
  const setActiveAgentId = useSessionStore((s) => s.setActiveAgentId);
  const setMessages = useSessionStore((s) => s.setMessages);
  const setPendingQueue = useSessionStore((s) => s.setPendingQueue);
  const setPendingQuestions = useSessionStore((s) => s.setPendingQuestions);
  const credentials = useSessionStore((s) => s.credentials);
  const availableBackends = useSessionStore((s) => s.availableBackends);
  const agents = useSessionStore((s) => s.agents);
  // Credentials shown in the create form are scoped to the selected backend.
  const backendCreds = credentials.filter((c) => c.backend === backend);
  const codexAvailable = availableBackends.includes("codex");
  // New sessions inherit the agent's default harness; the form still lets you
  // override per session.
  const agentBackend =
    agents.find((a) => a.id === agentId)?.backend ?? "claude-code";

  // Seed the form's backend (and clear any stale credential pick) from the
  // agent each time the create form opens.
  useEffect(() => {
    if (formOpen) {
      setBackend(agentBackend);
      setCredentialId("");
    }
  }, [formOpen, agentBackend]);

  const showDelegations = useSessionStore((s) => s.showDelegations);
  const setShowDelegations = useSessionStore((s) => s.setShowDelegations);

  // Group backing/member sessions are controller-owned implementation details.
  // They remain in the store for group history and resume, but only GroupChat
  // exposes them; an Agent's sidebar lists user-facing sessions exclusively.
  // Archived sessions live in the account-menu manage page, not here.
  // Delegation sessions (origin === "delegation") are hidden by default
  // to keep the sidebar clean under heavy fan-out — the user can flip
  // the global showDelegations toggle to see them. The hidden-count
  // pill at the bottom of this list surfaces what's been filtered.
  // (agent-collaboration.md §6)
  const allAgentSessions = getAgentSidebarSessions(
    sessions,
    agentId,
    folderId,
  );
  const hiddenDelegationCount = showDelegations
    ? 0
    : allAgentSessions.filter((s) => s.origin === "delegation").length;
  const agentSessions = showDelegations
    ? allAgentSessions
    : allAgentSessions.filter((s) => s.origin !== "delegation");

  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };

  const createSession = async () => {
    const name = newName.trim() || "New Session";
    try {
      const res = await fetch(`${API_URL}/api/agents/${agentId}/sessions`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          name,
          // Inside a folder the server inherits the folder's working
          // directory; the form deliberately doesn't collect one.
          working_dir: folderId ? null : workingDir.trim() || null,
          folder_id: folderId,
          credential_id: credentialId || null,
          backend,
        }),
      });
      if (res.ok) {
        const session: SessionInfo = await res.json();
        setSessions([...sessions, session]);
        setActiveGroupId(null);
        setActiveAgentId(agentId);
        setActiveSessionId(session.id);
        setNewName("");
        setWorkingDir("");
        setCredentialId("");
        setBackend("claude-code");
        onCloseForm();
      }
    } catch {
      // ignore
    }
  };

  const deleteSession = async (id: string) => {
    try {
      await fetch(`${API_URL}/api/sessions/${id}`, {
        method: "DELETE",
        headers,
      });
      setSessions(sessions.filter((s) => s.id !== id));
      if (activeSessionId === id) {
        setActiveSessionId(null);
      }
    } catch {
      // ignore
    }
  };

  const selectSession = async (id: string) => {
    setActiveGroupId(null);
    setActiveAgentId(agentId);
    setActiveSessionId(id);
    try {
      const [detailRes, bgRes] = await Promise.all([
        fetch(`${API_URL}/api/sessions/${id}`, { headers }),
        fetch(`${API_URL}/api/sessions/${id}/bg-tasks`, { headers }),
      ]);
      if (detailRes.ok) {
        const data = await detailRes.json();
        setMessages(id, data.messages || []);
        setPendingQueue(id, data.pending_queue || []);
        setPendingQuestions(id, data.pending_questions || []);
        if (typeof data.next_message_seq === "number") {
          useSessionStore
            .getState()
            .setLastAppliedSeq(id, data.next_message_seq - 1);
        }
      }
      if (bgRes.ok) {
        useSessionStore.getState().setBgTasks(id, await bgRes.json());
      }
    } catch {
      // ignore
    }
  };

  const reorderSessions = async (
    draggedId: string,
    targetId: string,
    position: SessionDropPosition,
  ) => {
    // Order the FULL group (hidden delegation sessions included) so their
    // relative positions stay stable when the user later reveals them.
    const groupIds = sortSessionsByOrder(allAgentSessions).map((s) => s.id);
    const nextIds = reorderSessionIds(groupIds, draggedId, targetId, position);
    if (!nextIds) return;

    const orderById = new Map(nextIds.map((id, index) => [id, index] as const));
    const previous = sessions;
    setSessions(
      sessions.map((session) =>
        orderById.has(session.id)
          ? { ...session, sort_order: orderById.get(session.id)! }
          : session,
      ),
    );
    try {
      const res = await fetch(
        `${API_URL}/api/agents/${agentId}/sessions/order`,
        {
          method: "PUT",
          headers,
          body: JSON.stringify({
            folder_id: folderId,
            session_ids: nextIds,
          }),
        },
      );
      if (!res.ok) throw new Error(`reorder failed: ${res.status}`);
      if (reorderErrorTimerRef.current !== null) {
        window.clearTimeout(reorderErrorTimerRef.current);
        reorderErrorTimerRef.current = null;
      }
      setReorderError(null);
    } catch (error) {
      // Optimistic update failed — restore the pre-drag order and tell the
      // user instead of silently snapping back.
      console.warn("[session-order] save failed", error);
      setSessions(previous);
      setReorderError("Couldn't save the new order. Please retry.");
      if (reorderErrorTimerRef.current !== null) {
        window.clearTimeout(reorderErrorTimerRef.current);
      }
      reorderErrorTimerRef.current = window.setTimeout(
        () => setReorderError(null),
        4000,
      );
    }
  };

  // Hit-test a pointer position against this list's rows. Using
  // elementFromPoint keeps the target accurate even when the pointer moves
  // faster than React can re-render.
  const dropTargetAt = (x: number, y: number) => {
    const row = document
      .elementFromPoint(x, y)
      ?.closest<HTMLElement>("[data-session-id]");
    if (!row || !listRef.current?.contains(row)) return null;
    const sessionId = row.dataset.sessionId;
    if (!sessionId) return null;
    const rect = row.getBoundingClientRect();
    const position: SessionDropPosition =
      y < rect.top + rect.height / 2 ? "before" : "after";
    return { sessionId, position };
  };

  const handleRowPointerDown = (
    e: ReactPointerEvent<HTMLDivElement>,
    s: SessionInfo,
  ) => {
    if (e.button !== 0) return;
    const target = e.target as HTMLElement;
    // Action buttons inside the row keep their normal click behavior.
    if (target.closest("button, a, input, select, textarea")) return;
    // A new press supersedes any stale listener set.
    dragCleanupRef.current?.();

    const candidate = {
      sessionId: s.id,
      startX: e.clientX,
      startY: e.clientY,
      active: false,
    };
    dragCandidateRef.current = candidate;

    const onMove = (event: PointerEvent) => {
      const current = dragCandidateRef.current;
      if (!current) return;
      if (!current.active) {
        // A tiny move is still a click; only start a drag past the threshold.
        if (
          Math.hypot(
            event.clientX - current.startX,
            event.clientY - current.startY,
          ) < 5
        ) {
          return;
        }
        current.active = true;
        setDraggingId(current.sessionId);
        document.body.style.userSelect = "none";
        document.body.style.cursor = "grabbing";
      }
      if (event.cancelable) event.preventDefault();
      const hit = dropTargetAt(event.clientX, event.clientY);
      if (!hit || hit.sessionId === current.sessionId) {
        setDropTarget(null);
        return;
      }
      setDropTarget((prev) =>
        prev && prev.id === hit.sessionId && prev.position === hit.position
          ? prev
          : { id: hit.sessionId, position: hit.position },
      );
    };

    const finish = (commit: boolean, event: PointerEvent) => {
      const current = dragCandidateRef.current;
      dragCleanupRef.current?.();
      dragCleanupRef.current = null;
      dragCandidateRef.current = null;
      setDraggingId(null);
      setDropTarget(null);
      if (!current || !current.active || !commit) return;
      // pointerup is followed by click; swallow it so a drag doesn't also
      // open the session.
      suppressClickRef.current = true;
      window.setTimeout(() => {
        suppressClickRef.current = false;
      }, 0);
      const hit = dropTargetAt(event.clientX, event.clientY);
      if (!hit || hit.sessionId === current.sessionId) return;
      void reorderSessions(current.sessionId, hit.sessionId, hit.position);
    };

    const onUp = (event: PointerEvent) => finish(true, event);
    const onCancel = (event: PointerEvent) => finish(false, event);
    const cleanup = () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
      window.removeEventListener("pointercancel", onCancel);
      document.body.style.userSelect = "";
      document.body.style.cursor = "";
    };
    dragCleanupRef.current = cleanup;
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    window.addEventListener("pointercancel", onCancel);
  };

  // Every session is a flat, EQUAL row in the sidebar — no parent/child
  // nesting, no fork chrome. A /fork duplicate or /rewind branch is just
  // another session; its lineage lives in the chat-header fork banner, not as
  // sidebar hierarchy (user preference: sidebar sessions never look nested).
  const renderSessionRow = (s: SessionInfo) => {
    const dropPosition =
      dropTarget?.id === s.id ? dropTarget.position : null;
    return (
      <div key={s.id} className="fork-node relative">
        {dropPosition && (
          <div
            className={`session-drop-indicator pointer-events-none absolute left-0 right-0 z-10 h-0.5 rounded-full bg-primary ${
              dropPosition === "before" ? "top-0" : "bottom-0"
            }`}
            aria-hidden="true"
          />
        )}
        <div
          className={`session-item group flex items-center gap-2 rounded-lg px-2 py-1.5 cursor-pointer select-none transition-colors ${
            s.id === activeSessionId
              ? "active bg-[hsl(var(--gray-200))] text-foreground"
              : "text-sidebar-foreground hover:bg-sidebar-accent"
          } ${draggingId === s.id ? "opacity-50" : ""}`}
          data-session-id={s.id}
          onPointerDown={(e) => handleRowPointerDown(e, s)}
          onClick={() => {
            if (suppressClickRef.current) return;
            void selectSession(s.id);
          }}
        >
          <span
            className="session-drag-handle inline-flex shrink-0 items-center text-sidebar-foreground/25 group-hover:text-sidebar-foreground/60"
            title="Drag to reorder"
            aria-hidden="true"
          >
            <IconGripVertical size={13} />
          </span>
          <span
            className={`status-dot status-${s.status} inline-block size-2 rounded-full shrink-0 ${
              s.status === "running"
                ? "bg-primary animate-pulse"
                : s.status === "waiting_approval"
                ? "bg-yellow-500"
                : "bg-muted-foreground/40"
            }`}
          />
          <span
            className={`session-name truncate text-sm flex-1 ${
              s.id === activeSessionId ? "font-medium" : ""
            }`}
          >
            {s.name}
          </span>
          {s.origin === "delegation" && (
            <span
              className="delegation-marker inline-flex items-center text-muted-foreground/80"
              title="Delegation session"
              aria-label="Delegation session"
            >
              <IconSubtask size={12} />
            </span>
          )}
          <div className="session-item-actions flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
            <button
              className="btn-copy-id inline-flex h-6 w-6 items-center justify-center rounded-md text-sidebar-foreground/60 hover:bg-card hover:text-sidebar-foreground"
              onClick={(e) => {
                e.stopPropagation();
                navigator.clipboard.writeText(s.id);
                setCopiedId(s.id);
                setTimeout(() => setCopiedId(null), 1500);
              }}
              title="Copy session ID"
            >
              {copiedId === s.id ? <IconCheck size={14} /> : <IconCopy size={14} />}
            </button>
            <button
              className="btn-delete inline-flex h-6 w-6 items-center justify-center rounded-md text-sidebar-foreground/60 hover:bg-destructive/10 hover:text-destructive"
              onClick={(e) => {
                e.stopPropagation();
                deleteSession(s.id);
              }}
              title="Delete session"
            >
              <IconX size={14} />
            </button>
          </div>
        </div>
      </div>
    );
  };

  const renderForkForest = (list: SessionInfo[]) => (
    <>{list.map(renderSessionRow)}</>
  );

  return (
    <div
      ref={listRef}
      className="session-list session-list-nested ml-3 mt-0.5 mb-1 pl-2 border-l border-sidebar-border/40"
    >
      <div className="session-list-items flex flex-col gap-0">
        {agentSessions.length === 0 && !formOpen && (
          <div className="text-[11px] italic text-sidebar-foreground/40 px-2 py-1">
            No sessions yet.
          </div>
        )}
        {hiddenDelegationCount > 0 && !formOpen && (
          <button
            type="button"
            className="delegation-toggle group flex items-center gap-1.5 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground rounded transition-colors"
            onClick={() => setShowDelegations(true)}
            title="Show delegation sessions"
          >
            <IconEye size={11} />
            <span>
              +{hiddenDelegationCount} delegation
              {hiddenDelegationCount === 1 ? "" : "s"} hidden
            </span>
          </button>
        )}
        {showDelegations &&
          allAgentSessions.some((s) => s.origin === "delegation") &&
          !formOpen && (
            <button
              type="button"
              className="delegation-toggle flex items-center gap-1.5 px-2 py-1 text-[11px] text-muted-foreground hover:text-foreground rounded transition-colors"
              onClick={() => setShowDelegations(false)}
              title="Hide delegation sessions"
            >
              <IconEyeOff size={11} />
              <span>Hide delegations</span>
            </button>
          )}
        {renderForkForest(agentSessions)}
        {reorderError && (
          <div
            className="px-2 py-1 text-[11px] leading-snug text-destructive"
            role="status"
          >
            {reorderError}
          </div>
        )}
      </div>

      {formOpen && (
        <div className="session-create mt-2 rounded-lg border-[0.7px] border-border bg-card p-3 space-y-2">
          <Input
            type="text"
            className="h-9 text-sm"
            value={newName}
            onChange={(e) => setNewName(e.target.value)}
            placeholder="Session name"
            autoFocus
          />
          {folderId ? (
            <div
              className="session-folder-path flex items-center gap-1.5 rounded-md bg-sidebar-accent/60 px-2 py-1.5 text-[11px] text-muted-foreground"
              title={folderWorkingDir ?? "Folder working directory"}
            >
              <IconFolder size={12} className="shrink-0" />
              <span className="truncate">
                {folderWorkingDir ?? "Folder working directory"}
              </span>
            </div>
          ) : (
            <Input
              type="text"
              className="h-9 text-sm"
              value={workingDir}
              onChange={(e) => setWorkingDir(e.target.value)}
              placeholder="Working directory (optional)"
            />
          )}
          {codexAvailable && (
            <div
              className="session-backend-select flex gap-2"
              role="radiogroup"
              aria-label="Backend"
            >
              {[
                { id: "claude-code", label: "Claude" },
                { id: "codex", label: "Codex" },
              ].map((b) => (
                <button
                  key={b.id}
                  type="button"
                  role="radio"
                  aria-checked={backend === b.id}
                  className={`btn-backend btn-backend-${b.id} flex-1 h-8 rounded-md border text-xs transition-colors ${
                    backend === b.id
                      ? "border-primary bg-primary/10 text-foreground font-medium"
                      : "border-border text-muted-foreground hover:bg-sidebar-accent"
                  }`}
                  onClick={() => {
                    setBackend(b.id);
                    setCredentialId("");
                  }}
                >
                  {b.label}
                </button>
              ))}
            </div>
          )}
          {backendCreds.length > 0 && (
            <select
              className="session-credential-select flex h-9 w-full rounded-md border border-border bg-input px-3 py-1 text-sm text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
              value={credentialId}
              onChange={(e) => setCredentialId(e.target.value)}
            >
              <option value="">Default auth (CLI login)</option>
              {backendCreds.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          )}
          <div className="flex justify-end gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setNewName("");
                setWorkingDir("");
                onCloseForm();
              }}
            >
              Cancel
            </Button>
            <Button className="btn btn-create" size="sm" onClick={createSession}>
              Create
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
